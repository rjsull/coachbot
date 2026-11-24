import unittest

from coachbot.engine import review


def master_plan():
    return {
        "schema": "coachbot/master-plan-v1",
        "name": "Example Training + Nutrition Plan",
        "weight_unit": "lb",
        "targets": {
            "calories_by_day": {"training": 2750, "off": 2600},
            "training_days_per_week": 4,
            "off_days_per_week": 3,
            "protein_g": 180,
            "training_sessions": 5,
        },
        "target_weekly_loss_lb": {"min": 0.35, "max": 0.4},
        "guardrails": {
            "signals": ["hoops_energy", "sleep_quality", "swing_tgu_quality"],
            "calorie_increase": [100, 150],
            "source": "Example Plan: any guardrail drop -> eat 100-150 more",
        },
        "progression": {
            "current_block": "W10-11 Saturday row: test 90 lb for 3x5",
            "source": "Example Plan: Three Stop Rules",
        },
        "stall": {
            "weeks": 3,
            "source": "Example Plan: recheck portions honestly, then reduce dinner carbs about one-third",
        },
    }


def master_checkin(week_ending="2026-11-08", weights=None):
    return {
        "schema": "coachbot/master-checkin-v1",
        "week_ending": week_ending,
        "weights": weights or [165],
        "nutrition_adherence": "on",
        "training_sessions": 5,
        "biofeedback": {
            "hoops_energy": "on",
            "sleep_quality": "on",
            "swing_tgu_quality": "on",
        },
        "rounds_over_15_min": False,
        "joint_ache": False,
        "elbow_grumble": False,
        "portion_recheck_complete": False,
        "medical_flags": [],
        "notes": "Synthetic test data",
    }


