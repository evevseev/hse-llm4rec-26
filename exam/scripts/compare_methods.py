"""Evaluate four fixed recommenders on the same temporal hold-out.

Run after prepare_validation.py: .venv/bin/python scripts/compare_methods.py
No validation behaviour is passed to feature construction or model fitting.
"""
import csv
import json
import platform
import re
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import scipy
from scipy import sparse
import sklearn
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.preprocessing import normalize

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / 'data' / 'processed'
REPORTS = ROOT / 'reports'
SEED = 42
METHODS = ['popularity', 'personal_frequency', 'cbf', 'association_rules']
PARAMETERS = {
    'k': 5, 'seed': SEED,
    'popularity': 'Number of distinct training viewers; ascending item ID breaks ties.',
    'personal_frequency': 'Qualified training airing counts; ties use popularity then item ID.',
    'cbf': {'category_weight': 2.0, 'genre_weight': 2.0, 'director_weight': 1.0,
            'actor_weight': 1.0, 'year_decade_weight': 0.3, 'smooth_idf': True,
            'item_normalization': 'l2', 'history_weight': 'log1p(qualified airing count)',
            'profile_normalization': 'l2', 'score': 'cosine similarity', 'batch_size': 256},
    'association_rules': {'min_pair_support_users': 3, 'min_confidence': 0.02,
                          'shrinkage': 10, 'max_consequents_per_antecedent': 100,
                          'history_weight': 'log1p(qualified airing count)',
                          'score': 'sum(history weight * confidence * support/(support+10))'},
    'selection': 'One fixed configuration per method; no hyperparameter search on validation.',
    'target_ties': 'Descending validation qualified-airing count, then ascending item ID.',
    'fallback': 'Append unseen-in-list popularity IDs; cold users receive identical popularity top five.',
    'repeat_policy': 'Previously watched items remain eligible for every method.'}


def load_counts(path):
    result = defaultdict(Counter)
    with path.open(newline='') as f:
        for row in csv.DictReader(f):
            result[row['user_id']][int(row['tv_show_id'])] = int(row['qualified_airings'])
    return dict(result)


def average_precision_at_5(prediction, relevant):
    if not relevant:
        raise ValueError('Empty targets are excluded from MAP; report their number separately.')
    seen, hits, total = set(), 0, 0.0
    for rank, item in enumerate(prediction[:5], 1):
        if item in relevant and item not in seen:
            hits += 1
            total += hits/rank
        seen.add(item)
    return total/min(5, len(relevant))


def item_features(metadata):
    """Union source attributes per item; never tokenize titles or validation descriptions."""
    features = {}
    for field, values in metadata.items():
        if field == 'tv_show_category':
            for value in values:
                features['category='+value.casefold()] = 2.0
        elif field.startswith('tv_show_genre_'):
            for value in values:
                features['genre='+value.casefold()] = 2.0
        elif field in ('director', 'actors'):
            for value in values:
                for token in re.split(r'[,;|]', value):
                    token = ' '.join(token.casefold().split())
                    if token:
                        features[('director=' if field == 'director' else 'actor=')+token] = 1.0
        elif field == 'year_of_production':
            for value in values:
                years = re.findall(r'\b(?:18|19|20)\d{2}\b', value)
                if years:
                    features[f'decade={int(years[0])//10*10}'] = 0.3
    return features


def rank_scores(scores, candidate_ids, candidate_popularity, fallback):
    positions = np.flatnonzero(scores > 0)
    if len(positions):
        order = np.lexsort((candidate_ids[positions], -candidate_popularity[positions], -scores[positions]))
        selected = candidate_ids[positions[order[:5]]].tolist()
    else:
        selected = []
    fill = 5-len(selected)
    for item in fallback:
        if len(selected) == 5:
            break
        if item not in selected:
            selected.append(item)
    assert len(selected) == len(set(selected)) == 5
    return selected, fill


def bootstrap_difference(values, reference):
    """Paired user bootstrap, conditional on this single hold-out and population."""
    differences = np.asarray(values)-np.asarray(reference)
    rng = np.random.default_rng(SEED)
    means = []
    for _ in range(2000):
        means.append(float(differences[rng.integers(0, len(differences), len(differences))].mean()))
    return {'mean_delta': float(differences.mean()),
            'paired_bootstrap_95_percent_interval': np.quantile(means, [.025, .975]).tolist(),
            'replicates': 2000, 'seed': SEED}


