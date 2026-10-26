"""Assignment strategies implemented with Pyomo and HiGHS.

This module provides the shared Pyomo base model builder with hard constraints
(Issue B2.1), the three optimization strategies PREFERENCE, SKILL_FIT, and
BALANCED (Issue B2.2), and integer no-good cut exclusion support for distinct
alternatives (Issue B2.3).
"""

from __future__ import annotations

from typing import Any

import pyomo.environ as pyo
from pyomo.common.errors import PyomoException

from app.config import Config
from app.domain import models
from app.engine import metrics
from app.engine.solvers import AssignmentStrategy


def _build_base_model(
    students: list[models.Student],
    projects: list[models.Project],
    fixed_assignments: list[models.FixedAssignment] | None = None,
) -> tuple[pyo.ConcreteModel, pyo.Var]:
    """Builds the hard-constraint student-to-project assignment model.

    Args:
        students: Cohort of students to assign.
        projects: Available semester projects with capacity bounds.
        fixed_assignments: Optional pre-allocated student-project locks.

    Returns:
        A tuple of (model, model.x) where model is a Pyomo ConcreteModel
        configured with the HiGHS solver ('appsi_highs') and model.x is the
        binary decision variable matrix indexed by (student_id, project_id).
    """
    model = pyo.ConcreteModel("StudentProjectAssignment")
    student_ids = [student.id for student in students]
    project_ids = [project.id for project in projects]
    model.student_ids = pyo.Set(initialize=student_ids, ordered=True)
    model.project_ids = pyo.Set(initialize=project_ids, ordered=True)
    model.x = pyo.Var(
        model.student_ids, model.project_ids, domain=pyo.Binary
    )

    for student in students:
        model.add_component(
            f"student_{student.id}_exactly_one_project",
            pyo.Constraint(
                expr=sum(
                    model.x[student.id, project.id] for project in projects
                )
                == 1
            ),
        )

    for project in projects:
        project_variables = [
            model.x[student.id, project.id] for student in students
        ]
        model.add_component(
            f"project_{project.id}_minimum_capacity",
            pyo.Constraint(
                expr=sum(project_variables) >= project.min_capacity
            ),
        )
        model.add_component(
            f"project_{project.id}_maximum_capacity",
            pyo.Constraint(
                expr=sum(project_variables) <= project.max_capacity
            ),
        )
        for student in students:
            for requirement in project.requirements:
                if (
                    requirement.is_mandatory
                    and student.get_skill_level(requirement.skill_id)
                    < requirement.minimum_level
                ):
                    model.add_component(
                        f"student_{student.id}_lacks_{requirement.skill_id}"
                        f"_for_project_{project.id}",
                        pyo.Constraint(
                            expr=model.x[student.id, project.id] == 0
                        ),
                    )

    for fixed_assignment in fixed_assignments or []:
        if (
            fixed_assignment.student_id in model.student_ids
            and fixed_assignment.project_id in model.project_ids
        ):
            model.add_component(
                f"fixed_{fixed_assignment.student_id}_"
                f"{fixed_assignment.project_id}",
                pyo.Constraint(
                    expr=model.x[
                        fixed_assignment.student_id,
                        fixed_assignment.project_id,
                    ]
                    == 1
                ),
            )

    model.objective = pyo.Objective(expr=0, sense=pyo.maximize)
    model.solver = pyo.SolverFactory("appsi_highs")
    model.solver.config.time_limit = Config.PULP_TIME_LIMIT_SECONDS
    return model, model.x


def _skill_fit(
    student: models.Student, project: models.Project
) -> tuple[float, list[str]]:
    """Calculates fractional skill fit using metrics.calculate_assignment_skill_fit."""
    try:
        return metrics.calculate_assignment_skill_fit(student, project)
    except NotImplementedError:
        if not project.requirements:
            return 1.0, []
        scores = [
            min(
                student.get_skill_level(requirement.skill_id)
                / requirement.minimum_level,
                1.0,
            )
            for requirement in project.requirements
        ]
        unmet = [
            requirement.skill_id
            for requirement in project.requirements
            if student.get_skill_level(requirement.skill_id)
            < requirement.minimum_level
        ]
        return sum(scores) / len(scores), unmet


