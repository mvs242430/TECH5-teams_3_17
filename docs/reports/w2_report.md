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
| **Julia** | A1 | — | — |
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
