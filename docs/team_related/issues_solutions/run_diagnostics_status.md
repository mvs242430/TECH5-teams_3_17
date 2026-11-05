# Run Diagnostics: Duplicate Messages and the INVALID_INPUT Status — Solution & Architectural Rationale

**Issue Title:** Every diagnostic message showed twice, and broken input that was also infeasible was labelled INFEASIBLE
**Branch:** `fix-run-diagnostics-status`
**Date:** 2026-11-05
**Author / Lead:** Team (AI-assisted, Claude Code)

This work has no file in `docs/team_related/issues/`, so this file uses the topic-name convention from `.agents/rules/solution_documentation.md`. It touches the status rules from [B3.1](../issues/B3.1.md), the diagnostics from [B3.3](../issues/B3.3.md) and the Solutions page from [A2.2.1](../issues/A2.2.1.md).

---

## 1. Architectural Pattern & Design Rationale

### Problem 1: each message appeared twice

- **What the user saw:** On `/solutions`, the "Run Diagnostics & Solver Notes" box listed "Insufficient overall capacity: total cohort size (10) exceeds aggregate maximum project capacity (6)." twice. The same happened for "Fixed assignments (4) for project 'P1' exceed its maximum capacity (3)."
- **Cause:** `validate_cohort` in `app/domain/validation.py` adds every infeasibility message to **both** `result.errors` and `result.infeasibility_reasons`. The engine saves both lists in the run (`diagnostics["reasons"]` and `diagnostics["errors"]`), and `solutions.html` printed one list and then the other.
- **Pattern applied:** Presentation logic in the **View** of our MVC split (Jinja2 template). The page shows `reasons` first, then only those `errors` that are not already in `reasons`. It uses Jinja's built-in `reject('in', ...)` filter.
- **Why the view and not the engine or the validator:**
  - `app/domain/validation.py` is a protected teacher file, and storing a proof as both an error and a reason is its documented contract (`ValidationOutcome.errors` = "fatal errors that reject input", `infeasibility_reasons` = "proof details").
  - Keeping the engine's stored data complete means other readers (tests, the Compare page, future exports) still see both lists.
  - The fix also cleans up runs **already saved** in the database, with no rerun or migration needed.

### Problem 2: when to say INVALID_INPUT and when to say INFEASIBLE

The contract (`app/contract/contract.py`, `ValidationOutcome`) separates two kinds of failure:

| Status | Meaning | Examples from `validation.py` |
| :--- | :--- | :--- |
| `INVALID_INPUT` | The data itself is broken (structure or referential integrity). | Unknown student or project in a lock, a student locked to two projects, duplicate IDs, min capacity above max, empty cohort |
| `INFEASIBLE` | The data is well formed, but the hard constraints cannot all hold. | More students than seats, more locks on a project than it has seats, a mandatory skill nobody has |

- **Cases that stay INFEASIBLE:** "10 students, 6 seats" and "4 locks on a 3-seat project" are infeasible, not invalid input. Every ID is valid. The rules just cannot all be met at once. The teacher's test `test_infeasible_cohort_integration` expects the capacity-deficit scenario to be `INFEASIBLE`, and B3.1's *Done when* says the same.
- **The bug:** `execute_run` checked `is_feasible` before `is_valid`. Input that was broken **and** infeasible, for example a lock on unknown student `S9` plus too few seats, was labelled `INFEASIBLE`. The broken data was then listed under an infeasibility headline, and the coordinator could not tell that the data had to be fixed first.
- **Pattern applied:** Guard-clause ordering in Component B (`app/engine/solvers.py`). Because the validator copies every reason into `errors`, `is_valid` is `False` even for a purely infeasible cohort. So the engine works out the **structural errors** as the errors that are *not* infeasibility reasons:

  ```python
  structural_errors = [
      err
      for err in val_outcome.errors
      if err not in val_outcome.infeasibility_reasons
  ]
  ```

  Case A (`INFEASIBLE`) now runs only when `not is_feasible and not structural_errors`. Any structural error falls through to Case B (`INVALID_INPUT`), which lists every error, including the infeasibility ones.
- **Why this order:** A capacity or skill proof means little when the data has errors of its own. Fix the data first, then check whether the rules can be met.

### Component scope

- `app/visualization/`: `templates/solutions.html` only.
- `app/engine/`: `solvers.py`, one condition and the `structural_errors` list in `execute_run`. No Flask or Jinja2 imports were added.
- `tests/`: new tests only, with zero existing tests changed.
- `app/contract/`, `app/domain/`, `app/persistence/` and `app/contract/mocks.py` are **not** changed.

