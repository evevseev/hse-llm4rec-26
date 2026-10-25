"""History-only and availability-only feature snapshots for learning to rank.

Future schedule fields used: programme ID, channel, start and duration only.
No future content metadata or future viewing behaviour enters a feature.
"""
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo('Europe/Kyiv')
DAY = 86400


def epoch(value, schedule=False):
    if schedule:
        value = f'{value[6:10]}-{value[3:5]}-{value[:2]} {value[11:]}'
    return int(datetime.fromisoformat(value).replace(tzinfo=ZONE).timestamp())


BEGIN = epoch('2020-03-09 00:00:00')
OUTER_CUTOFF = epoch('2020-05-18 00:00:00')
OUTER_END = epoch('2020-07-27 00:00:00')
WINDOWS = [('weeks_15_16', epoch('2020-04-06 00:00:00'), epoch('2020-04-20 00:00:00')),
           ('weeks_17_18', epoch('2020-04-20 00:00:00'), epoch('2020-05-04 00:00:00')),
           ('weeks_19_20', epoch('2020-05-04 00:00:00'), OUTER_CUTOFF)]
FEATURES = ['personal_count', 'log_personal_count', 'personal_share', 'personal_weekly_rate',
    'recent_14day_count', 'previous_14day_count', 'recent_trend', 'days_since_last_item_watch',
    'personal_rank_reciprocal', 'global_viewers', 'log_global_viewers', 'global_viewer_fraction',
    'global_qualified_airings', 'global_weekly_airings', 'baseline_score', 'baseline_rank_reciprocal',
    'user_training_airings', 'user_distinct_items', 'history_calendar_days', 'user_recent_fraction',
    'future_airings_per_week', 'future_airing_start_day_fraction', 'future_distinct_channels',
    'future_first_airing_position', 'future_last_airing_position', 'schedule_channel_affinity',
    'schedule_start_time_affinity', 'future_mean_duration_minutes', 'personal_item_known',
    'global_item_known', 'user_favorite_share', 'user_channel_concentration']
RANKER_PARAMETERS = {'objective': 'rank:pairwise', 'eval_metric': 'map@5', 'n_estimators': 120,
    'max_depth': 3, 'learning_rate': .05, 'min_child_weight': 20, 'reg_lambda': 1.,
    'subsample': 1., 'colsample_bytree': 1., 'tree_method': 'hist', 'max_bin': 64,
    'lambdarank_pair_method': 'topk', 'lambdarank_num_pair_per_sample': 5,
    'random_state': 42, 'n_jobs': 4}


def time_slot(value):
    local = datetime.fromtimestamp(int(value), ZONE)
    return local.weekday()*6+local.hour//4


def load_events():
    rows = []
    path = ROOT / 'data' / 'processed' / 'learning_to_rank' / 'history' / 'training_airing_details.csv'
    with path.open(newline='') as f:
        for r in csv.DictReader(f):
            rows.append((r['user_id'], int(r['tv_show_id']), int(r['channel_id']),
                         int(r['airing_start_epoch']), int(r['airing_end_epoch']), int(r['overlap_seconds'])))
    assert all(BEGIN <= a < b <= OUTER_CUTOFF for _, _, _, a, b, _ in rows)
    return rows


