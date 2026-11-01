# Deliverable: Week 3 Milestone Report, Analytical Note Summary & Reproducible Demonstration

**Project:** TECH5 Student-to-Project Assignment Decision Support System (DSS)  
**Team:** Team 6 (Groups 3 and 17 — 5 Members)  
**Repository:** [`mvs242430/TECH5-teams_3_17`](https://github.com/mvs242430/TECH5-teams_3_17)  
**Milestone:** Week 3 — *Robustness, Decision Support, Analytical Note & End-to-End Verification*  
**Date:** 1 November 2026  

> [!IMPORTANT]
> **Formal Week 3 Deliverable — Analytical Note (Deliverable 6):**  
> Our complete mathematical formulation and analytical note (structured strictly according to `docs/analytical_note_template.md` for our **Pyomo + HiGHS** optimization engine) is maintained at:  
> 👉 **[`docs/analytical_note_template_filled.md`](../analytical_note_template_filled.md)**

---

## 1. Week 3 Requirements, Milestone & Deliverable Checklist

All Week 3 course requirements, end-to-end milestone capabilities, edge-case resolutions, automated `pytest -v` checks, and analytical documentation deliverables are complete and verified:

| Week 3 Requirement | Status | Repository Evidence |
| :--- | :---: | :--- |
| **Resolve remaining edge cases across engine & UI** | ✅ **Done** | All 15 Section-13 edge cases pass in [`tests/test_edge_cases.py`](../../tests/test_edge_cases.py); input ID/seat boundary checks merged via [PR #48](https://github.com/mvs242430/TECH5-teams_3_17/pull/48); cross-cohort comparison & emptied-solution guards merged via [PR #50](https://github.com/mvs242430/TECH5-teams_3_17/pull/50); UI bad-data walkthrough documented in `X2` (`x2-bad-data-walkthrough`). |
| **Ensure all 50+ automated tests pass (`pytest -v` with zero unexpected failures or regressions)** | ✅ **Done** | `.venv/bin/python -m pytest -v` $\rightarrow$ **`105 passed in 3.13s` (`0 failed`, `0 xfailed`)**, covering all 51 starter tests (including all 15 previously `xfailed` tasks) plus 54 unit, edge-case, and UI integration tests (plus 6 additional regression/E2E tests on branches `x2-bad-data-walkthrough` and `x3-end-to-end-test`). |
| **Complete the Analytical Note (`docs/analytical_note_template.md`)** | ✅ **Done** | Full **Pyomo + HiGHS** mathematical formulation, feasibility proofs, 4-pillar performance measures, assumptions, recommendation criteria, and analytical limitations delivered in **[`docs/analytical_note_template_filled.md`](../analytical_note_template_filled.md)** (summarized in Section 2 below). |
| **Milestone: Full end-to-end functionality verified** *(data entry, run trigger, distinct alternative generation, comparison, transparent recommendations, fixed assignments, infeasibility handling)* | ✅ **Done** | Verified across all 7 end-to-end stages in live UI workflows and automated lifecycle tests ([`tests/test_component_integration.py`](../../tests/test_component_integration.py) and [`tests/test_visualization_component.py`](../../tests/test_visualization_component.py)); detailed stage-by-stage verification matrix in Section 3. |
| **Prepare a reproducible demonstration** | ✅ **Done** | Deterministic 4-scenario live walkthrough (`standard`, `fixed`, `infeasible`, `conflicting`) + interactive **Lock & Rerun** + headless Python verification protocol documented in Section 5 with exact live Pyomo/HiGHS metrics. |

---

## 2. Analytical Note Summary ([`docs/analytical_note_template_filled.md`](../analytical_note_template_filled.md))

The formal Week 3 deliverable — **[`docs/analytical_note_template_filled.md`](../analytical_note_template_filled.md)** — documents the complete analytical architecture of Component B (`app/engine/`) and its decision-support integration with Component A (`app/visualization/`):

| Analytical Pillar | Summary of Formulation & Design | Detailed Section |
| :--- | :--- | :---: |
| **1. Assignment Approach** | **Mixed-Integer Linear Programming (MILP)** modeled algebraically in **Pyomo (`pyomo>=6.7`)** and solved in-process via **HiGHS (`highspy>=1.7` / `appsi_highs`)**. Certifies global optimality, proves infeasibility deterministically without heuristic guesswork, and solves the benchmark cohort in `< 0.05s` with zero external binary dependencies. | [§1.1–§1.2](../analytical_note_template_filled.md#1-problem-definition--mathematical-modeling-approach) |
| **2. Feasibility & Hard Constraints** | Binary decision matrix $x_{s,p} \in \{0, 1\}$ subject to 5 linear constraint families: (1) exact single-project allocation $\sum_{p \in P} x_{s,p} = 1$; (2) project headcount bounds $l_p \le \sum_{s \in S} x_{s,p} \le u_p$; (3) administrative fixed locks $x_{s^*, p^*} = 1$; (4) individual mandatory skill prerequisites $x_{s,p} = 0$ whenever $\text{skill}_{s,k} < \text{req}_{p,k}$ ($m_{p,k}=1$); and (5) Balas–Jeroslow integer no-good cuts $\sum_{(s,p) \in A^{(j)}} x_{s,p} \le \|S\| - 1$. | [§2.1–§2.4](../analytical_note_template_filled.md#2-mathematical-formulation) |
| **3. Multi-Objective Strategies & Distinct Alternatives** | Implements three `AssignmentStrategy` subclasses (`PREFERENCE`, `SKILL_FIT`, `BALANCED` with convex weight $\alpha = 0.5$ over unit-normalized preference score $w_{s,p}^{\text{pref}}$ and capped skill fit $\sigma_{s,p} \in [0,1]$). `AssignmentEngine.execute_run` combines **strategy rotation** with cumulative **no-good cuts** to guarantee genuinely distinct Pareto alternatives. | [§2.5–§2.6](../analytical_note_template_filled.md#25-optimization-objectives--strategies) |
| **4. Performance Measures & Comparison Deltas** | Independent post-solve evaluation in [`metrics.py`](../../app/engine/metrics.py) across **Feasibility** (`is_feasible`, `violations`), **Efficiency** (capped fractional skill fit $\bar{\sigma}$, unmet soft requirements, mean rank $\bar{r}$), **Fairness** (rank histogram, unranked count $U$, worst rank $r_{\max}$, **pairwise Gini coefficient $G$**, and rank variance $\operatorname{Var}(\tilde{r})$), **Capacity Utilization**, and directional **B − A** deltas. | [§3–§4](../analytical_note_template_filled.md#3-evaluation-indicators--analytical-metrics) |
| **5. Transparent Recommendation Criteria** | Rule-based lexicographic selection in [`recommendations.py`](../../app/engine/recommendations.py) across 3 policy lenses (*Student Preference Maximization*, *Project Skill Quality*, *Balanced & Egalitarian Allocation*), strictly separating **Selection Criteria**, **Calculated Evidence**, and **Administrative Policy Advice**. | [§5](../analytical_note_template_filled.md#5-transparent-recommendation-rules) |
| **6. Assumptions & Limitations** | Documents incomplete preference penalties ($-2R$ in `PREFERENCE`, $-1.0$ in `BALANCED`, $\rho = r_{\text{max\_stated}} + 1$ in fairness), tie-breaking determinism, zero-skill/zero-requirement defaults, pre-solver vs. solver-proven infeasibility boundaries, no-good cut loss of total unimodularity, linear Borda utility assumptions, individual vs. team skill synergies, and static snapshot scope. | [§6–§7](../analytical_note_template_filled.md#6-assumptions-boundary-conditions--edge-cases) |

---

## 3. Milestone Verification & Edge-Case Resolution

### 3.1 Seven-Stage End-to-End Functional Verification

| Milestone Stage | Implemented Workflow (`Component A` $\leftrightarrow$ `Contract` $\leftrightarrow$ `Component B`) | Verifying Automated Tests |
| :--- | :--- | :--- |
| **1. Data Entry & RBAC** | Interactive CRUD forms for Skills (`/skills`), Projects with mandatory/soft skill matrix (`/projects`), Students with ranked preferences (`/students`), and Fixed Locks (`/fixed-assignments`); sticky form validation, dependency delete guards, and `Student Viewer` read-only enforcement. | `test_skills_crud_workflow`, `test_projects_crud_workflow`, `test_dashboard_and_crud_workflow`, `test_role_switcher` |
| **2. Run Trigger** | Coordinator/Admin launches optimization (`POST /runs/trigger`) selecting primary strategy (`PREFERENCE`, `SKILL_FIT`, `BALANCED`) and `max_alternatives`; dispatches strongly typed `contract.RunRequest` in-process to `AssignmentEngine.execute_run`. | `test_scenario_loading_and_optimization_trigger`, `test_contract_execute_and_retrieval` |
| **3. Distinct Alternative Generation** | Engine rotates strategies while appending linear integer no-good cuts ($\sum_{(s,p) \in A^{(j)}} x_{s,p} \le \|S\| - 1$); stops cleanly without duplicates if fewer feasible allocations exist. | `test_distinct_alternatives_generation`, `test_edge_case_14_single_feasible_solution`, `test_edge_case_15_duplicate_avoidance_no_good_cuts` |
| **4. Side-by-Side Comparison** | `/compare` computes `RunComparison` via `engine.compare_solutions`, rendering 5 KPI delta cards ($\Delta$ Changed Students, $\Delta$ Skill Fit, $\Delta$ Mean Rank, $\Delta$ Gini, Rank Shifts), plain-language impact summary, and student-level reallocation table. | `test_compare_solutions_view`, `test_solution_comparison`, `test_compare_same_cohort_across_runs_still_works` |
| **5. Transparent Recommendations** | `/recommendations/<run_id>` and quick-jump badges on `/runs/<run_id>` present 3 policy lenses with separated **Criteria**, **Calculated Evidence**, and **Administrative Advice**. | `test_full_lifecycle_integration` (`generate_recommendations` & UI rendering) |
| **6. Fixed Assignments & Lock-and-Rerun** | Pre-allocated locks ($x_{s^*, p^*} = 1$) enforced across all alternatives; single-click `POST /solutions/<id>/lock-and-rerun` pins a student-project pair, preserves original strategy & `max_alternatives`, and re-solves immediately. | `test_fixed_assignment_preservation`, `test_lock_and_rerun_creates_exactly_one_fixed_assignment_and_preserves_strategy` |
| **7. Infeasibility & Bad-Input Handling** | Pre-solver `validate_cohort` catches capacity deficits, minimum-quota excess, and contradictory locks; Pyomo `solve(..., load_solutions=False)` catches coupled MILP infeasibility without crashing and persists structured `diagnostics["reasons"]`. | `test_infeasible_cohort_integration`, `test_edge_case_7` through `test_edge_case_13` |

### 3.2 Edge Cases & Robustness Improvements Resolved in Week 2–3

1. **All 15 Specification Edge Cases (`B3.4`):** Verified in [`tests/test_edge_cases.py`](../../tests/test_edge_cases.py), covering incomplete preferences (Case 1), tied #1 rankings across students (Case 2), zero-skill students (Case 3), zero-requirement projects (Case 4), unknown project/skill IDs (Cases 5–6), aggregate capacity deficits and minimum-quota excesses (Cases 7–8), capacity inversions (Case 9), conflicting and over-capacity fixed locks (Cases 10–11), unavailable mandatory skills (Case 12), general coupled MILP infeasibility (Case 13), single feasible allocation (Case 14), and strict non-duplication under cuts (Case 15).
2. **Cross-Cohort Comparison & Emptied-Solution Guards (`A2.1.1`, [PR #50](https://github.com/mvs242430/TECH5-teams_3_17/pull/50)):** Reloading scenarios or adding/deleting students previously caused `ON DELETE CASCADE` or cohort mismatches to surface raw errors when comparing historical runs. `/compare` now filters emptied solutions out of dropdowns and displays a clear user-facing banner whenever two selected solutions belong to different student cohorts (6 new regression tests).
3. **Identifier Format & Seat-Cap Validation (`a1-input-fixes`, [PR #48](https://github.com/mvs242430/TECH5-teams_3_17/pull/48)):** Student and project IDs are strictly validated against `^[A-Za-z0-9_-]{1,20}$` and project capacities above `50` seats are rejected cleanly with sticky form state (14 parametrized regression tests).
4. **Bad-Data Walkthrough & Diagnostic Polish (`X2` & `X3` branches):** Walkthrough across all 4 scenarios plus 5 adversarial UI inputs added pre-insert existence checks on fixed locks, explicit lock-replacement notices, deduplicated reason/error rendering with a *"What to change"* remediation panel (`x2-bad-data-walkthrough`), and a full HTTP end-to-end integration test through the real Pyomo/HiGHS engine (`x3-end-to-end-test`).

---

## 4. Automated Test Suite Verification (`pytest -v`)

Running the complete test suite with `pytest -v` confirms **105 passing tests, 0 failures, and 0 `xfail` markers** (exceeding the 51 baseline tests with zero regressions):

```text
$ .venv/bin/python -m pytest -v
============================= test session starts ==============================
platform darwin -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0
collected 105 items

tests/test_component_integration.py::test_full_lifecycle_integration PASSED      [  0%]
tests/test_component_integration.py::test_infeasible_cohort_integration PASSED   [  1%]
tests/test_contract_and_engine.py (5 contract & substitutability tests) PASSED   [  6%]
tests/test_edge_cases.py (15 Section-13 boundary & solver edge cases) PASSED     [ 20%]
tests/test_metrics.py (6 skill-fit, Gini, indicator & delta tests) PASSED        [ 26%]
tests/test_models.py (4 domain entity & serialization tests) PASSED              [ 30%]
tests/test_persistence.py (3 SQLite 3NF schema, FK & repository tests) PASSED    [ 33%]
tests/test_solvers.py (12 Pyomo/HiGHS MILP, strategies & cut tests) PASSED       [ 44%]
tests/test_validation.py (6 cohort pre-solver validation tests) PASSED           [ 50%]
tests/test_visualization_component.py (52 UI, RBAC, CRUD, compare & lock tests)  [100%]

============================= 105 passed in 3.13s ==============================
```

| Test Module | Architectural Layer Verified | Passed | Failed / XFailed |
| :--- | :--- | :---: | :---: |
| [`tests/test_visualization_component.py`](../../tests/test_visualization_component.py) | Component A routes, RBAC, Skills/Projects/Students CRUD, sticky validation, `/compare` cohort guards, `/recommendations`, Lock & Rerun | `52` | `0` |
| [`tests/test_edge_cases.py`](../../tests/test_edge_cases.py) | All 15 Section-13 edge cases (incomplete/tied preferences, zero skills/reqs, capacity deficits, mandatory skills, no-good cuts) | `15` | `0` |
| [`tests/test_solvers.py`](../../tests/test_solvers.py) | Pyomo base MILP constraints, fixed locks, mandatory skill fixing, 3 strategies (`PREFERENCE`, `SKILL_FIT`, `BALANCED`), integer cuts | `12` | `0` |
| [`tests/test_metrics.py`](../../tests/test_metrics.py) | Capped fractional skill fit, pairwise Gini index, 4-pillar solution indicators, pairwise solution comparison | `6` | `0` |
| [`tests/test_validation.py`](../../tests/test_validation.py) | Pre-solver structural validation and mathematical feasibility rules | `6` | `0` |
| [`tests/test_contract_and_engine.py`](../../tests/test_contract_and_engine.py) | `AssignmentEngineContract` ABC compliance, DTO validation, persistence, retrieval, and mock substitutability | `5` | `0` |
| [`tests/test_models.py`](../../tests/test_models.py) | Domain dataclasses, invariants, and JSON serialization helpers | `4` | `0` |
| [`tests/test_persistence.py`](../../tests/test_persistence.py) | SQLite 3NF schema, WAL mode, foreign-key cascades, and repository CRUD round-trips | `3` | `0` |
| [`tests/test_component_integration.py`](../../tests/test_component_integration.py) | Full in-process lifecycle (seed $\rightarrow$ solve $\rightarrow$ compare $\rightarrow$ recommend $\rightarrow$ lock & rerun) and infeasible run flow | `2` | `0` |
| **Total** | **All 4 Testing Layers (Unit, Persistence, Contract, Integration)** | **`105`** | **`0`** |

---

## 5. Reproducible Demonstration Walkthrough (Zero Mock Data)

### 5.1 Environment Setup & Launch
```bash
# macOS / Linux
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run.py

# Windows PowerShell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```
Open **`http://127.0.0.1:5000`** in a browser (default role: `Administrator`; switchable in the navbar between `Administrator`, `Programme Coordinator`, and read-only `Student Viewer`).

### 5.2 Five-Minute End-to-End Demo Script & Expected Live Outputs

| Demo Step | User Action in Web UI | Exact Reproducible Output (Pyomo + HiGHS) |
| :--- | :--- | :--- |
| **Step 1: Data Entry & RBAC Check** | Visit **Skills** (`/skills`) and **Projects** (`/projects`) to inspect/add a skill or edit project requirements; switch role to `Student Viewer` to verify edit/trigger controls are blocked (`403` / permission warning), then switch back to `Programme Coordinator` or `Administrator`. | Relational updates persist immediately in SQLite (`instance/tech5_dss.db`); `Student Viewer` cannot mutate cohort data or launch runs. |
| **Step 2: Scenario 1 — Standard Trade-Off Benchmark** | Go to **Scenarios** (`/scenarios`) $\rightarrow$ load **Standard Trade-Off Benchmark** (10 students `S01–S10`, 4 projects `P1–P4` with bounds `[1, 3]`, 12 seats) $\rightarrow$ trigger run with `PREFERENCE` and `3` alternatives. | Status **`COMPLETED`** (`< 0.05s`) with **3 distinct solutions**:<br>• **Alt #1 (`PREFERENCE`):** Mean Rank `1.00`, Worst Rank `1`, Gini `0.0000`, Skill Fit `98.3%`<br>• **Alt #2 (`SKILL_FIT`):** Mean Rank `1.20`, Worst Rank `2`, Gini `0.1333`, Skill Fit `100.0%`<br>• **Alt #3 (`BALANCED`):** Mean Rank `1.10`, Worst Rank `2`, Gini `0.0818`, Skill Fit `100.0%` |
| **Step 3: Side-by-Side Comparison** | Click **Compare** (`/compare`) $\rightarrow$ compare **Alt #1 (`PREFERENCE`)** vs. **Alt #2 (`SKILL_FIT`)**. | Displays **$\Delta$ Mean Skill Fit `+1.7%`**, **$\Delta$ Mean Rank `+0.20`**, **$\Delta$ Gini `+0.1333`**, plain-language impact summary, and exact displaced students moving from rank 1 to rank 2. |
| **Step 4: Transparent Recommendations** | From `/runs/<run_id>`, click **View Recommendations** (`/recommendations/<run_id>`). | Recommends **Alt #1** for *Student Preference Maximization* and *Balanced & Egalitarian Allocation* ($G = 0.0000, \bar{r} = 1.00$), and **Alt #2** for *Project Skill Quality* ($\bar{\sigma} = 100.0\%$, `0` unmet soft requirements), separating **Criteria**, **Evidence**, and **Policy Advice**. |
| **Step 5: Scenario 2 & Interactive Lock & Rerun** | Load **Fixed Assignment Scenario** (`S02` locked to `P2`) and run; or open any solution (`/solutions/<id>`), choose a student-project pair in **Lock & Rerun**, and submit. | `S02` $\rightarrow$ `P2` (`Fixed` badge) holds across **all 3 generated alternatives**; interactive **Lock & Rerun** saves the new `APPROVED` lock, preserves the original strategy, and immediately solves a new run showing peer ripple effects. |
| **Step 6: Scenarios 3 & 4 — Infeasibility & Contradictory Locks** | Load **Capacity Deficit** (`10 students > 6 seats`) and launch a run; then load **Contradictory Fixed Assignments** (`4` students locked to `P1` with `max_capacity = 3`) and launch a run. | Both runs terminate safely as **`INFEASIBLE`** with `0` corrupt solutions and explicit diagnostic messages (*"Insufficient overall capacity: total cohort size (10) exceeds aggregate maximum project capacity (6)"* and *"Fixed assignments (4) for project 'P1' exceed its maximum capacity (3)"*). |

### 5.3 Headless In-Process Python Verification
Component B can also be verified headlessly without starting Flask:
```python
from app.contract import contract
from app.engine import solvers
from app.samples import demo_data

scenario = demo_data.get_standard_scenario()
engine = solvers.AssignmentEngine()
run = engine.execute_run(
    contract.RunRequest(
        students=scenario["students"],
        projects=scenario["projects"],
        skills=scenario["skills"],
        fixed_assignments=scenario["fixed_assignments"],
        strategy_key="PREFERENCE",
        max_alternatives=3,
    )
)
print(run.status, len(run.solutions))  # COMPLETED 3
```

---

## 6. Team Contributions & AI Collaboration Summary

### 6.1 Member Responsibilities Across Deliverables

| Member | Sub-Team & Role | Key Week 2–3 Deliverables & Contributions |
| :--- | :--- | :--- |
| **Julia** | **Team A (`A1`)** · Data Management, Validation, DB Docs & QA | Skills/Projects CRUD & sticky validation (`A1.1–A1.3`), ID/seat boundary hardening ([PR #48](https://github.com/mvs242430/TECH5-teams_3_17/pull/48)), 3NF database docs ([`database_design.md`](../database_design.md)), bad-data UI audit (`X2`), full HTTP E2E test (`X3`), Git evidence (`X6`), progress reports (`A1.5`). |
| **Tanver** | **Team A (`A2`)** · Comparison, Recommendations, Lock & Rerun & Architecture | Side-by-side `/compare` view (`A2.1`), transparent `/recommendations/<run_id>` UI (`A2.2`), interactive **Lock & Rerun** workflow (`A2.3`), system architecture documentation (`A2.5`). |
| **Daniel** | **Team B (`B1`)** · Analytical Metrics, Fairness & Indicators | Fractional capped skill-fit calculator, pairwise Gini inequality index, 4-pillar solution indicators, and pairwise comparison deltas in [`metrics.py`](../../app/engine/metrics.py) (`B1.1–B1.3`) + indicator formulations (`B1.4`). |
| **Torkil** | **Team B (`B2`)** · Pyomo/HiGHS MILP Formulation & Cuts | Pyomo + HiGHS setup (`0.3`), base MILP constraint builder (`B2.1`), `PREFERENCE` / `SKILL_FIT` / `BALANCED` strategies (`B2.2`), Balas–Jeroslow integer no-good cuts (`B2.3`) in [`strategies.py`](../../app/engine/strategies.py) + MILP formulation (`B2.4`). |
| **Marie** | **Team B (`B3`)** · Engine Orchestration, Edge Cases, Integration & Release | `AssignmentEngine.execute_run` orchestration & persistence (`B3.1–B3.2`), infeasibility diagnostics (`B3.3`), all 15 Section-13 edge-case tests (`B3.4`), cross-cohort comparison fix (`A2.1.1`, [PR #50](https://github.com/mvs242430/TECH5-teams_3_17/pull/50)), analytical note synthesis & Week 3 integration. |

### 6.2 How We Used & Verified AI Tools in Week 3
- **Code-to-Math Verification for the Analytical Note:** We cross-checked every equation in [`docs/analytical_note_template_filled.md`](../analytical_note_template_filled.md) line-by-line against [`strategies.py`](../../app/engine/strategies.py), [`solvers.py`](../../app/engine/solvers.py), [`metrics.py`](../../app/engine/metrics.py), and [`recommendations.py`](../../app/engine/recommendations.py)—updating an earlier Week 1 `PuLP/CBC` draft so that solver bindings (`appsi_highs`), unranked penalties ($-2R$, $-1.0$, $\rho = r_{\text{max\_stated}} + 1$), and strategy objectives match our real Python implementation 100%.
- **Adversarial Bad-Data & Regression Testing:** AI pair-programming helped script Flask test-client walkthroughs across bad inputs (`X2`, `A2.1.1`, `a1-input-fixes`), exposing cohort-mismatch edge cases on `/compare` and duplicate reason lines on failed runs; every fix was paired with dedicated `pytest` assertions without weakening any existing starter test.
- **Human Verification:** All test suites (`105 passed`), live benchmark metrics across the 4 scenarios, and headless contract snippets were executed and verified directly against the local SQLite and Pyomo/HiGHS runtime.
