import math
from datetime import date

MASTER_PLAN_SCHEMA = "coachbot/master-plan-v1"
MASTER_CHECKIN_SCHEMA = "coachbot/master-checkin-v1"
STATUSES = {"on", "drift", "off", "na"}


def _require_fields(data, fields, label):
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    missing = [field for field in fields if field not in data]
    if missing:
        raise ValueError(f"{label} missing required fields: {', '.join(missing)}")
    return data


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _require_number(data, field, minimum=0, strictly_positive=False):
    value = data[field]
    if not _is_number(value) or value < minimum or (strictly_positive and value <= 0):
        qualifier = "positive" if strictly_positive else f">= {minimum}"
        raise ValueError(f"{field} must be a {qualifier} number")


def _require_choice(data, field, choices):
    value = data[field]
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"{field} must be one of: {', '.join(sorted(choices))}")


def _require_bool(data, field):
    if not isinstance(data[field], bool):
        raise ValueError(f"{field} must be true or false")


def _optional_positive(data, field):
    value = data.get(field)
    if value is None:
        return
    if not _is_number(value) or value <= 0:
        raise ValueError(f"{field} must be a positive number or null")


def _require_text(data, field):
    if not isinstance(data[field], str) or not data[field].strip():
        raise ValueError(f"{field} must be a non-empty string")


def validate_checkin(checkin):
    _require_fields(checkin, ["week_ending", "weights", "medical_flags", "notes"], "check-in")
    try:
        parsed_date = date.fromisoformat(checkin["week_ending"])
    except (TypeError, ValueError) as error:
        raise ValueError("week_ending must be an ISO date (YYYY-MM-DD)") from error
    if parsed_date.isoformat() != checkin["week_ending"]:
        raise ValueError("week_ending must be an ISO date (YYYY-MM-DD)")
    if (
        not isinstance(checkin["weights"], list)
        or not checkin["weights"]
        or any(not _is_number(weight) or weight <= 0 for weight in checkin["weights"])
    ):
        raise ValueError("weights must contain at least one positive numeric weigh-in")
    if not isinstance(checkin["medical_flags"], list) or any(
        not isinstance(flag, str) or not flag.strip() for flag in checkin["medical_flags"]
    ):
        raise ValueError("medical_flags must be a list of non-empty strings")
    if not isinstance(checkin["notes"], str):
        raise ValueError("notes must be a string")

    if checkin.get("schema") == MASTER_CHECKIN_SCHEMA:
        _require_fields(
            checkin,
            [
                "nutrition_adherence",
                "training_sessions",
                "biofeedback",
                "rounds_over_15_min",
                "joint_ache",
                "elbow_grumble",
                "portion_recheck_complete",
            ],
            "master check-in",
        )
        _require_choice(checkin, "nutrition_adherence", {"on", "drift", "off"})
        _require_number(checkin, "training_sessions")
        biofeedback = _require_fields(
            checkin["biofeedback"],
            ["hoops_energy", "sleep_quality", "swing_tgu_quality"],
            "biofeedback",
        )
        for signal in biofeedback:
            _require_choice(biofeedback, signal, STATUSES)
        for field in (
            "rounds_over_15_min",
            "joint_ache",
            "elbow_grumble",
            "portion_recheck_complete",
        ):
            _require_bool(checkin, field)
        for field in ("waist_inches", "neck_inches"):
            _optional_positive(checkin, field)
    else:
        _require_fields(
            checkin,
            [
                "calories_avg",
                "protein_avg",
                "steps_avg",
                "training_sessions",
                "sleep_hours_avg",
                "energy",
                "hunger",
                "stress",
                "overeating_episodes",
            ],
            "check-in",
        )
        for field in (
            "calories_avg",
            "protein_avg",
            "steps_avg",
            "training_sessions",
            "sleep_hours_avg",
            "overeating_episodes",
        ):
            _require_number(checkin, field)
        for field in ("energy", "hunger", "stress"):
            if not _is_number(checkin[field]) or not 1 <= checkin[field] <= 5:
                raise ValueError(f"{field} must be between 1 and 5")
    return checkin


