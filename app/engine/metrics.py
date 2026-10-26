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
    """Calculates skill fit score and unmet requirements for a student-project pair.

    In compliance with Section 7.2 of the TECH5 specification, skill fit
    evaluates how well the candidate student satisfies the required technical
    skills of the target project.

    Args:
        student: The student under evaluation.
        project: The project under evaluation.

    Returns:
        A tuple of (skill_fit_score [0.0, 1.0], list_of_unmet_skill_ids).
    """
    # Check if project has requirements; if not, skill fit is 100% and no unmet requirements
    if not project.requirements:
        return 1.0, []

    # Store requirement score and any unmet skills
    scores: list[float] = []
    unmet: list[str] = []

    # Go through all requirements and calculate skill fit score for each
    for requirement in project.requirements:
        student_level = student.get_skill_level(requirement.skill_id)
        required_level = requirement.minimum_level

        # Avoid division by zero
        if required_level <= 0:
            score = 1.0
        # Calculate score as ratio of student's skill level to required level
        else:
            score = min(student_level / required_level, 1.0)

        scores.append(score)

        # Record unmet requirement if student's skill level is below the required level
        if student_level < required_level:
            unmet.append(requirement.skill_id)

    # Calculate average skill fit score across all requirements
    skill_fit_score = sum(scores) / len(scores)

    # Return skill fit score and list of unmet requirements
    return skill_fit_score, unmet


def calculate_gini(values: list[float]) -> float:
    """Calculates the Gini coefficient of inequality for non-negative values.

    In compliance with Section 7.3 of the TECH5 specification, the Gini
    coefficient measures the inequality/fairness in student preference rank
    distribution (0.0 represents perfect equality, 1.0 represents extreme
    inequality).

    Args:
        values: Non-negative numerical series (e.g. assigned preference ranks).

    Returns:
        The Gini coefficient in [0.0, 1.0].

    Raises:
        ValueError: If any value in values is negative.
    """
    # Gini coefficient only defined for non-negative values.
    for value in values:
        if value < 0:
            raise ValueError("Gini coefficient requires non-negative values.")

    # Empty list means no inequality
    if not values:
        return 0.0

    # Calculate sum of values
    total = sum(values)
    if total == 0:
        return 0.0

    # Calculate Gini coefficient with formula:
    # G = (1/(2*n^2*mean)) * sum_i sum_j |x_i - x_j|

    # Store differences
    difference = 0.0

    # Calculate sum of absolute differences between all pairs of values
    for value_i in values:
        for value_j in values:
            difference += abs(value_i - value_j)

    # Calculate Gini coefficient
    gini = difference / (2 * len(values) * total)

    # Return Gini coefficient
    return gini


