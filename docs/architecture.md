# Deliverable 3: System Architecture Specification & Design Rationale

## 1. Executive Architectural Overview

The **TECH5 Student-to-Project Assignment Decision Support System (DSS)** is an integrated application engineered for the Norwegian School of Economics (NHH). It solves the complex combinatorial allocation problem of assigning a cohort of students to semester research and consulting projects based on multidimensional criteria: **student ranked preferences**, **student skill proficiencies**, **project skill requirements**, **project capacity bounds**, and **administrative pre-allocation locks**.

In accordance with the updated project specification (Sections 5, 7, 8, and 15), the system is architected as **two decoupled, modular application components** running within a single integrated Python application:

1. **Component A (Visualization & Recommendation Component)**:
   - Manages user workflow, cohort data inspection, CRUD interfaces, benchmark scenario seeding, role switching (Admin, Coordinator, Student Viewer), multi-solution visual side-by-side trade-off comparisons, and evidence-backed recommendations.
2. **Component B (Assignment Engine)**:
   - Validates input feasibility, executes mathematical Integer Linear Programming (PuLP) using the **Strategy Pattern** (`PreferenceOrientedSolver`, `SkillFitOrientedSolver`, `BalancedTradeoffSolver`), generates distinct Pareto alternatives via integer no-good cuts, evaluates multidimensional quality/fairness metrics, and captures diagnostics.

The two components are mediated strictly by an **internal Python component contract** (`app/contract/contract.py`), backed by a shared relational SQLite 3NF persistence layer (`app/persistence`).

---

## 2. Component Diagram & Internal Interface

```mermaid
flowchart TD
    subgraph Component_A["Component A: Visualization & Recommendation (app/visualization)"]
        UI[Jinja2 HTML5 / CSS3 Responsive UI]
        WebRoutes[Flask Web Blueprint: visualization_web]
        RoleAuth[Role-Based Access Control: Admin / Coord / Student]
        RecPresenter[Recommendation & Trade-Off Presentation]
    end

    subgraph InternalContract["Internal Component Contract (app/contract/contract.py)"]
        ContractABC["AssignmentEngineContract (ABC)"]
        DTOs["RunRequest | ValidationOutcome | DiagnosticInfo | RunComparison"]
    end

    subgraph Component_B["Component B: Assignment Engine (app/engine)"]
        SolverEngine["AssignmentEngine (implements Contract)"]
        StrategyPattern["Strategy Pattern: Preference, Skill-Fit, Balanced"]
        PuLPSolver["PuLP ILP Solver & Pareto No-Good Cuts"]
        MetricsEngine["Analytical Indicators & Gini Fairness Engine"]
        ValidationEngine["Domain Feasibility Validator"]
    end

    subgraph Persistence["Shared Relational Persistence (app/persistence)"]
        DBMgr["DatabaseManager (SQLite WAL Mode, Foreign Keys)"]
        Repos["Repository Pattern: Students, Projects, Skills, Runs"]
        Schema["3NF Relational Schema & Performance Indexes"]
    end

    UI --> WebRoutes
    WebRoutes --> RoleAuth
    WebRoutes --> RecPresenter
    WebRoutes -->|Invokes Python Methods| ContractABC
    ContractABC -.->|Implemented By| SolverEngine

    SolverEngine --> StrategyPattern
    StrategyPattern --> PuLPSolver
    SolverEngine --> MetricsEngine
    SolverEngine --> ValidationEngine

    WebRoutes --> Repos
    SolverEngine --> Repos
    Repos --> DBMgr
    DBMgr --> Schema
```

---

## 3. Design Rationale: Two-Component Modular Monolith vs. Microservices

### 3.1 Motivation for In-Process Two-Component Architecture
1. **Curricular Alignment & Feasibility**:
   - The primary pedagogical objective is object-oriented software design, relational database integration, and decision support. Microservices introduce substantial operational complexity (distributed networking, ports, HTTP status translation, retries, serialization boilerplate) that distracts from the core analytical problem.
2. **High Modularity Without Operational Overhead**:
   - Component A and Component B maintain strict separation of concerns. Component B has zero knowledge of Flask request objects, HTML templates, or cookies. It can be instantiated, validated, and tested headlessly in pure Python scripts or test harnesses.
3. **Type Safety & Compiler Diagnostics**:
   - In-process contract calls pass typed dataclasses (`RunRequest`, `ValidationOutcome`, `RunComparison`) directly. Type checkers (`mypy`, `pylint`) and IDEs provide immediate syntax and type validation, eliminating runtime JSON schema mismatch errors.
4. **Performance & Determinism**:
   - Direct method invocations eliminate JSON serialization/deserialization CPU cycles and network socket latency, allowing instant interactive comparison and optimization execution.

---

## 4. Object-Oriented Architecture & Design Patterns

