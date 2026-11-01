# X3 Solution — One full end-to-end test

**Owner:** Julia (A1)  
**Branch:** `x3-end-to-end-test`  
**Test:** `tests/test_component_integration.py::test_x3_full_end_to_end_flow`

## 1. What the test proves

One user journey, start to finish, through the **real** `AssignmentEngine` (no mock):

| Step | What the test does | What it checks |
|---|---|---|
| 1 | `POST /load-scenario/standard` | Page says "Standard Cohort" |
| 2 | `POST /runs/trigger` | Run is `COMPLETED`; page has no "not yet implemented" (= mock fallback) |
| 3 | read the run through the engine contract | ≥ 2 solutions |
| 4 | `GET /compare?sol1=…&sol2=…` | 200 + comparison heading |
| 5 | `GET /recommendations/<run_id>` | 200 |
| 6 | `POST /solutions/<id>/lock-and-rerun` | flash "locked to Project" |
| 7 | read the new run | new run ≠ old run, and **every** solution has the locked student on the locked project with `is_fixed = True` |
| 8 | load `infeasible`, run again | run is `INFEASIBLE` and **every** reason in `diagnostics["reasons"]` is visible on the page |

## 2. Pattern and why

- **Integration test across the component contract.** The test talks to Component A only through HTTP routes (like a user) and reads results only through `AssignmentEngineContract` (`list_runs`, `get_run`). It never touches Pyomo directly, so it tests the *wiring* between A and B, not the maths (that is `test_solvers.py`).
- **Which student to lock:** we pick a student whose project is *different* in solution 2 than in solution 1. Locking someone who never moves would pass trivially; this way the lock really forces the engine to keep a choice it would otherwise change.
- **Escaping:** the page shows reasons through Jinja, which turns `'` into `&#39;`. We compare with `markupsafe.escape(reason)` so the test does not break if a reason contains a quote.

## 3. Files changed

- `tests/test_component_integration.py` — new test + `import markupsafe` (no existing test changed).

## 4. Verification

```text
$ python -m pytest -q
```
➜ *Julia: paste your real output here after running on your machine (Pyomo/HiGHS installed).*

The test's plumbing (routes, IDs, assertions) was checked in a sandbox where Pyomo could not be installed, with a stand-in solver that follows the same hard rules. That shows the test is wired correctly; the real MILP check is your local run.

## 5. Check your understanding

1. Why does step 2 check that "not yet implemented" is **not** on the page?
2. Why do we check the lock in **every** solution of the new run, not only the first?
3. Step 8 runs before the solver is ever called. Which function decides it is infeasible? (Hint: `validate_inputs`.)

*If you cannot explain every line, ask the AI to teach you before accepting or committing.*
