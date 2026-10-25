# Generated with an AI assistant
"""Checks that ranking features cannot read future views or training-only labels."""
import json
import time
import unittest
from pathlib import Path

import numpy as np

from ltr_features import FEATURES, OUTER_CUTOFF, WINDOWS, Snapshot, epoch, target_counts


class RankingFeatureTests(unittest.TestCase):
    def setUp(self):
        self.cutoff = epoch('2020-04-06 00:00:00')
        self.finish = epoch('2020-04-20 00:00:00')
        self.events = [('u', 11, 1, epoch('2020-03-20 10:00:00'), epoch('2020-03-20 11:00:00'), 3600),
                       ('u', 11, 1, epoch('2020-04-01 10:00:00'), epoch('2020-04-01 11:00:00'), 3600),
                       ('u', 12, 2, epoch('2020-03-25 10:00:00'), epoch('2020-03-25 11:00:00'), 3600)]
        self.schedule = [(11, 1, self.cutoff+86400, self.cutoff+90000),
                         (12, 2, self.cutoff+2*86400, self.cutoff+2*86400+3600),
                         (13, 3, self.cutoff+3*86400, self.cutoff+3*86400+3600)]

    def test_appending_future_views_does_not_change_features(self):
        original = Snapshot(self.events, self.schedule, ['u'], self.cutoff, self.finish)
        poisoned = self.events+[('u', 13, 3, self.cutoff+86400, self.cutoff+90000, 3600)]*100
        changed = Snapshot(poisoned, self.schedule, ['u'], self.cutoff, self.finish)
        a, x, _ = original.candidates_and_features('u')
        b, y, _ = changed.candidates_and_features('u')
        np.testing.assert_array_equal(a, b)
        np.testing.assert_array_equal(x, y)

    def test_personal_counts_and_unknown_item_flags(self):
        snap = Snapshot(self.events, self.schedule, ['u', 'cold'], self.cutoff, self.finish)
        positions, features, _ = snap.candidates_and_features('u')
        rows = {int(snap.items[j]): features[k] for k, j in enumerate(positions)}
        self.assertEqual(rows[11][FEATURES.index('personal_count')], 2)
        self.assertEqual(rows[13][FEATURES.index('personal_item_known')], 0)
        self.assertEqual(rows[13][FEATURES.index('global_item_known')], 0)
        self.assertGreater(rows[11][FEATURES.index('schedule_channel_affinity')], 0)
        self.assertEqual(rows[13][FEATURES.index('schedule_channel_affinity')], 0)
        self.assertEqual(snap.user_total[snap.user_index['cold']], 0)

    def test_supervised_targets_exclude_boundary_crossing_airings(self):
        events = [('u', 11, 1, self.cutoff-100, self.cutoff+100, 200),
                  ('u', 12, 1, self.cutoff, self.cutoff+100, 100),
                  ('u', 13, 1, self.finish-100, self.finish+100, 200)]
        self.assertEqual(target_counts(events, self.cutoff, self.finish), {'u': [12]})

    def test_schedule_rates_are_normalized_by_target_weeks(self):
        snap = Snapshot(self.events, self.schedule, ['u'], self.cutoff, self.finish)
        j = snap.item_index[11]
        self.assertEqual(snap.airings_weekly[j], .5)

    def test_positive_injection_is_optional_and_not_a_feature(self):
        many = [(i, 1, self.cutoff+86400, self.cutoff+90000) for i in range(1000, 1121)]
        snap = Snapshot(self.events, many, ['u'], self.cutoff, self.finish)
        natural, x, added = snap.candidates_and_features('u')
        injected, y, added_positive = snap.candidates_and_features('u', [1120])
        self.assertEqual(len(natural), 100)
        self.assertEqual(added, 0)
        self.assertEqual(added_positive, 1)
        self.assertEqual(len(injected), 101)
        np.testing.assert_array_equal(x, y[:100])
        self.assertNotIn('label', FEATURES)

    def test_all_training_label_windows_end_before_outer_validation(self):
        for _, cutoff, finish in WINDOWS:
            self.assertLess(cutoff, finish)
            self.assertLessEqual(finish, OUTER_CUTOFF)


if __name__ == '__main__':
    began = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RankingFeatureTests))
    record = {'status': 'passed' if result.wasSuccessful() else 'failed', 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors), 'runtime_seconds': time.perf_counter()-began}
    (Path(__file__).resolve().parents[1] / 'reports' / 'ltr_feature_tests.json').write_text(json.dumps(record, indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
