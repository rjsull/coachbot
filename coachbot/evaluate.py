"""Standalone regression runner for plan decision rules.

A case file is JSON:

    {
      "plan": "../plans/example-plan.json",
      "cases": [
        {"name": "baseline", "history": [checkin, ...],
         "expect": {"decision.code": "baseline"}}
      ]
    }

Every history entry and every plan is run through the same validation the CLI
uses, so a regression file cannot smuggle in data the app would reject.
Paths are resolved relative to the case file.
"""

from __future__ import annotations

import json
from pathlib import Path

from .engine import review
from .validation import validate_checkin, validate_plan


def _load(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def _resolve(base, reference):
    candidate = Path(reference).expanduser()
    if candidate.is_absolute():
        return candidate
    return (base / candidate).resolve()


def _get(document, dotted):
    value = document
    for part in dotted.split("."):
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = value[part]
    return value


def run_evaluation(path):
    case_path = Path(path).expanduser().resolve()
    document = _load(case_path)
    if not isinstance(document.get("cases"), list) or not document["cases"]:
        raise ValueError("evaluation file must contain a non-empty 'cases' list")
    default_plan = validate_plan(_load(_resolve(case_path.parent, document["plan"])))

    results = []
    failures = []
    for index, case in enumerate(document["cases"]):
        name = case.get("name") or f"case {index + 1}"
        mismatches = []
        try:
            plan = (
                validate_plan(_load(_resolve(case_path.parent, case["plan"])))
                if case.get("plan")
                else default_plan
            )
            history = [validate_checkin(entry) for entry in case["history"]]
            if not history:
                raise ValueError("history must contain at least one check-in")
            outcome = review(plan, history)
            for dotted, expected in case.get("expect", {}).items():
                try:
                    actual = _get(outcome, dotted)
                except (KeyError, IndexError, ValueError):
                    mismatches.append(
                        {"path": dotted, "expected": expected, "actual": "<missing>"}
                    )
                    continue
                if actual != expected:
                    mismatches.append(
                        {"path": dotted, "expected": expected, "actual": actual}
                    )
        except (KeyError, OSError, TypeError, ValueError) as error:
            mismatches.append(
                {"path": "<case>", "expected": "runs", "actual": f"error: {error}"}
            )

        passed = not mismatches
        results.append({"name": name, "passed": passed, "mismatches": mismatches})
        if not passed:
            failures.append({"name": name, "mismatches": mismatches})

    return {
        "total": len(results),
        "passed": sum(1 for result in results if result["passed"]),
        "failed": len(failures),
        "failures": failures,
        "cases": results,
    }


if __name__ == "__main__":
    import sys

    report = run_evaluation(sys.argv[1])
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report["failed"] == 0 else 1)