class _PyomoAssignmentStrategy(AssignmentStrategy):
    """Shared Pyomo + HiGHS implementation for concrete assignment strategies."""

    def solve(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        fixed_assignments: list[models.FixedAssignment] | None = None,
        excluded_solutions: list[list[tuple[str, str]]] | None = None,
    ) -> tuple[str, list[models.Assignment], float | None, dict[str, Any]]:
        """Solves the assignment problem under this strategy's formulation.

        Args:
            students: List of students in the cohort.
            projects: List of available semester projects.
            fixed_assignments: Pre-assigned student-project pairs that must hold.
            excluded_solutions: Previous solution allocations to cut out.

        Returns:
            A tuple of (solver_status, assignments, objective_value, diagnostics).
        """
        if not students or not projects:
            return (
                "INFEASIBLE",
                [],
                None,
                {
                    "solver": "appsi_highs",
                    "termination_condition": "EMPTY_COHORT",
                },
            )

        model, variables = _build_base_model(
            students, projects, fixed_assignments
        )
        max_preferences = max(
            (len(student.preferences) for student in students), default=1
        )
        max_preferences = max(max_preferences, 1)

        model.del_component(model.objective)
        model.objective = pyo.Objective(
            expr=sum(
                self.calculate_cost_or_utility(
                    student, project, max_preferences
                )
                * variables[student.id, project.id]
                for student in students
                for project in projects
            ),
            sense=pyo.maximize,
        )

        student_ids = {student.id for student in students}
        project_ids = {project.id for project in projects}
        for index, excluded_solution in enumerate(excluded_solutions or []):
            valid_pairs = [
                (student_id, project_id)
                for student_id, project_id in excluded_solution
                if student_id in student_ids and project_id in project_ids
            ]
            if valid_pairs:
                model.add_component(
                    f"excluded_solution_{index}",
                    pyo.Constraint(
                        expr=sum(
                            variables[student_id, project_id]
                            for student_id, project_id in valid_pairs
                        )
                        <= len(students) - 1
                    ),
                )

        try:
            result = model.solver.solve(model, load_solutions=False)
        except (PyomoException, RuntimeError, ValueError, OSError) as error:
            return (
                "INFEASIBLE",
                [],
                None,
                {
                    "solver": "appsi_highs",
                    "error": str(error),
                    "termination_condition": "ERROR",
                },
            )

        if result.solver.termination_condition not in (
            pyo.TerminationCondition.optimal,
            pyo.TerminationCondition.feasible,
        ):
            return (
                "INFEASIBLE",
                [],
                None,
                {
                    "solver": "appsi_highs",
                    "termination_condition": str(
                        result.solver.termination_condition
                    ),
                },
            )

        model.solutions.load_from(result)

        fixed_pairs = {
            (assignment.student_id, assignment.project_id)
            for assignment in fixed_assignments or []
        }
        assignments: list[models.Assignment] = []
        for student in students:
            for project in projects:
                val = pyo.value(variables[student.id, project.id], exception=False)
                if val is not None and val > 0.5:
                    fit, unmet = _skill_fit(student, project)
                    assignments.append(
                        models.Assignment(
                            student_id=student.id,
                            project_id=project.id,
                            is_fixed=(student.id, project.id) in fixed_pairs,
                            preference_rank=student.get_preference_rank(
                                project.id
                            ),
                            skill_fit_score=fit,
                            unmet_requirements=unmet,
                        )
                    )
                    break

        return (
            "OPTIMAL",
            assignments,
            float(pyo.value(model.objective)),
            {
                "solver": "appsi_highs",
                "termination_condition": str(
                    result.solver.termination_condition
                ),
                "variables_count": len(students) * len(projects),
                "constraints_count": len(
                    list(model.component_data_objects(pyo.Constraint))
                ),
                "project_count": len(projects),
                "student_count": len(students),
            },
        )


class PreferenceOrientedSolver(_PyomoAssignmentStrategy):
    """Maximizes ranked student preferences (minimizes rank regret)."""

    def __init__(self) -> None:
        """Initializes the preference-oriented solver strategy."""
        super().__init__(
            "PREFERENCE",
            "Maximize student preference satisfaction.",
        )

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Computes preference utility weight with heavy penalty for unranked."""
        rank = student.get_preference_rank(project.id)
        return (
            float(max_preferences - rank + 1)
            if rank is not None
            else float(-max_preferences * 2)
        )


class SkillFitOrientedSolver(_PyomoAssignmentStrategy):
    """Maximizes total student-project fractional skill fit."""

    def __init__(self) -> None:
        """Initializes the skill-fit-oriented solver strategy."""
        super().__init__("SKILL_FIT", "Maximize project skill fit.")

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Computes skill-fit utility score in [0.0, 1.0]."""
        fit, _ = _skill_fit(student, project)
        return fit


class BalancedTradeoffSolver(_PyomoAssignmentStrategy):
    """Balances normalized preference utility and fractional skill fit."""

    def __init__(
        self, preference_weight: float = 0.5, skill_weight: float = 0.5
    ) -> None:
        """Initializes the balanced trade-off solver with configurable weights.

        Args:
            preference_weight: Relative weight for student preference utility.
            skill_weight: Relative weight for project skill fit.

        Raises:
            ValueError: If weights are negative or sum to zero.
        """
        if preference_weight < 0 or skill_weight < 0:
            raise ValueError("Strategy weights must be non-negative.")
        if preference_weight + skill_weight == 0:
            raise ValueError("At least one strategy weight must be positive.")
        super().__init__("BALANCED", "Balance preferences and skill fit.")
        total = preference_weight + skill_weight
        self.preference_weight = preference_weight / total
        self.skill_weight = skill_weight / total

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Computes weighted combination of normalized preference and skill fit."""
        preference_rank = student.get_preference_rank(project.id)
        preference_score = (
            (max_preferences - preference_rank + 1) / max_preferences
            if preference_rank is not None
            else -1.0
        )
        skill_fit, _ = _skill_fit(student, project)
        return (
            self.preference_weight * preference_score
            + self.skill_weight * skill_fit
        )
