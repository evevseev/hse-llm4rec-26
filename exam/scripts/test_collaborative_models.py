"""Hand-computed mathematical checks for PPR and implicit ALS."""
import json
import time
import unittest
from pathlib import Path

import numpy as np
from scipy import sparse
from threadpoolctl import threadpool_limits

from collaborative_models import (als_update, build_transition, fit_implicit_als,
                                  implicit_objective, personalized_pagerank)


class CollaborativeModelTests(unittest.TestCase):
    def test_graph_cosine_weights_and_no_self_loops(self):
        counts = sparse.csr_matrix([[1., 2., 0., 0.], [3., 1., 0., 0.], [0., 1., 1., 0.]])
        transition, dangling, graph = build_transition(counts, neighbors=1, min_pair_users=1)
        self.assertAlmostEqual(graph[0, 1], 2/np.sqrt(2*3))
        self.assertEqual(graph.diagonal().sum(), 0)
        self.assertLessEqual(np.diff(graph.indptr).max(), 1)
        self.assertTrue(dangling[3])
        np.testing.assert_allclose(np.asarray(transition.sum(axis=1)).ravel(), [1, 1, 1, 0])

    def test_pair_support_threshold(self):
        counts = sparse.csr_matrix([[1., 1.], [0., 1.]])
        _, dangling, graph = build_transition(counts, min_pair_users=2)
        self.assertEqual(graph.nnz, 0)
        self.assertTrue(dangling.all())

    def test_two_node_ppr_has_known_solution(self):
        transition = sparse.csr_matrix([[0., 1.], [1., 0.]])
        ranks, info = personalized_pagerank(np.array([[1., 0.]]), transition, np.array([False, False]),
                                          tolerance=1e-12, max_iterations=250)
        np.testing.assert_allclose(ranks[0], [1/1.85, .85/1.85], atol=1e-12)
        self.assertTrue(info['converged'])

    def test_dangling_mass_returns_to_personalization_and_cold_stays_zero(self):
        transition = sparse.csr_matrix((2, 2))
        ranks, info = personalized_pagerank(np.array([[3., 1.], [0., 0.]]), transition, np.array([True, True]))
        np.testing.assert_allclose(ranks, [[.75, .25], [0, 0]])
        self.assertTrue(info['converged'])

    def test_als_update_matches_explicit_dense_weighted_regression(self):
        factors = np.array([[1., 0.], [0., 1.], [1., 1.]])
        excess = sparse.csr_matrix([[2., 0., 4.], [0., 0., 0.]])
        actual = als_update(excess, factors, .1)
        confidence = np.diag([3., 1., 5.])
        expected = np.linalg.solve(factors.T @ confidence @ factors+.1*np.eye(2),
                                   factors.T @ confidence @ np.array([1., 0., 1.]))
        np.testing.assert_allclose(actual[0], expected, atol=1e-12)
        np.testing.assert_array_equal(actual[1], [0., 0.])

    def test_sparse_loss_matches_full_dense_implicit_loss(self):
        users = np.array([[1., .5], [0., 1.]])
        items = np.array([[.2, .3], [.4, .5], [.6, .7]])
        excess = sparse.csr_matrix([[2., 0., 4.], [0., 3., 0.]])
        dense = excess.toarray()
        preference = (dense > 0).astype(float)
        expected = np.sum((1+dense)*(preference-users @ items.T)**2)+.1*(np.sum(users**2)+np.sum(items**2))
        self.assertAlmostEqual(implicit_objective(excess, users, items, .1), expected, places=12)

    def test_als_loss_decreases_and_seed_is_reproducible(self):
        counts = sparse.csr_matrix([[4., 0., 1.], [0., 3., 2.], [0., 0., 0.]])
        users, items, history = fit_implicit_als(counts, factors=2, iterations=3)
        again_u, again_i, _ = fit_implicit_als(counts, factors=2, iterations=3)
        np.testing.assert_array_equal(users, again_u)
        np.testing.assert_array_equal(items, again_i)
        np.testing.assert_array_equal(users[2], [0., 0.])
        self.assertLess(history[-1]['training_objective'], history[0]['training_objective'])


if __name__ == '__main__':
    began = time.perf_counter()
    with threadpool_limits(limits=1):
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CollaborativeModelTests))
    report = {'status': 'passed' if result.wasSuccessful() else 'failed', 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors),
              'runtime_seconds': time.perf_counter()-began,
              'command': '.venv/bin/python scripts/test_collaborative_models.py'}
    (Path(__file__).resolve().parents[1] / 'reports' / 'collaborative_unit_tests.json').write_text(json.dumps(report, indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
