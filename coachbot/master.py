from .metrics import body_composition, weight_metrics


def review(plan, history):
    current = history[-1]
    previous_weights = history[-2]["weights"] if len(history) > 1 else None
    targets = plan["targets"]
    weekly_calories = (
        targets["calories_by_day"]["training"] * targets["training_days_per_week"]
        + targets["calories_by_day"]["off"] * targets["off_days_per_week"]
    ) / 7
    adherence = {
        "nutrition_on_plan": current["nutrition_adherence"] == "on",
        "training_met": current["training_sessions"] >= targets["training_sessions"],
    }
    adherence["adherent"] = all(adherence.values())
    decision = {
        "code": "baseline",
        "action": "hold",
        "calories_delta": 0,
        "summary": "Baseline recorded; no trend decision yet.",
    }

    ranks = {"on": 0, "drift": 1, "off": 2}
    previous_biofeedback = history[-2]["biofeedback"] if len(history) > 1 else {}
    changed_signals = []
    for signal in plan["guardrails"]["signals"]:
        current_status = current["biofeedback"][signal]
        previous_status = previous_biofeedback.get(signal, "on")
        if current_status == "na" or previous_status == "na":
            continue
        if ranks[current_status] > ranks[previous_status]:
            changed_signals.append(signal)

    slow_changes = []
    for index in range(1, len(history)):
        change = weight_metrics(
            history[index]["weights"], history[index - 1]["weights"]
        )["change"]
        slow_changes.append(change > -plan["target_weekly_loss_lb"]["min"])
    slow_or_flat_streak = 0
    for is_slow in reversed(slow_changes):
        if not is_slow:
            break
        slow_or_flat_streak += 1

    if changed_signals:
        low, high = plan["guardrails"]["calorie_increase"]
        decision = {
            "code": "recovery_guardrail",
            "action": "propose_calorie_change",
            "calories_delta": None,
            "calorie_increase_range": [low, high],
            "changed_signals": changed_signals,
            "proposed_daily_calories": {
                day: [
                    targets["calories_by_day"][day] + low,
                    targets["calories_by_day"][day] + high,
                ]
                for day in ("training", "off")
            },
            "source": plan["guardrails"]["source"],
            "summary": "A recovery guardrail dropped; consider the plan's 100-150 kcal increase before further restriction.",
        }
    elif (
        previous_weights is not None
        and plan["target_weekly_loss_lb"]["min"]
        <= -weight_metrics(current["weights"], previous_weights)["change"]
        <= plan["target_weekly_loss_lb"]["max"]
    ):
        decision = {
            "code": "on_pace",
            "action": "hold",
            "calories_delta": 0,
            "source": "Example Plan target rate: 0.35-0.4 lb/week",
            "summary": "Weekly-average weight loss is inside the target band; keep the plan unchanged.",
        }
    elif slow_or_flat_streak >= plan["stall"]["weeks"]:
        if current["portion_recheck_complete"]:
            decision = {
                "code": "stall_step_two",
                "action": "propose_dinner_carb_reduction",
                "calories_delta": None,
                "dinner_carb_reduction": "about 1/3",
                "source": plan["stall"]["source"],
                "summary": "Portions were rechecked; the plan's next and final stall step is reducing dinner carbs by about one-third.",
            }
        else:
            decision = {
                "code": "stall_step_one",
                "action": "portion_recheck",
                "calories_delta": 0,
                "source": plan["stall"]["source"],
                "summary": "Three slow/flat weeks: honestly recheck portions, including butter and oil. Do not cut dinner carbs yet.",
            }
    elif previous_weights is not None:
        decision = {
            "code": "off_pace",
            "action": "hold",
            "calories_delta": 0,
            "source": "Example Plan target rate: 0.35-0.4 lb/week",
            "summary": "Weekly-average change is outside the 0.35-0.4 lb/week band; one week is not a trend, so hold and keep logging.",
        }

    stop_reasons = []
    if current["biofeedback"]["sleep_quality"] != "on":
        stop_reasons.append("sleep is not On")
    if current["joint_ache"]:
        stop_reasons.append("joint ache")
    if current["elbow_grumble"]:
        stop_reasons.append("elbow grumble")
    if current["rounds_over_15_min"]:
        stop_reasons.append("push/pull rounds exceeded 15 minutes")
    directives = ["Repeat last week; no bump."] if stop_reasons else []
    if current["elbow_grumble"]:
        directives.append("Rows only this week; skip hangs.")
    if current["rounds_over_15_min"]:
        directives.append("Push/pull exceeded 15 minutes: no progression that block.")
    training = {
        "progression": "repeat_last_week" if stop_reasons else "follow_current_block",
        "block": plan["progression"]["current_block"],
        "directives": directives,
        "stop_reasons": stop_reasons,
        "source": plan["progression"]["source"],
    }

    if current["medical_flags"]:
        decision = {
            "code": "professional_review",
            "action": "professional_review",
            "calories_delta": 0,
            "medical_flags": current["medical_flags"],
            "summary": "Medical flags were reported; automated adjustment is paused for professional review.",
        }

    previous_measurement = next(
        (
            entry
            for entry in reversed(history[:-1])
            if entry.get("waist_inches") is not None
        ),
        None,
    )

    return {
        "week_ending": current["week_ending"],
        "metrics": {
            "weight": weight_metrics(current["weights"], previous_weights),
            "weekly_calorie_target": round(weekly_calories, 3),
            "adherence": adherence,
            "slow_or_flat_streak": slow_or_flat_streak,
            "body_composition": body_composition(
                current,
                previous_measurement,
                plan.get("height_in"),
            ),
        },
        "training": training,
        "decision": decision,
    }
