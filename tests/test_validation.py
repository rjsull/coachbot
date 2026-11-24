import copy
import unittest

from coachbot.validation import validate_checkin, validate_plan
from tests.test_engine import sample_checkin, sample_plan
from tests.test_master_plan import master_checkin, master_plan


class ValidationTests(unittest.TestCase):
    def test_valid_checkin_is_returned_unchanged(self):
        checkin = sample_checkin()
        original = copy.deepcopy(checkin)

        self.assertEqual(validate_checkin(checkin), original)
        self.assertEqual(checkin, original)

    def test_checkin_requires_at_least_one_weight(self):
        checkin = sample_checkin()
        checkin["weights"] = []

        with self.assertRaisesRegex(ValueError, "weights"):
            validate_checkin(checkin)

    def test_valid_master_plan_and_checkin_are_accepted(self):
        self.assertEqual(validate_plan(master_plan()), master_plan())
        self.assertEqual(validate_checkin(master_checkin()), master_checkin())

    def test_master_checkin_rejects_unknown_biofeedback_status(self):
        checkin = master_checkin()
        checkin["biofeedback"]["sleep_quality"] = "great"

        with self.assertRaisesRegex(ValueError, "sleep_quality"):
            validate_checkin(checkin)

    def test_master_plan_rejects_non_object_targets(self):
        plan = master_plan()
        plan["targets"] = []

        with self.assertRaisesRegex(ValueError, "targets"):
            validate_plan(plan)

    def test_master_checkin_rejects_non_object_biofeedback(self):
        checkin = master_checkin()
        checkin["biofeedback"] = []

        with self.assertRaisesRegex(ValueError, "biofeedback"):
            validate_checkin(checkin)

    def test_master_checkin_rejects_negative_waist(self):
        checkin = master_checkin()
        checkin["waist_inches"] = -1

        with self.assertRaisesRegex(ValueError, "waist_inches"):
            validate_checkin(checkin)

    def test_general_plan_requires_rules_the_engine_reads(self):
        plan = sample_plan()
        del plan["adjustment"]["confirmation_weeks"]

        with self.assertRaisesRegex(ValueError, "confirmation_weeks"):
            validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
