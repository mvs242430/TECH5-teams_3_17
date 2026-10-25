"""Pyomo assignment model construction helpers."""

import pyomo.environ as pyo

from app.config import Config
from app.domain import models


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

    model.objective = pyo.Objective(expr=0, sense=pyo.minimize)
    model.solver = pyo.SolverFactory("appsi_highs")
    model.solver.config.time_limit = Config.PULP_TIME_LIMIT_SECONDS
    return model, model.x
