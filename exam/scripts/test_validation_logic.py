# Generated with an AI assistant
"""Small, hand-computed checks for the temporal join and MAP semantics."""
import json
import time
import unittest
from pathlib import Path

import numpy as np

from compare_methods import average_precision_at_5, rank_scores
from prepare_validation import covered_seconds, timestamp


class ValidationLogicTests(unittest.TestCase):
    def test_fragment_union_removes_duplicates_and_overlaps(self):
        self.assertEqual(covered_seconds([(0, 40), (0, 40), (30, 60), (70, 90)]), 80)

    def test_fragments_can_qualify_an_airing_together(self):
        intervals = [(0, 35), (40, 85)]
        self.assertLess(max(b-a for a, b in intervals), 80)
        self.assertEqual(covered_seconds(intervals), 80)

    def test_daylight_saving_elapsed_time(self):
        self.assertEqual(timestamp('2020-03-30 09:02:48')-timestamp('2020-03-28 22:47:45'), 119703)

    def test_airing_duration_is_elapsed_seconds(self):
        start = timestamp('2020-03-29 02:30:00')
        self.assertEqual(start+3600, timestamp('2020-03-29 04:30:00'))

    def test_map_rewards_early_hits(self):
        relevant = {1, 2, 3, 4, 5}
        self.assertAlmostEqual(average_precision_at_5([1, 9, 8, 7, 6], relevant), .2)
        self.assertAlmostEqual(average_precision_at_5([9, 8, 7, 6, 1], relevant), .04)

    def test_map_short_target_and_duplicates(self):
        self.assertAlmostEqual(average_precision_at_5([1, 1, 9, 8, 2], {1, 2}), .7)
        self.assertEqual(average_precision_at_5([1, 2, 3, 4, 5], {1, 2}), 1.0)

    def test_empty_targets_are_not_silently_scored(self):
        with self.assertRaises(ValueError):
            average_precision_at_5([1, 2, 3, 4, 5], set())

    def test_ranking_and_fallback_do_not_duplicate_ids(self):
        result, fill = rank_scores(np.array([0., 2., 2., 0., 0., 0.]),
                                  np.array([10, 20, 30, 40, 50, 60]),
                                  np.array([9, 3, 7, 5, 4, 0]),
                                  [10, 30, 40, 50, 20, 60])
        self.assertEqual(result, [30, 20, 10, 40, 50])
        self.assertEqual(fill, 3)


if __name__ == '__main__':
    began = time.perf_counter()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ValidationLogicTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'status': 'passed' if result.wasSuccessful() else 'failed',
              'tests_run': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'runtime_seconds': time.perf_counter()-began,
              'command': '.venv/bin/python scripts/test_validation_logic.py'}
    path = Path(__file__).resolve().parents[1] / 'reports' / 'validation_unit_tests.json'
    path.write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
