# Project Agent Rules & Development Guidelines

Welcome to the **TECH5 Student-to-Project Assignment Decision Support System (DSS)**.

All AI coding assistants (Antigravity, Claude, Copilot, etc.) working in this repository must strictly adhere to the following project policies and architectural boundaries:

---

## 1. The "Explain-Before-Accept" Policy

> **Policy Directive:** You must explain the underlying architectural pattern and rationale **before** generating or editing code. Every line of code written must be defensible by the students during academic grading and project presentation.

### Rules of Engagement:
1. **Architectural Explanation First:** Before proposing code edits, explicitly state:
   - What architectural pattern applies (e.g., *Strategy Pattern*, *Repository Pattern*, *Component Contract / DTO*, *Blueprint/MVC*).
   - Why this pattern is chosen and which files are being touched.
   - High-level logic flow in plain business/engineering terms.
2. **Teach Upon Request:** If the student asks for clarification on any line, SQL query, mathematical constraint, or function, prioritize teaching and explaining the logic over writing more code.
3. **No Black-Box Output:** Never produce opaque, compressed, or undocumented code. Include helpful comments on non-trivial logic.
4. **Pedagogical Checkpoint:** Conclude code proposals by inviting the student to check their understanding: *"If you cannot explain every line, ask me to teach you before accepting or committing."*

Detailed rule specification is maintained in [`.agents/rules/explain_before_accept.md`](.agents/rules/explain_before_accept.md).

---

## 2. System Architecture & Boundaries

The codebase is an **in-process, two-component modular monolith** within a single Python runtime.

- **Component A: Visualization & Recommendation (`app/visualization/`):**
  - Built with Flask, Jinja2 templates, CSS, and Vanilla JS.
  - Handles routing, forms, role-based views (Admin, Coordinator, Student), scenario loading, and trade-off comparison.
- **Component B: Assignment Engine (`app/engine/`):**
  - Mathematical optimization (PuLP MILP), metrics calculation (Gini, skill fit), and diagnostics.
  - **Strict Decoupling:** Must NEVER import Flask, `request`, `session`, or Jinja2. Must remain pure headless Python.
- **Internal Component Contract (`app/contract/`):**
  - All communication between Component A and Component B goes strictly through `AssignmentEngineContract` using typed Data Transfer Objects (`RunRequest`, `ValidationOutcome`, `RunComparison`).
  - **Zero Microservices / Network Overheads:** Never introduce HTTP REST APIs, webhooks, or subprocess calls between Component A and Component B.
- **Relational Persistence (`app/persistence/`):**
  - SQLite 3NF schema (`schema.sql`) accessed via the Repository Pattern (`DatabaseManager`, `StudentRepository`, `ProjectRepository`, `SkillRepository`, `RunRepository`).

---

## 3. Testing, Verification, and Safety Constraints

- **51 Automated Tests:** The test suite contains 36 baseline passing tests and 15 xfailed target tasks (3 for Team A, 12 for Team B).
- **Never Cheat on Tests:** Never delete tests, never edit test assertions to force a pass, and never hardcode test outputs.
- **Progressive Test Activation:** When completing an issue, only remove the `@pytest.mark.xfail(...)` decorator from the targeted test once the underlying feature is fully and genuinely implemented.
- **Verification Command:** Always verify changes by running:
  ```bash
  python -m pytest -q
  ```

---

## 4. Direct Terminal Error Verification Rule

> **Policy Directive:** When a user or teammate pastes a terminal error or traceback into the chat, you must **directly verify and inspect the actual terminal output** using your terminal command execution tool rather than relying solely on the pasted snippet.

### Actions Required:
1. **Reproduce via Terminal:** Run the failing test, script, or command directly to capture complete, untruncated `stdout`, `stderr`, and exit status.
2. **Inspect the True Source:** Cross-check the live traceback against the exact lines of code in the filesystem before proposing fixes.
3. **Validate Resolution:** Re-run the command after editing to prove that the error is resolved.