def compute_solution_indicators(
    students: list[models.Student],
    projects: list[models.Project],
    assignments: list[models.Assignment],
    fixed_assignments: list[models.FixedAssignment] | None = None,
) -> dict[str, Any]:
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
    """
    # Check for fixed assignments
    if fixed_assignments is None:
        fixed_assignments = []

    # Create dictionaries for quick lookup using id
    student_dict: dict[str, models.Student] = {}
    for student in students:
        student_dict[student.id] = student

    project_dict: dict[str, models.Project] = {}
    for project in projects:
        project_dict[project.id] = project

    # 1. Feasibility
    violations: list[str] = []
    assigned_students: set[str] = set()
    valid_assignments: list[models.Assignment] = []

    # Count assignments per project
    project_counts: dict[str, int] = {}
    for project in projects:
        project_counts[project.id] = 0

    # Check each assignment for feasibility violations
    for assignment in assignments:
        # Check if student id exists
        if assignment.student_id not in student_dict:
            violations.append(f"Unknown student: {assignment.student_id}")
            continue

        # Check if project id exists
        if assignment.project_id not in project_dict:
            violations.append(f"Unknown project: {assignment.project_id}")
            continue

        # Check if student has not been assigned multiple times
        if assignment.student_id in assigned_students:
            violations.append(
                f"Student assigned multiple times: {assignment.student_id}"
            )
            continue

        # Register student as assigned and increment project count
        assigned_students.add(assignment.student_id)
        project_counts[assignment.project_id] += 1
        # Exclude unknown IDs and duplicates from the calculated metrics.
        valid_assignments.append(assignment)

        # Get student and project objects
        student = student_dict[assignment.student_id]
        project = project_dict[assignment.project_id]

        # Check mandatory skill requirements
        for requirement in project.requirements:
            if requirement.is_mandatory:
                student_level = student.get_skill_level(requirement.skill_id)

                # If student's skill level is below the mandatory requirement, record violation
                if student_level < requirement.minimum_level:
                    violations.append(
                        f"Student {student.id} does not meet mandatory skill "
                        f"{requirement.skill_id}"
                    )

    # Check for unassigned students
    for student in students:
        if student.id not in assigned_students:
            violations.append(f"Student {student.id} is unassigned")

    # Check project capacity
    for project in projects:
        count = project_counts[project.id]

        if count < project.min_capacity:
            violations.append(
                f"Project {project.id} is below minimum capacity"
            )

        if count > project.max_capacity:
            violations.append(
                f"Project {project.id} exceeds maximum capacity"
            )

    # Create a dictionary of student assignments
    student_assignments: dict[str, models.Assignment] = {}
    for assignment in valid_assignments:
        student_assignments[assignment.student_id] = assignment

    # Check if fixed assignments are respected
    for fixed in fixed_assignments:
        if fixed.student_id not in student_assignments:
            violations.append(
                f"Fixed assignment for unassigned student: {fixed.student_id} "
                "was not respected"
            )
        elif (
            student_assignments[fixed.student_id].project_id
            != fixed.project_id
        ):
            violations.append(
                f"Fixed assignment for student {fixed.student_id} "
                "was not respected"
            )

    # Solution is feasible if there are no violations
    is_feasible = len(violations) == 0

    # 2. Efficiency
    total_skill_fit = 0.0
    unmet_requirements = 0

    for assignment in valid_assignments:
        # Calculate skill fit score for each assignment
        total_skill_fit += assignment.skill_fit_score

        # Get project for this assignment
        project = project_dict.get(assignment.project_id)

        # Counts unmet soft requirements (non-mandatory)
        if project is not None:
            for skill_id in assignment.unmet_requirements:
                for requirement in project.requirements:
                    if (
                        requirement.skill_id == skill_id
                        and not requirement.is_mandatory
                    ):
                        unmet_requirements += 1

    # Calculate mean skill fit score
    if valid_assignments:
        mean_skill_fit = round(total_skill_fit / len(valid_assignments), 4)
    else:
        mean_skill_fit = 0.0
    total_skill_fit = round(total_skill_fit, 4)

    # 3. Fairness
    # Store preference ranks and counts for Gini calculation
    ranks: list[int] = []
    rank_distribution: dict[str, int] = {}
    unranked_count = 0

    # Count preference ranks and unranked students
    for assignment in valid_assignments:
        if assignment.preference_rank is None:
            unranked_count += 1
        else:
            rank = assignment.preference_rank
            ranks.append(rank)

            # Get key for rank distribution dictionary
            key = f"rank_{rank}"

            if key not in rank_distribution:
                rank_distribution[key] = 0

            rank_distribution[key] += 1

    # Average preference rank
    if ranks:
        mean_rank = round(sum(ranks) / len(ranks), 2)
    else:
        mean_rank = 0.0

    # Find largest preference rank
    max_preference_rank = 0

    for student in students:
        for preference in student.preferences:
            if preference.rank > max_preference_rank:
                max_preference_rank = preference.rank

    # Treat unranked project as one rank worse than the worst ranked project
    unranked_rank = max_preference_rank + 1

    if unranked_count > 0:
        worst_rank = unranked_rank
    elif ranks:
        worst_rank = max(ranks)
    else:
        worst_rank = 0

    # Create ranks list for Gini calculation, including unranked students
    fairness_ranks = [float(r) for r in ranks] + [
        float(unranked_rank)
    ] * unranked_count

    rank_gini = round(calculate_gini(fairness_ranks), 4)

    # Calculate variance of preference ranks
    if fairness_ranks:
        fairness_mean = sum(fairness_ranks) / len(fairness_ranks)
        squared_differences = 0.0

        for rank_val in fairness_ranks:
            squared_differences += (rank_val - fairness_mean) ** 2

        rank_variance = round(squared_differences / len(fairness_ranks), 4)
    else:
        rank_variance = 0.0

    # Calculate percentage of unranked students
    if students:
        unranked_pct = round(unranked_count / len(students) * 100, 1)
    else:
        unranked_pct = 0.0

    # 4. Capacity
    total_capacity = 0
    project_utilization: dict[str, dict[str, Any]] = {}

    # Calculate each project capacity utilization
    for project in projects:
        total_capacity += project.max_capacity

        assigned_count = project_counts[project.id]

        if project.max_capacity > 0:
            utilization = round(
                assigned_count / project.max_capacity * 100, 1
            )
        else:
            utilization = 0.0

        # Store project's capacity metrics
        project_utilization[project.id] = {
            "assigned_count": assigned_count,
            "min_capacity": project.min_capacity,
            "max_capacity": project.max_capacity,
            "utilization_pct": utilization,
        }

    # Total capacity utilization across all projects
    if total_capacity > 0:
        overall_utilization = round(
            len(valid_assignments) / total_capacity * 100, 1
        )
    else:
        overall_utilization = 0.0

    # Return structured dictionary of answers for feasibility, efficiency, fairness, and capacity indicators
    return {
        "feasibility": {
            "is_feasible": is_feasible,
            "violations": violations,
            "assigned_count": len(valid_assignments),
            "total_students": len(students),
        },
        "efficiency": {
            "mean_skill_fit": mean_skill_fit,
            "unmet_soft_requirements_count": unmet_requirements,
            "total_skill_fit_sum": total_skill_fit,
        },
        "fairness": {
            "rank_distribution": rank_distribution,
            "mean_rank": mean_rank,
            "worst_rank": worst_rank,
            "unranked_count": unranked_count,
            "unranked_pct": unranked_pct,
            "rank_gini": rank_gini,
            "rank_variance": rank_variance,
        },
        "capacity": {
            "total_assigned": len(valid_assignments),
            "total_capacity": total_capacity,
            "overall_utilization_pct": overall_utilization,
            "projects": project_utilization,
        },
    }


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
        ValueError: If solution_a and solution_b do not contain the same students.
    """
    # Create dictionaries for quick lookup with student id
    assignments_a: dict[str, models.Assignment] = {}
    for assignment in solution_a.assignments:
        assignments_a[assignment.student_id] = assignment

    assignments_b: dict[str, models.Assignment] = {}
    for assignment in solution_b.assignments:
        assignments_b[assignment.student_id] = assignment

    # Both solutions must have the same students to compare
    if assignments_a.keys() != assignments_b.keys():
        raise ValueError("Solutions must have the same students to compare.")

    # Find penalty rank for unranked assignments
    all_ranks: list[int] = []

    for assignment in solution_a.assignments:
        if assignment.preference_rank is not None:
            all_ranks.append(assignment.preference_rank)

    for assignment in solution_b.assignments:
        if assignment.preference_rank is not None:
            all_ranks.append(assignment.preference_rank)

    if all_ranks:
        unranked_rank = max(all_ranks) + 1
    else:
        unranked_rank = 1

    # Store changed assignments and counts of rank improvements/worsenings
    changed_assignments: list[dict[str, Any]] = []
    rank_improved_count = 0
    rank_worsened_count = 0

    # Compare each student's assignment in solution A and B
    for student_id in assignments_a:
        assignment_a = assignments_a[student_id]
        assignment_b = assignments_b[student_id]

        # Record students whose project changed
        if assignment_a.project_id != assignment_b.project_id:
            rank_a = assignment_a.preference_rank
            rank_b = assignment_b.preference_rank

            # Use penalty rank when assignment is unranked
            if rank_a is None:
                compare_rank_a = unranked_rank
            else:
                compare_rank_a = rank_a

            if rank_b is None:
                compare_rank_b = unranked_rank
            else:
                compare_rank_b = rank_b

            # Positive delta means student got worse rank
            rank_delta = compare_rank_b - compare_rank_a

            if rank_delta < 0:
                rank_improved_count += 1
            elif rank_delta > 0:
                rank_worsened_count += 1

            changed_assignments.append(
                {
                    "student_id": student_id,
                    "student_name": student_id,
                    "project_a_id": assignment_a.project_id,
                    "project_a_title": assignment_a.project_id,
                    "project_b_id": assignment_b.project_id,
                    "project_b_title": assignment_b.project_id,
                    "rank_a": rank_a,
                    "rank_b": rank_b,
                    "rank_delta": rank_delta,
                }
            )

    # Get indicators for both solutions
    efficiency_a = solution_a.indicators.get("efficiency", {})
    efficiency_b = solution_b.indicators.get("efficiency", {})

    fairness_a = solution_a.indicators.get("fairness", {})
    fairness_b = solution_b.indicators.get("fairness", {})

    # Calculate changes from solution A to B
    delta_mean_skill_fit = round(
        efficiency_b.get("mean_skill_fit", 0.0)
        - efficiency_a.get("mean_skill_fit", 0.0),
        4,
    )

    delta_mean_rank = round(
        fairness_b.get("mean_rank", 0.0) - fairness_a.get("mean_rank", 0.0),
        4,
    )

    delta_unranked_count = fairness_b.get(
        "unranked_count", 0
    ) - fairness_a.get("unranked_count", 0)

    delta_gini = round(
        fairness_b.get("rank_gini", 0.0) - fairness_a.get("rank_gini", 0.0),
        4,
    )

    # Store metric changes
    delta_metrics = {
        "mean_skill_fit_delta": delta_mean_skill_fit,
        "mean_rank_delta": delta_mean_rank,
        "unranked_count_delta": delta_unranked_count,
        "gini_delta": delta_gini,
    }

    # Trade-off summary statements
    trade_off_summary: list[str] = []

    # Compare average skill fit
    if delta_mean_skill_fit > 0:
        trade_off_summary.append(
            "Average skill fit improved by "
            f"{round(delta_mean_skill_fit * 100, 2)}%."
        )
    elif delta_mean_skill_fit < 0:
        trade_off_summary.append(
            "Average skill fit worsened by "
            f"{round(abs(delta_mean_skill_fit) * 100, 2)}%."
        )

    # Compare average preference rank
    if delta_mean_rank > 0:
        trade_off_summary.append(
            f"Average preference rank worsened by {delta_mean_rank}."
        )
    elif delta_mean_rank < 0:
        trade_off_summary.append(
            f"Average preference rank improved by {abs(delta_mean_rank)}."
        )

    # Compare changes count
    if rank_worsened_count > 0:
        trade_off_summary.append(
            f"{rank_worsened_count} students worsened their preference rank."
        )
    if rank_improved_count > 0:
        trade_off_summary.append(
            f"{rank_improved_count} students improved their preference rank."
        )

    # Check if any students changed assignments
    if not changed_assignments:
        trade_off_summary.append(
            "No students changed project assignments between solutions A and B."
        )

    # Return comparison results
    return {
        "solution_a_id": solution_a.id,
        "solution_a_alt": solution_a.alternative_number,
        "solution_b_id": solution_b.id,
        "solution_b_alt": solution_b.alternative_number,
        "is_distinct": len(changed_assignments) > 0,
        "changed_students_count": len(changed_assignments),
        "total_students": len(solution_a.assignments),
        "rank_improved_count": rank_improved_count,
        "rank_worsened_count": rank_worsened_count,
        "delta_mean_skill_fit": delta_mean_skill_fit,
        "delta_mean_rank": delta_mean_rank,
        "delta_unranked_count": delta_unranked_count,
        "delta_metrics": delta_metrics,
        "trade_off_summary": trade_off_summary,
        "changed_assignments": changed_assignments,
    }

