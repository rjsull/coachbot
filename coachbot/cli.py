import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

from .engine import review
from .evaluate import run_evaluation
from .report import render_review
from .store import CoachStore
from .validation import validate_checkin, validate_plan

DEFAULT_DB = "~/.local/share/coachbot/coach.db"


def _load_json(path):
    with Path(path).expanduser().open(encoding="utf-8") as handle:
        return json.load(handle)


def _current_review(store):
    active = store.active_plan()
    if active is None:
        raise ValueError("no active plan; run 'plan set' first")
    history = store.history()
    if not history:
        raise ValueError("no check-ins; run 'checkin add' first")
    result = review(active["data"], history)
    result["plan_version"] = active["version"]
    result["plan_name"] = active["data"]["name"]
    result["weight_unit"] = active["data"].get("weight_unit", "lb")
    return result


def _last_sunday(today=None):
    today = today or date.today()
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _week_ending(value):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "must be an ISO date (YYYY-MM-DD)"
        ) from error
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("must be an ISO date (YYYY-MM-DD)")
    return value


def _checkin_template(plan, week_ending):
    if plan.get("schema") == "coachbot/master-plan-v1":
        return {
            "schema": "coachbot/master-checkin-v1",
            "week_ending": week_ending,
            "weights": [],
            "nutrition_adherence": "on",
            "training_sessions": 0,
            "biofeedback": {
                "hoops_energy": "na",
                "sleep_quality": "on",
                "swing_tgu_quality": "on",
            },
            "rounds_over_15_min": False,
            "joint_ache": False,
            "elbow_grumble": False,
            "portion_recheck_complete": False,
            "waist_inches": None,
            "neck_inches": None,
            "medical_flags": [],
            "notes": "",
        }
    return {
        "week_ending": week_ending,
        "weights": [],
        "calories_avg": 0,
        "protein_avg": 0,
        "steps_avg": 0,
        "training_sessions": 0,
        "sleep_hours_avg": 0,
        "energy": 3,
        "hunger": 3,
        "stress": 3,
        "overeating_episodes": 0,
        "medical_flags": [],
        "notes": "",
    }


def build_parser():
    parser = argparse.ArgumentParser(prog="coachbot")
    parser.add_argument("--db", default=os.environ.get("COACHBOT_DB", DEFAULT_DB))
    parser.add_argument("--format", choices=("json", "text"), default="json")
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan")
    plan_commands = plan.add_subparsers(dest="plan_command", required=True)
    plan_set = plan_commands.add_parser("set")
    plan_set.add_argument("path")
    plan_commands.add_parser("show")

    checkin = commands.add_parser("checkin")
    checkin_commands = checkin.add_subparsers(dest="checkin_command", required=True)
    checkin_add = checkin_commands.add_parser("add")
    checkin_add.add_argument("path")
    checkin_template = checkin_commands.add_parser("template")
    checkin_template.add_argument(
        "--week-ending",
        type=_week_ending,
        help="ISO date for the week's Sunday; defaults to the most recent Sunday",
    )
    checkin_template.add_argument(
        "--out", help="write the template here instead of printing it"
    )

    commands.add_parser("review")
    commands.add_parser("history")
    evaluation = commands.add_parser("eval", help="run a regression case file")
    evaluation.add_argument("path")
    return parser


def main(argv=None):
    os.umask(0o077)
    parser = build_parser()
    arguments = parser.parse_args(argv)

    if arguments.command == "eval":
        report = run_evaluation(arguments.path)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["failed"] == 0 else 1

    store = CoachStore(arguments.db)
    try:
        if arguments.command == "plan" and arguments.plan_command == "set":
            plan = validate_plan(_load_json(arguments.path))
            version = store.save_plan(plan)
            output = {"version": version, "name": plan["name"]}
        elif arguments.command == "plan":
            output = store.active_plan()
            if output is None:
                raise ValueError("no active plan")
        elif arguments.command == "checkin" and arguments.checkin_command == "template":
            active = store.active_plan()
            if active is None:
                raise ValueError("no active plan; run 'plan set' first")
            week_ending = arguments.week_ending or _last_sunday().isoformat()
            output = _checkin_template(active["data"], week_ending)
            if arguments.out:
                destination = Path(arguments.out).expanduser()
                destination.write_text(
                    json.dumps(output, indent=2) + "\n", encoding="utf-8"
                )
                os.chmod(destination, 0o600)
                output = {"written": str(destination), "week_ending": week_ending}
        elif arguments.command == "checkin":
            active = store.active_plan()
            if active is None:
                raise ValueError("no active plan; run 'plan set' first")
            checkin = validate_checkin(_load_json(arguments.path))
            master_plan = active["data"].get("schema") == "coachbot/master-plan-v1"
            master_checkin = checkin.get("schema") == "coachbot/master-checkin-v1"
            if master_plan != master_checkin:
                raise ValueError("check-in schema does not match the active plan")
            store.add_checkin(checkin)
            output = _current_review(store)
        elif arguments.command == "review":
            output = _current_review(store)
        else:
            output = {"checkins": store.history()}

        if arguments.format == "text" and isinstance(output, dict) and "decision" in output:
            print(render_review(output))
        else:
            print(json.dumps(output, indent=2, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"error: {error}\n")
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
