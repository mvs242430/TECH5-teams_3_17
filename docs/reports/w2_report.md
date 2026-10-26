# Deliverable: Week 2 Progress Report & Implementation Decisions

**Project:** TECH5 Student-to-Project Assignment Decision Support System (DSS)  
**Team:** 6 (Groups 3 and 17)  
**Repository:** [`mvs242430/TECH5-teams_3_17`](https://github.com/mvs242430/TECH5-teams_3_17)   
**Milestone:** Week 2 — *Implement, Verify, and Integrate*  
**Date:** 27th October 2026  

---

## 1. Executive Summary & Status

During Week 2, the team transitioned to feature implementation on dedicated branches. This report documents the decisions, architectural boundaries, and test verification for **Task A1.1 (Skills CRUD & Validation)**, completed by Marie.

### Status at a Glance
- **Issue:** [`A1.1`](../team_related/issues/A1.1.md) · Branch: `a1.1-skills` (merged into `main`)
- **Pytest:** `37 passed, 14 xfailed` (`test_skills_crud_workflow` PASSED; 0 regressions)
- **Scope:** [`routes.py`](../../app/visualization/routes.py), [`skills.html`](../../app/visualization/templates/skills.html), [`test_visualization_component.py`](../../tests/test_visualization_component.py)

### Team Task Progress

| Member | Responsibility | Allocated Tasks Done | Tasks Done for Other Members |
| :--- | :--- | :--- | :--- |
| **Julia** | A1 Responsible | — | — |
| **Tanver** | A2 | — | — |
| **Daniel** | B1 | — | — |
| **Torkil** | B2 | — | — |
| **Marie** | B3 | — | [`A1.1`](../team_related/issues/A1.1.md) Skills: add and delete |

---

## 2. Technical Decisions & Architectural Rationale

### 2.1 Architectural Patterns Applied

1. **Model-View-Controller (MVC) via Flask Blueprints:**
   - In [`routes.py`](../../app/visualization/routes.py), the route functions `create_skill` and `delete_skill` serve strictly as **Controllers**. They parse form inputs, enforce role-based access control, apply business validation rules, invoke persistence methods, and return view responses.
   - The view layer ([`skills.html`](../../app/visualization/templates/skills.html)) handles presentation, conditional role-based action buttons, and modal dialogs.
2. **Repository Pattern:**
   - Database operations are completely encapsulated behind [`SkillRepository`](../../app/persistence/repositories.py), [`StudentRepository`](../../app/persistence/repositories.py), and [`ProjectRepository`](../../app/persistence/repositories.py). Routes never execute raw SQL statements, adhering strictly to the modular monolith boundaries.
3. **Role-Based Access Control (RBAC):**
   - Mutating routes verify authorization using `auth.can_edit_cohort_data()` at execution entry. Non-admin roles (such as `Student Viewer` or unauthenticated sessions) receive an explicit `"Permission denied"` flash alert and are redirected.

---

### 2.2 Key Engineering & Design Decisions

| Decision Area | Chosen Approach | Rationale & Trade-offs |
| :--- | :--- | :--- |
| **Identifier Format** | Regex `^[a-z0-9_]+$` | Restricting skill IDs to lowercase alphanumeric characters and underscores prevents URI encoding issues, shell escaping pitfalls, and case-mismatch inconsistencies across relational joins. |
| **Sticky Form State** | Re-render view with `form_data` (HTTP 200) on validation error | Instead of an immediate HTTP 302 redirect that clears user inputs upon error, re-rendering `skills.html` retains the user's entered name and description. Users only need to correct the invalid identifier rather than retyping the entire form. |
| **Error Feedback** | Red input border (`.is-invalid`) + Flash banner | When an ID conflict or format error occurs, the server sets `has_id_error=True`, rendering a highlighted `2px solid #dc2626` border and focus glow around the identifier input box for clear visual hierarchy. |
| **Referential Integrity** | Pre-delete dependency check across students & projects | Before deleting a skill, `delete_skill` queries `StudentRepository` and `ProjectRepository`. If any student possesses the skill or any project requires it, deletion is blocked with an informative flash alert (e.g. *"Cannot delete skill: still referenced by 2 student(s) and 1 project(s)"*), preventing accidental data corruption. |
| **Confirmation UX** | Custom In-App Modal Dialog | Rather than relying on browser-native `window.confirm()` popups (which look generic and vary across operating systems), an in-app CSS/JS modal was built directly into `skills.html`. It displays the skill name in brackets, an amber warning badge, a `Cancel` button, and a `Yes, Delete` danger button. |
| **Navigation State** | Client-side DOM class binding (`active`) | Added DOM initialization that adds `.active` (`color: #38bdf8`) to the Skills navigation tab on page load, providing clear visual orientation within the DSS navbar. |


## 1. Executive Summary & Status

During Week 2, I worked on **B1 — analytical metrics and solution comparison** in `app/engine/metrics.py`. The purpose was to replace mock analytical results with real metrics that can be used by the assignment engine and Team A's user interface.

### Status at a Glance

- **B1.1:** Skill-fit score and Gini coefficient implemented.
- **B1.2:** Solution indicators for feasibility, efficiency, fairness, and capacity implemented.
- **B1.3:** Comparison of two alternative solutions implemented.
- **Main files:** `app/engine/metrics.py`, `tests/test_metrics.py`
- **Verification:** The implemented B1 metric tests pass locally. Final full-suite pytest output should be recorded before submission.

---

## 2. Technical Decisions & Implementation Rationale

### 2.1 Analytical Structure

The analytical calculations were kept inside **Component B (`app/engine`)** so that the assignment engine remains independent of Flask and the visualization layer. The functions return structured dictionaries that can be consumed by Team A without requiring UI-specific logic inside the engine.

The solution indicators were divided into four categories:

- **Feasibility:** checks whether assignment rules and constraints are respected.
- **Efficiency:** measures student-project skill fit and unmet optional requirements.
- **Fairness:** evaluates preference ranks and inequality of assignment outcomes.
- **Capacity:** measures project utilisation.

---

### 2.2 Key Design Decisions

| Decision Area | Chosen Approach | Rationale |
| :--- | :--- | :--- |
| **Skill-fit scoring** | Each requirement is scored as `min(student level / required level, 1.0)` and the scores are averaged. | Creates a comparable score between 0 and 1 while preventing overqualification from increasing the score above full satisfaction. |
| **Edge cases in skill fit** | Projects without requirements receive a score of `1.0`; zero-level requirements are handled without division by zero. | Makes the metric robust for valid edge cases. |
| **Gini fairness measure** | Gini is calculated from pairwise absolute differences; empty/all-zero inputs return `0.0`, while negative inputs are rejected. | Provides a reusable measure of inequality while avoiding invalid calculations. |
| **Unranked assignments** | Unranked assignments are excluded from `mean_rank`, counted separately, and treated as one rank worse than the worst stated preference when calculating fairness comparisons. | Prevents unranked assignments from making the average rank look artificially better while still reflecting their negative fairness effect. |
| **Feasibility separated from quality** | Constraint violations are reported independently from efficiency and fairness metrics. | A solution can be identified as infeasible rather than simply appearing to have poor analytical scores. |
| **Stable indicator structure** | Fixed key names are returned for feasibility, efficiency, fairness, and capacity. | Team A and the recommendation logic read these values directly, so consistent names are necessary for integration. |
| **Solution comparison** | Changes are calculated consistently as **Solution B − Solution A**, including skill fit, mean rank, unranked assignments, and Gini. | Gives all comparison values a consistent interpretation. |
| **Changed assignments** | Only students assigned to a different project in the two solutions are included in the detailed comparison. | Keeps the comparison focused on meaningful allocation changes. |
| **Rounding** | Comparison deltas are rounded to four decimal places. | Avoids floating-point artefacts and gives stable values for tests and presentation. |
| **Trade-off summaries** | Numerical comparison results are also converted into short human-readable statements. | Makes the DSS easier to interpret for users who do not want to evaluate raw metrics alone. |

---

## 3. Verification & Documentation

The implementation was verified using `pytest`, with the B1 tests activated after the corresponding functions were implemented.

```bash
python -m pytest tests/test_metrics.py -q
python -m pytest -q
```

The B1 implementation is also documented according to the repository's solution-documentation rules, describing the main analytical decisions, data flow, modified files, and verification results.

The main integration objective is that real solutions generated by Team B can be evaluated in `metrics.py` and passed in a predictable structure to Team A's comparison and recommendation views without relying on mock analytical data.