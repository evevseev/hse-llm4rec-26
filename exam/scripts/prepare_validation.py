"""Create temporal interaction counts without using test-period behaviour.

Run: .venv/bin/python scripts/prepare_validation.py
Only Python's standard library is required. All timestamps use Europe/Kyiv.
"""
import bisect
import csv
import hashlib
import json
import platform
import resource
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from itertools import groupby
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
PROCESSED = DATA / 'processed'
REPORTS = ROOT / 'reports'
ZONE = ZoneInfo('Europe/Kyiv')
FEATURE_FIELDS = ['tv_show_category', 'tv_show_genre_1', 'tv_show_genre_2',
                  'tv_show_genre_3', 'year_of_production', 'director', 'actors']


def timestamp(value, schedule=False):
    if schedule:
        value = f'{value[6:10]}-{value[3:5]}-{value[:2]} {value[11:]}'
    return int(datetime.fromisoformat(value).replace(tzinfo=ZONE).timestamp())


BEGIN = timestamp('2020-03-09 00:00:00')
CUTOFF = timestamp('2020-05-18 00:00:00')
END = timestamp('2020-07-27 00:00:00')


def covered_seconds(intervals):
    """Length of an interval union; never double-count duplicated viewing logs."""
    total = 0
    left = right = None
    for start, end in intervals:
        if left is None:
            left, right = start, end
        elif start <= right:
            right = max(right, end)
        else:
            total += right-left
            left, right = start, end
    return total + (right-left if left is not None else 0)


def write_counts(path, counts):
    with path.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'tv_show_id', 'qualified_airings'])
        for (user, item), count in sorted(counts.items(), key=lambda x: (int(x[0][0]), x[0][1])):
            writer.writerow([user, item, count])


