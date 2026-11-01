# Deliverable 6 Engine Gaps: Solution & Architectural Rationale

**Issue Title:** Gaps between the engine and the Deliverable 6 analytical note
**Branch:** `deliverable6-engine-gaps`
**Date:** 2026-11-01
**Author / Lead:** Team (AI-assisted, Claude Code)

This work has no file in `docs/team_related/issues/`, so this file uses the topic-name convention from `.agents/rules/solution_documentation.md`.

---

## 1. Architectural Pattern & Design Rationale

- **Pattern Applied:** No new pattern. Each fix stays inside a pattern we already use: the *Strategy Pattern* (`AssignmentStrategy`) for solving, and the *Component Contract / DTO* (`RunComparison`) for passing results to the UI.
- **Why Chosen:** The note must describe what the code does. Most gaps were small differences between the two, so the right fix is the smallest change in the layer that owns the logic.
- **Component Scope:**
  - `app/engine/`: metrics, recommendations, strategies, solvers. Still no Flask, request, session or Jinja2 imports.
  - `app/visualization/`: one card on `/compare`, one sentence on the recommendations page, and one warning after Lock & Rerun. Component A only reads what the contract gives it.
  - `app/contract/`, `app/domain/` and `app/persistence/` are not changed. `docs/team_related/onboarding_for_students.md` says to leave them alone unless an issue says otherwise, and no issue covers this work.

---

## 2. High-Level Logic & Data Flow Walkthrough

### Fix 1: Worst-rank delta

$$\Delta r_{\max} = r_{\max, B} - r_{\max, A}$$

`compare_two_solutions` reads `worst_rank` from the fairness indicators of both solutions and adds the difference to `delta_metrics` as `worst_rank_delta`. It also writes a sentence for the Trade-off Findings list.

We add no new field to `RunComparison`. Its `to_dict` and `from_dict` already pass `delta_metrics` through unchanged. `compare.html` reads the value with `comparison.delta_metrics.get('worst_rank_delta', 0)`, the same way it reads `gini_delta`, so `routes.py` needs no change for this.

We use the indicator, not the per-student comparison, so the number matches the run page. An unranked student therefore counts as one rank below the worst stated preference in the cohort.

Flow: indicators → `compare_two_solutions` → `delta_metrics` → `RunComparison` → `/compare`.

### Fix 2: Recommendation tie-break

Priority 2 now compares three measures in order, and each one only matters if the one before it is a tie:

1. Mean skill fit (higher is better).
2. Unmet soft requirements (lower is better).
3. Mean rank (lower is better).

`criteria_used` now names the real sort keys in the real order for all three priorities. Priority 1 lists the unranked count first. Priority 3 lists mean rank instead of the "Harmonized score", which no code ever calculated.

**Demo result:** Alt 2 and Alt 3 both have 100.0% skill fit and 0 unmet soft requirements. Alt 3 has mean rank 1.10 against 1.20, so Priority 2 now picks Alt 3.

**Known limit:** `mean_rank` only covers students with a ranked project. A solution that puts many students on unranked projects can look better on this tie-break. Priority 1 looks at the unranked count first, but Priority 2 does not.

### Fix 3: Solver stop reasons

The rule is that a status may only claim what was proved.

| HiGHS stop | Allocation stored? | `solver_status` | Run status |
| :--- | :--- | :--- | :--- |
| `optimal` | yes | `OPTIMAL` | `COMPLETED` |
| `infeasible`, `infeasibleOrUnbounded` | no | `INFEASIBLE` | `INFEASIBLE` |
| any other stop | yes | `FEASIBLE` | `COMPLETED`, with a warning |
| `maxTimeLimit` | no | `TIME_LIMIT` | `FAILED` |
| any other stop, or an exception | no | `NOT_SOLVED` | `FAILED` |

Three details matter here:

- **The time limit never reached HiGHS.** `_build_base_model` set `model.solver.config.time_limit`, but Pyomo's legacy `solve()` overwrites that value with its own `timelimit` argument, which defaults to `None`. With the config set to 0, the solver still ran to `optimal`. So there was no time limit at all, and the old code could never have hit it. The limit is now passed in the `solve()` call, and the line with no effect is gone.
- **`feasible` never appears on its own.** Pyomo's mapping for HiGHS has no `feasible` stop. A time-limit stop that holds an allocation arrives as `maxTimeLimit` with a stored solution. `_classify_solver_stop` therefore looks for a stored solution, not for the word `feasible`.
- **`infeasibleOrUnbounded` means infeasible here.** All variables are binary, so the objective is bounded, and "unbounded" cannot be the cause.

In `execute_run`:

- `FEASIBLE` solutions are kept. The run reports `solver_status` `Feasible`, and the message on the run page names the alternatives that are not proven optimal. Each solution also stores a warning.
- If no solution exists and the solver did not prove infeasibility, the run is `FAILED`. The reasons say that nothing was proved. `run_detail.html` already shows the message, the reasons and any other status.
- If some solutions exist but the search for more stopped on `TIME_LIMIT` or `NOT_SOLVED`, the run gets a warning that more alternatives may exist. If it stopped on `INFEASIBLE`, the no-good cuts proved the list is complete, so there is no warning.

Two changes in Component A follow from this:

