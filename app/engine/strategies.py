"""Pyomo assignment strategies and distinct-solution constraints."""

from __future__ import annotations

import abc
from typing import Any

import pyomo.environ as pyo

from app.config import Config
from app.domain import models


def _build_base_model(
    students: list[models.Student],
    projects: list[models.Project],
    fixed_assignments: list[models.FixedAssignment] | None = None,
) -> tuple[pyo.ConcreteModel, Any]:
    """Build the common assignment model and return it with its choice vars."""
    student_ids = [student.id for student in students]
    project_ids = [project.id for project in projects]
    project_by_id = {project.id: project for project in projects}
    fixed_assignments = fixed_assignments or []

    model = pyo.ConcreteModel()
    model.students = pyo.Set(initialize=student_ids, ordered=True)
    model.projects = pyo.Set(initialize=project_ids, ordered=True)
    model.x = pyo.Var(model.students, model.projects, domain=pyo.Binary)

    model.one_project = pyo.Constraint(
        model.students,
        rule=lambda m, student_id: sum(
            m.x[student_id, project_id] for project_id in m.projects
        )
        == 1,
    )
    model.capacity = pyo.ConstraintList()
    for project in projects:
        assigned = sum(
            model.x[student_id, project.id] for student_id in model.students
        )
        model.capacity.add(assigned >= project.min_capacity)
        model.capacity.add(assigned <= project.max_capacity)

    fixed_by_student = {fixed.student_id: fixed.project_id for fixed in fixed_assignments}
    model.fixed = pyo.ConstraintList()
    for student_id, project_id in fixed_by_student.items():
        if student_id in model.students and project_id in model.projects:
            model.fixed.add(model.x[student_id, project_id] == 1)
            for other_project_id in project_ids:
                if other_project_id != project_id:
                    model.fixed.add(model.x[student_id, other_project_id] == 0)

    model.mandatory_skills = pyo.ConstraintList()
    for student in students:
        for project in projects:
            forbidden = any(
                requirement.is_mandatory
                and student.get_skill_level(requirement.skill_id)
                < requirement.minimum_level
                for requirement in project.requirements
            )
            if forbidden:
                model.mandatory_skills.add(model.x[student.id, project.id] == 0)

    # Keep these maps on the model so strategy objectives remain readable.
    model._project_by_id = project_by_id
    return model, model.x


class AssignmentStrategy(abc.ABC):
    """Base class for objective-specific assignment strategies."""

    def __init__(self, name: str, description: str) -> None:
        self.name = name
        self.description = description

    @abc.abstractmethod
    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Return the objective coefficient for a student-project pair."""

    def solve(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        fixed_assignments: list[models.FixedAssignment] | None = None,
        excluded_solutions: list[list[tuple[str, str]]] | None = None,
    ) -> tuple[str, list[models.Assignment], float | None, dict[str, Any]]:
        """Solve once, excluding every complete assignment supplied."""
        model, choices = _build_base_model(
            students, projects, fixed_assignments
        )
        max_preferences = max(
            (len(student.preferences) for student in students), default=1
        )
        model.objective = pyo.Objective(
            expr=sum(
                self.calculate_cost_or_utility(
                    student,
                    project,
                    max_preferences,
                )
                * choices[student.id, project.id]
                for student in students
                for project in projects
            ),
            sense=pyo.maximize,
        )

        model.no_good_cuts = pyo.ConstraintList()
        student_ids = {student.id for student in students}
        project_ids = {project.id for project in projects}
        for earlier_solution in excluded_solutions or []:
            pairs = [
                (student_id, project_id)
                for student_id, project_id in earlier_solution
                if student_id in student_ids and project_id in project_ids
            ]
            if pairs:
                model.no_good_cuts.add(
                    sum(choices[student_id, project_id] for student_id, project_id in pairs)
                    <= len(students) - 1
                )

        solver = pyo.SolverFactory("appsi_highs")
        solver.options["time_limit"] = Config.PULP_TIME_LIMIT_SECONDS
        try:
            result = solver.solve(model)
        except (RuntimeError, ValueError, OSError) as exc:
            return "INFEASIBLE", [], None, {
                "error": str(exc),
                "termination_condition": "ERROR",
            }

        status = str(result.solver.termination_condition).upper()
        if status not in {"OPTIMAL", "FEASIBLE"}:
            return "INFEASIBLE", [], None, {
                "termination_condition": status,
                "solver_status": str(result.solver.status),
            }

        project_by_id = {project.id: project for project in projects}
        fixed_pairs = {
            (fixed.student_id, fixed.project_id)
            for fixed in fixed_assignments or []
        }
        assignments: list[models.Assignment] = []
        for student in students:
            for project_id in project_by_id:
                if pyo.value(choices[student.id, project_id]) > 0.5:
                    project = project_by_id[project_id]
                    fit, unmet = _skill_fit(student, project)
                    assignments.append(
                        models.Assignment(
                            student_id=student.id,
                            project_id=project_id,
                            is_fixed=(student.id, project_id) in fixed_pairs,
                            preference_rank=student.get_preference_rank(project_id),
                            skill_fit_score=fit,
                            unmet_requirements=unmet,
                        )
                    )
                    break

        objective_value = pyo.value(model.objective)
        return "OPTIMAL", assignments, objective_value, {
            "termination_condition": status,
            "solver_status": str(result.solver.status),
            "variables_count": len(students) * len(projects),
            "constraints_count": len(model.component_map(pyo.Constraint)),
        }


def _skill_fit(
    student: models.Student, project: models.Project
) -> tuple[float, list[str]]:
    if not project.requirements:
        return 1.0, []
    unmet = [
        requirement.skill_id
        for requirement in project.requirements
        if student.get_skill_level(requirement.skill_id) < requirement.minimum_level
    ]
    return (len(project.requirements) - len(unmet)) / len(project.requirements), unmet


class PreferenceOrientedSolver(AssignmentStrategy):
    """Maximize ranked preference utility."""

    def __init__(self) -> None:
        super().__init__("PREFERENCE", "Maximize student preference satisfaction.")

    def calculate_cost_or_utility(
        self, student: models.Student, project: models.Project, max_preferences: int
    ) -> float:
        rank = student.get_preference_rank(project.id)
        return float(max_preferences + 1 - rank) if rank is not None else -float(max_preferences)


class SkillFitOrientedSolver(AssignmentStrategy):
    """Maximize the proportion of project requirements satisfied."""

    def __init__(self) -> None:
        super().__init__("SKILL_FIT", "Maximize student-project skill fit.")

    def calculate_cost_or_utility(
        self, student: models.Student, project: models.Project, _max_preferences: int
    ) -> float:
        return _skill_fit(student, project)[0]


class BalancedTradeoffSolver(AssignmentStrategy):
    """Balance preference utility and skill fit."""

    def __init__(self, preference_weight: float = 0.5) -> None:
        super().__init__("BALANCED", "Balance preference satisfaction and skill fit.")
        self.preference_weight = preference_weight

    def calculate_cost_or_utility(
        self, student: models.Student, project: models.Project, max_preferences: int
    ) -> float:
        preference = PreferenceOrientedSolver().calculate_cost_or_utility(
            student, project, max_preferences
        )
        preference = max(0.0, preference) / max_preferences
        return self.preference_weight * preference + (1 - self.preference_weight) * _skill_fit(
            student, project
        )[0]
