import math


def weight_metrics(weights, previous_weights=None):
    average = sum(weights) / len(weights)
    result = {
        "average": round(average, 2),
        "previous_average": None,
        "change": None,
        "change_pct": None,
    }
    if previous_weights is not None:
        previous_average = sum(previous_weights) / len(previous_weights)
        result["previous_average"] = round(previous_average, 2)
        result["change"] = round(average - previous_average, 2)
        result["change_pct"] = round(
            (average - previous_average) / previous_average * 100, 6
        )
    return result


def navy_body_fat(waist_inches, neck_inches, height_inches):
    """US Navy circumference estimate for men. Returns None on impossible input."""
    if waist_inches <= neck_inches or height_inches <= 0:
        return None
    estimate = (
        86.010 * math.log10(waist_inches - neck_inches)
        - 70.041 * math.log10(height_inches)
        + 36.76
    )
    return round(estimate, 1)


def body_composition(current, previous, height_inches):
    waist = current.get("waist_inches")
    neck = current.get("neck_inches")
    if waist is None or neck is None:
        return None
    result = {"waist_inches": waist, "neck_inches": neck}
    if height_inches:
        estimate = navy_body_fat(waist, neck, height_inches)
        if estimate is not None:
            result["navy_body_fat_pct"] = estimate
    previous_waist = (previous or {}).get("waist_inches")
    if previous_waist is not None:
        result["waist_change"] = round(waist - previous_waist, 2)
    return result
