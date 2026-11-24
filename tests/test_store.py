import json
import tempfile
import unittest
from pathlib import Path

from coachbot.store import CoachStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "coach.db"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_active_plan_survives_reopening_store(self):
        plan = {"name": "Persisted plan", "targets": {"calories": 2500}}
        store = CoachStore(self.db_path)
        version = store.save_plan(plan)
        store.close()

        reopened = CoachStore(self.db_path)
        self.assertEqual(version, 1)
        self.assertEqual(
            reopened.active_plan(), {"version": 1, "data": plan}
        )
        reopened.close()

    def test_checkin_history_is_durable_and_chronological(self):
        later = {"week_ending": "2026-11-15", "weights": [201]}
        earlier = {"week_ending": "2026-11-08", "weights": [200]}
        store = CoachStore(self.db_path)
        store.add_checkin(later)
        store.add_checkin(earlier)
        store.close()

        reopened = CoachStore(self.db_path)
        self.assertEqual(reopened.history(), [earlier, later])
        reopened.close()

    def test_duplicate_week_is_rejected_instead_of_silently_overwritten(self):
        original = {"week_ending": "2026-11-08", "weights": [200]}
        changed = {"week_ending": "2026-11-08", "weights": [999]}
        store = CoachStore(self.db_path)
        store.add_checkin(original)

        with self.assertRaisesRegex(ValueError, "2026-11-08"):
            store.add_checkin(changed)

        self.assertEqual(store.history(), [original])
        store.close()


if __name__ == "__main__":
    unittest.main()