Detailed rule specification is maintained in [`.agents/rules/terminal_error_diagnosis.md`](.agents/rules/terminal_error_diagnosis.md).

---

## 5. Google Python Style & Code Formatting Standards

> **Policy Directive:** All Python code must strictly adhere to the **Google Python Style Guide**, maintaining full consistency with the existing codebase.

### Standards Required:
1. **Google Docstrings:** Public modules, classes, and methods must have docstrings formatted with `Args:`, `Returns:`, and `Raises:` blocks.
2. **Type Annotations (Python 3.10+):** Complete type hints on all parameters and return types using built-in generics (`list[str]`, `dict[str, Any]`, `X | None`).
3. **Naming:** `PascalCase` for classes, `snake_case` for functions/variables, `UPPER_CASE` for constants, `_leading_underscore` for private helpers.
4. **Clean Imports:** Grouped into standard library, third-party, and local `app.*` imports. No wildcard imports (`*`).
5. **Formatting:** 4-space indentation, target 80-character line lengths, trailing commas in multi-line lists/dicts/calls.

Detailed rule specification is maintained in [`.agents/rules/google_python_style.md`](.agents/rules/google_python_style.md).

---

## 6. Git Branching & Isolated QA Subagent Workflow

> **Policy Directive:** Every issue implementation from `docs/team_related/issues/` must start on a dedicated feature branch and must pass an independent, zero-shared-context QA subagent audit (`qa-tester`) before committing or pushing to remote.

### Mandatory Workflow Gates:
1. **Pre-Implementation Branch Gate (One Issue = One Branch):**
   - Never implement directly on `main`. Before modifying any files for an issue, check `git branch --show-current`.
   - If on `main` (or another issue's branch), switch to `main`, pull latest changes, and create a new branch named `<issue-code>-<short-topic>` (e.g., `git switch -c a1.1-skills` or `git switch -c b1.1-metrics`).
2. **Pre-Commit / Pre-Push Isolated QA Gate (`qa-tester`):**
   - Before running `git commit` or `git push`, activate the workspace skill [`.agents/skills/qa-tester/SKILL.md`](.agents/skills/qa-tester/SKILL.md).
   - Define and invoke the `qa-tester` subagent (`define_subagent` / `invoke_subagent`) with **zero shared implementation context**—pass only the target issue file path (`docs/team_related/issues/<ID>.md`).
   - Block committing and pushing until the `qa-tester` subagent returns a **PASS** verdict confirming branch isolation, allowed file scope, test integrity, and passing `python -m pytest -q`.

Detailed rule specification is maintained in [`.agents/rules/git_and_qa_workflow.md`](.agents/rules/git_and_qa_workflow.md).

---

## 7. Mandatory Issue Solution Documentation Rule

> **Policy Directive:** For every issue implemented from `docs/team_related/issues/`, the agent must persistently document the architectural rationale, data flow, files modified, test evidence, and pedagogical checkpoint in a dedicated markdown file under `docs/team_related/issues_solutions/<ISSUE_ID>_solution.md` before committing.

### Standards Required:
1. **Standard Path & Naming:** Save to `docs/team_related/issues_solutions/<ISSUE_ID>_solution.md` (e.g., `A1.1_solution.md`, `B1.1_solution.md`).
2. **Required Structure:** Include:
   - Architectural Pattern Applied & Rationale
   - High-Level Logic & Data Flow Walkthrough
   - Summary of Files Changed
   - Verification & Pytest Output
   - Pedagogical Checkpoint ("Check Your Understanding" self-defense questions)
3. **Commit Inclusion:** The solution file must be staged (`git add`) and committed on the feature branch together with the code changes.
4. **Iterative Updates:** If user feedback or code review prompts subsequent enhancements, append those updates to the existing solution document.

Detailed rule specification is maintained in [`.agents/rules/solution_documentation.md`](.agents/rules/solution_documentation.md).

