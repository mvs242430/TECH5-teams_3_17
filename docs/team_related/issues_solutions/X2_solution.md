# X2 Solution — Walk through every scenario with bad data

**Owner:** Julia (A1), with Marie (B3) for the engine-side follow-up  
**Branch:** `x2-bad-data-walkthrough`

## 1. What we did

We loaded every scenario in `app/samples/demo_data.py` and a few extra bad inputs through the Flask test client, started a run each time, and read what the screen said. For each case we asked two questions from the issue: *does the screen say what is wrong?* and *does it say what to change?*

| # | Bad input | Before the fix | After the fix |
|---|---|---|---|
| 1 | `infeasible` scenario (10 students, 6 seats) | Reason shown, **but twice** (once under reasons, once under errors). No hint on what to change. | Reason shown once + "What to change" box with links. |
| 2 | `conflicting` scenario (4 locks on P1, capacity 3) | Same: reason twice, no hint. | Reason once + hint. |
| 3 | Empty database → run | `INVALID INPUT`, "cohort cannot be empty", each line twice. | Each line once + hint. |
| 4 | Fixed-lock form with a student ID that does not exist (stale page, deleted student) | **Crash** — `sqlite3.IntegrityError: FOREIGN KEY constraint failed` (HTTP 500). | Warning: "Student 'NOPE' does not exist. Pick a student from the list or add the student on the Students page first." Nothing saved. |
| 5 | Locking a student who is already locked | Said "Fixed assignment **created**" while silently replacing the old lock. | Says "was locked to Project P1 and is now locked to Project P2". |
| 6 | Project with a must-have skill level nobody has | Clear reason (twice). | Reason once + hint. See open question below. |
| 7 | Sum of minimum capacities (15) above cohort size (10) | Clear reason (twice). | Reason once + hint. |
| 8 | Unknown scenario name | Friendly warning. | Unchanged — already fine. |
| 9 | Student Viewer starts a run | "Permission denied". | Unchanged — already fine. |

## 2. Pattern and why

- **Validate at the boundary (Blueprint/MVC controller).** The route `create_fixed_assignment` now checks the IDs against `StudentRepository` / `ProjectRepository` *before* saving, the same way `create_project` already validates its form. The database foreign key is still there as the last safety net, but the user should never see it.
- **Presentation-only fix for duplicates.** The engine (Component B) puts each infeasibility reason in both `diagnostics["reasons"]` and `diagnostics["errors"]`. We did **not** change the engine output (that is part of the component contract and Team B's tests); the template just skips errors that are already listed as reasons (Jinja filter `reject('in', shown_reasons)`).
- **"What to change" box.** Shown only when the run is `INFEASIBLE` or `INVALID_INPUT`. It maps each kind of problem to the page where you fix it (Projects, Fixed Locks, Students).

## 3. Files changed

- `app/visualization/routes.py` — `create_fixed_assignment`: unknown-ID check, "lock replaced" message.
- `app/visualization/templates/run_detail.html` — no duplicate lines, "What to change" box.
- `tests/test_visualization_component.py` — 5 new tests (2 unknown-ID, 1 re-lock, 2 failed-run page checks).

## 4. Open question for Team B (not fixed here)

**Must-have skill on a project with `min_capacity = 0`.** `validate_inputs` reports *"Mandatory requirement impossible"* even when the project is allowed to stay empty. If nobody can join it, the solver could just leave it empty, so the run is not really infeasible. Marie/Torkil: should this check only apply when `min_capacity ≥ 1`? (File: `app/domain/validation.py`, the loop over `project.requirements`.)

## 5. Verification

```text
$ python -m pytest -q
```
➜ *Julia: paste your real output here after running on your machine (Pyomo/HiGHS installed).*

The 5 new tests were also run in a sandbox without Pyomo: the 3 form tests need no solver and pass; the 2 failed-run tests only use the pre-solver check and pass.

## 6. Check your understanding

1. Why did the form crash with a *database* error instead of showing a message? (Hint: who checked the ID first — Flask or SQLite?)
2. Why did we fix the duplicate lines in the template instead of in `solvers.py`?
3. A student is locked to P1 and you lock them to P2. How many rows are in `fixed_assignments` for that student afterwards, and why? (Hint: look at `UNIQUE` in `schema.sql`.)

*If you cannot explain every line, ask the AI to teach you before accepting or committing.*
