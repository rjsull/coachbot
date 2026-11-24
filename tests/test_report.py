import unittest
from pathlib import Path

from coachbot.engine import review
from coachbot.report import render_review
from tests.test_master_plan import master_checkin, master_plan


class ReportTests(unittest.TestCase):
    def test_text_report_names_the_decision_and_omits_json_braces(self):
        result = review(master_plan(), [master_checkin()])
        result["plan_name"] = "Example Training + Nutrition Plan"
        result["plan_version"] = 1
        result["weight_unit"] = "lb"

        text = render_review(result)

        self.assertIn("DECISION: BASELINE", text)
        self.assertIn("165.0 lb weekly average", text)
        self.assertIn("2685.714 kcal/day", text)
        self.assertNotIn('"decision"', text)

    def test_guardrail_report_shows_the_adjustment_range_and_training_stop(self):
        first = master_checkin()
        latest = master_checkin("2026-11-15", [164.6])
        latest["biofeedback"]["sleep_quality"] = "drift"
        result = review(master_plan(), [first, latest])
        result["weight_unit"] = "lb"

        text = render_review(result)

        self.assertIn("EAT MORE - GUARDRAIL", text)
        self.assertIn("sleep_quality", text)
        self.assertIn("+100-150 kcal/day", text)
        self.assertIn("repeat_last_week", text)
        self.assertIn("Repeat last week", text)

    def test_report_shows_waist_and_navy_estimate_when_measured(self):
        checkin = master_checkin()
        checkin["waist_inches"] = 32.0
        checkin["neck_inches"] = 15.0
        plan = master_plan()
        plan["height_in"] = 72
        result = review(plan, [checkin])
        result["weight_unit"] = "lb"

        text = render_review(result)

        self.assertIn('Waist/neck   32.0" / 15.0"', text)
        self.assertIn("Navy BF ~12.5%", text)


if __name__ == "__main__":
    unittest.main()
