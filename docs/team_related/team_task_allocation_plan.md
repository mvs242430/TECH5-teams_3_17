# TECH5 Collaborative Project: Team Task Allocation & Three-Week Plan

*Corrected plan. **Detailed instructions for every task (what to build, exact files, step-by-step with the AI agent, prompt to paste, "done when" checks) are in [`issues/`](issues/README.md).** Beginners start with [`onboarding_for_students.md`](onboarding_for_students.md).*

Brief: *TECH5 Collaborative Project: The Student-to-Project Assignment Challenge*. Team A (2 people) builds the **face** (`app/visualization/`), Team B (3 people) builds the **brain** (`app/engine/`). Start state: `36 passed, 15 xfailed`. Finish line: **`51 passed, 0 xfailed`** and all 9 deliverables.

---

## 1. Who does what

| Person | Role | Main files | Deliverable lead |
|---|---|---|---|
| **A1** | Data person: skill & project forms, friendly errors | `routes.py` (skills/projects functions), `skills.html`, `project_form.html`, `projects.html` | D1 progress reports, D5 database & SQL |
| **A2** | Decision person: compare, recommendations, lock & re-run, access, demo | `routes.py` (compare/runs functions), `compare.html`, `recommendations.html`, `solution_detail.html`, `auth.py` | D3 architecture, D8 demo |
| **B1** | Scores person: skill fit, fairness, comparison numbers | `app/engine/metrics.py` | D6 (indicators part) |
| **B2** | Optimiser person: maths model, strategies, alternatives, professor approval | `app/engine/strategies.py`, `requirements.txt` | D6 (formulation part) |
| **B3** | Boss + safety person: run orchestration, diagnostics, edge cases | `app/engine/solvers.py`, `tests/test_edge_cases.py` | D2 working app, D4 contract, D7 testing |
| **All** | | | D9 team reflection |

Deliverables: D1 progress reports · D2 working app · D3 architecture · D4 component contract · D5 database & SQL · D6 analytical note · D7 testing evidence · D8 reproducible demo · D9 team reflection.

Shared-file rule: A1 and A2 both use `routes.py`, but each edits only their own functions. B2 works in `strategies.py`, B3 in `solvers.py` (made possible by issue 0.5). Pull `main` before every work session.

---

## 2. Corrected issue plan

Size: S ≤ 1 h · M ≤ half day · L ≤ 1 day. Details of each issue: `docs/team_related/issues/<ID>.md`.

### Setup (Week 1)

| ID | What | Where | Owner | Week | Size |
|---|---|---|---|---|---|
| [0.1](issues/0.1.md) | Set up computer, prove `36 passed, 15 xfailed` | none | everyone | 1 | S |
| [0.2](issues/0.2.md) | Board, labels, PR + issue templates, protect `main` | `.github/` (new) | A1 | 1 | S |
| [0.3](issues/0.3.md) | Add PuLP solver library (**blocks Team B**) | `requirements.txt` | B2 | 1 | S |
| [0.4](issues/0.4.md) | Fix wrong test counts and file names in docs | `README.md`, `docs/team_related/developer_onboarding_guide.md` | A1 | 1 | S |
| [0.5](issues/0.5.md) | Move `AssignmentStrategy` to its own file (avoids B2/B3 conflicts) | `app/engine/strategies.py` (new), `solvers.py` | B3 | 1 | M |

### Team A: the face

