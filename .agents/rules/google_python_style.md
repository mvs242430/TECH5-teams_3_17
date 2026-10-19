# Google Python Style & Formatting Guide

## Core Directive
All Python code written or modified in this repository must strictly adhere to the **Google Python Style Guide**.

The existing codebase (`app/domain/`, `app/contract/`, `app/engine/`, `app/persistence/`) is authored following this standard. Every new class, function, method, and test must seamlessly match this style.

---

## 1. Google-Style Docstrings (Mandatory)

Every public module, class, function, and method must have a descriptive docstring formatted with Google conventions:

```python
def calculate_assignment_skill_fit(
    student: models.Student,
    project: models.Project,
) -> tuple[float, list[str]]:
    """Calculates skill fit score and unmet requirements for a student-project pair.

    Evaluates how well the candidate student satisfies the required technical
    skills of the target project, computing the ratio against minimum levels.

    Args:
        student: The student under evaluation with declared skill levels.
        project: The target semester project with declared skill requirements.

    Returns:
        A tuple of (skill_fit_score [0.0, 1.0], list_of_unmet_skill_ids).

    Raises:
        ValueError: If student or project records contain invalid data.
    """
```

### Docstring Rules:
- **One-line summary:** First line must be a concise, imperative sentence ending in a period.
- **Args section:** Format as `<parameter_name>: Description`. Do NOT repeat type names inside the description if already type-annotated.
- **Returns section:** Describe the return value and its range/semantics.
- **Raises section:** List any explicitly raised exceptions.

---

## 2. Modern Type Annotations (PEP 484, PEP 585, PEP 604)

- Every function and method signature must include complete type annotations for all parameters and the return type (`-> None`, `-> float`, etc.).
- Use standard built-in generic collections (Python 3.10+):
  - `list[str]`, `dict[str, Any]`, `set[tuple[str, str]]`, `tuple[str, int]`
- Use the pipe operator `|` for unions and optional types:
  - `repositories.RunRepository | None` instead of `Optional[RunRepository]`
  - `int | float` instead of `Union[int, float]`
- Use `from typing import Any` when generic untyped dictionaries are necessary.

---

## 3. Naming Conventions

| Entity | Convention | Example |
|---|---|---|
| **Packages & Modules** | `snake_case` | `solvers.py`, `demo_data.py` |
| **Classes & Exceptions** | `PascalCase` | `AssignmentEngine`, `PreferenceOrientedSolver` |
| **Functions & Methods** | `snake_case` | `calculate_gini()`, `execute_run()` |
| **Variables & Attributes** | `snake_case` | `student_id`, `objective_value` |
| **Constants** | `UPPER_CASE` | `PULP_TIME_LIMIT_SECONDS`, `DEFAULT_STRATEGY` |
| **Private / Internal** | `_leading_underscore` | `_build_base_model()`, `_solve_single()` |

---

## 4. Imports Organization & Cleanliness

Imports must be grouped in the following order, separated by a single blank line:
1. **Standard library imports** (`abc`, `dataclasses`, `logging`, `typing`, `uuid`)
2. **Third-party library imports** (`flask`, `pulp`, `pytest`)
3. **Application / local imports** (`from app.contract import contract`, `from app.domain import models`)

### Rules:
- Use absolute imports within the `app` package.
- **Never use wildcard imports:** `from app.domain.models import *` is strictly forbidden.
- Sort imports alphabetically within each group.

---

## 5. Formatting & Code Structure

- **Indentation:** Exactly 4 spaces per indentation level (no tabs).
- **Line Length:** Target 80 characters (maximum 88 characters for readability). Break long function definitions, tuples, and mathematical expressions across multiple lines with trailing commas.
- **Trailing Commas:** Always include trailing commas in multi-line parameter lists, dictionaries, lists, and tuples for clean Git diffs.
- **Comparisons:**
  - Use `is None` or `is not None` to check for `None` (never `== None`).
  - Use `if not sequence:` to check for empty collections.
  - Avoid comparing booleans to `True` or `False` (use `if is_mandatory:` not `if is_mandatory == True:`).
- **Defensive Error Handling:** Handle specific exceptions (`KeyError`, `ValueError`, `NotImplementedError`) rather than catching bare `except:`.
