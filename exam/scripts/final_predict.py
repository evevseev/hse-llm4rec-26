# Generated with an AI assistant.
"""Build checked final CSV files without submitting anything to Kaggle."""
import csv
import hashlib
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse
from threadpoolctl import threadpool_limits

from collaborative_models import build_transition, personalized_pagerank
from prepare_validation import BEGIN, END, prepare_fold

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
WORK = DATA / 'processed' / 'final_prediction'
OUT = ROOT / 'reports'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    began = time.perf_counter()
    with (DATA / 'submission.csv').open(newline='') as f:
        template = list(csv.DictReader(f))
    users = [r['user_id'] for r in template]
    assert len(users) == len(set(users)) == 1260
    # Rebuild once from all available viewing behaviour, with the same union/80% rule.
    prepare_fold(output_dir=WORK, report_path=OUT / 'final_interaction_preparation.json',
                 begin=BEGIN, cutoff=END, finish=END, quiet=True)
    histories = {}
    with (WORK / 'train_interactions.csv').open(newline='') as f:
        for r in csv.DictReader(f):
            histories.setdefault(r['user_id'], {})[int(r['tv_show_id'])] = int(r['qualified_airings'])
    candidates = set()
    test_schedule = DATA / 'export_arh_31-42-final.csv'
    with test_schedule.open(newline='', encoding='utf-8-sig') as f:
        for r in csv.DictReader(f):
            if int(r['tv_show_id']) != 0 and int(r['duration']) > 0:
                candidates.add(int(r['tv_show_id']))
    popularity = Counter(i for history in histories.values() for i in history)
    fallback = sorted(candidates, key=lambda i: (-popularity[i], i))
    maximum = max(popularity[i] for i in candidates)
    checks = {}

    def save(filename, predictions):
        path = ROOT / filename
        with path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'tv_show_id'])
            writer.writerows((u, ' '.join(map(str, ids))) for u, ids in zip(users, predictions))
        with path.open(newline='') as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == ['user_id', 'tv_show_id']
            rows = list(reader)
        assert [r['user_id'] for r in rows] == users
        assert len(rows) == 1260
        for r in rows:
            ids = list(map(int, r['tv_show_id'].split()))
            assert len(ids) == len(set(ids)) == 5 and 0 not in ids and set(ids) <= candidates
        checks[filename] = {'status': 'passed', 'rows': len(rows), 'original_user_order': True,
            'five_distinct_nonzero_available_ids_per_row': True, 'sha256': sha(path)}
        print(f'Saved and verified {filename}: {checks[filename]["sha256"]}', flush=True)

    def frequency(bonus):
        result = []
        for u in users:
            history = histories.get(u, {})
            if not history:
                result.append(fallback[:5])
                continue
            result.append(sorted(candidates, key=lambda i:
                (-(history.get(i, 0)+bonus*popularity[i]/maximum), -popularity[i], i))[:5])
        return result

    # First requested deliverable is persisted before any graph work.
    save('submission_frequency_bonus3.csv', frequency(3))
    train_users = sorted(histories, key=int)
    items = sorted(popularity)
    item_index = {i: j for j, i in enumerate(items)}
    user_index = {u: j for j, u in enumerate(train_users)}
    rr, cc, vv = [], [], []
    for u, history in histories.items():
        for i, n in history.items():
            rr.append(user_index[u]); cc.append(item_index[i]); vv.append(n)
    counts = sparse.csr_matrix((np.array(vv, dtype=float), (rr, cc)), shape=(len(train_users), len(items)))
    transition, dangling, graph = build_transition(counts, neighbors=50, min_pair_users=3)
    ppr_predictions = {u: fallback[:5] for u in users if u not in user_index}
    warm = [u for u in users if u in user_index]
    available = [i for i in candidates if i in item_index]
    available.sort()
    columns = [item_index[i] for i in available]
    convergence = []
    for start in range(0, len(warm), 128):
        batch = warm[start:start+128]
        seeds = counts[[user_index[u] for u in batch]].copy()
        seeds.data = np.log1p(seeds.data)
        ranks, info = personalized_pagerank(seeds, transition, dangling, damping=.5)
        convergence.append(info)
        for u, row in zip(batch, ranks[:, columns]):
            positive = [j for j, score in enumerate(row) if score > 0]
            ordered = sorted(positive, key=lambda j: (-row[j], -popularity[available[j]], available[j]))
            ids = [available[j] for j in ordered[:5]]
            ids += [i for i in fallback if i not in ids][:5-len(ids)]
            ppr_predictions[u] = ids
    assert all(r['converged'] for r in convergence)
    save('submission_ppr.csv', [ppr_predictions[u] for u in users])
    save('submission_frequency_bonus6.csv', frequency(6))
    manifest = {'generated_with': 'Generated with an AI assistant', 'status': 'passed',
        'submitted_to_kaggle': False, 'files': checks,
        'parameters': {'training_weeks': '11–30', 'training_begin': '2020-03-09 00:00:00 Europe/Kyiv',
            'training_end_exclusive': '2020-07-27 00:00:00 Europe/Kyiv',
            'join': 'Same channel; positive half-open interval overlap; interval union per user-airing.',
            'watched': 'Merged overlap >=80% of the full airing; boundary-crossing airings excluded.',
            'candidates': 'Nonzero IDs with positive-duration airings in the weeks 31–42 schedule.',
            'popularity': 'Distinct training viewers per item, including all training users, not just template users.',
            'frequency_score': 'personal qualified-airing count + bonus * popularity / maximum candidate popularity',
            'bonuses': [3, 6], 'repeat_recommendations': True,
            'ppr': {'damping': .5, 'personalization': 'Normalized log1p personal counts',
                'graph': 'Refit the same binary-viewer cosine graph on weeks 11–30; support>=3, top 50 outgoing neighbors, no self edges.',
                'dangling': 'Return mass to personal seed distribution', 'tolerance_l1': 1e-8, 'max_iterations': 100},
            'ties': 'Descending training popularity, then ascending item ID.',
            'fallback': 'Append popularity-ranked available IDs without duplicates; cold users get popularity top five.'},
        'candidate_ids': len(candidates), 'training_users_with_qualified_history': len(histories),
        'template_users_without_qualified_history': sum(u not in histories for u in users),
        'graph_edges': graph.nnz, 'ppr_convergence': convergence,
        'input_sha256': {n: sha(DATA / n) for n in ['dataset11-30.csv', 'export_arh_11-20-final.csv',
            'export_arh_21-30-final.csv', 'export_arh_31-42-final.csv', 'submission.csv']},
        'training_interactions_sha256': sha(WORK / 'train_interactions.csv'),
        'runtime_seconds': time.perf_counter()-began}
    (OUT / 'final_prediction_checks.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Saved reports/final_prediction_checks.json', flush=True)


if __name__ == '__main__':
    with threadpool_limits(limits=1):
        run()
