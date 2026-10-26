"""Assignment strategies implemented with Pyomo and HiGHS."""

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
    """Build the hard-constraint student-to-project assignment model."""
    model = pyo.ConcreteModel("StudentProjectAssignment")
    student_ids = [student.id for student in students]
    project_ids = [project.id for project in projects]
    model.student_ids = pyo.Set(initialize=student_ids)
    model.project_ids = pyo.Set(initialize=project_ids)
    model.x = pyo.Var(
        model.student_ids, model.project_ids, domain=pyo.Binary
    )

    for student in students:
        model.add_component(
            f"student_{student.id}_exactly_one_project",
            pyo.Constraint(
                expr=sum(model.x[student.id, project.id] for project in projects)
                == 1
            ),
        )

    for project in projects:
        project_variables = [
            model.x[student.id, project.id] for student in students
        ]
        model.add_component(
            f"project_{project.id}_minimum_capacity",
            pyo.Constraint(expr=sum(project_variables) >= project.min_capacity),
        )
        model.add_component(
            f"project_{project.id}_maximum_capacity",
            pyo.Constraint(expr=sum(project_variables) <= project.max_capacity),
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
                        pyo.Constraint(expr=model.x[student.id, project.id] == 0),
                    )

    for fixed_assignment in fixed_assignments or []:
        if (
            fixed_assignment.student_id in model.student_ids
            and fixed_assignment.project_id in model.project_ids
        ):
            model.add_component(
                f"fixed_{fixed_assignment.student_id}_{fixed_assignment.project_id}",
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
    """Return skill fit, with a local calculation until metrics is implemented."""
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
    """Shared implementation for concrete Pyomo assignment strategies."""

    def _objective_value(
        self, student: models.Student, project: models.Project, max_preferences: int
    ) -> float:
        return self.calculate_cost_or_utility(
            student, project, max_preferences
        )

    def solve(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        fixed_assignments: list[models.FixedAssignment] | None = None,
        excluded_solutions: list[list[tuple[str, str]]] | None = None,
    ) -> tuple[str, list[models.Assignment], float | None, dict[str, Any]]:
        """Solve the assignment model and return structured results."""
        model, variables = _build_base_model(
            students, projects, fixed_assignments
        )
        max_preferences = max(
            (preference.rank for student in students for preference in student.preferences),
            default=1,
        )
        objective = sum(
            self._objective_value(student, project, max_preferences)
            * variables[student.id, project.id]
            for student in students
            for project in projects
        )
        model.del_component(model.objective)
        model.objective = pyo.Objective(expr=objective, sense=pyo.maximize)

        for index, excluded_solution in enumerate(excluded_solutions or []):
            model.add_component(
                f"excluded_solution_{index}",
                pyo.Constraint(
                    expr=sum(
                        variables[student_id, project_id]
                        for student_id, project_id in excluded_solution
                    )
                    <= len(excluded_solution) - 1
                ),
            )

        try:
            result = model.solver.solve(model)
        except PyomoException as error:
            return "INFEASIBLE", [], None, {"error": str(error)}

        if result.solver.termination_condition not in (
            pyo.TerminationCondition.optimal,
            pyo.TerminationCondition.feasible,
        ):
            return "INFEASIBLE", [], None, {
                "termination_condition": str(result.solver.termination_condition)
            }

        fixed_pairs = {
            (assignment.student_id, assignment.project_id)
            for assignment in fixed_assignments or []
        }
        project_by_id = {project.id: project for project in projects}
        student_by_id = {student.id: student for student in students}
        assignments: list[models.Assignment] = []
        for student in students:
            for project in projects:
                if pyo.value(variables[student.id, project.id]) > 0.5:
                    fit, unmet = _skill_fit(student, project)
                    assignments.append(
                        models.Assignment(
                            student_id=student.id,
                            project_id=project.id,
                            is_fixed=(student.id, project.id) in fixed_pairs,
                            preference_rank=student.get_preference_rank(project.id),
                            skill_fit_score=fit,
                            unmet_requirements=unmet,
                        )
                    )

        return (
            "OPTIMAL",
            assignments,
            float(pyo.value(model.objective)),
            {
                "solver": "appsi_highs",
                "termination_condition": str(
                    result.solver.termination_condition
                ),
                "project_count": len(project_by_id),
                "student_count": len(student_by_id),
            },
        )


class PreferenceOrientedSolver(_PyomoAssignmentStrategy):
    """Maximize ranked student preferences."""

    def __init__(self) -> None:
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
        rank = student.get_preference_rank(project.id)
        return (
            float(max_preferences - rank + 1)
            if rank is not None
            else float(-max_preferences * 2)
        )


class SkillFitOrientedSolver(_PyomoAssignmentStrategy):
    """Maximize total student-project skill fit."""

    def __init__(self) -> None:
        super().__init__("SKILL_FIT", "Maximize project skill fit.")

    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        fit, _ = _skill_fit(student, project)
        return fit


class BalancedTradeoffSolver(_PyomoAssignmentStrategy):
    """Balance preference satisfaction and skill fit."""

    def __init__(
        self, preference_weight: float = 0.5, skill_weight: float = 0.5
    ) -> None:
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
