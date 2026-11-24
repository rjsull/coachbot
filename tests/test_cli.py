import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_master_plan import master_checkin


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, database, *arguments):
        result = subprocess.run(
            [sys.executable, "-m", "coachbot", "--db", str(database), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_plan_checkin_and_review_work_across_processes(self):
        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "coach.db"
            checkin_path = Path(tempdir) / "checkin.json"
            checkin_path.write_text(json.dumps(master_checkin()))

            plan_result = self.run_cli(
                database, "plan", "set", "plans/example-plan.json"
            )
            added = self.run_cli(database, "checkin", "add", str(checkin_path))
            reviewed = self.run_cli(database, "review")

        self.assertEqual(plan_result["version"], 1)
        self.assertEqual(added["decision"]["code"], "baseline")
        self.assertEqual(reviewed["plan_version"], 1)
        self.assertEqual(reviewed["plan_name"], "Example Training + Nutrition Plan")
        self.assertEqual(reviewed["metrics"]["weekly_calorie_target"], 2685.714)

    def test_checkin_template_round_trips_through_validation(self):
        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "coach.db"
            template_path = Path(tempdir) / "week.json"
            self.run_cli(database, "plan", "set", "plans/example-plan.json")

            template = self.run_cli(
                database,
                "checkin",
                "template",
                "--week-ending",
                "2026-11-22",
            )
            self.assertEqual(template["schema"], "coachbot/master-checkin-v1")
            self.assertEqual(template["week_ending"], "2026-11-22")
            self.assertEqual(template["weights"], [])

            template["weights"] = [164.6]
            template_path.write_text(json.dumps(template))
            added = self.run_cli(database, "checkin", "add", str(template_path))

        self.assertEqual(added["decision"]["code"], "baseline")
        self.assertEqual(added["weight_unit"], "lb")

    def test_text_format_renders_a_review_without_json(self):
        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "coach.db"
            checkin_path = Path(tempdir) / "checkin.json"
            checkin_path.write_text(json.dumps(master_checkin()))
            self.run_cli(database, "plan", "set", "plans/example-plan.json")
            self.run_cli(database, "checkin", "add", str(checkin_path))

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "coachbot",
                    "--db",
                    str(database),
                    "--format",
                    "text",
                    "review",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DECISION: BASELINE", result.stdout)
        self.assertNotIn('"decision"', result.stdout)


if __name__ == "__main__":
    unittest.main()
