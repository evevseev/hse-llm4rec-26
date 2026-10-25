"""Train one fixed pairwise ranker using supervised labels no later than week 20.

This script never reads validation_interactions.csv or weeks 21–30 schedules.
"""
import csv
import hashlib
import json
import platform
import resource
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_limits

from ltr_features import (FEATURES, OUTER_CUTOFF, RANKER_PARAMETERS, WINDOWS, Snapshot,
                          load_events, load_schedule, target_counts)
from xgboost_runtime import XGBRanker, xgboost

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'processed' / 'learning_to_rank'
OUT = ROOT / 'reports'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    began = time.perf_counter()
    DATA.mkdir(exist_ok=True)
    protocol = {'model': 'XGBoost pairwise learning to rank', 'parameters': RANKER_PARAMETERS,
        'features': FEATURES, 'training_windows': [{'name': n, 'history_cutoff_epoch': c, 'label_end_epoch': e} for n, c, e in WINDOWS],
        'outer_history_cutoff_epoch': OUTER_CUTOFF,
        'candidate_generation': 'Up to 100: top 50 baseline score, top 30 channel-affinity*log1p(weekly future airings), top 20 weekly future airings; deduplicate and fill by baseline.',
        'training_labels': 'Binary membership in each user top five qualified-airing frequencies in the next two weeks; item ID breaks count ties.',
        'training_positive_injection': 'Append missing positive IDs only during training, never during outer prediction. Injection status is not a feature.',
        'training_population': 'Warm users with at least one supervised target in each earlier window.',
        'model_selection': 'One fixed configuration, all three windows used for fitting. No outer-label selection or early stopping.',
        'outer_evaluation': 'Original weeks 21–30 and original MAP@5 population/labels. Load behaviour only after prediction artifacts are frozen.',
        'future_schedule_use': 'Only ID, channel, start and duration. No future titles, categories, genre or viewer information.',
        'cold_policy': 'Same training popularity top five as every previous method.',
        'score_policy': 'Rank raw margins; equivalently sigmoid margins are strictly positive monotone scores, not calibrated viewing probabilities.'}
    (OUT / 'ltr_plan.json').write_text(json.dumps(protocol, indent=2)+'\n')
    events = load_events()
    # Independently reconcile the richer export with the frozen training counts.
    event_counts = Counter((u, item) for u, item, _, _, _, _ in events)
    with (ROOT / 'data' / 'processed' / 'train_interactions.csv').open(newline='') as f:
        expected = Counter({(r['user_id'], int(r['tv_show_id'])): int(r['qualified_airings']) for r in csv.DictReader(f)})
    assert event_counts == expected
    schedule = load_schedule(['export_arh_11-20-final.csv'])
    users = sorted({e[0] for e in events}, key=int)
    xblocks, yblocks, groups, query_records, windows = [], [], [], [], []
    offset = 0
    for name, cutoff, finish in WINDOWS:
        assert cutoff < finish <= OUTER_CUTOFF
        snapshot = Snapshot(events, schedule, users, cutoff, finish)
        targets = target_counts(events, cutoff, finish)
        queries = positives = injected = natural_hits = total_targets = 0
        for u in users:
            row = snapshot.user_index[u]
            if u not in targets or snapshot.user_total[row] == 0:
                continue
            positions, features, added = snapshot.candidates_and_features(u, injected_targets=targets[u])
            ids = snapshot.items[positions]
            labels = np.isin(ids, targets[u]).astype(np.uint8)
            assert labels.sum() == len(targets[u]) and 1 <= len(targets[u]) <= 5
            xblocks.append(features); yblocks.append(labels); groups.append(len(labels))
            query_records.append({'window': name, 'user_id': u, 'history_cutoff_epoch': cutoff,
                'label_end_epoch': finish, 'row_start': offset, 'rows': len(labels),
                'positive_items': len(targets[u]), 'injected_positives': added})
            offset += len(labels)
            queries += 1; positives += len(targets[u]); injected += added
            natural_hits += len(targets[u])-added; total_targets += len(targets[u])
        windows.append({'name': name, 'history_cutoff_epoch': cutoff, 'label_end_epoch': finish,
            'maximum_history_event_end': snapshot.history_max_end, 'queries': queries, 'positive_rows': positives,
            'injected_positives': injected, 'natural_candidate_target_recall': natural_hits/total_targets,
            'available_programmes': len(snapshot.items), 'future_schedule_rows': snapshot.future_schedule_rows})
        print(f'{name}: {queries} queries, {positives} positives, {injected} positives injected.', flush=True)
        del snapshot
    X = np.concatenate(xblocks); y = np.concatenate(yblocks); group = np.array(groups, dtype=np.uint32)
    del xblocks, yblocks
    assert X.shape[0] == y.shape[0] == int(group.sum()) and X.shape[1] == len(FEATURES)
    np.savez_compressed(DATA / 'training_examples.npz', X=X, y=y, group=group)
    with (OUT / 'ltr_training_queries.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(query_records[0])); writer.writeheader(); writer.writerows(query_records)
    model = XGBRanker(**RANKER_PARAMETERS)
    fit_start = time.perf_counter()
    model.fit(X, y, group=group, verbose=False)
    fit_seconds = time.perf_counter()-fit_start
    model.save_model(DATA / 'ranker.ubj')
    importance = sorted([{'feature': name, 'normalized_gain': float(value)} for name, value in zip(FEATURES, model.feature_importances_)], key=lambda r: (-r['normalized_gain'], r['feature']))
    (OUT / 'ltr_feature_importance.json').write_text(json.dumps(importance, indent=2)+'\n')
    result = {'plan_sha256': digest(OUT / 'ltr_plan.json'), 'windows': windows,
        'training_queries': len(groups), 'training_rows': len(y), 'positive_rows': int(y.sum()),
        'features': len(FEATURES), 'maximum_label_end_epoch': max(e for _, _, e in WINDOWS),
        'outer_validation_behaviour_used': False, 'outer_schedule_used_during_training': False,
        'fit_seconds': fit_seconds, 'runtime_seconds': time.perf_counter()-began,
        'model_sha256': digest(DATA / 'ranker.ubj'), 'training_examples_sha256': digest(DATA / 'training_examples.npz'),
        'history_sha256': digest(DATA / 'history' / 'training_airing_details.csv'),
        'training_counts_sha256': digest(ROOT / 'data' / 'processed' / 'train_interactions.csv'),
        'training_schedule_sha256': digest(ROOT / 'data' / 'export_arh_11-20-final.csv'),
        'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux',
        'environment': {'python': sys.version, 'platform': platform.platform(), 'xgboost': xgboost.__version__, 'numpy': np.__version__}}
    (OUT / 'ltr_training_results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        main()