| ID | What | Where | Owner | Week | Size |
|---|---|---|---|---|---|
| [A1.1](issues/A1.1.md) | Skills: add and delete (with checks) | `routes.py` `create_skill`/`delete_skill`, `skills.html`, `test_skills_crud_workflow` | A1 | 1 | M |
| [A1.2](issues/A1.2.md) | Projects: create, edit, delete with skill requirements; edit form pre-fills saved values | `routes.py` project functions, `project_form.html`, `projects.html`, `test_projects_crud_workflow` | A1 | 1–2 | L |
| [A1.3](issues/A1.3.md) | Friendly messages for bad input (8 cases, a test each) | `routes.py`, `student_form.html`, `project_form.html`, `tests/test_visualization_component.py` | A1 | 2 | M |
| [A1.4](issues/A1.4.md) | D5: database and SQL documentation with real query results | `docs/database_design.md`, `app/persistence/queries.sql` | A1 (+B1) | 2 | M |
| [A1.5](issues/A1.5.md) | D1: progress reports 1 and 2 | `docs/progress_report_1.md`, `_2.md` (new) | A1 (+B2) | 1, 2 | S |
| [A2.1](issues/A2.1.md) | Compare page: what improves / worsens / who is affected | `routes.py` `compare_solutions`, `compare.html`, `test_compare_solutions_view` | A2 | 1–2 | L |
| [A2.2](issues/A2.2.md) | Recommendations: evidence vs advice clearly separated | `recommendations.html`, `run_detail.html` | A2 | 2 | M |
| [A2.3](issues/A2.3.md) | Lock-and-re-run: permission check, keep strategy, show changes | `routes.py` `lock_and_rerun`, `solution_detail.html` | A2 | 2 | M |
| [A2.4](issues/A2.4.md) | Role-access audit: Student Viewer can never change data | `auth.py`, `routes.py` (all POST), templates, tests | A2 | 3 | M |
| [A2.5](issues/A2.5.md) | D3: architecture diagrams and design rationale | `docs/architecture.md` | A2 (+B3) | 1–3 | M |
| [A2.6](issues/A2.6.md) | D8: reproducible demo script with real numbers | `docs/reproducible_demonstration.md` | A2 (+B2) | 3 | L |

### Team B: the brain

| ID | What | Where | Owner | Week | Size |
|---|---|---|---|---|---|
| [B-0](issues/B-0.md) | Method proposal (ILP), send to professor, record reply | `docs/method_proposal.md` (new) | B2 | 1 | M |
| [B1.1](issues/B1.1.md) | Skill-fit score and Gini | `metrics.py`, `test_skill_fit_calculation`, `test_gini_calculation` | B1 | 1 | M |
| [B1.2](issues/B1.2.md) | Solution indicators (feasibility, efficiency, fairness, capacity) | `metrics.py`, `test_solution_indicators_calculation` | B1 | 2 | L |
| [B1.3](issues/B1.3.md) | Compare-two-solutions numbers (exact keys for the Compare page) | `metrics.py`, `test_solution_comparison` | B1 | 2 | M |
| [B2.1](issues/B2.1.md) | PuLP model: yes/no variables and hard rules | `strategies.py`, `tests/test_solvers.py` | B2 | 2 | L |
| [B2.2](issues/B2.2.md) | Three strategies: `PREFERENCE`, `SKILL_FIT`, `BALANCED` | `strategies.py`, `tests/test_solvers.py` | B2 | 2 | L |
| [B2.3](issues/B2.3.md) | Distinct alternatives with no-good cuts | `strategies.py`, `test_distinct_alternatives_generation` | B2 | 2 | M |
| [B3.1](issues/B3.1.md) | `AssignmentEngine.execute_run` (placeholder strategy first, real ones in Week 2) | `solvers.py` | B3 | 1–2 | L |
| [B3.2](issues/B3.2.md) | Update old tests that expect "not implemented" (merge with B3.1) | `tests/test_solvers.py`, `test_contract_and_engine.py`, `test_component_integration.py` | B3 | 2 | M |
| [B3.3](issues/B3.3.md) | Readable diagnostics when no solution exists | `solvers.py`, `app/domain/validation.py` (reasons only) | B3 | 2–3 | M |
| [B3.4](issues/B3.4.md) | Seven edge-case tests: 1, 2, 3, 4, 13, 14, 15 | `tests/test_edge_cases.py` + fixes in `app/engine/` | B3 (+B1, B2) | 2–3 | L |
| [B3.5](issues/B3.5.md) | D4: component contract document | `docs/internal_component_contract.md` | B3 (+A1) | 1–2 | M |
| [B3.6](issues/B3.6.md) | D7: testing evidence | `docs/testing_and_quality.md` | B3 (+A1, B1) | 3 | M |
| [B2.4 + B1.4](issues/B2.4-B1.4.md) | D6: analytical note (B2 formulation, B1 indicators, B3 diagnostics) | `docs/analytical_note.md` (from template) | B2, B1, B3 | 3 | M each |