- Lock & Rerun warns when a run is `FAILED`, so it does not look like a plain success.
- The recommendations page no longer says a solution is "the mathematically optimal selection". It said this for every recommendation, which was too strong even for a proven solution, because a recommendation only picks the best of the alternatives in one run. It now says exactly that.

### Fix 4: Edge case 13

The old test stops in the validator, because it has too few students for the minimum. Two new tests reach HiGHS:

- Two projects with minimum 1 both need the only student with a mandatory skill.
- A student is fixed to a project without having its mandatory skill.

A helper asserts that validation passes, and that the run reports `termination_condition` `infeasible`. Only a real solve sets this key, so the test cannot pass through the validator. The old test stays as it was.

---

## 3. Summary of Files Changed

| File Path | Modification Description |
| :--- | :--- |
| `app/engine/metrics.py` | Adds `worst_rank_delta` to `delta_metrics` and writes a trade-off sentence. |
| `app/visualization/templates/compare.html` | Adds the ΔWorst Rank card, read from `delta_metrics`. |
| `app/engine/recommendations.py` | Adds the mean-rank tie-break and corrects `criteria_used`. |
| `app/engine/strategies.py` | Adds `_classify_solver_stop`, passes the time limit to `solve()`, and removes the setting that had no effect. |
| `app/engine/solvers.py` | Adds `USABLE_SOLVER_STATUSES`, and handles `FEASIBLE`, `TIME_LIMIT` and `NOT_SOLVED` in `execute_run`. |
| `app/visualization/routes.py` | Warns after Lock & Rerun when a run is `FAILED`. |
| `app/visualization/templates/recommendations.html` | Replaces the "mathematically optimal" claim with what a recommendation really is. |
| `tests/test_recommendations.py` | New file for the recommendation rules. |
| `tests/test_metrics.py`, `test_solvers.py`, `test_edge_cases.py`, `test_visualization_component.py` | New tests for each fix. No existing assertion changed. |

---

## 4. Verification & QA Status

- There are no `xfail` markers to remove for this work.
- Verification command: `python -m pytest -q`, run with the project's `.venv`.
- Result: `137 passed` (105 before, 32 new), zero regressions.
- Run against the unchanged code on `main`, 26 of the 32 new tests fail. The other 6 guard behaviour that must stay the same, such as a normal run still reporting `Optimal`.
- `test_time_limit_reaches_highs` and `test_run_stopped_by_time_limit_is_failed_not_infeasible` use the real solver with a limit of 0 seconds. They passed 15 times out of 15.

Checks on real data, outside the test suite:

| Check | Result |
| :--- | :--- |
| Demo run, Alt 1 → Alt 2 | $\Delta \bar{\sigma} = +0.0167$, $\Delta \bar{r} = +0.20$, $\Delta r_{\max} = +1$, $\Delta G = +0.1333$, same as Section 4.1 of the note |
| Demo run, recommendations | Priority 1 Alt 1, Priority 2 Alt 3, Priority 3 Alt 1 |
| 400 × 30 with 6 no-good cuts, limit 0 s and 0.02 s | `TIME_LIMIT`, no allocation |
| Same, limit 0.05 s | `FEASIBLE`, 400 assigned, objective -4081 against the optimum 3191, and `compute_solution_indicators` confirms it is feasible |
| Same, limit 0.1 s and more | `OPTIMAL`, objective 3191 |
| `/compare` rendered through Flask | Card shows `+1`, in red |

The 400 × 30 cohort uses `random.Random(3)`. Each of the 400 students ranks 8 of the 30 projects, and each project has 5 to 20 seats. All rows use `PREFERENCE`, and the 6 cuts are its first six solutions. The exact objectives may differ on other computers, because a time limit depends on speed.

The test for a time-limit stop with a stored allocation forces the stop reason on a real solve, because the real timing window is too narrow for a stable test. The 0.05-second row above is the same case on real HiGHS, checked by hand.

The `/compare` page was checked through its rendered HTML and tests. It was not viewed in a browser.

---

## 5. Check Your Understanding (Pedagogical Checkpoint)

1. *Why does the worst-rank delta use the indicators and not the rank of each student?* So the number matches what the run page shows, including how unranked students count.
2. *Why is the delta inside `delta_metrics` and not a new field on `RunComparison`?* `RunComparison` is in `app/domain/`, which we do not change without an issue. `delta_metrics` already passes through unchanged, and `gini_delta` already works this way.
3. *Why is mean rank the last key in Priority 2 and not the first?* Priority 2 is about skills. Mean rank may only decide between solutions that are equal on skills.
4. *Why is a run that hits the time limit `FAILED` and not `INFEASIBLE`?* Infeasible is a proof that no allocation exists. A time limit proves nothing.
5. *Why did setting `solver.config.time_limit` do nothing?* The legacy `solve()` replaces the config value with its own `timelimit` argument, which is `None` by default.
6. *Why can a solution be `FEASIBLE` and still be used?* It meets all hard constraints. We only cannot say that nothing better exists, and the run page tells the coordinator so.
7. *How do the new edge case 13 tests prove that HiGHS gave the answer?* They assert that validation passes, and that the run has a `termination_condition` of `infeasible`, which only a real solve sets.

> **Pedagogical Checkpoint:** *"If you cannot explain every line, ask me to teach you before accepting or committing."*