---

## 2. High-Level Logic & Data Flow Walkthrough

1. **Request:** `POST /runs/trigger` builds a `RunRequest` and calls `AssignmentEngine.execute_run` through the contract.
2. **Validation:** `validate_inputs` calls `validation.validate_cohort` and returns a `ValidationOutcome` with `is_valid`, `is_feasible`, `errors` and `infeasibility_reasons`.
3. **Classification (changed):**
   - `structural_errors` = errors that are not reasons.
   - Infeasible and no structural errors → `INFEASIBLE`, with message "Run proved mathematically infeasible before solver execution." and `reasons` set to the infeasibility proofs.
   - Otherwise, any error → `INVALID_INPUT`, with message "Input cohort failed pre-solver validation checks." and `reasons` set to all errors.
   - Otherwise → the solver runs as before.
4. **Persistence:** `run_repo.save_run(run)` stores `diagnostics` as JSON, unchanged.
5. **View (changed):** `solutions.html` sets `diag_reasons` and `extra_errors = errors | reject('in', diag_reasons)`, then prints each list. Every message appears once. The Student Viewer still sees only the "Detailed diagnostics are hidden" line.

---

## 3. Summary of Files Changed

| File Path | Modification Description |
| :--- | :--- |
| `app/visualization/templates/solutions.html` | Shows `reasons`, then only the `errors` not already listed, so each diagnostic appears once (old saved runs included). |
| `app/engine/solvers.py` | `execute_run` computes `structural_errors`. A run is `INFEASIBLE` only when the input has no structural errors. Broken input is `INVALID_INPUT` even when it is also infeasible. |
| `tests/test_edge_cases.py` | New: `test_broken_and_infeasible_input_reports_invalid_input` and `test_fixed_locks_over_capacity_run_stays_infeasible`. |
| `tests/test_component_integration.py` | New: `test_infeasible_run_lists_each_diagnostic_once` (capacity-deficit message appears exactly once on the page). |
| `docs/team_related/issues_solutions/run_diagnostics_status.md` | This document. |

---

## 4. Verification & QA Status

- Verification command: `.venv/bin/python -m pytest -q`
- Output on this branch: `279 passed in 11.23s` (276 on `main` + 3 new, zero regressions).
- The new tests were checked against the old code: with the fix reverted, `test_broken_and_infeasible_input_reports_invalid_input` and `test_infeasible_run_lists_each_diagnostic_once` **fail**, and they pass with it. `test_fixed_locks_over_capacity_run_stays_infeasible` passes both ways on purpose: it guards that the over-capacity lock case stays `INFEASIBLE`.
- Checked in the running app on a saved run (`af11ba01`, 4 locks on a 3-seat project): the message now appears once, and the badge still says INFEASIBLE.

**Notes left as they are:**
- `templates/run_detail.html` has the same double-printing code, but no route renders it since A2.2.1 (`/runs/<id>` now renders `solutions.html`), so it was not changed.
- In Case A, the fallback `if not reasons and val_outcome.errors: reasons = list(val_outcome.errors)` can no longer be reached (any error that is not a reason now goes to Case B). It was kept to keep the change small.

---

## 5. Check Your Understanding (Pedagogical Checkpoint)

1. *Why is "10 students, 6 seats" INFEASIBLE and not INVALID_INPUT?* Every student and project is well formed. The data is correct, but the capacity constraint cannot be met. INVALID_INPUT is for data that is broken in itself.
2. *Why can't the engine simply check `is_valid` first?* The validator puts every infeasibility reason into `errors` too, so `is_valid` is `False` for a purely infeasible cohort. Checking it first would relabel the capacity-deficit scenario as INVALID_INPUT and break the teacher's integration test.
3. *Why fix the duplicates in the template rather than in the engine?* The validator's two lists are part of its contract, and the template fix also repairs runs already stored in the database.
4. *What does `reject('in', diag_reasons)` do?* It keeps only the items of `errors` for which `item in diag_reasons` is false.
5. *How does this respect the component boundaries?* The engine change uses only the `ValidationOutcome` DTO, with no Flask or Jinja2. The view only reads `run.diagnostics`. The protected `app/domain/` and `app/contract/` folders are untouched.

> **Pedagogical Checkpoint:** *"If you cannot explain every line, ask me to teach you before accepting or committing."*