### Shared integration

| ID | What | Where | Owner | Week | Size |
|---|---|---|---|---|---|
| [X1](issues/X1.md) | Swap mock engine for real engine, walk every page | `routes.py` `trigger_run`, `lock_and_rerun` | A2 + B3 | 2 | M |
| [X2](issues/X2.md) | Try every scenario incl. bad data, fix unclear screens | scenarios in `app/samples/demo_data.py` | A1 + B3 | 3 | M |
| [X3](issues/X3.md) | One full end-to-end test, no mock | `tests/test_component_integration.py` | A1 | 3 | M |
| [X4](issues/X4.md) | Remove starter leftovers (`Starter Carcass`, `TODO (Team`) | `app/` | A2 | 3 | S |
| [X5](issues/X5.md) | D9: team reflection, rewritten with the real story | `docs/team_reflection_and_rubric.md` | everyone (B3 collects) | 3 | M |
| [X6](issues/X6.md) | Git/PR evidence | `docs/git_evidence.md` (new) | A1 | 3 | S |
| [X7](issues/X7.md) | Final release check, tag `v1.0` | none | all | 3 | S |

---

## 3. Weekly plan and gates

| Week | Team A | Team B | Gate at end of week |
|---|---|---|---|
| **1** | 0.1, 0.2, 0.4, A1.1, A1.2, A2.1 (on mock), A2.5 start, A1.5 | 0.1, 0.3, 0.5, B-0, B1.1, B3.1 (placeholder), B3.5 | Forms create skills/projects; compare works on mock; method proposal sent |
| **2** | A1.2 finish, A1.3, A1.4, A2.2, A2.3, X1, A1.5 | B1.2, B1.3, B2.1–B2.3, B3.1 final, B3.2, B3.3, B3.4 start | Real engine swapped in; 2+ different solutions on `/compare` |
| **3** | A2.4, A2.6, X2, X3, X4, X6 | B3.4, B3.6, B2.4, B1.4, X5 | `51 passed`, demo rehearsed twice, all 9 deliverables done (X7) |

**Critical path:** `0.3 → 0.5 → B2.1 → B2.2 → B2.3 → B3.4` and `B1.1 → B1.2 → B1.3 → real data on the Compare page`. If the professor's reply is late, B2 keeps working under the same strategy names, so Team A is never blocked.

**Deliverable owners:** D1 A1 · D2 B3 + A2 · D3 A2 · D4 B3 · D5 A1 · D6 B2 (+B1, B3) · D7 B3 · D8 A2 · D9 all.

## 4. What changed from the first version (short)

- Added what was missing: PuLP install (0.3), engine file split (0.5), updating tests that expect "not implemented" (B3.2), professor-approval owner (B-0).
- Team A tasks now require real test assertions, not just "page does not crash".
- B3 starts in Week 1 with a placeholder strategy; Team A takes integration and QA tasks, so work is balanced.
- Pre-written docs (`reproducible_demonstration.md`, `team_reflection_and_rubric.md`) must be rewritten from real results, not submitted as they are.
- Issues name functions, not line numbers; real file names (`solution_detail.html`); test count 51 / 36 pass / 15 xfail everywhere.

## 5. How we know we are done

1. `python -m pytest -q` shows `51 passed`.
2. `grep -rn "xfail\|TODO (Team" app tests` finds nothing.
3. A teammate who did not write the demo follows `docs/reproducible_demonstration.md` on a fresh clone and gets the same results.
4. A non-developer completes section 1.4 of the onboarding guide alone in under 30 minutes.
