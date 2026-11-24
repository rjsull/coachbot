import unittest

from coachbot.engine import review


def sample_plan():
    return {
        "name": "Synthetic maintenance plan",
        "weight_unit": "lb",
        "targets": {
            "calories": 2500,
            "protein_g": 180,
            "steps": 9000,
            "training_sessions": 4,
        },
        "trend": {"min_change_pct": -0.2, "max_change_pct": 0.2},
        "adherence": {
            "calorie_tolerance_pct": 5,
            "protein_min_pct": 90,
            "steps_min_pct": 90,
            "training_min_pct": 75,
        },
        "adjustment": {
            "enabled": True,
            "source": "Synthetic plan for tests",
            "confirmation_weeks": 2,
            "below_target_calorie_delta": 100,
            "above_target_calorie_delta": -100,
            "min_calories": 1800,
            "max_calories": 3000,
        },
    }


def sample_checkin(week_ending="2026-11-08", weights=None):
    return {
        "week_ending": week_ending,
        "weights": weights or [200] * 7,
        "calories_avg": 2500,
        "protein_avg": 180,
        "steps_avg": 9000,
        "training_sessions": 4,
        "sleep_hours_avg": 7.5,
        "energy": 4,
        "hunger": 3,
        "stress": 3,
        "overeating_episodes": 0,
        "medical_flags": [],
        "notes": "Synthetic test data",
    }


class EngineTests(unittest.TestCase):
    def test_first_checkin_establishes_baseline_without_adjustment(self):
        result = review(sample_plan(), [sample_checkin()])

        self.assertEqual(result["decision"]["code"], "baseline")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual(result["decision"]["calories_delta"], 0)
        self.assertEqual(result["metrics"]["weight"]["average"], 200.0)

    def test_one_out_of_band_week_waits_for_confirmation(self):
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [199] * 7),
        ]

        result = review(sample_plan(), history)

        self.assertEqual(result["metrics"]["weight"]["zone"], "below_target")
        self.assertEqual(result["decision"]["code"], "awaiting_confirmation")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual(result["decision"]["calories_delta"], 0)

    def test_consecutive_adherent_out_of_band_weeks_propose_configured_change(self):
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [199] * 7),
            sample_checkin("2026-11-22", [198] * 7),
        ]

        result = review(sample_plan(), history)

        self.assertEqual(result["metrics"]["zone_streak"], 2)
        self.assertEqual(result["decision"]["code"], "adjustment_proposed")
        self.assertEqual(result["decision"]["action"], "propose_calorie_change")
        self.assertEqual(result["decision"]["calories_delta"], 100)
        self.assertEqual(result["decision"]["proposed_calories"], 2600)
        self.assertEqual(result["decision"]["source"], "Synthetic plan for tests")

    def test_poor_adherence_blocks_otherwise_confirmed_adjustment(self):
        latest = sample_checkin("2026-11-22", [198] * 7)
        latest["calories_avg"] = 2000
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [199] * 7),
            latest,
        ]

        result = review(sample_plan(), history)

        self.assertFalse(result["metrics"]["adherence"]["calories_within_tolerance"])
        self.assertFalse(result["metrics"]["adherence"]["adherent"])
        self.assertEqual(result["decision"]["code"], "adherence_hold")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual(result["decision"]["calories_delta"], 0)

    def test_confirmation_streak_requires_adherence_in_each_week(self):
        second = sample_checkin("2026-11-15", [199] * 7)
        second["training_sessions"] = 1
        history = [
            sample_checkin(),
            second,
            sample_checkin("2026-11-22", [198] * 7),
        ]

        result = review(sample_plan(), history)

        self.assertEqual(result["metrics"]["adherent_zone_streak"], 1)
        self.assertEqual(result["decision"]["code"], "awaiting_confirmation")
        self.assertEqual(result["decision"]["calories_delta"], 0)

    def test_medical_flags_override_otherwise_confirmed_adjustment(self):
        latest = sample_checkin("2026-11-22", [198] * 7)
        latest["medical_flags"] = ["dizziness"]
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [199] * 7),
            latest,
        ]

        result = review(sample_plan(), history)

        self.assertEqual(result["decision"]["code"], "professional_review")
        self.assertEqual(result["decision"]["action"], "professional_review")
        self.assertEqual(result["decision"]["calories_delta"], 0)
        self.assertEqual(result["decision"]["medical_flags"], ["dizziness"])

    def test_adjustment_that_crosses_calorie_bound_requires_manual_review(self):
        plan = sample_plan()
        plan["targets"]["calories"] = 1800
        plan["adjustment"]["below_target_calorie_delta"] = -100
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [199] * 7),
            sample_checkin("2026-11-22", [198] * 7),
        ]
        for checkin in history:
            checkin["calories_avg"] = 1800

        result = review(plan, history)

        self.assertEqual(result["decision"]["code"], "calorie_bound_review")
        self.assertEqual(result["decision"]["action"], "manual_review")
        self.assertNotIn("proposed_calories", result["decision"])

    def test_on_target_adherent_trend_holds_plan(self):
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [200] * 7),
        ]

        result = review(sample_plan(), history)

        self.assertEqual(result["metrics"]["weight"]["zone"], "within_target")
        self.assertEqual(result["decision"]["code"], "on_target")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual(result["decision"]["calories_delta"], 0)

    def test_above_target_trend_uses_its_own_configured_adjustment(self):
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [201] * 7),
            sample_checkin("2026-11-22", [202] * 7),
        ]

        result = review(sample_plan(), history)

        self.assertEqual(result["metrics"]["weight"]["zone"], "above_target")
        self.assertEqual(result["decision"]["code"], "adjustment_proposed")
        self.assertEqual(result["decision"]["calories_delta"], -100)
        self.assertEqual(result["decision"]["proposed_calories"], 2400)

    def test_monitor_only_plan_never_proposes_an_adjustment(self):
        plan = sample_plan()
        plan["adjustment"]["enabled"] = False
        history = [
            sample_checkin(),
            sample_checkin("2026-11-15", [199] * 7),
            sample_checkin("2026-11-22", [198] * 7),
        ]

        result = review(plan, history)

        self.assertEqual(result["decision"]["code"], "monitor_only")
        self.assertEqual(result["decision"]["action"], "hold")
        self.assertEqual(result["decision"]["calories_delta"], 0)
        self.assertNotIn("proposed_calories", result["decision"])


if __name__ == "__main__":
    unittest.main()