def prepare_fold(output_dir=PROCESSED, report_path=REPORTS / 'validation_preparation.json',
                 begin=BEGIN, cutoff=CUTOFF, finish=END,
                 sources=('export_arh_11-20-final.csv', 'export_arh_21-30-final.csv'), quiet=False,
                 export_channel_details=False):
    began = time.perf_counter()
    output_dir.mkdir(exist_ok=True, parents=True)
    stats = Counter()
    airings = []
    airing_channels = []
    index = defaultdict(list)
    metadata = defaultdict(lambda: defaultdict(set))
    display_metadata = {}
    candidates = set()
    sources = list(sources)
    seen = set()
    for filename in sources:
        with (DATA / filename).open(newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                stats['schedule_rows'] += 1
                item = int(row['tv_show_id'])
                if not item:
                    stats['zero_id_schedule_rows_excluded'] += 1
                    continue
                start = timestamp(row['start_time'], True)
                duration = int(row['duration'])
                end = start + duration  # duration is elapsed seconds, not wall-clock arithmetic.
                if duration <= 0:
                    stats['nonpositive_labelled_airings_excluded'] += 1
                    continue
                channel = int(row['channel_id'])
                display_metadata.setdefault(str(item), {
                    'title': row['tv_show_title'], 'category': row['tv_show_category']})
                # No validation-period descriptions enter the training feature catalogue.
                if begin <= start < cutoff:
                    for field in FEATURE_FIELDS:
                        value = row[field].strip()
                        if value:
                            metadata[item][field].add(value)
                if cutoff < finish and start < finish and end > cutoff:
                    candidates.add(item)
                # Exclude entire boundary-crossing airings instead of changing their denominator.
                if begin <= start and end <= cutoff:
                    period = 'train'
                elif cutoff <= start and end <= finish:
                    period = 'validation'
                else:
                    stats['boundary_crossing_labelled_airings_excluded'] += 1
                    continue
                key = (channel, start, end, item)
                if key in seen:
                    stats['duplicate_labelled_airings_excluded'] += 1
                    continue
                seen.add(key)
                aid = len(airings)
                airings.append((item, duration, period, start, end))
                if export_channel_details:
                    airing_channels.append(channel)
                index[channel].append((start, end, aid))
                stats[f'{period}_eligible_airings'] += 1
    starts, prefix_ends = {}, {}
    for channel, rows in index.items():
        rows.sort()
        starts[channel] = [r[0] for r in rows]
        maximum = 0
        prefix_ends[channel] = []
        for start, end, _ in rows:
            maximum = max(maximum, end)
            prefix_ends[channel].append(maximum)
    stats['schedule_preparation_seconds'] = round(time.perf_counter()-began, 3)
    db_path = output_dir / 'overlap_work.sqlite'
    conn = sqlite3.connect(db_path)
    conn.execute('DROP TABLE IF EXISTS overlaps')
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA temp_store=FILE')
    conn.execute('CREATE TABLE overlaps (user_idx INTEGER, airing INTEGER, start INTEGER, end INTEGER)')
    users = []
    user_index = {}
    buffer = []
    log_began = time.perf_counter()
    with (DATA / 'dataset11-30.csv').open(newline='') as f:
        for row in csv.DictReader(f):
            stats['log_rows'] += 1
            start, end = timestamp(row['start_time']), timestamp(row['stop_time'])
            if start >= finish or end <= begin:
                stats['log_rows_outside_fold_excluded'] += 1
                continue
            user = row['user_id']
            if user not in user_index:
                user_index[user] = len(users)
                users.append(user)
            channel = int(row['vsetv_id'])
            if end <= start:
                stats['nonpositive_view_intervals_excluded'] += 1
                continue
            stats['reported_duration_mismatches_after_timezone'] += int(row['duraton']) != end-start
            if channel not in index:
                continue
            j = bisect.bisect_left(starts[channel], end)-1
            while j >= 0 and prefix_ends[channel][j] > start:
                a, b, aid = index[channel][j]
                if b > start:
                    left, right = max(start, a), min(end, b)
                    assert left < right
                    buffer.append((user_index[user], aid, left, right))
                    stats['overlap_pairs'] += 1
                j -= 1
            if len(buffer) >= 50000:
                conn.executemany('INSERT INTO overlaps VALUES (?,?,?,?)', buffer)
                buffer.clear()
    conn.executemany('INSERT INTO overlaps VALUES (?,?,?,?)', buffer)
    conn.commit()
    stats['log_join_seconds'] = round(time.perf_counter()-log_began, 3)
    if not quiet:
        print(f"Joined {stats['log_rows']:,} logs into {stats['overlap_pairs']:,} overlap fragments.", flush=True)
    merge_began = time.perf_counter()
    counts = {'train': Counter(), 'validation': Counter()}
    fragment_examples = []
    training_events_file = (output_dir / 'training_airings.csv').open('w', newline='')
    training_events_writer = csv.writer(training_events_file)
    training_events_writer.writerow(['user_id', 'tv_show_id', 'airing_start_epoch', 'airing_end_epoch'])
    detail_file = (output_dir / 'training_airing_details.csv').open('w', newline='') if export_channel_details else None
    detail_writer = csv.writer(detail_file) if detail_file else None
    if detail_writer:
        detail_writer.writerow(['user_id', 'tv_show_id', 'channel_id', 'airing_start_epoch',
                                'airing_end_epoch', 'overlap_seconds', 'airing_duration_seconds'])
    query = conn.execute('SELECT user_idx, airing, start, end FROM overlaps ORDER BY user_idx, airing, start, end')
    for (uid, aid), group in groupby(query, key=lambda r: r[:2]):
        intervals = [(r[2], r[3]) for r in group]
        item, duration, period, a, b = airings[aid]
        overlap = covered_seconds(intervals)
        assert 0 < overlap <= duration
        stats[f'{period}_user_airings_with_overlap'] += 1
        if overlap * 5 >= duration * 4:
            counts[period][users[uid], item] += 1
            if period == 'train':
                training_events_writer.writerow([users[uid], item, a, b])
                if detail_writer:
                    detail_writer.writerow([users[uid], item, airing_channels[aid], a, b, overlap, duration])
            stats[f'{period}_qualified_user_airings'] += 1
            if max(right-left for left, right in intervals) * 5 < duration * 4:
                stats[f'{period}_qualified_only_after_fragment_merging'] += 1
                if len(fragment_examples) < 5:
                    fragment_examples.append({'user_id': users[uid], 'tv_show_id': item,
                        'period': period, 'airing_start_epoch': a, 'airing_end_epoch': b,
                        'duration_seconds': duration, 'union_seconds': overlap,
                        'fragments_epoch': intervals})
    training_events_file.close()
    if detail_file:
        detail_file.close()
    conn.close()
    # This is disposable intermediate state created by this script only.
    db_path.unlink()
    for period in counts:
        write_counts(output_dir / f'{period}_interactions.csv', counts[period])
        stats[f'{period}_user_item_pairs'] = len(counts[period])
        stats[f'{period}_users_with_history'] = len({u for u, _ in counts[period]})
    stats['fragment_merge_seconds'] = round(time.perf_counter()-merge_began, 3)
    metadata_out = {str(item): {field: sorted(values) for field, values in fields.items()}
                    for item, fields in sorted(metadata.items())}
    (output_dir / 'training_metadata.json').write_text(json.dumps(metadata_out, ensure_ascii=False, indent=2)+'\n')
    (output_dir / 'display_metadata.json').write_text(json.dumps(display_metadata, ensure_ascii=False, indent=2)+'\n')
    (output_dir / 'validation_candidates.json').write_text(json.dumps(sorted(candidates))+'\n')
    (output_dir / 'all_users.json').write_text(json.dumps(sorted(users, key=int))+'\n')
    hashes = {}
    for filename in sources + ['dataset11-30.csv', 'submission.csv']:
        digest = hashlib.sha256()
        with (DATA / filename).open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                digest.update(block)
        hashes[filename] = digest.hexdigest()
    manifest = {'timezone': str(ZONE), 'begin': datetime.fromtimestamp(begin, ZONE).strftime('%Y-%m-%d %H:%M:%S'),
        'cutoff': datetime.fromtimestamp(cutoff, ZONE).strftime('%Y-%m-%d %H:%M:%S'),
        'end': datetime.fromtimestamp(finish, ZONE).strftime('%Y-%m-%d %H:%M:%S'),
        'watch_fraction_threshold': 0.8, 'boundary_rule': 'Exclude airings not fully contained in one window.',
        'aggregation': 'Union viewing fragments per user and airing, then count qualified airings per user-item.',
        'candidate_rule': 'Nonzero IDs with a positive-duration airing overlapping the validation window.',
        'training_metadata_rule': 'Only airings starting before the cutoff; no validation metadata used for features.',
        'source_sha256': hashes, 'statistics': dict(stats),
        'fragment_merge_examples': fragment_examples, 'validation_candidates': len(candidates),
        'python': sys.version, 'platform': platform.platform(),
        'runtime_seconds': round(time.perf_counter()-began, 3),
        'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux'}
    report_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    if not quiet:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest


def main():
    prepare_fold()


if __name__ == '__main__':
    main()
