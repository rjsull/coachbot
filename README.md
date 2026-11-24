# coachbot

A deterministic tracker for a written training and nutrition plan. The engine
does arithmetic and rule matching only: it never invents data, never applies a
change on its own, and every recommendation names the written plan rule it came
from.

No wearables, no step counts, no auto-sync, no model fudging a missing number.
Weekly averages and explicit check-ins only. If a required field is missing, it
asks instead of guessing.

Everything in this repo is an example: `plans/EXAMPLE_PLAN.txt` is an invented
plan, and the regression vectors in `eval/` use synthetic weights. No real
person's health data is here.

## Install

```sh
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
# offline fallback for old pip/setuptools:
# .venv/bin/python setup.py develop
```

The database defaults to `~/.local/share/coachbot/coach.db`, created mode 600.
Override with `--db PATH` or `COACHBOT_DB`. The commands below assume the venv
is active (`source .venv/bin/activate`); otherwise prefix them with `.venv/bin/`.

## Weekly workflow

```sh
# Once: load a plan
coachbot plan set plans/example-plan.json

# Each week: generate a check-in, fill in weights and adherence, add it
coachbot checkin template --out /tmp/week.json
$EDITOR /tmp/week.json
coachbot --format text checkin add /tmp/week.json
```

`checkin add` prints the review immediately, so one command records and
evaluates the week. `coachbot --format text review` reprints the latest decision
(`--format` is a global flag, so it goes before the subcommand).

Inputs the engine expects:

- `weights`: every morning weigh-in you have for the week (one is enough).
- `nutrition_adherence`: `on`, `drift`, or `off`.
- `training_sessions`: sessions completed (example plan target is 5).
- `biofeedback`: `hoops_energy`, `sleep_quality`, `swing_tgu_quality` as
  `on`, `drift`, `off`, or `na` when the movement was not performed.
- `rounds_over_15_min`, `joint_ache`, `elbow_grumble`: stop-rule flags.
- `portion_recheck_complete`: only true after the stall step-one recheck.
- `waist_inches`, `neck_inches`: optional, measured every two weeks as the plan
  says (morning, fasted, three readings averaged). When both are present the
  report shows the US Navy body-fat estimate; `height_in` comes from the plan.

## Decision precedence

1. Medical flags -> `professional_review`; every other recommendation is
   replaced.
2. A guardrail signal that worsened since last week -> `recovery_guardrail`
   (eat 100-150 more) and training repeats last week.
3. Weight loss inside 0.35-0.4 lb/week -> `on_pace`, hold.
4. One week outside the band -> `off_pace`, hold; one week is not a trend.
5. Three slow or flat weeks -> `stall_step_one` (recheck portions); only after
   that is marked complete -> `stall_step_two` (dinner carbs down about 1/3).
6. First check-in -> `baseline`, record only.

Weight is the weekly mean compared against the prior week's mean. Medical flags
are a hard stop for automation, not a diagnosis.

## Commands

```
coachbot plan set PATH          load/version a plan
coachbot plan show              active plan JSON
coachbot checkin template       printable check-in skeleton
coachbot checkin add PATH       validate, store, and review
coachbot review                 latest decision
coachbot history                all check-ins
coachbot eval PATH              regression cases (no database needed)
```

## Demo

```sh
.venv/bin/python examples/demo.py
```

Three throwaway scenarios against the example plan with synthetic weights: on
pace, a sleep guardrail, and a three-week stall. Nothing is written to a
database.

## Tests

```sh
python3 -m unittest discover -s tests -v            # 41 tests
.venv/bin/coachbot eval eval/master-cases.json      # 6/6 cases
```

The engine is the product: `coachbot/engine.py` holds the precedence rules,
`coachbot/metrics.py` the weekly arithmetic, `coachbot/validation.py` the input
contract, and `coachbot/store.py` an append-only SQLite history where duplicate
weeks are rejected rather than overwritten.

## Why it is built this way

A tracker that guesses is worse than no tracker. The design rules follow from
that: a missing weight is never estimated, a duplicate week is rejected instead
of overwritten, every decision carries the plan line it came from, medical flags
outrank every automated recommendation, and no change applies itself. The human
records the week and makes the call.
