"""Frozen 20-configuration search grid and non-overlapping validation periods."""
import json
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configurations():
    configs = []
    for bonus in [0, 1, 3, 6]:
        configs.append({'id': f'frequency_bonus_{bonus}', 'family': 'frequency', 'bonus': bonus})
    for damping, history in product([.5, .85], ['raw', 'log']):
        configs.append({'id': f'ppr_d{str(damping).replace(".", "")}_{history}',
                        'family': 'ppr', 'damping': damping, 'history': history})
    for factors, reg, alpha in product([16, 32], [.1, 1.], [0., 20.]):
        configs.append({'id': f'mf_f{factors}_r{str(reg).replace(".", "")}_a{int(alpha)}',
                        'family': 'mf', 'factors': factors, 'regularization': reg, 'alpha': alpha})
    for family in ['cbf', 'association_rules']:
        for history in ['raw', 'log']:
            configs.append({'id': family+'_'+history, 'family': family, 'history': history})
    assert len(configs) == len({r['id'] for r in configs}) == 20
    return configs


def plan():
    return {'configurations': configurations(), 'unique_configuration_limit': 20,
        'reference_config_id': 'frequency_bonus_3', 'max_parallel_workers': 4, 'blas_threads_per_worker': 1,
        'seed': 42, 'metric': 'MAP@5 over users with at least one target',
        'fixed_parameters': {'mf_target': 'log1p(qualified airing count)', 'mf_iterations': 15,
            'ppr_neighbors': 50, 'ppr_min_pair_users': 3, 'ppr_max_iterations': 100, 'ppr_tolerance': 1e-8,
            'cbf_fields_and_weights': 'Original category/genre=2, actor/director=1, decade=0.3; training-only TF-IDF.',
            'rules': 'Original pair support>=3, confidence>=0.02, shrinkage=10, top 100 consequents.',
            'ranking': 'Positive scores; training popularity then ID breaks ties; common popularity fallback; repeats allowed.'},
        'folds': {
            'primary': {'begin': '2020-03-09 00:00:00', 'cutoff': '2020-05-18 00:00:00', 'end': '2020-07-27 00:00:00',
                        'train_weeks': '11-20', 'validation_weeks': '21-30', 'data_dir': 'data/processed'},
            'secondary': {'begin': '2020-03-09 00:00:00', 'cutoff': '2020-04-20 00:00:00', 'end': '2020-05-18 00:00:00',
                          'train_weeks': '11-16', 'validation_weeks': '17-20', 'data_dir': 'data/processed/search_secondary'}},
        'finalist_rule': 'Freeze the top four primary MAP configurations (ID breaks ties) before secondary evaluation; add reference bonus=3 if absent.',
        'decision_rule': 'Require positive mean MAP gain vs reference on both folds and a positive lower bound of the secondary paired 95% bootstrap interval. Among survivors maximize the smaller fold gain; tie-break by primary MAP then ID. If none, retain reference.',
        'uncertainty': 'Report paired 2000-user-bootstrap intervals with seed 42; conditional on these folds, not corrected for model selection.',
        'limitations': ['Validation periods do not overlap, but users and history do.',
            'Secondary validation is earlier and lies within primary training; it is a temporal robustness check, not an independent future test.',
            'Validation horizons differ: ten weeks primary and four weeks secondary.',
            'Secondary results are examined only for the frozen finalists and reference; no grid expansion.']}


if __name__ == '__main__':
    (ROOT / 'reports' / 'hyperparameter_plan.json').write_text(json.dumps(plan(), indent=2)+'\n')
    print('Saved exactly 20 configurations and the frozen selection protocol.')
