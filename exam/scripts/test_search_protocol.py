"""Check the grid budget, temporal separation and conservative selection rule."""
import json
import time
import unittest
from collections import Counter
from pathlib import Path

from prepare_validation import timestamp
from run_hyperparameter_search import select_robust_configuration
from search_plan import configurations, plan


def fixture(values):
    return {'ranking': [{'id': key, 'map_at_5': score} for key, score, _, _ in values],
            'comparisons_vs_reference': {key: {'mean_delta': delta,
                'paired_bootstrap_95_percent_interval': [lower, delta+.01]}
                for key, _, delta, lower in values}}


class SearchProtocolTests(unittest.TestCase):
    def test_twenty_unique_configurations_cover_five_families(self):
        grid = configurations()
        self.assertEqual(len({r['id'] for r in grid}), 20)
        self.assertEqual(Counter(r['family'] for r in grid),
                         {'frequency': 4, 'ppr': 4, 'mf': 8, 'cbf': 2, 'association_rules': 2})

    def test_validation_windows_do_not_overlap(self):
        folds = plan()['folds']
        self.assertLess(timestamp(folds['secondary']['cutoff']), timestamp(folds['secondary']['end']))
        self.assertEqual(timestamp(folds['secondary']['end']), timestamp(folds['primary']['cutoff']))
        for fold in folds.values():
            self.assertLess(timestamp(fold['begin']), timestamp(fold['cutoff']))

    def test_primary_winner_is_rejected_if_secondary_gain_is_negative(self):
        primary = fixture([('candidate', .4, .05, .01)])
        secondary = fixture([('candidate', .3, -.02, -.04)])
        self.assertEqual(select_robust_configuration(primary, secondary, '')['selected_config_id'], 'frequency_bonus_3')

    def test_positive_secondary_mean_is_not_enough_when_interval_crosses_zero(self):
        primary = fixture([('candidate', .4, .05, .01)])
        secondary = fixture([('candidate', .35, .002, -.003)])
        self.assertEqual(select_robust_configuration(primary, secondary, '')['selected_config_id'], 'frequency_bonus_3')

    def test_choose_larger_worst_fold_gain_not_largest_primary_score(self):
        primary = fixture([('high_primary', .4, .05, .01), ('stable', .37, .02, .01)])
        secondary = fixture([('high_primary', .35, .005, .001), ('stable', .36, .015, .004)])
        self.assertEqual(select_robust_configuration(primary, secondary, '')['selected_config_id'], 'stable')


if __name__ == '__main__':
    began = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SearchProtocolTests))
    report = {'status': 'passed' if result.wasSuccessful() else 'failed', 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors), 'runtime_seconds': time.perf_counter()-began,
              'command': '.venv/bin/python scripts/test_search_protocol.py'}
    (Path(__file__).resolve().parents[1] / 'reports' / 'search_unit_tests.json').write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
