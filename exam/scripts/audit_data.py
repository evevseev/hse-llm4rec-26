# Generated with an AI assistant
"""Data audit only: no recommender fitting or Kaggle submissions.

Run from repository root: python3 scripts/audit_data.py
Uses the standard library. Intervals are half-open; timestamps remain timezone-naive.
"""
import bisect
import csv
import hashlib
import json
import platform
import resource
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / 'data', ROOT / 'reports'
EPOCH = datetime(2020, 1, 1)


def stamp(value, schedule=False):
    if schedule:
        value = f'{value[6:10]}-{value[3:5]}-{value[:2]} {value[11:]}'
    return int((datetime.fromisoformat(value) - EPOCH).total_seconds())


def text(seconds):
    return (EPOCH + timedelta(seconds=seconds)).isoformat(sep=' ')


def run():
    began = time.perf_counter()
    result = {'environment': {'python': sys.version, 'platform': platform.platform()},
              'scope': 'Full-file audit; join statistics are per log-row/airing pair, not aggregated user-airing labels.',
              'files': {}, 'schedule': {}}
    index = defaultdict(list)
    zero_examples = {}
    train_ids, future_ids = set(), set()
    for path in sorted(DATA.glob('*.csv')):
        digest = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                digest.update(block)
        result['files'][path.name] = {'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    for path in sorted(DATA.glob('export*.csv')):
        future = '31-42' in path.name
        counts = Counter()
        channels, ids, categories = set(), set(), set()
        missing = Counter()
        lo, hi = float('inf'), 0
        duplicates = 0
        invalid_examples = []
        seen = set()
        with path.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames
            for line, row in enumerate(reader, 2):
                start = stamp(row['start_time'], True)
                duration = int(row['duration'])
                end = start + duration
                channel, item = int(row['channel_id']), int(row['tv_show_id'])
                counts['rows'] += 1
                counts['labelled_rows' if item else 'zero_rows'] += 1
                counts['nonpositive_duration'] += duration <= 0
                if duration <= 0 and len(invalid_examples) < 3:
                    invalid_examples.append(dict(line=line, **row))
                channels.add(channel)
                ids.add(item)
                categories.add(row['tv_show_category'])
                lo, hi = min(lo, start), max(hi, end)
                if item:
                    for field in columns[6:]:
                        missing[field] += not row[field].strip()
                    key = (channel, start, end, item)
                    duplicates += key in seen
                    seen.add(key)
                    (future_ids if future else train_ids).add(item)
                # Keep only labelled training airings in the interval index.
                airing = (start, end, item, path.name, line, row['tv_show_title'],
                          row['tv_show_category'], row['channel_title'])
                if not future and item:
                    index[channel].append(airing)
                elif not future and channel not in zero_examples:
                    zero_examples[channel] = airing
        result['schedule'][path.name] = dict(counts, columns=columns, channels=len(channels),
            distinct_nonzero_ids=len(ids - {0}), categories=sorted(categories),
            min_start=text(lo), max_end=text(hi), duplicate_labelled_airing_keys=duplicates,
            missing_fields_labelled=dict(missing), nonpositive_duration_examples=invalid_examples)
    starts, prefix_ends = {}, {}
    for channel, rows in index.items():
        rows.sort()
        starts[channel] = [a[0] for a in rows]
        maximum = 0
        prefix_ends[channel] = []
        for a in rows:
            maximum = max(maximum, a[1])
            prefix_ends[channel].append(maximum)
    result['training_schedule_index'] = {
        'labelled_airings': sum(map(len, index.values())),
        'airings_starting_before_prior_airings_end': sum(
            a[0] < prefix_ends[c][i-1]
            for c, rows in index.items() for i, a in enumerate(rows) if i > 0)}
    result['candidate_coverage'] = {'training_ids': len(train_ids), 'future_ids': len(future_ids),
        'future_ids_absent_from_training_schedule': len(future_ids - train_ids)}
    with (DATA / 'submission.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        template_columns = reader.fieldnames
        template = list(reader)
    test_users = {r['user_id'] for r in template}
    result['template'] = {'columns': template_columns, 'rows': len(template),
        'unique_users': len(test_users), 'all_five_zeros': all(r['tv_show_id'].split() == ['0'] * 5 for r in template)}
    counts, durations, weeks = Counter(), Counter(), Counter()
    users, channels, labelled_users, qualified_users = set(), set(), set(), set()
    examples = {}
    mismatches = []
    mismatch_deltas = Counter()
    kyiv = ZoneInfo('Europe/Kyiv')
    timezone_checks = Counter()
    lo, hi = float('inf'), 0

    def example(user, line, channel, start, end, airing):
        a, b, item, filename, schedule_line, title, category, channel_title = airing
        overlap = max(0, min(end, b) - max(start, a))
        return dict(user_id=user, log_file='dataset11-30.csv', log_line=line,
                    channel_id=channel, channel_title=channel_title,
                    view_start=text(start), view_end=text(end), view_seconds=end-start,
                    schedule_file=filename, schedule_line=schedule_line, tv_show_id=item,
                    title=title, category=category, airing_start=text(a), airing_end=text(b),
                    airing_seconds=b-a, overlap_seconds=overlap,
                    fraction=overlap/(b-a), qualifies_80_percent=overlap * 5 >= (b-a) * 4)

    with (DATA / 'dataset11-30.csv').open(newline='') as f:
        reader = csv.DictReader(f)
        result['log_columns'] = reader.fieldnames
        for line, row in enumerate(reader, 2):
            user, channel = row['user_id'], int(row['vsetv_id'])
            start, end = stamp(row['start_time']), stamp(row['stop_time'])
            duration = int(row['duraton'])
            counts['rows'] += 1
            counts['duration_mismatch'] += duration != end-start
            if duration != end-start:
                mismatch_deltas[str(duration-(end-start))] += 1
                utc_elapsed = int(datetime.fromisoformat(row['stop_time']).replace(tzinfo=kyiv).timestamp()
                                  - datetime.fromisoformat(row['start_time']).replace(tzinfo=kyiv).timestamp())
                timezone_checks['mismatches_explained_by_Europe_Kyiv_DST'] += utc_elapsed == duration
                if len(mismatches) < 5:
                    mismatches.append(dict(line=line, computed_seconds=end-start, **row))
            counts['nonpositive_interval'] += end <= start
            durations[duration] += 1
            weeks[str((EPOCH + timedelta(seconds=start)).isocalendar().week)] += 1
            users.add(user)
            channels.add(channel)
            lo, hi = min(lo, start), max(hi, end)
            matches = []
            if channel in index and end > start:
                rows = index[channel]
                j = bisect.bisect_left(starts[channel], end) - 1
                while j >= 0 and prefix_ends[channel][j] > start:
                    airing = rows[j]
                    if airing[1] > start and airing[1] > airing[0]:
                        overlap = min(end, airing[1]) - max(start, airing[0])
                        qualifies = overlap * 5 >= (airing[1]-airing[0]) * 4
                        counts['labelled_overlap_pairs'] += 1
                        counts['qualified_pairs_80_percent'] += qualifies
                        matches.append((airing, qualifies))
                    j -= 1
            if matches:
                counts['log_rows_touching_labelled_airing'] += 1
                labelled_users.add(user)
                if any(q for _, q in matches):
                    qualified_users.add(user)
                    counts['log_rows_with_qualified_pair'] += 1
                for airing, qualifies in matches:
                    tag = 'qualified' if qualifies else 'below_threshold'
                    if tag not in examples:
                        examples[tag] = [example(user, line, channel, start, end, airing)]
                if len(matches) > 1 and len({q for _, q in matches}) > 1 and 'multiple_airings' not in examples:
                    examples['multiple_airings'] = [example(user, line, channel, start, end, a)
                                                   for a, _ in sorted(matches)]
            if 'unlabelled_airtime' not in examples and channel in zero_examples:
                a = zero_examples[channel]
                if min(end, a[1]) > max(start, a[0]) and a[1] > a[0]:
                    examples['unlabelled_airtime'] = [example(user, line, channel, start, end, a)]
    def quantile(p):
        target = (counts['rows']-1)*p
        total = 0
        for value, n in sorted(durations.items()):
            total += n
            if total > target:
                return value
    result['log'] = dict(counts, users=len(users), channels=len(channels),
        min_start=text(lo), max_end=text(hi), rows_by_iso_week=dict(weeks),
        duration_seconds={str(p): quantile(p) for p in [0, .25, .5, .75, .9, .99, 1]},
        users_touching_labelled_airing=len(labelled_users),
        users_with_qualified_pair=len(qualified_users),
        template_users_absent_from_log=len(test_users-users),
        template_users_without_labelled_overlap=len(test_users-labelled_users),
        template_users_without_qualified_pair=len(test_users-qualified_users))
    result['examples'] = examples
    result['duration_mismatch_examples'] = mismatches
    result['duration_mismatch_deltas_reported_minus_computed'] = dict(mismatch_deltas)
    result['timezone_diagnostic'] = dict(timezone_checks)
    # Independently check the indexed lookup with a linear scan for saved sessions.
    checks = []
    sessions = {(r['user_id'], r['log_line'], r['channel_id'], r['view_start'], r['view_end'])
                for rows in examples.values() for r in rows}
    for user, line, channel, begin, finish in sorted(sessions):
        start, end = stamp(begin), stamp(finish)
        rows = index.get(channel, [])
        brute = {a[3:5] for a in rows if a[0] < end and a[1] > start and a[1] > a[0]}
        indexed = set()
        if rows:
            j = bisect.bisect_left(starts[channel], end)-1
            while j >= 0 and prefix_ends[channel][j] > start:
                a = rows[j]
                if a[1] > start and a[1] > a[0]:
                    indexed.add(a[3:5])
                j -= 1
        assert indexed == brute, (line, indexed, brute)
        checks.append({'log_line': line, 'labelled_matches': len(brute), 'indexed_equals_linear_scan': True})
    result['independent_join_checks'] = checks
    result['runtime_seconds'] = round(time.perf_counter()-began, 3)
    result['peak_rss_native_units'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result['peak_rss_units'] = 'bytes on macOS; KiB on Linux'
    OUT.mkdir(exist_ok=True)
    (OUT / 'audit_results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    flattened = [dict(example_kind=tag, **r) for tag, rows in examples.items() for r in rows]
    with (OUT / 'join_examples.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(flattened[0]))
        writer.writeheader()
        writer.writerows(flattened)
    print(json.dumps({k: result[k] for k in ['log', 'candidate_coverage', 'runtime_seconds']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