class MasterPlanTests(unittest.TestCase):
    def test_baseline_uses_mixed_day_calories_without_wearable_metrics(self):
        result = review(master_plan(), [master_checkin()])

        self.assertEqual(result["decision"]["code"], "baseline")
        self.assertEqual(result["metrics"]["weekly_calorie_target"], 2685.714)
        self.assertTrue(result["metrics"]["adherence"]["nutrition_on_plan"])
        self.assertTrue(result["metrics"]["adherence"]["training_met"])
        self.assertNotIn("steps_met", result["metrics"]["adherence"])
        self.assertEqual(result["training"]["progression"], "follow_current_block")

    def test_sleep_drop_uses_recovery_guardrail_and_stops_progression(self):
        first = master_checkin()
        latest = master_checkin("2026-11-15", [164.6])
        latest["biofeedback"]["sleep_quality"] = "drift"

        result = review(master_plan(), [first, latest])

        self.assertEqual(result["decision"]["code"], "recovery_guardrail")
        self.assertEqual(result["decision"]["calorie_increase_range"], [100, 150])
        self.assertEqual(result["decision"]["changed_signals"], ["sleep_quality"])
        self.assertEqual(
            result["decision"]["proposed_daily_calories"],
            {"training": [2850, 2900], "off": [2700, 2750]},
        )
        self.assertEqual(result["training"]["progression"], "repeat_last_week")
        self.assertIn("no bump", result["training"]["directives"][0])

    def test_three_slow_weeks_start_with_portion_recheck_not_carb_cut(self):
        history = [
            master_checkin(weights=[165]),
            master_checkin("2026-11-15", [164.8]),
            master_checkin("2026-11-22", [164.6]),
            master_checkin("2026-11-29", [164.4]),
        ]

        result = review(master_plan(), history)

        self.assertEqual(result["metrics"]["slow_or_flat_streak"], 3)
        self.assertEqual(result["decision"]["code"], "stall_step_one")
        self.assertEqual(result["decision"]["action"], "portion_recheck")
        self.assertNotIn("dinner_carb_reduction", result["decision"])
        self.assertEqual(result["decision"]["source"], master_plan()["stall"]["source"])

    def test_stall_step_two_requires_completed_portion_recheck(self):
        history = [
            master_checkin(weights=[165]),
            master_checkin("2026-11-15", [164.8]),
            master_checkin("2026-11-22", [164.6]),
            master_checkin("2026-11-29", [164.4]),
        ]
        history[-1]["portion_recheck_complete"] = True

        result = review(master_plan(), history)

        self.assertEqual(result["decision"]["code"], "stall_step_two")
        self.assertEqual(result["decision"]["action"], "propose_dinner_carb_reduction")
        self.assertEqual(result["decision"]["dinner_carb_reduction"], "about 1/3")
        self.assertEqual(result["decision"]["calories_delta"], None)

    def test_master_plan_medical_flags_override_all_recommendations(self):
        latest = master_checkin("2026-11-15", [164.8])
        latest["biofeedback"]["sleep_quality"] = "drift"
        latest["medical_flags"] = ["dizziness"]

        result = review(master_plan(), [master_checkin(), latest])

        self.assertEqual(result["decision"]["code"], "professional_review")
        self.assertEqual(result["decision"]["action"], "professional_review")
        self.assertEqual(result["decision"]["calories_delta"], 0)
        self.assertNotIn("proposed_daily_calories", result["decision"])

    def test_training_stop_fields_and_elbow_rule_are_enforced(self):
        checkin = master_checkin()
        checkin["joint_ache"] = True
        checkin["elbow_grumble"] = True
        checkin["rounds_over_15_min"] = True

        result = review(master_plan(), [checkin])

        self.assertEqual(result["training"]["progression"], "repeat_last_week")
        self.assertEqual(len(result["training"]["stop_reasons"]), 3)
        joined = " ".join(result["training"]["directives"])
        self.assertIn("Rows only", joined)
        self.assertIn("skip hangs", joined)
        self.assertIn("no progression that block", joined)

    def test_weight_loss_inside_target_band_holds_plan(self):
        history = [
            master_checkin(weights=[165]),
            master_checkin("2026-11-15", [164.625]),
        ]

        result = review(master_plan(), history)

        self.assertEqual(result["metrics"]["weight"]["change"], -0.38)
        self.assertEqual(result["decision"]["code"], "on_pace")
        self.assertEqual(result["decision"]["calories_delta"], 0)

    def test_one_off_pace_week_holds_without_calling_it_a_stall(self):
        fast = review(
            master_plan(),
            [master_checkin(weights=[165]), master_checkin("2026-11-15", [164.0])],
        )
        gained = review(
            master_plan(),
            [master_checkin(weights=[165]), master_checkin("2026-11-15", [165.5])],
        )

        for result in (fast, gained):
            self.assertEqual(result["decision"]["code"], "off_pace")
            self.assertEqual(result["decision"]["action"], "hold")
            self.assertEqual(result["decision"]["calories_delta"], 0)
        self.assertEqual(fast["metrics"]["slow_or_flat_streak"], 0)
        self.assertEqual(gained["metrics"]["slow_or_flat_streak"], 1)

    def test_waist_compares_with_most_recent_measurement_not_last_week(self):
        history = [
            master_checkin("2026-11-01", [165]),
            master_checkin("2026-11-08", [164.8]),
            master_checkin("2026-11-15", [164.6]),
            master_checkin("2026-11-22", [164.4]),
        ]
        history[0]["waist_inches"] = 32.0
        history[0]["neck_inches"] = 15.0
        history[-1]["waist_inches"] = 31.75
        history[-1]["neck_inches"] = 15.0
        plan = master_plan()
        plan["height_in"] = 72

        result = review(plan, history)

        body = result["metrics"]["body_composition"]
        self.assertEqual(body["waist_change"], -0.25)
        self.assertAlmostEqual(body["navy_body_fat_pct"], 11.9, places=1)


if __name__ == "__main__":
    unittest.main()
