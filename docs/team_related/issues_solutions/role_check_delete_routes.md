# Role Check on Routes That Delete Data: Solution & Architectural Rationale

**Issue Title:** A read-only role could delete all cohort data and all solutions
**Branch:** `fix-role-check-destructive-routes`
**Date:** 2026-11-02
**Author / Lead:** Team (AI-assisted, Claude Code)

This work has no file in `docs/team_related/issues/`, so this file uses the topic-name convention from `.agents/rules/solution_documentation.md`. It covers part of [A2.4](../issues/A2.4.md) (the "scenarios, clear data/solutions" gaps that issue names). The rest of A2.4 is still open: the check of every POST route, the `test_student_viewer_cannot_mutate` test and the "Role × Action" table in `docs/architecture.md`.

---

## 1. Architectural Pattern & Design Rationale

- **Pattern Applied:** Role-based access control with a *guard clause* at the start of each Flask route (the controller in our MVC split). It is the same pattern `create_student`, `trigger_run` and `lock_and_rerun` already use: ask an `auth` helper, and if the answer is no, flash a message and redirect before any work is done.
- **Why Chosen:** The route is the only place every request passes through, so the check there cannot be skipped by posting to the URL directly. Hiding the buttons in the templates is only for the user's comfort. The real protection is the server-side check.
- **The bug:** Three POST routes changed or deleted data with no role check at all. A Student Viewer (read only) could post to `/clear-data` and delete every student. This was reproduced on a throwaway database: 10 students before, 0 after.
- **Component Scope:**
  - `app/visualization/`: `routes.py` (three guard clauses), `dashboard.html` and `scenarios.html` (buttons hidden).
  - `tests/test_visualization_component.py`: new tests only.
  - `app/visualization/auth.py` is not changed: the two existing helpers already express the rules we need.
  - `app/contract/`, `app/domain/`, `app/persistence/` and `app/engine/` are not changed.

### Which roles may use each route, and why

| Route | What it deletes | Helper | Admin | Coordinator | Student Viewer |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `POST /clear-data` | All students, projects, skills, preferences, fixed assignments | `can_edit_cohort_data()` | ✅ | ❌ | ❌ |
| `POST /load-scenario/<name>` | Same as above, then loads the scenario | `can_edit_cohort_data()` | ✅ | ❌ | ❌ |
| `POST /clear-solutions` | All runs and solutions (no cohort data) | `can_trigger_optimization()` | ✅ | ✅ | ❌ |

- **Clear data and load scenario → Admin only.** Both wipe the whole cohort. `docs/architecture.md` (Section 6) says the Coordinator is "read-only on baseline student data", and every other route that changes cohort data (students, projects, skills) already uses `can_edit_cohort_data()`. Loading a scenario counts as editing cohort data, because the first thing it does is `clear_all_cohort_data()`.
- **Clear solutions → Admin and Coordinator.** It only deletes runs and solutions, which are the Coordinator's work ("Runs & Analysis" in `auth.UserRole`). The same two roles can already create runs with `trigger_run` and `lock_and_rerun`, so the rule is "whoever may create runs may delete them". If the team prefers to keep this Admin only, change the helper to `can_edit_cohort_data()` and swap the roles in the two `clear_solutions` tests.

---

## 2. High-Level Logic & Data Flow Walkthrough

1. **Request:** The browser sends `POST /clear-data` (or one of the other two).
2. **Role lookup:** The route calls `auth.can_edit_cohort_data()` or `auth.can_trigger_optimization()`. These read the role from the Flask session (`get_current_role()`).
3. **Refused:** If the role is not allowed, the route flashes "Permission denied for current role." as `danger` and redirects to the dashboard. No repository method is called, so nothing is deleted.
4. **Allowed:** Otherwise the route runs exactly as before and calls `RunRepository().clear_all_cohort_data()` or `clear_all_current_solutions()`.
5. **Templates:** The context processor `inject_template_globals` already passes `can_edit` and `can_optimize` to every template. The templates use them to decide which buttons to draw:
   - `dashboard.html`: the three quick benchmark buttons need `can_edit`. Roles without it see a short notice instead, like the existing notice on the "Launch Optimization Run" panel. The "Delete Solutions" card needs `can_optimize`. The "click Standard Trade-Off Benchmark above" hint in the empty run list is only shown to roles that can see that button.
   - `scenarios.html`: the four "Load …" buttons and the "Database Reset" card need `can_edit`. The scenario descriptions stay visible to everyone, with one notice at the top that explains why the buttons are missing.

In `load_scenario` the check is placed **before** `clear_all_cohort_data()`. If it came after the wipe, a refused request would still delete the cohort.

