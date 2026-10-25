# Generated with an AI assistant
"""Hand-computed checks for the two transparently recorded extensions."""
import json
import time
import unittest
from pathlib import Path

from evaluate_recency import rank_history, recency_weight, smoothed_scores


class FrequencyExtensionTests(unittest.TestCase):
    def test_half_life_weights(self):
        cutoff = 100*86400
        self.assertEqual(recency_weight(cutoff, cutoff), 1)
        self.assertEqual(recency_weight(cutoff-28*86400, cutoff), .5)
        self.assertEqual(recency_weight(cutoff-56*86400, cutoff), .25)

    def test_future_event_is_rejected(self):
        with self.assertRaises(ValueError):
            recency_weight(101, 100)

    def test_invalid_half_life_is_rejected(self):
        with self.assertRaises(ValueError):
            recency_weight(100, 100, 0)

    def test_popularity_pseudo_counts(self):
        score = smoothed_scores({10: 7, 20: 1}, {10: .3, 20: 1.5, 30: 3.0})
        self.assertEqual(score[10], 7.3)
        self.assertEqual(score[20], 2.5)
        self.assertEqual(score[30], 3.0)

    def test_strong_personal_preference_survives(self):
        score = smoothed_scores({10: 4}, {20: 3., 30: 2., 40: 1., 50: .5})
        result, _ = rank_history(score, {10, 20, 30, 40, 50}, {10: 0, 20: 10, 30: 5, 40: 3, 50: 1})
        self.assertEqual(result[0], 10)

    def test_cold_start_returns_popularity(self):
        result, fill = rank_history({}, {10, 20, 30, 40, 50, 60},
                                    {10: 0, 20: 5, 30: 4, 40: 3, 50: 2, 60: 1})
        self.assertEqual(result, [20, 30, 40, 50, 60])
        self.assertEqual(fill, 5)


if __name__ == '__main__':
    began = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FrequencyExtensionTests))
    report = {'status': 'passed' if result.wasSuccessful() else 'failed', 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'runtime_seconds': time.perf_counter()-began,
              'command': '.venv/bin/python scripts/test_frequency_extensions.py'}
    (Path(__file__).resolve().parents[1] / 'reports' / 'frequency_extension_tests.json').write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