def main():
    began = time.perf_counter()
    timings = {}
    train = load_counts(PROCESSED / 'train_interactions.csv')
    # This input contains only IDs and availability, never validation viewing behaviour.
    candidate_ids = np.array(json.loads((PROCESSED / 'validation_candidates.json').read_text()), dtype=np.int64)
    metadata = json.loads((PROCESSED / 'training_metadata.json').read_text())
    users = json.loads((PROCESSED / 'all_users.json').read_text())
    user_index = {u: i for i, u in enumerate(users)}
    item_ids = sorted(set(candidate_ids.tolist()) | {int(i) for i in metadata}
                      | {i for history in train.values() for i in history})
    item_index = {item: i for i, item in enumerate(item_ids)}
    candidate_columns = np.array([item_index[int(i)] for i in candidate_ids])
    rr, cc, vv = [], [], []
    for user, history in train.items():
        for item, count in history.items():
            rr.append(user_index[user])
            cc.append(item_index[item])
            vv.append(count)
    matrix = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=(len(users), len(item_ids)))
    binary = matrix.copy()
    binary.data[:] = 1
    popularity = np.asarray(binary.sum(axis=0)).ravel()
    candidate_popularity = popularity[candidate_columns]
    fallback = candidate_ids[np.lexsort((candidate_ids, -candidate_popularity))].tolist()
    predictions, fallback_slots, raw_scores = {}, {}, {}
    timings['shared_input_and_training_matrix_seconds'] = time.perf_counter()-began

    start = time.perf_counter()
    predictions['popularity'] = [fallback[:5] for _ in users]
    fallback_slots['popularity'] = [0 for _ in users]
    raw_scores['popularity'] = [{item: float(popularity[item_index[item]]) for item in fallback[:5]} for _ in users]
    timings['popularity_fit_and_predict_seconds'] = time.perf_counter()-start

    start = time.perf_counter()
    personal_predictions, personal_fill, personal_scores = [], [], []
    for user in users:
        scores = np.zeros(len(candidate_ids))
        history = train.get(user, {})
        for pos, item in enumerate(candidate_ids):
            scores[pos] = history.get(int(item), 0)
        recs, fill = rank_scores(scores, candidate_ids, candidate_popularity, fallback)
        personal_predictions.append(recs)
        personal_fill.append(fill)
        personal_scores.append({item: float(history.get(item, 0)) for item in recs})
    predictions['personal_frequency'], fallback_slots['personal_frequency'] = personal_predictions, personal_fill
    raw_scores['personal_frequency'] = personal_scores
    timings['personal_frequency_fit_and_predict_seconds'] = time.perf_counter()-start

    weighted = matrix.copy()
    weighted.data = np.log1p(weighted.data)
    start = time.perf_counter()
    feature_ids = sorted(int(i) for i in metadata)
    vectorizer = DictVectorizer(dtype=np.float64)
    features = vectorizer.fit_transform([item_features(metadata[str(item)]) for item in feature_ids])
    tfidf = TfidfTransformer(norm='l2', smooth_idf=True)
    features = tfidf.fit_transform(features)
    # Fit vocabulary and IDF exclusively on the training item catalogue.
    feature_rows = {item: r for r, item in enumerate(feature_ids)}
    coordinates = features.tocoo()
    padded = sparse.csr_matrix((coordinates.data,
        ([item_index[feature_ids[r]] for r in coordinates.row], coordinates.col)),
        shape=(len(item_ids), features.shape[1]))
    profiles = normalize(weighted @ padded, norm='l2')
    candidate_vectors = padded[candidate_columns]
    timings['cbf_fit_seconds'] = time.perf_counter()-start
    start = time.perf_counter()
    cbf_predictions, cbf_fill, cbf_scores = [], [], []
    for begin in range(0, len(users), 256):
        scores = (profiles[begin:begin+256] @ candidate_vectors.T).toarray()
        for row in scores:
            recs, fill = rank_scores(row, candidate_ids, candidate_popularity, fallback)
            cbf_predictions.append(recs)
            cbf_fill.append(fill)
            cbf_scores.append({item: float(row[np.searchsorted(candidate_ids, item)]) for item in recs})
    predictions['cbf'], fallback_slots['cbf'] = cbf_predictions, cbf_fill
    raw_scores['cbf'] = cbf_scores
    timings['cbf_predict_seconds'] = time.perf_counter()-start

    start = time.perf_counter()
    co_view = (binary.T @ binary).tocsr()
    rule_row, rule_col, rule_weight, rule_records = [], [], [], []
    for antecedent in range(len(item_ids)):
        left, right = co_view.indptr[antecedent:antecedent+2]
        consequent = co_view.indices[left:right]
        support = co_view.data[left:right]
        confidence = support/max(popularity[antecedent], 1)
        valid = (consequent != antecedent) & (support >= 3) & (confidence >= .02)
        consequent, support, confidence = consequent[valid], support[valid], confidence[valid]
        weight = confidence * support/(support+10)
        order = np.lexsort((np.array(item_ids)[consequent], -weight))[:100]
        for k in order:
            j = consequent[k]
            rule_row.append(antecedent)
            rule_col.append(j)
            rule_weight.append(weight[k])
            rule_records.append([item_ids[antecedent], item_ids[j], int(popularity[antecedent]),
                                 int(support[k]), float(confidence[k]), float(weight[k])])
    rules = sparse.csr_matrix((rule_weight, (rule_row, rule_col)), shape=(len(item_ids), len(item_ids)))
    timings['association_rules_fit_seconds'] = time.perf_counter()-start
    start = time.perf_counter()
    association_predictions, association_fill, association_scores = [], [], []
    for begin in range(0, len(users), 256):
        scores = (weighted[begin:begin+256] @ rules[:, candidate_columns]).toarray()
        for row in scores:
            recs, fill = rank_scores(row, candidate_ids, candidate_popularity, fallback)
            association_predictions.append(recs)
            association_fill.append(fill)
            association_scores.append({item: float(row[np.searchsorted(candidate_ids, item)]) for item in recs})
    predictions['association_rules'], fallback_slots['association_rules'] = association_predictions, association_fill
    raw_scores['association_rules'] = association_scores
    timings['association_rules_predict_seconds'] = time.perf_counter()-start

    # Only now load validation behaviour, after all models and predictions are fixed.
    validation = load_counts(PROCESSED / 'validation_interactions.csv')
    targets = {u: [i for i, n in sorted(h.items(), key=lambda p: (-p[1], p[0]))[:5]]
               for u, h in validation.items()}
    candidate_set = set(candidate_ids.tolist())
    assert all(set(items) <= candidate_set for items in targets.values())
    with (ROOT / 'data' / 'submission.csv').open(newline='') as f:
        template_users = {r['user_id'] for r in csv.DictReader(f)}
    evaluated = [u for u in users if u in targets]
    segments = {
        'all_target_users': evaluated,
        'five_target_users': [u for u in evaluated if len(targets[u]) == 5],
        'template_target_users': [u for u in evaluated if u in template_users],
        'warm_target_users': [u for u in evaluated if u in train],
        'cold_target_users': [u for u in evaluated if u not in train],
        'light_history_target_users': [u for u in evaluated if 0 < sum(train.get(u, {}).values()) <= 10],
        'heavy_history_target_users': [u for u in evaluated if sum(train.get(u, {}).values()) >= 100]}
    per_user = {}
    for method in METHODS:
        per_user[method] = {u: average_precision_at_5(predictions[method][user_index[u]], set(targets[u])) for u in evaluated}
        for user in users:
            recs = predictions[method][user_index[user]]
            assert len(recs) == len(set(recs)) == 5 and set(recs) <= candidate_set and 0 not in recs
            if user not in train:
                assert recs == predictions['popularity'][user_index[user]]
    rows = []
    for segment, members in segments.items():
        for method in METHODS:
            hits = [len(set(predictions[method][user_index[u]]) & set(targets[u])) for u in members]
            rows.append({'segment': segment, 'method': method, 'users': len(members),
                'map_at_5': float(np.mean([per_user[method][u] for u in members])) if members else None,
                'precision_at_5': float(np.mean(hits)/5) if members else None,
                'recall_at_5': float(np.mean([h/len(targets[u]) for h, u in zip(hits, members)])) if members else None,
                'hit_rate_at_5': float(np.mean(np.array(hits) > 0)) if members else None})
    with (REPORTS / 'validation_metrics.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (REPORTS / 'validation_predictions.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'method', 'tv_show_id', 'fallback_slots', 'ap_at_5'])
        for user in users:
            i = user_index[user]
            for method in METHODS:
                writer.writerow([user, method, ' '.join(map(str, predictions[method][i])),
                                 fallback_slots[method][i], per_user[method].get(user, '')])
    with (REPORTS / 'validation_targets.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'target_ids', 'target_qualified_airing_counts', 'distinct_validation_items'])
        for user in sorted(targets, key=int):
            writer.writerow([user, ' '.join(map(str, targets[user])),
                ' '.join(str(validation[user][item]) for item in targets[user]), len(validation[user])])
    with (REPORTS / 'association_rules.csv').open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['antecedent_id', 'consequent_id', 'antecedent_users', 'pair_users', 'confidence', 'shrunk_confidence'])
        writer.writerows(rule_records)

    # Restrict examples to the evaluated template cohort; choose by training volume,
    # never by any method's score or recommendation accuracy.
    example_pool = sorted((u for u in template_users if u in train and u in targets), key=lambda u: (sum(train[u].values()), int(u)))
    selected = [('heavy', example_pool[-1]), ('light', example_pool[0])]
    display = json.loads((PROCESSED / 'display_metadata.json').read_text())
    examples = []
    for label, user in selected:
        i = user_index[user]
        relevant = set(targets.get(user, []))
        example = {'label': label, 'user_id': user, 'selection': 'Maximum/minimum positive training airing count among template users with validation targets; user ID breaks ties. No method performance is used.',
            'training_qualified_airings': sum(train[user].values()), 'training_distinct_items': len(train[user]),
            'validation_targets': [{'tv_show_id': item, **display[str(item)], 'count': validation[user][item]} for item in targets.get(user, [])],
            'methods': {}}
        for method in METHODS:
            example['methods'][method] = {'ap_at_5': per_user[method].get(user),
                'recommendations': [{'rank': rank, 'tv_show_id': item, **display[str(item)],
                    'method_score': raw_scores[method][i][item], 'in_validation_top5': item in relevant,
                    'qualified_validation_airings': validation.get(user, {}).get(item, 0),
                    'qualified_training_airings': train[user].get(item, 0)}
                    for rank, item in enumerate(predictions[method][i], 1)]}
        examples.append(example)
    (REPORTS / 'validation_examples.json').write_text(json.dumps(examples, ensure_ascii=False, indent=2)+'\n')
    primary_scores = {method: [per_user[method][u] for u in evaluated] for method in METHODS}
    comparisons = {f'{method}_minus_popularity': bootstrap_difference(primary_scores[method], primary_scores['popularity'])
                   for method in METHODS if method != 'popularity'}
    comparisons.update({f'{method}_minus_personal_frequency': bootstrap_difference(primary_scores[method], primary_scores['personal_frequency'])
                        for method in ['cbf', 'association_rules']})
    summaries = {}
    for method in METHODS:
        recs = [predictions[method][user_index[u]] for u in evaluated]
        summaries[method] = {'catalogue_items_recommended': len({i for rec in recs for i in rec}),
            'mean_fallback_slots': float(np.mean([fallback_slots[method][user_index[u]] for u in evaluated])),
            'fraction_recommendations_seen_in_training': float(np.mean([i in train.get(u, {}) for u, rec in zip(evaluated, recs) for i in rec]))}
    summary = {'parameters': PARAMETERS, 'metrics': rows, 'timings': timings,
        'population': {'all_log_users': len(users), 'training_users': len(train),
            'evaluated_users': len(evaluated), 'users_without_validation_targets_excluded': len(users)-len(evaluated),
            'template_users': len(template_users), 'template_users_without_targets': len(template_users-set(targets)),
            'target_size_distribution': dict(Counter(map(len, targets.values()))),
            'candidate_items': len(candidate_ids), 'training_metadata_items': len(feature_ids),
            'candidate_items_without_training_metadata': sum(int(i) not in feature_rows for i in candidate_ids),
            'candidate_items_without_training_views': int((candidate_popularity == 0).sum()),
            'validation_top5_items_seen_in_own_training': sum(i in train.get(u, {}) for u, t in targets.items() for i in t),
            'validation_top5_items_total': sum(map(len, targets.values()))},
        'model_sizes': {'content_features': features.shape[1], 'retained_rules': len(rule_records)},
        'recommendation_diagnostics': summaries, 'paired_comparisons': comparisons,
        'winner_on_primary_map': max(METHODS, key=lambda m: np.mean(primary_scores[m])),
        'runtime_seconds': round(time.perf_counter()-began, 3),
        'peak_rss_native_units': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'peak_rss_units': 'bytes on macOS; KiB on Linux',
        'environment': {'python': sys.version, 'platform': platform.platform(),
            'numpy': np.__version__, 'scipy': scipy.__version__, 'scikit_learn': sklearn.__version__}}
    (REPORTS / 'validation_results.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: summary[k] for k in ['population', 'winner_on_primary_map', 'timings', 'runtime_seconds']}, indent=2))
    for row in rows:
        if row['segment'] == 'all_target_users':
            print(f"{row['method']}: MAP@5={row['map_at_5']:.6f}; users={row['users']}")


if __name__ == '__main__':
    main()
