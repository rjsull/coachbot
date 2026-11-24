#!/usr/bin/env python3
"""End-to-end demo of the shipped example plan with synthetic weekly check-ins.

Run from the repo root:  python examples/demo.py
Every run uses a throwaway database; no personal data is written.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ON_PACE = [
    ("2026-11-01", [165.2, 165.1, 165.0, 164.9, 165.0, 164.9, 164.9],
     {"waist_inches": 32.0, "neck_inches": 15.0}),
    ("2026-11-08", [164.8, 164.7, 164.6, 164.6, 164.5, 164.6, 164.5], {}),
    ("2026-11-15", [164.3, 164.2, 164.2, 164.3, 164.2, 164.3, 164.2], {}),
    ("2026-11-22", [163.9, 163.8, 163.8, 163.9, 163.8, 163.8, 163.9],
     {"waist_inches": 31.75, "neck_inches": 15.0}),
]

STALL = [
    ("2026-11-01", [165.2, 165.1, 165.0, 164.9, 165.0, 164.9, 164.9], {}),
    ("2026-11-08", [164.9, 164.9, 164.8, 164.8, 164.7, 164.8, 164.7], {}),
    ("2026-11-15", [164.7, 164.7, 164.6, 164.6, 164.5, 164.6, 164.5], {}),
    ("2026-11-22", [164.5, 164.5, 164.4, 164.4, 164.3, 164.4, 164.3], {}),
]


def checkin(week_ending, weights, overrides):
    entry = {
        "schema": "coachbot/master-checkin-v1",
        "week_ending": week_ending,
        "weights": weights,
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
        "notes": "Synthetic demo data",
    }
    entry.update(overrides)
    return entry


def run(database, *arguments):
    result = subprocess.run(
        [sys.executable, "-m", "coachbot", "--db", str(database), *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout)
    return result.stdout


def scenario(title, weeks):
    print("=" * 68)
    print(title)
    print("=" * 68)
    with tempfile.TemporaryDirectory() as tempdir:
        database = Path(tempdir) / "coach.db"
        run(database, "plan", "set", "plans/example-plan.json")
        output = ""
        for week_ending, weights, overrides in weeks:
            path = Path(tempdir) / f"{week_ending}.json"
            path.write_text(json.dumps(checkin(week_ending, weights, overrides)))
            output = run(database, "--format", "text", "checkin", "add", str(path))
    print(output.rstrip())
    print()


def main():
    scenario("Scenario 1: four adherent weeks at 0.35-0.40 lb/week", ON_PACE)
    guardrail = [list(week) for week in ON_PACE]
    guardrail[-1][2] = {
        **guardrail[-1][2],
        "biofeedback": {
            "hoops_energy": "on",
            "sleep_quality": "drift",
            "swing_tgu_quality": "on",
        },
    }
    scenario("Scenario 2: same week, but sleep quality dropped", guardrail)
    scenario("Scenario 3: three slow weeks -> stall step one", STALL)


if __name__ == "__main__":
    main()
