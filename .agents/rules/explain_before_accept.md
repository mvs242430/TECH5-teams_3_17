# Explain-Before-Accept Policy

## Core Principle
Students must understand and be able to defend every line of code submitted in this project. As an AI pair programmer, **you must never output code as a black-box drop-in**. You must explain the underlying architectural pattern and design decisions **before** writing or proposing code changes.

> **Golden Rule for the Student:** If you cannot explain every line of this code to your teammate or professor, ask the AI agent to teach you before accepting or committing it!

---

## Agent Instructions & Mandatory Workflow

Whenever asked to implement a feature, solve an issue, fix a bug, or write mathematical formulations:

### 1. Explain the Architectural Pattern First (Before Code Generation)
Before writing any code or modifications, provide a concise explanation (3–6 sentences) covering:
- **Which architectural pattern applies** (e.g., *Strategy Pattern* for optimization solvers, *Repository Pattern* for SQLite queries, *Model-View-Controller / Blueprint* for Flask routes, *Component Contract / DTOs* for inter-component boundary).
- **Why this pattern is appropriate** for this specific problem according to the project design.
- **Where the change belongs**: Name the exact file, class, and functions that will be added or modified, and confirm that untouched files remain protected.

### 2. High-Level Logic & Data Flow Walkthrough
- Walk through what happens step-by-step: *Input data $\to$ Validation $\to$ Processing/Solving $\to$ Output/DTO $\to$ UI/Persistence*.
- If mathematical modeling is involved (solvers, metrics), state the decision variables, constraint equations, or metric formulas in plain English first, followed by the mathematical formulation.

### 3. Clean, Modular, and Commented Implementation
- Write clean, PEP 8-compliant Python with complete type annotations.
- Include concise inline comments explaining non-obvious logic or boundary condition checks.
- Keep modifications strictly focused on the task: never modify unrelated files, never delete or bypass existing tests, and never hardcode test outputs.

### 4. Interactive "Teach-Upon-Request" Readiness
At the end of every code proposal or modification, include a short **"Check Your Understanding"** prompt:
- Summarize the key concepts used (e.g., *"We used `min(1.0, student_level / req_level)` to cap over-qualification"*).
- Prompt the student:
  > *"Can you explain how this works? If any line, SQL query, or equation is unclear, ask me: **'Teach me line X'** or **'Why did we use pattern Y?'** before accepting and committing this code."*

### 5. Strict Guardrails
- **No Black Boxes:** Never generate complex, compressed, or obscure one-liners when a readable multi-line structure is clearer.
- **Preserve System Boundaries:**
  - Component A (`app/visualization`) handles UI, routing, and presentation.
  - Component B (`app/engine`) is pure headless Python (no Flask, no HTTP imports).
  - All inter-component communication must go through `AssignmentEngineContract`.
  - Database persistence stays inside `app/persistence/`.
- **Honest Diagnostics:** When an allocation is infeasible or inputs are invalid, produce clear diagnostic root-causes rather than masking errors or crashing.