### 4.1 Strategy Pattern (Assignment Algorithms)
The Assignment Engine defines an abstract base strategy `AssignmentStrategy(abc.ABC)` with concrete subclasses:
- `PreferenceOrientedSolver`: Maximizes student ranked preferences (assigning rank 1 awards highest utility, penalizing unranked assignments).
- `SkillFitOrientedSolver`: Maximizes qualification fit across all required project skills.
- `BalancedTradeoffSolver`: Combines normalized preference satisfaction and skill coverage using Pareto scalarization.

```
       +-----------------------------------+
       |     AssignmentStrategy (ABC)      |
       +-----------------------------------+
       | + calculate_cost_or_utility(...)  |
       | + solve(...)                      |
       +-----------------------------------+
             ^               ^          ^
             |               |          |
  +----------+----+   +------+----+   +-+----------------+
  | Preference    |   | SkillFit  |   | BalancedTradeoff |
  | OrientedSolver|   | Solver    |   | Solver           |
  +---------------+   +-----------+   +------------------+
```

### 4.2 Abstract Contract Pattern (Component Boundary)
`AssignmentEngineContract` defines the public interface required by Component A. Concrete `AssignmentEngine` implements all contract methods, ensuring that any mock or alternative solver can be substituted without touching Component A.

### 4.3 Repository Pattern (Data Access Layer)
Persistence operations are encapsulated into domain repositories:
- `StudentRepository`: Manages `students`, `student_skills`, and `preferences`.
- `ProjectRepository`: Manages `projects` and `project_requirements`.
- `SkillRepository`: Manages defined competencies.
- `FixedAssignmentRepository`: Manages administrative pre-allocation locks.
- `RunRepository`: Manages `assignment_runs`, `solutions`, and `assignments`.

---

## 5. Relational Database Architecture

```mermaid
erDiagram
    students ||--o{ student_skills : "possesses"
    skills ||--o{ student_skills : "classified under"
    students ||--o{ preferences : "submits"
    projects ||--o{ preferences : "ranked in"
    projects ||--o{ project_requirements : "demands"
    skills ||--o{ project_requirements : "specified by"
    students ||--o{ fixed_assignments : "locked to"
    projects ||--o{ fixed_assignments : "hosts"
    assignment_runs ||--o{ solutions : "produces"
    solutions ||--o{ assignments : "allocates"
    students ||--o{ assignments : "assigned"
    projects ||--o{ assignments : "contains"

    students {
        TEXT id PK
        TEXT display_name
    }
    projects {
        TEXT id PK
        TEXT title
        TEXT description
        INTEGER min_capacity
        INTEGER max_capacity
    }
    skills {
        TEXT id PK
        TEXT name
        TEXT description
    }
    student_skills {
        TEXT student_id PK,FK
        TEXT skill_id PK,FK
        INTEGER level
    }
    project_requirements {
        TEXT project_id PK,FK
        TEXT skill_id PK,FK
        INTEGER minimum_level
        INTEGER is_mandatory
    }
    preferences {
        TEXT student_id PK,FK
        TEXT project_id PK,FK
        INTEGER rank
    }
    fixed_assignments {
        TEXT student_id PK,FK
        TEXT project_id FK
        TEXT status
        TEXT reason
    }
    assignment_runs {
        TEXT id PK
        TEXT created_at
        TEXT status
        TEXT configuration
        TEXT diagnostics
    }
    solutions {
        TEXT id PK
        TEXT run_id FK
        INTEGER alternative_number
        TEXT strategy_name
        REAL objective_value
        TEXT indicators
        TEXT warnings
        TEXT diagnostics
    }
    assignments {
        INTEGER id PK
        TEXT solution_id FK
        TEXT student_id FK
        TEXT project_id FK
        INTEGER is_fixed
        INTEGER preference_rank
        REAL skill_fit_score
        TEXT unmet_requirements
    }
```

---

## 6. Role-Based Access Control (RBAC)

The application models three explicit business roles in `app/visualization/auth.py`:
1. **Course Administrator (`ADMIN`)**: Full authorization. Can edit students, projects, skills, and fixed assignments, trigger optimization runs, and switch active roles.
2. **Program Coordinator (`COORDINATOR`)**: Operational authorization. Can manage fixed assignment locks, trigger solver runs, and inspect detailed recommendations and comparisons. Read-only on baseline student data.
3. **Student Viewer (`STUDENT`)**: Transparency view. Can browse anonymized dashboard metrics, project descriptions, and high-level allocation summaries. Mutating actions are disabled.

### 6.1 Role × Action Table

*Added by the students (issue A2.4). It records how the code follows §6
above; §6 is the teacher's specification and is not changed.*

Every route that changes data checks the current role with one helper from
`app/visualization/auth.py` before it touches the database. Pages that show
individual student data, and the form pages, check the role the same way
before they render. A refused request flashes "Permission denied for current
role." and changes nothing. Templates get the same helpers as flags
(`can_edit`, `can_optimize`, `can_manage_locks`, `can_view_records` and
`can_switch_roles`, from `inject_template_globals` in `routes.py`), so a role
only sees the links and buttons it can use.