def _validate_master_plan(plan):
    _require_fields(
        plan,
        [
            "name",
            "weight_unit",
            "targets",
            "target_weekly_loss_lb",
            "guardrails",
            "progression",
            "stall",
        ],
        "master plan",
    )
    _optional_positive(plan, "height_in")
    targets = _require_fields(
        plan["targets"],
        [
            "calories_by_day",
            "training_days_per_week",
            "off_days_per_week",
            "protein_g",
            "training_sessions",
        ],
        "targets",
    )
    calories_by_day = _require_fields(
        targets["calories_by_day"], ["training", "off"], "calories_by_day"
    )
    for field in ("training", "off"):
        _require_number(calories_by_day, field, strictly_positive=True)
    for field in ("training_days_per_week", "off_days_per_week", "training_sessions"):
        _require_number(targets, field, strictly_positive=True)
        if not isinstance(targets[field], int):
            raise ValueError(f"{field} must be a whole number")
    _require_number(targets, "protein_g", strictly_positive=True)
    if targets["training_days_per_week"] + targets["off_days_per_week"] != 7:
        raise ValueError("training_days_per_week and off_days_per_week must total 7")

    loss = _require_fields(plan["target_weekly_loss_lb"], ["min", "max"], "target_weekly_loss_lb")
    _require_number(loss, "min", strictly_positive=True)
    _require_number(loss, "max", strictly_positive=True)
    if loss["min"] > loss["max"]:
        raise ValueError("target weekly loss min must not exceed max")

    guardrails = _require_fields(
        plan["guardrails"], ["signals", "calorie_increase", "source"], "guardrails"
    )
    if not isinstance(guardrails["signals"], list) or not guardrails["signals"] or any(
        not isinstance(signal, str) or not signal.strip()
        for signal in guardrails["signals"]
    ):
        raise ValueError("guardrails.signals must be a non-empty list of names")
    increase = guardrails["calorie_increase"]
    if (
        not isinstance(increase, list)
        or len(increase) != 2
        or any(not _is_number(value) or value <= 0 for value in increase)
        or increase[0] > increase[1]
    ):
        raise ValueError("guardrail calorie_increase must be an ascending [min, max] pair")

    progression = _require_fields(plan["progression"], ["current_block", "source"], "progression")
    _require_text(progression, "current_block")
    stall = _require_fields(plan["stall"], ["weeks", "source"], "stall")
    _require_number(stall, "weeks", minimum=1)
    if not isinstance(stall["weeks"], int):
        raise ValueError("stall.weeks must be a whole number")


def _validate_general_plan(plan):
    _require_fields(
        plan, ["name", "weight_unit", "targets", "trend", "adherence", "adjustment"], "plan"
    )
    targets = _require_fields(
        plan["targets"], ["calories", "protein_g", "steps", "training_sessions"], "targets"
    )
    for field in ("calories", "protein_g", "steps", "training_sessions"):
        _require_number(targets, field, strictly_positive=True)

    trend = _require_fields(plan["trend"], ["min_change_pct", "max_change_pct"], "trend")
    for field in ("min_change_pct", "max_change_pct"):
        if not _is_number(trend[field]):
            raise ValueError(f"trend.{field} must be a number")
    if trend["min_change_pct"] > trend["max_change_pct"]:
        raise ValueError("trend min_change_pct must not exceed max_change_pct")

    adherence = _require_fields(
        plan["adherence"],
        ["calorie_tolerance_pct", "protein_min_pct", "steps_min_pct", "training_min_pct"],
        "adherence",
    )
    for field in adherence:
        _require_number(adherence, field, minimum=0)

    adjustment = _require_fields(
        plan["adjustment"],
        [
            "enabled",
            "source",
            "confirmation_weeks",
            "below_target_calorie_delta",
            "above_target_calorie_delta",
            "min_calories",
            "max_calories",
        ],
        "adjustment",
    )
    _require_bool(adjustment, "enabled")
    _require_text(adjustment, "source")
    _require_number(adjustment, "confirmation_weeks", minimum=1)
    if not isinstance(adjustment["confirmation_weeks"], int):
        raise ValueError("adjustment.confirmation_weeks must be a whole number")
    for field in ("below_target_calorie_delta", "above_target_calorie_delta"):
        if not _is_number(adjustment[field]):
            raise ValueError(f"adjustment.{field} must be a number")
    for field in ("min_calories", "max_calories"):
        _require_number(adjustment, field, strictly_positive=True)
    if adjustment["min_calories"] > adjustment["max_calories"]:
        raise ValueError("adjustment.min_calories must not exceed max_calories")


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    if plan.get("schema") == MASTER_PLAN_SCHEMA:
        _validate_master_plan(plan)
    else:
        _validate_general_plan(plan)
    return plan
