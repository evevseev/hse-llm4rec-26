# Generated with an AI assistant
"""Dense, hand-computed checks for repeat-aware regression and personalization."""
import json
import time
import unittest
from pathlib import Path

import numpy as np
from scipy import sparse
from threadpoolctl import threadpool_limits

from collaborative_models import personalized_pagerank
from repeat_aware_models import fit_log_count_als, log_count_objective, log_count_update


class RepeatAwareTests(unittest.TestCase):
    def setUp(self):
        self.other = np.array([[1., 0.], [0., 1.], [1., 1.]])
        self.counts = sparse.csr_matrix([[1., 0., 5.], [0., 0., 0.]])

    def check_update(self, alpha):
        target = np.log1p([1., 0., 5.])
        confidence = np.diag(1+alpha*target)
        expected = np.linalg.solve(self.other.T @ confidence @ self.other+.1*np.eye(2),
                                   self.other.T @ confidence @ target)
        actual = log_count_update(self.counts, self.other, alpha=alpha)
        np.testing.assert_allclose(actual[0], expected, atol=1e-12)
        np.testing.assert_array_equal(actual[1], [0., 0.])

    def test_weighted_log_targets_match_dense_regression(self):
        self.check_update(20.)

    def test_uniform_confidence_keeps_nonzero_log_targets(self):
        self.check_update(0.)

    def check_objective(self, alpha):
        users = np.array([[.5, 1.], [0., .25]])
        targets = np.log1p(self.counts.toarray())
        confidence = 1+alpha*targets
        expected = np.sum(confidence*(targets-users @ self.other.T)**2)+.1*(np.sum(users**2)+np.sum(self.other**2))
        self.assertAlmostEqual(log_count_objective(self.counts, users, self.other, alpha=alpha), expected, places=11)

    def test_weighted_loss_includes_missing_pairs(self):
        self.check_objective(20.)

    def test_uniform_loss_matches_dense_log_count_matrix(self):
        self.check_objective(0.)

    def test_loss_decreases_for_both_confidence_choices(self):
        for alpha in [0., 20.]:
            with self.subTest(alpha=alpha):
                users, items, history = fit_log_count_als(self.counts, alpha=alpha, factors=2, iterations=3)
                losses = [r['training_objective'] for r in history]
                self.assertTrue(all(b <= a+1e-8 for a, b in zip(losses, losses[1:])))
                np.testing.assert_array_equal(users[1], [0., 0.])
                again, _, _ = fit_log_count_als(self.counts, alpha=alpha, factors=2, iterations=3)
                np.testing.assert_array_equal(users, again)

    def test_invalid_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            fit_log_count_als(self.counts, alpha=-1)
        with self.assertRaises(ValueError):
            fit_log_count_als(sparse.csr_matrix([[-1., 2.]]))

    def test_raw_frequency_ppr_matches_analytic_personalization(self):
        transition = sparse.csr_matrix([[0., 1.], [1., 0.]])
        scores, _ = personalized_pagerank(np.array([[9., 1.]]), transition, np.array([False, False]),
                                          tolerance=1e-12, max_iterations=250)
        expected_first = (.9+.85*.1)/1.85
        self.assertAlmostEqual(scores[0, 0], expected_first, places=11)
        scaled, _ = personalized_pagerank(np.array([[90., 10.]]), transition, np.array([False, False]),
                                          tolerance=1e-12, max_iterations=250)
        np.testing.assert_allclose(scores, scaled, atol=1e-12)


if __name__ == '__main__':
    began = time.perf_counter()
    with threadpool_limits(limits=1):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RepeatAwareTests))
    report = {'status': 'passed' if result.wasSuccessful() else 'failed', 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'runtime_seconds': time.perf_counter()-began,
              'command': '.venv/bin/python scripts/test_repeat_aware_models.py'}
    (Path(__file__).resolve().parents[1] / 'reports' / 'repeat_aware_unit_tests.json').write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