| Action | Route(s) | Helper checked | Admin | Coordinator | Student Viewer |
| :--- | :--- | :--- | :---: | :---: | :---: |
| View the dashboard, projects, skills, runs and recommendations | `GET /`, `/projects`, `/skills`, `/runs/<id>`, `/recommendations/<id>` | none (read only) | Yes | Yes | Yes, summaries only |
| View solutions and comparisons | `GET /solutions/<id>`, `/compare` | none for the page; student names use `can_view_student_records()` | Yes | Yes | Yes, student IDs only (no names) |
| View students, preferences and fixed locks | `GET /students`, `/preferences`, `/fixed-assignments` | `can_view_student_records()` | Yes | Yes | No |
| Open the student and project forms | `GET /students/new`, `/students/<id>/edit`, `/projects/new`, `/projects/<id>/edit` | `can_edit_cohort_data()` | Yes | No | No |
| Create, edit or delete students | `POST /students/new`, `/students/<id>/edit`, `/students/<id>/delete` | `can_edit_cohort_data()` | Yes | No | No |
| Create, edit or delete projects | `POST /projects/new`, `/projects/<id>/edit`, `/projects/<id>/delete` | `can_edit_cohort_data()` | Yes | No | No |
| Create or delete skills | `POST /skills/new`, `/skills/<id>/delete` | `can_edit_cohort_data()` | Yes | No | No |
| Open the benchmark scenarios page | `GET /scenarios` | `can_edit_cohort_data()` | Yes | No | No |
| Load a benchmark scenario (replaces the whole cohort) | `POST /load-scenario/<name>` | `can_edit_cohort_data()` | Yes | No | No |
| Clear all cohort data | `POST /clear-data` | `can_edit_cohort_data()` | Yes | No | No |
| Create or release a fixed-assignment lock | `POST /fixed-assignments/new`, `/fixed-assignments/<student_id>/delete` | `can_manage_fixed_assignments()` | Yes | Yes | No |
| Trigger an optimisation run | `POST /runs/trigger` | `can_trigger_optimization()` | Yes | Yes | No |
| Lock a student from a solution and re-run | `POST /solutions/<id>/lock-and-rerun` | `can_manage_fixed_assignments()` and `can_trigger_optimization()` | Yes | Yes | No |
| Clear all runs and solutions | `POST /clear-solutions` | `can_trigger_optimization()` | Yes | Yes | No |
| Switch to any role | `POST /set-role` | `can_switch_to_role()` | Yes | No | No |
| Return to Administrator | `POST /set-role` with `role=ADMIN` | `can_switch_to_role()` | Yes | Yes | Yes |

Notes:
- **Coordinator and cohort data.** §6 says the Coordinator is "Read-only on
  baseline student data" and lists only locks, runs and inspection. The
  teacher's starter code also lets only the Admin edit cohort data. So the
  Coordinator cannot edit students, preferences, projects or skills.
  `docs/team_reflection_and_rubric.md` §1.1 says the forms let "coordinators
  and administrators" edit this data; we read that as naming both roles as
  the forms' users overall, because §6 gives the rights of each role. The
  team chose this reading on 2026-11-03.
- **Student Viewer, summaries & pseudonymized IDs.** §6 allows "anonymized
  dashboard metrics, project descriptions, and high-level allocation
  summaries". The Student Viewer therefore cannot open the students,
  preferences, fixed locks or scenarios pages, and their links are hidden. On
  solution and compare pages, allocation rows are pseudonymized to student IDs
  only (real names are omitted from the template context so a student can look
  up their own ID without seeing classmates' names). On run and solution pages,
  diagnostics and notices are hidden too, because they can name a student (for
  example "Student 'Alice Chen' (S01) has submitted no ranked preferences").
  Indicators, project capacity, rank distribution, recommendations and counts
  stay visible.
- **Role switching.** §6 gives "switch active roles" to the Admin, so only
  the Admin sees the role list. The prototype has no login, so the other
  roles see a "Return to Administrator" button instead; it stands in for
  signing in again, and without it a Student Viewer could never leave the
  role. This is not security: anyone at the keyboard can go back to Admin.
  A real deployment would take the role from sign-in.
- Fixed locks have their own helper, `can_manage_fixed_assignments()`, even
  though it allows the same roles as `can_trigger_optimization()` today.
  Running the solver and changing its inputs are separate rules, so changing
  one does not silently change the other.
- The test `test_student_viewer_cannot_mutate` in
  `tests/test_visualization_component.py` posts to every `POST` route in this
  table as a Student Viewer and checks that no table in the database changed.
  `test_mutating_route_list_covers_every_post_route` fails if a new `POST`
  route is added without being added to that test. The tests under "Teacher's
  role rules" in the same file cover the read pages, form pages and role
  switching.
