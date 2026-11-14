"""CP-SAT scheduler (Task 20), standard mode. Same inputs, rules and output as the greedy
scheduler, but solved jointly instead of one cue at a time.

Model (times in integer milliseconds):
- For each cue c, wording v and allowed window part w where the wording fits, a boolean
  x[c,v,w] and an optional interval of length d(c,v) whose start lies in w.
- Each cue is placed at most once: sum over (v, w) of x[c,v,w] <= 1.
- No two chosen intervals overlap (one NoOverlap over all of them). Windows are already
  free of speech, so this is the full standard-mode constraint.
- Objective, in strict order: (1) the total priority of placed cues, (2) the total spoken
  time (longer wordings say more), (3) earlier starts (closer to the visual's appearance).
  The weights make each term dominate everything after it.

Not placing anything is always a solution, so the model cannot be infeasible; a solver that
returns no solution within the time limit is reported as such. Every skipped cue gets a reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ortools.sat.python import cp_model

from seehere.db.enums import DescriptionVariant
from seehere.schedule.greedy import VARIANT_ORDER, CueInput, Placement, Skipped
from seehere.schedule.windows import Window, window_for

_Option = tuple[cp_model.IntVar, CueInput, DescriptionVariant, int, cp_model.IntVar]
PRIORITY_SCALE = 1000  # priority 0.734 -> 734


@dataclass(frozen=True)
class CpSatResult:
    placed: list[Placement]
    skipped: list[Skipped]
    status: str  # "optimal", "feasible" or "no_solution"
    objective: float | None


def _ms_up(t: float) -> int:
    return math.ceil(round(t * 1000, 6))


def _ms_down(t: float) -> int:
    return math.floor(round(t * 1000, 6))


def schedule_cp_sat(
    cues: list[CueInput], windows: list[Window], *, time_limit_s: float = 2.0
) -> CpSatResult:
    model = cp_model.CpModel()
    choices: dict[str, list[_Option]] = {}
    intervals = []
    latest_ms = 1
    for cue in sorted(cues, key=lambda c: str(c.id)):
        opts: list[_Option] = []
        for variant in VARIANT_ORDER:
            need = cue.durations.get(variant)
            if need is None:
                continue
            d = _ms_up(need)
            for k, w in enumerate(window_for(windows, cue.earliest_s, cue.latest_s)):
                lo, hi = _ms_up(w.start_s), _ms_down(w.end_s) - d
                if hi < lo:
                    continue
                tag = f"{cue.id}:{variant}:{k}"
                x = model.new_bool_var(f"x:{tag}")
                start = model.new_int_var(lo, hi, f"s:{tag}")
                intervals.append(model.new_optional_fixed_size_interval_var(start, d, x, tag))
                opts.append((x, cue, variant, d, start))
                latest_ms = max(latest_ms, hi)
        if opts:
            model.add_at_most_one(o[0] for o in opts)
            choices[str(cue.id)] = opts
    model.add_no_overlap(intervals)

    # Lexicographic weights: one priority point outweighs any amount of spoken time, and one
    # millisecond of spoken time outweighs any amount of earliness.
    all_opts = [o for opts in choices.values() for o in opts]
    total_d = sum(o[3] for o in all_opts) + 1
    late_terms = []
    for x, cue, _v, _d, start in all_opts:
        late = model.new_int_var(0, latest_ms, f"late:{cue.id}:{_v}:{start.name}")
        model.add(late == start - _ms_up(cue.earliest_s)).only_enforce_if(x)
        model.add(late == 0).only_enforce_if(x.Not())
        late_terms.append(late)
    late_scale = latest_ms * max(len(all_opts), 1) + 1
    if PRIORITY_SCALE * total_d * late_scale > 2**62:  # very long lectures: drop the tie-break
        late_scale, late_terms = 1, []
    model.maximize(
        sum(
            x * (round(cue.priority * PRIORITY_SCALE) * total_d * late_scale + d * late_scale)
            for x, cue, _v, d, _s in all_opts
        )
        - sum(late_terms)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1  # one worker: the same input always gives the same answer
    solver.parameters.random_seed = 0
    code = solver.solve(model)
    if code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        reason = "the solver found no schedule within its time limit"
        return CpSatResult([], [Skipped(c.id, reason) for c in cues], "no_solution", None)

    placed, chosen = [], set()
    for opts in choices.values():
        for x, cue, variant, d, start in opts:
            if solver.value(x):
                s = solver.value(start)
                placed.append(Placement(cue.id, variant, s / 1000, (s + d) / 1000))
                chosen.add(cue.id)
    skipped = [Skipped(c.id, explain(c, windows)) for c in cues if c.id not in chosen]
    return CpSatResult(
        sorted(placed, key=lambda p: p.start_s),
        sorted(skipped, key=lambda k: str(k.cue_id)),
        "optimal" if code == cp_model.OPTIMAL else "feasible",
        solver.objective_value,
    )


def explain(cue: CueInput, windows: list[Window]) -> str:
    """Why a cue was left out of an optimal schedule."""
    allowed = window_for(windows, cue.earliest_s, cue.latest_s)
    if not allowed:
        return "no pause in speech while it is on screen"
    longest = max(w.length for w in allowed)
    shortest = min(cue.durations.values(), default=math.inf)
    if shortest > longest + 1e-6:
        return f"the longest free pause ({longest:.1f} s) is too short"
    return "its pause went to higher-priority descriptions"