def load_schedule(filenames):
    rows, seen = [], set()
    for filename in filenames:
        with (ROOT / 'data' / filename).open(newline='', encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                item, duration = int(r['tv_show_id']), int(r['duration'])
                if not item or duration <= 0:
                    continue
                start, channel = epoch(r['start_time'], True), int(r['channel_id'])
                key = (item, channel, start, start+duration)
                if key not in seen:
                    seen.add(key)
                    rows.append(key)
    return rows


def target_counts(events, cutoff, finish):
    counts = defaultdict(Counter)
    for u, item, _, start, end, _ in events:
        if cutoff <= start < end <= finish:
            counts[u][item] += 1
    return {u: [i for i, _ in sorted(h.items(), key=lambda v: (-v[1], v[0]))[:5]] for u, h in counts.items()}


class Snapshot:
    def __init__(self, events, schedule, users, cutoff, finish):
        if cutoff > OUTER_CUTOFF or cutoff >= finish:
            raise ValueError('History cutoff must be valid and no later than the outer training boundary.')
        self.users, self.cutoff, self.finish = users, cutoff, finish
        self.user_index = {u: j for j, u in enumerate(users)}
        history = [e for e in events if BEGIN <= e[3] < e[4] <= cutoff]
        future = [r for r in schedule if r[2] < finish and r[3] > cutoff]
        self.items = np.array(sorted({r[0] for r in future}), dtype=np.int64)
        self.item_index = {int(i): j for j, i in enumerate(self.items)}
        all_items = sorted(set(self.items.tolist()) | {e[1] for e in history})
        ai = {i: j for j, i in enumerate(all_items)}
        channels = sorted({r[1] for r in future} | {e[2] for e in history})
        ci = {c: j for j, c in enumerate(channels)}
        self.channels, self.channel_index = channels, ci
        self.history_days = (datetime.fromtimestamp(cutoff, ZONE).date()-datetime.fromtimestamp(BEGIN, ZONE).date()).days
        target_days = (datetime.fromtimestamp(finish, ZONE).date()-datetime.fromtimestamp(cutoff, ZONE).date()).days
        self.target_days = target_days
        rr, cc, vv, recent, previous = [], [], [], [], []
        self.last = defaultdict(dict)
        channel_mass = np.zeros((len(users), len(channels)))
        slot_mass = np.zeros((len(users), 42))
        for u, item, channel, start, end, overlap in history:
            if u not in self.user_index:
                continue
            row, column = self.user_index[u], ai[item]
            rr.append(row); cc.append(column); vv.append(1)
            recent.append(int(end > cutoff-14*DAY))
            previous.append(int(cutoff-28*DAY < end <= cutoff-14*DAY))
            self.last[u][item] = max(self.last[u].get(item, 0), end)
            channel_mass[row, ci[channel]] += overlap
            slot_mass[row, time_slot(start)] += overlap
        shape = (len(users), len(all_items))
        counts = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=shape)
        recent_counts = sparse.csr_matrix((np.array(recent, dtype=float), (rr, cc)), shape=shape)
        previous_counts = sparse.csr_matrix((np.array(previous, dtype=float), (rr, cc)), shape=shape)
        cols = [ai[int(i)] for i in self.items]
        self.counts = counts[:, cols].tocsr()
        self.recent = recent_counts[:, cols].tocsr()
        self.previous = previous_counts[:, cols].tocsr()
        self.user_total = np.asarray(counts.sum(axis=1)).ravel()
        self.user_distinct = np.diff(counts.indptr)
        self.user_recent = np.asarray(recent_counts.sum(axis=1)).ravel()
        self.user_favorite = np.array([counts.getrow(j).data.max(initial=0) for j in range(len(users))])
        binary = counts.copy(); binary.data[:] = 1
        self.popularity = np.asarray(binary.sum(axis=0)).ravel()[cols]
        self.global_counts = np.asarray(counts.sum(axis=0)).ravel()[cols]
        self.warm_users = max(1, int((self.user_total > 0).sum()))
        self.maximum_popularity = max(1, self.popularity.max(initial=0))
        self.channel_share = channel_mass/np.maximum(channel_mass.sum(axis=1, keepdims=True), 1)
        self.slot_share = slot_mass/np.maximum(slot_mass.sum(axis=1, keepdims=True), 1)
        self.airings = np.zeros(len(self.items))
        self.duration = np.zeros(len(self.items))
        first, last = np.full(len(self.items), finish, dtype=float), np.full(len(self.items), cutoff, dtype=float)
        day_sets, channel_sets = defaultdict(set), defaultdict(set)
        ar, ac, av, sr, sc = [], [], [], [], []
        for item, channel, start, end in future:
            j = self.item_index[item]
            self.airings[j] += 1
            self.duration[j] += min(end, finish)-max(start, cutoff)
            first[j] = min(first[j], max(start, cutoff))
            last[j] = max(last[j], min(end, finish))
            day_sets[j].add(datetime.fromtimestamp(max(start, cutoff), ZONE).date())
            channel_sets[j].add(channel)
            ar.append(j); ac.append(ci[channel]); av.append(1.)
            sr.append(j); sc.append(time_slot(start))
        self.days_fraction = np.array([len(day_sets[j])/target_days for j in range(len(self.items))])
        self.channel_count = np.array([len(channel_sets[j]) for j in range(len(self.items))])
        self.first = (first-cutoff)/(finish-cutoff)
        self.last_position = (last-cutoff)/(finish-cutoff)
        self.duration /= np.maximum(self.airings, 1)*60
        self.airings_weekly = self.airings/(target_days/7)
        self.schedule_channels = sparse.diags(1/np.maximum(self.airings, 1)) @ sparse.csr_matrix((av, (ar, ac)), shape=(len(self.items), len(channels)))
        self.schedule_slots = sparse.diags(1/np.maximum(self.airings, 1)) @ sparse.csr_matrix((np.ones(len(sr)), (sr, sc)), shape=(len(self.items), 42))
        self.fallback = np.lexsort((self.items, -self.popularity))[:5]
        self.history_max_end = max((e[4] for e in history), default=BEGIN)
        self.future_schedule_rows = len(future)

    def user_vectors(self, user):
        row = self.user_index[user]
        personal = self.counts.getrow(row).toarray().ravel()
        recent = self.recent.getrow(row).toarray().ravel()
        previous = self.previous.getrow(row).toarray().ravel()
        base = personal+3*self.popularity/self.maximum_popularity
        order = np.lexsort((self.items, -self.popularity, -base))
        base_rank = np.empty(len(order)); base_rank[order] = np.arange(1, len(order)+1)
        personal_order = np.lexsort((self.items, -self.popularity, -personal))
        personal_rank = np.empty(len(order)); personal_rank[personal_order] = np.arange(1, len(order)+1)
        channel = np.asarray(self.schedule_channels @ self.channel_share[row]).ravel()
        slot = np.asarray(self.schedule_slots @ self.slot_share[row]).ravel()
        return row, personal, recent, previous, base, order, base_rank, personal_rank, channel, slot

    def candidates_and_features(self, user, injected_targets=()):
        row, personal, recent, previous, base, order, base_rank, personal_rank, channel, slot = self.user_vectors(user)
        channel_order = np.lexsort((self.items, -self.popularity, -(channel*np.log1p(self.airings_weekly))))
        airing_order = np.lexsort((self.items, -self.popularity, -self.airings_weekly))
        chosen = list(dict.fromkeys(order[:50].tolist()+channel_order[:30].tolist()+airing_order[:20].tolist()))
        if len(chosen) < min(100, len(self.items)):
            for j in order:
                if int(j) not in chosen:
                    chosen.append(int(j))
                if len(chosen) == min(100, len(self.items)):
                    break
        natural = set(chosen)
        for item in injected_targets:
            if item not in self.item_index:
                raise ValueError('A target is outside schedule availability.')
            position = self.item_index[item]
            if position not in natural:
                chosen.append(position)
        chosen = list(dict.fromkeys(chosen))
        j = np.array(chosen, dtype=int)
        last = np.array([min(365., (self.cutoff-self.last.get(user, {}).get(int(self.items[k]), self.cutoff-365*DAY))/DAY) for k in j])
        total, weeks = max(1, self.user_total[row]), self.history_days/7
        personal_recip = np.where(personal[j] > 0, 1/personal_rank[j], 0)
        columns = [personal[j], np.log1p(personal[j]), personal[j]/total, personal[j]/weeks,
            recent[j], previous[j], (recent[j]-previous[j])/(1+recent[j]+previous[j]), last,
            personal_recip, self.popularity[j], np.log1p(self.popularity[j]), self.popularity[j]/self.warm_users,
            self.global_counts[j], self.global_counts[j]/weeks, base[j], 1/base_rank[j],
            np.full(len(j), self.user_total[row]), np.full(len(j), self.user_distinct[row]),
            np.full(len(j), self.history_days), np.full(len(j), self.user_recent[row]/total),
            self.airings_weekly[j], self.days_fraction[j], self.channel_count[j], self.first[j], self.last_position[j],
            channel[j], slot[j], self.duration[j], (personal[j] > 0).astype(float), (self.popularity[j] > 0).astype(float),
            np.full(len(j), self.user_favorite[row]/total), np.full(len(j), self.channel_share[row].max(initial=0))]
        features = np.column_stack(columns).astype(np.float32)
        assert features.shape == (len(j), len(FEATURES)) and np.isfinite(features).all()
        return j, features, len(chosen)-len(natural)
