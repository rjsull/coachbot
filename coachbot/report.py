"""Human-readable rendering of review output. No decisions live here."""

from __future__ import annotations

DECISION_TITLES = {
    "baseline": "BASELINE",
    "on_pace": "HOLD - ON PACE",
    "on_target": "HOLD - ON TARGET",
    "adherence_hold": "HOLD - ADHERENCE",
    "awaiting_confirmation": "HOLD - AWAITING CONFIRMATION",
    "recovery_guardrail": "EAT MORE - GUARDRAIL",
    "stall_step_one": "STALL - STEP 1: PORTION RECHECK",
    "stall_step_two": "STALL - STEP 2: DINNER CARBS",
    "off_pace": "HOLD - OFF PACE",
    "adjustment_proposed": "PROPOSED CALORIE CHANGE",
    "calorie_bound_review": "MANUAL REVIEW - CALORIE BOUND",
    "professional_review": "STOP - PROFESSIONAL REVIEW",
    "monitor_only": "MONITOR ONLY",
}

ADHERENCE_LABELS = {
    "nutrition_on_plan": "nutrition on plan",
    "training_met": "training target met",
    "calories_within_tolerance": "calories in tolerance",
    "protein_met": "protein target met",
    "steps_met": "steps target met",
    "adherent": "adherent",
}


def _check(value):
    return "yes" if value else "no"


def _weight_line(weight, unit):
    base = f"{weight['average']} {unit} weekly average"
    if weight["change"] is None:
        return base + " (baseline week)"
    return base + f" ({weight['change']:+.2f} {unit} / {weight['change_pct']:+.2f}% vs prior week)"


def render_review(result):
    metrics = result["metrics"]
    weight = metrics["weight"]
    unit = result.get("weight_unit", "lb")
    lines = [
        f"CoachBot - {result.get('plan_name', 'Plan')} (plan v{result.get('plan_version', '?')})",
        f"Week ending {result['week_ending']}",
        "",
        f"Weight       {_weight_line(weight, unit)}",
    ]
    if "weekly_calorie_target" in metrics:
        lines.append(
            f"Calories     {metrics['weekly_calorie_target']} kcal/day weekly average target"
        )
    if "slow_or_flat_streak" in metrics:
        lines.append(f"Slow/flat    {metrics['slow_or_flat_streak']} consecutive weeks")
    if metrics.get("body_composition"):
        body = metrics["body_composition"]
        line = f"Waist/neck   {body['waist_inches']}\" / {body['neck_inches']}\""
        if body.get("navy_body_fat_pct") is not None:
            line += f" - Navy BF ~{body['navy_body_fat_pct']}%"
        if body.get("waist_change") is not None:
            line += f" (waist {body['waist_change']:+.2f}\")"
        lines.append(line)
    if "zone_streak" in metrics:
        lines.append(f"Zone streak  {metrics['zone_streak']} week(s)")

    adherence = metrics.get("adherence") or {}
    checks = [
        f"{ADHERENCE_LABELS.get(key, key)}: {_check(value)}"
        for key, value in adherence.items()
        if key != "adherent"
    ]
    if checks:
        lines.append("Adherence    " + "; ".join(checks))

    decision = result["decision"]
    lines += [
        "",
        "DECISION: " + DECISION_TITLES.get(decision["code"], decision["code"].upper()),
        "  " + decision["summary"],
    ]
    if decision.get("proposed_calories") is not None:
        lines.append(f"  Proposed: {decision['proposed_calories']} kcal/day")
    if decision.get("proposed_daily_calories"):
        proposed = decision["proposed_daily_calories"]
        detail = ", ".join(
            f"{day} {bounds[0]}-{bounds[1]}" for day, bounds in proposed.items()
        )
        lines.append(f"  Proposed: +{decision['calorie_increase_range'][0]}-"
                     f"{decision['calorie_increase_range'][1]} kcal/day ({detail})")
    if decision.get("changed_signals"):
        lines.append("  Signals: " + ", ".join(decision["changed_signals"]))
    if decision.get("dinner_carb_reduction"):
        lines.append(f"  Dinner carbs: down {decision['dinner_carb_reduction']}")
    if decision.get("medical_flags"):
        lines.append("  Medical flags: " + ", ".join(decision["medical_flags"]))
    if decision.get("source"):
        lines.append(f"  Source: {decision['source']}")

    training = result.get("training")
    if training:
        lines += ["", f"Training: {training['block']}"]
        lines.append(f"  Progression: {training['progression']}")
        for directive in training.get("directives", []):
            lines.append(f"  - {directive}")
        for reason in training.get("stop_reasons", []):
            lines.append(f"  Stop reason: {reason}")
    return "\n".join(lines)
