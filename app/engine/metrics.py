"""Calculators for feasibility, efficiency, fairness, and trade-offs.

This module provides analytical functions to evaluate solutions according to
the requirements in Section 7 of the TECH5 specification.

Students (Team B) must implement these analytical functions to compute
student-project skill fit, Gini inequality, solution indicators, and
side-by-side trade-off comparisons.
"""

from typing import Any

from app.domain import models


def calculate_assignment_skill_fit(
    student: models.Student,
    project: models.Project,
) -> tuple[float, list[str]]:

    if not project.requirements:
        return 1.0, []

    scores = []
    unmet = []

    for requirement in project.requirements:
        student_level = student.get_skill_level(requirement.skill_id)
        required_level = requirement.minimum_level

        # Avoid division by zero
        if required_level <= 0:
            score = 1.0
        else:
            score = min(student_level / required_level, 1.0)

        scores.append(score)

        if student_level < required_level:
            unmet.append(requirement.skill_id)
    

    skill_fit_score = sum(scores) / len(scores)

    return skill_fit_score, unmet



    """Calculates skill fit score and unmet requirements for a student-project pair."""

    
    """In compliance with Section 7.2 of the TECH5 specification, skill fit
    evaluates how well the candidate student satisfies the required technical
    skills of the target project.

    Args:
        student: The student under evaluation.
        project: The project under evaluation.

    Returns:
        A tuple of (skill_fit_score [0.0, 1.0], list_of_unmet_skill_ids).

    Raises:
        NotImplementedError: To be implemented by Team B.
    """
    raise NotImplementedError(
        "TODO (Team B): Implement calculate_assignment_skill_fit"
    )



def calculate_gini(values: list[float]) -> float:

    for value in values:
        if value < 0:
            raise ValueError("Gini coefficient requires non-negative values.")

    if not values:
        return 0.0

    total = sum(values)
    if total == 0:
        return 0.0

    # Calculate Gini coefficient with formula: 
    # G = (1/(2*n^2*mean)) * sum_i sum_j |x_i - x_j|

    difference = 0.0

    for value_i in values:
        for value_j in values:
            difference += abs(value_i - value_j)

    gini = difference / (2*len(values) * total)
    
    return gini

    """Calculates the Gini coefficient of inequality for non-negative values.

    In compliance with Section 7.3 of the TECH5 specification, the Gini
    coefficient measures the inequality/fairness in student preference rank
    distribution (0.0 represents perfect equality, 1.0 represents extreme inequality).

    Args:
        values: Non-negative numerical series (e.g. assigned preference ranks).

    Returns:
        The Gini coefficient in [0.0, 1.0].

    Raises:
        NotImplementedError: To be implemented by Team B.
    """
    raise NotImplementedError("TODO (Team B): Implement calculate_gini")


def compute_solution_indicators(
    students: list[models.Student],
    projects: list[models.Project],
    assignments: list[models.Assignment],
    fixed_assignments: list[models.FixedAssignment] | None = None,
) -> dict[str, Any]:

    # check for fixed assignments
    if fixed_assignments is None:
        fixed_assignments = []

    # create dictionaries for quick lookup
    student_dict = {}
    for student in students:
        student_dict[student.id] = student

    project_dict = {}
    for project in projects:
        project_dict[project.id] = project

    """Feasibility"""

    violations = []
    assigned_students = set()

    project_counts = {}
    for project in projects:
        project_counts[project.id] = 0

    for assignment in assignments:

        if assignment.student_id not in student_dict:
            violations.append(f"Unknown student: {assignment.student_id}")
            continue

        if assignment.project_id not in project_dict:
            violations.append(f"Unknown project: {assignment.project_id}")
            continue

        if assignment.student_id in assigned_students:
            violations.append(f"Student assigned multiple times: {assignment.student_id}")
            continue

    assigned_students.add(assignment.student_id)
    project_counts[assignment.project_id] += 1

    student = student_dict[assignment.student_id]
    project = project_dict[assignment.project_id]

    # Check mandatory skill requirements
    for requirement in project.requirements:
        if requirement.is_mandatory:
            student_level = student.get_skill_level(requirement.skill_id)

            if student_level < requirement.minimum_level:
                violations.append(f"Student {student.id} does not meet mandatory skill {requirement.skill_id}")

    # Check for unassigned students
    for student in students:
        if student.id not in assigned_students:
            violations.append(f"Student {student.id} is unassigned")

    # Check project capacity
    if project in projects:
        count = project_counts[project.id]

        if count < project.min_capacity:
            violations.append(f"Project {project.id} is below minimum capacity")

        if count > project.max_capacity:
            violations.append(f"Project {project.id} exceeds maximum capacity")

# check fixed assignments
student_assignments = {}
for assignment in assignments:
    student_assignments[assignment.student_id] = assignment

    for fixed in fixed_assignments:
        if fixed.student_id not in student_assignments:
            violations.append(f"Fixed assignment for unassigned student: {fixed.student_id} was not respected")

        elif (student_assignments[fixed.student_id] != fixed.project_id):
            violations.append(f"Fixed assignment violation for student {fixed.student_id}: expected {fixed.project_id}, got {student_assignments[fixed.student_id].project_id}")

    is_feasible = len(violations) == 0
        

    
    """Computes comprehensive feasibility, efficiency, and fairness indicators.

    Evaluates a solution across the four dimensions defined in the specification:
    1. Feasibility: Exact student count, capacity bounds, fixed assignments.
    2. Efficiency: Mean skill-fit score, unmet soft requirements count.
    3. Fairness: Rank distribution, mean rank, worst rank, unranked count, Gini.
    4. Capacity: Total assigned, total capacity, overall utilization, per-project.

    Args:
        students: Complete cohort of students.
        projects: Catalog of semester projects.
        assignments: List of student-to-project allocations.
        fixed_assignments: Optional list of locked pre-allocations.

    Returns:
        Dictionary containing structured indicators and diagnostic metrics:
        {
            "feasibility": {"is_feasible": bool, "violations": list[str], ...},
            "efficiency": {"mean_skill_fit": float, ...},
            "fairness": {"mean_rank": float, "worst_rank": int, "rank_gini": float, ...},
            "capacity": {"overall_utilization_pct": float, "projects": dict, ...}
        }

    Raises:
        NotImplementedError: To be implemented by Team B.
    """
    raise NotImplementedError(
        "TODO (Team B): Implement compute_solution_indicators"
    )


def compare_two_solutions(
    solution_a: models.Solution,
    solution_b: models.Solution,
) -> dict[str, Any]:
    """Performs detailed trade-off comparison between two alternative solutions.

    In compliance with Section 7.4 of the specification, identifies:
    - Changed student allocations between solutions A and B.
    - Improved and worsened student preference ranks.
    - Deltas in mean skill-fit, mean rank, and Gini coefficient.
    - Human-readable trade-off summary statements.

    Args:
        solution_a: Baseline solution.
        solution_b: Alternative solution to compare against A.

    Returns:
        Dictionary documenting differences, changed assignments, and trade-offs:
        {
            "solution_a_id": str,
            "solution_b_id": str,
            "is_distinct": bool,
            "changed_students_count": int,
            "changed_assignments": list[dict[str, Any]],
            "delta_metrics": dict[str, Any],
            "trade_off_summary": list[str]
        }

    Raises:
        NotImplementedError: To be implemented by Team B.
    """
    raise NotImplementedError("TODO (Team B): Implement compare_two_solutions")
