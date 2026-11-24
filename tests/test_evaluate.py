import unittest
from pathlib import Path

from coachbot.evaluate import run_evaluation


ROOT = Path(__file__).resolve().parents[1]


class EvaluationTests(unittest.TestCase):
    def test_master_plan_regression_vectors_all_pass(self):
        report = run_evaluation(ROOT / "eval" / "master-cases.json")

        self.assertEqual(report["total"], 6)
        self.assertEqual(report["passed"], 6)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["failures"], [])


if __name__ == "__main__":
    unittest.main()
