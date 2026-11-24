from .metrics import weight_metrics
from .master import review as master_review


def _adherence(plan, checkin):
    targets = plan["targets"]
    limits = plan["adherence"]
    checks = {
        "calories_within_tolerance": abs(checkin["calories_avg"] - targets["calories"])
        <= targets["calories"] * limits["calorie_tolerance_pct"] / 100,
        "protein_met": checkin["protein_avg"]
        >= targets["protein_g"] * limits["protein_min_pct"] / 100,
        "steps_met": checkin["steps_avg"]
        >= targets["steps"] * limits["steps_min_pct"] / 100,
        "training_met": checkin["training_sessions"]
        >= targets["training_sessions"] * limits["training_min_pct"] / 100,
    }
    checks["adherent"] = all(checks.values())
    return checks


def review(plan, history):
    if plan.get("schema") == "coachbot/master-plan-v1":
        return master_review(plan, history)

    current = history[-1]
    previous_weights = history[-2]["weights"] if len(history) > 1 else None
    weight = weight_metrics(current["weights"], previous_weights)
    adherence = _adherence(plan, current)
    zone_streak = 0
    adherent_zone_streak = 0
    decision = {
        "code": "baseline",
        "action": "hold",
        "calories_delta": 0,
        "summary": "Baseline recorded; no trend adjustment yet.",
    }

    if previous_weights is not None:
        zones = []
        for index in range(1, len(history)):
            weekly_weight = weight_metrics(
                history[index]["weights"], history[index - 1]["weights"]
            )
            change_pct = weekly_weight["change_pct"]
            if change_pct < plan["trend"]["min_change_pct"]:
                zones.append("below_target")
            elif change_pct > plan["trend"]["max_change_pct"]:
                zones.append("above_target")
            else:
                zones.append("within_target")

        zone = zones[-1]
        weight["zone"] = zone
        zone_streak = 0
        for past_zone in reversed(zones):
            if past_zone != zone:
                break
            zone_streak += 1

        adherent_zone_streak = 0
        past_adherence = [_adherence(plan, entry) for entry in history[1:]]
        for past_zone, checks in reversed(list(zip(zones, past_adherence))):
            if past_zone != zone or not checks["adherent"]:
                break
            adherent_zone_streak += 1

        decision = {
            "code": "on_target",
            "action": "hold",
            "calories_delta": 0,
            "summary": "Trend is within the configured target band; keep the plan unchanged.",
        }
        if not adherence["adherent"]:
            decision = {
                "code": "adherence_hold",
                "action": "hold",
                "calories_delta": 0,
                "summary": "Targets were not met closely enough to interpret the trend; do not adjust calories yet.",
            }
        elif zone in {"below_target", "above_target"}:
            decision = {
                "code": "awaiting_confirmation",
                "action": "hold",
                "calories_delta": 0,
                "summary": "Trend is outside target; wait for the configured adherent confirmation period.",
            }
            if adherent_zone_streak >= plan["adjustment"]["confirmation_weeks"]:
                delta = plan["adjustment"][f"{zone}_calorie_delta"]
                proposed = plan["targets"]["calories"] + delta
                if not plan["adjustment"]["enabled"]:
                    decision = {
                        "code": "monitor_only",
                        "action": "hold",
                        "calories_delta": 0,
                        "summary": "A trend met the confirmation rule, but automatic adjustment proposals are disabled.",
                    }
                elif (
                    plan["adjustment"]["min_calories"]
                    <= proposed
                    <= plan["adjustment"]["max_calories"]
                ):
                    decision = {
                        "code": "adjustment_proposed",
                        "action": "propose_calorie_change",
                        "calories_delta": delta,
                        "proposed_calories": proposed,
                        "source": plan["adjustment"]["source"],
                        "summary": f"Confirmed {zone.replace('_', '-')} trend; apply the plan's configured calorie adjustment.",
                    }
                else:
                    decision = {
                        "code": "calorie_bound_review",
                        "action": "manual_review",
                        "calories_delta": 0,
                        "summary": "The configured adjustment crosses a calorie bound; manual review is required.",
                    }

    if current["medical_flags"]:
        decision = {
            "code": "professional_review",
            "action": "professional_review",
            "calories_delta": 0,
            "medical_flags": current["medical_flags"],
            "summary": "Medical flags were reported; automated adjustment is paused for professional review.",
        }

    return {
        "week_ending": current["week_ending"],
        "metrics": {
            "weight": weight,
            "zone_streak": zone_streak,
            "adherent_zone_streak": adherent_zone_streak,
            "adherence": adherence,
        },
        "decision": decision,
    }