---

## 3. Summary of Files Changed

| File Path | Modification Description |
| :--- | :--- |
| `app/visualization/routes.py` | Guard clause at the start of `load_scenario` and `clear_data` (`can_edit_cohort_data`) and `clear_solutions` (`can_trigger_optimization`). |
| `app/visualization/templates/dashboard.html` | Benchmark buttons shown only with `can_edit` (notice otherwise); "Delete Solutions" card only with `can_optimize`; empty-state hint only with `can_edit`. |
| `app/visualization/templates/scenarios.html` | Notice for roles without `can_edit`; the four load buttons and the "Database Reset" card shown only with `can_edit`. |
| `tests/test_visualization_component.py` | New `standard_client` fixture, three small helpers and 12 test cases (see below). No existing test changed. |
| `docs/team_related/issues_solutions/role_check_delete_routes.md` | This file. |

---

## 4. Verification & QA Status

New tests (all use the `standard_client` fixture: standard benchmark plus one saved mock run):

| Test | Roles | Checks |
| :--- | :--- | :--- |
| `test_clear_data_is_denied_for_non_admin` | Coordinator, Student | Permission message; same students and project count |
| `test_clear_data_still_works_for_admin` | Admin | Success message; no students or projects left |
| `test_load_scenario_is_denied_for_non_admin` | Coordinator, Student | Permission message; an extra student `S_KEEP` (in no scenario) is still there; no fixed assignment loaded |
| `test_load_scenario_still_works_for_admin` | Admin | Success message; `S_KEEP` gone; the scenario's one fixed assignment loaded |
| `test_clear_solutions_is_denied_for_student_viewer` | Student | Permission message; the saved run is still there |
| `test_clear_solutions_still_works_for_run_roles` | Admin, Coordinator | Success message; no runs left; students untouched |
| `test_delete_buttons_shown_only_to_allowed_roles` | All three | The load, clear-data and clear-solutions forms appear on the dashboard and scenarios pages only for allowed roles |

- **Fail on old code:** Run against `main` before this fix, the 7 "denied" and "hidden button" cases fail and the 5 "still works" cases pass, which is expected because those roles were allowed before too.
- **Verification command:** `.venv/bin/python -m pytest -q`
- **Output:** `157 passed` (145 before this change + 12 new), no failures, no existing test changed.
- **Not checked:** The pages were checked through the Flask test client, not looked at in a browser.
- **Independent QA (`qa-tester`):** **PASS**, no blocking findings. It confirmed the branch, the file scope, that only tests were added (no existing test changed), `157 passed`, and `7 failed, 5 passed` for the new tests on the old code. One of its suggestions was applied afterwards: type hints (`Any`) on the new `standard_client` fixture and `_switch_role` helper, as `_lock_first_assignment` already does. The suite still gives `157 passed` after that.

### Known limits and follow-ups

- **A mistyped scenario name still wipes the cohort.** `load_scenario` calls `clear_all_cohort_data()` before it checks the name, so an Admin posting `/load-scenario/typo` loses all students (10 → 0) and then sees "Unknown scenario". This is an input-validation order problem, not a role problem, so it is not fixed here. The fix is to look up the scenario first and wipe only when the name is known.
- **Docs and code disagree about fixed assignments.** `docs/architecture.md` says the Coordinator "can manage fixed assignment locks", but the fixed-assignment routes use `can_edit_cohort_data()` (Admin only). This belongs to A2.4's "Role × Action" table.
- **The rest of A2.4** (every POST route, one parametrised viewer test) is still open.

---

## 5. Check Your Understanding (Pedagogical Checkpoint)

1. *Why is hiding the button in the template not enough on its own?* (Anyone can send a POST to `/clear-data` with a tool like `curl` or the browser console. Only the check in the route stops that.)
2. *Why must the check in `load_scenario` come before `clear_all_cohort_data()`?* (Otherwise the wipe happens first, and the refusal only changes the message the user sees.)
3. *Why does `clear_solutions` use `can_trigger_optimization()` and not `can_edit_cohort_data()`?* (It deletes runs, not cohort data, and the roles that may create runs are Admin and Coordinator.)
4. *Why does the load-scenario test add the student `S_KEEP`?* (No scenario contains it, so if it disappears we know the wipe ran, whatever the scenario's own students look like.)
5. *How does the template know the role?* (`inject_template_globals` in `routes.py` passes `can_edit` and `can_optimize` to every template from the same `auth` helpers the routes use, so the buttons and the routes always agree.)

> **Pedagogical Checkpoint:** *"If you cannot explain every line, ask me to teach you before accepting or committing."*
