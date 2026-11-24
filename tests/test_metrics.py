import unittest

from coachbot.metrics import body_composition, navy_body_fat, weight_metrics


class WeightMetricsTests(unittest.TestCase):
    def test_uses_weekly_means_for_absolute_and_percentage_change(self):
        result = weight_metrics([175, 177, 173], [165, 165, 165])

        self.assertEqual(result["average"], 175.0)
        self.assertEqual(result["previous_average"], 165.0)
        self.assertEqual(result["change"], 10.0)
        self.assertAlmostEqual(result["change_pct"], 6.06061, places=5)

    def test_navy_estimate_lands_in_a_plausible_band(self):
        estimate = navy_body_fat(32.0, 15.0, 70)

        self.assertIsNotNone(estimate)
        self.assertTrue(9.0 <= estimate <= 20.0)
        self.assertAlmostEqual(estimate, round(navy_body_fat(32.0, 15.0, 70), 1), places=1)

    def test_navy_estimate_rejects_impossible_circumferences(self):
        self.assertIsNone(navy_body_fat(15.0, 15.5, 70))

    def test_body_composition_tracks_waist_change_and_skips_missing_data(self):
        self.assertIsNone(body_composition({"weights": [165]}, None, 70))

        result = body_composition(
            {"waist_inches": 32.0, "neck_inches": 15.0},
            {"waist_inches": 32.5},
            70,
        )

        self.assertEqual(result["waist_inches"], 32.0)
        self.assertEqual(result["waist_change"], -0.5)
        self.assertIn("navy_body_fat_pct", result)


if __name__ == "__main__":
    unittest.main()
