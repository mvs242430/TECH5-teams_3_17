# Solution Documentation & Pedagogical Artifact Policy

## Core Principle
Students must be able to defend their architectural choices, mathematical constraints, and data flows during academic grading and project presentation. 

Whenever an AI coding assistant (Antigravity, Claude, Copilot, etc.) completes an issue from `docs/team_related/issues/`, the explanation produced under the **Explain-Before-Accept Policy** must be persistently written to a dedicated solution markdown file in `docs/team_related/issues_solutions/` before committing.

---

## 1. File Naming & Path Convention

- **Directory:** `docs/team_related/issues_solutions/`
- **File Name:** `<ISSUE_ID>_solution.md`
  - Examples: `A1.1_solution.md`, `A1.2_solution.md`, `B1.1_solution.md`, `B2.1_solution.md`
- **Topic-Specific Solutions:** For standalone tasks without an explicit single issue code, use the short topic name (e.g., `nav_bar.md`).

---

## 2. Mandatory Solution File Structure

Every solution document saved in `docs/team_related/issues_solutions/<ISSUE_ID>_solution.md` must adhere to the following template:

```markdown
# Issue <ISSUE_ID> Solution & Architectural Rationale

**Issue Title:** <Title as stated in docs/team_related/issues/<ISSUE_ID>.md>  
**Branch:** `<branch-name>`  
**Date:** <Date>  
**Author / Lead:** <Team Member Name / Role>  

---

## 1. Architectural Pattern & Design Rationale
- **Pattern Applied:** (e.g., Strategy Pattern, Repository Pattern, MVC / Flask Blueprint, Component Contract / DTOs)
- **Why Chosen:** Rationale according to the modular monolith boundaries and academic defensibility.
- **Component Scope:** Clearly identify touched components (`app/visualization/`, `app/engine/`, `app/contract/`, `app/persistence/`).

---

## 2. High-Level Logic & Data Flow Walkthrough
- Step-by-step description: Input data -> Validation -> Core Processing/Solving -> DTO Output -> UI/Persistence.
- If mathematical modeling (MILP / metrics): List decision variables, constraint formulations, and objective functions in plain English followed by algebraic equations.

---

## 3. Summary of Files Changed
| File Path | Modification Description |
| :--- | :--- |
| `app/...` | What was added or changed and why |

---

## 4. Verification & QA Status
- Un-xfailed test(s) for this issue.
- Verification command run: `.venv/bin/python -m pytest -q`.
- Exact test output (e.g., `37 passed, 14 xfailed in 0.60s`, zero regressions).

---

## 5. Check Your Understanding (Pedagogical Checkpoint)
Key self-check questions for student grading defense:
1. *Why was this pattern and file location chosen?*
2. *How is data validation, edge-case safety, or authorization enforced?*
3. *How does this implementation adhere to system boundaries?*

> **Pedagogical Checkpoint:** *"If you cannot explain every line, ask me to teach you before accepting or committing."*
```

---

## 3. Workflow Integration & Timing

1. **When to Write the File:**
   - Immediately after the implementation passes local test execution (`python -m pytest -q`) and before invoking the pre-commit QA gate (`qa-tester`).
2. **Commit Inclusion:**
   - The solution markdown file `docs/team_related/issues_solutions/<ISSUE_ID>_solution.md` must be staged (`git add`) and committed on the dedicated feature branch together with the implementation code.
3. **Subsequent Enhancements:**
   - If user feedback or code review requires further modifications to the feature (e.g., UI tweaks, edge-case handling), append these updates directly to the existing solution file under a new section (e.g., `### Updates Made to ...`).
