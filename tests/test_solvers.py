"""Unit tests for optimization solvers and distinct alternative generation."""

import pytest
import pyomo.environ as pyo

from app.contract import contract
from app.domain import models
from app.engine import solvers
from app.engine import strategies
from app.samples import demo_data


def test_assignment_strategy_abc() -> None:
    """Verifies that AssignmentStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        solvers.AssignmentStrategy()  # type: ignore[abstract]


def test_assignment_engine_initialization() -> None:
    """Verifies that AssignmentEngine initializes cleanly with empty strategies."""
    engine = solvers.AssignmentEngine()
    assert isinstance(engine, contract.AssignmentEngineContract)
    assert isinstance(engine.strategies, dict)
    assert len(engine.strategies) == 0


def test_assignment_engine_raises_not_implemented() -> None:
    """Verifies that execute_run raises NotImplementedError for Team B."""
    engine = solvers.AssignmentEngine()
    benchmark = demo_data.get_standard_scenario()
    request = contract.RunRequest(
        students=benchmark["students"],
        projects=benchmark["projects"],
    )
    with pytest.raises(NotImplementedError) as exc_info:
        engine.execute_run(request)
    assert "TODO (Team B)" in str(exc_info.value)


def test_base_model_solves_tiny_case() -> None:
    students = [
        models.Student(id="S1", display_name="Student 1"),
        models.Student(id="S2", display_name="Student 2"),
        models.Student(id="S3", display_name="Student 3"),
    ]
    projects = [
        models.Project(id="P1", title="Project 1", max_capacity=2),
        models.Project(id="P2", title="Project 2", min_capacity=1, max_capacity=2),
    ]

    model, variables = strategies._build_base_model(students, projects)

    results = model.solver.solve(model)
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal
    assert sum(
        pyo.value(variables[student.id, project.id])
        for student in students
        for project in projects
    ) == len(students)


def test_base_model_honours_fixed_lock() -> None:
    students = [
        models.Student(id="S1", display_name="Student 1"),
        models.Student(id="S2", display_name="Student 2"),
    ]
    projects = [
        models.Project(id="P1", title="Project 1", max_capacity=2),
        models.Project(id="P2", title="Project 2", max_capacity=2),
    ]

    model, variables = strategies._build_base_model(
        students,
        projects,
        [models.FixedAssignment(student_id="S1", project_id="P2")],
    )

    results = model.solver.solve(model)
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal
    assert pyo.value(variables["S1", "P2"]) == 1


def test_base_model_forbids_students_below_mandatory_skill() -> None:
    students = [
        models.Student(id="S1", display_name="Student 1", skills={"python": 1}),
        models.Student(id="S2", display_name="Student 2", skills={"python": 3}),
    ]
    projects = [
        models.Project(
            id="P1",
            title="Python Project",
            min_capacity=1,
            max_capacity=1,
            requirements=[
                models.ProjectRequirement(
                    project_id="P1",
                    skill_id="python",
                    minimum_level=2,
                    is_mandatory=True,
                )
            ],
        ),
        models.Project(
            id="P2", title="Other Project", min_capacity=1, max_capacity=1
        ),
    ]

    model, variables = strategies._build_base_model(students, projects)

    results = model.solver.solve(model)
    assert results.solver.termination_condition == pyo.TerminationCondition.optimal
    assert pyo.value(variables["S1", "P1"]) == 0
    assert pyo.value(variables["S2", "P1"]) == 1


@pytest.mark.parametrize(
    "strategy",
    [
        strategies.PreferenceOrientedSolver(),
        strategies.SkillFitOrientedSolver(),
        strategies.BalancedTradeoffSolver(),
    ],
)
def test_strategies_solve_standard_scenario(
    strategy: solvers.AssignmentStrategy,
) -> None:
    benchmark = demo_data.get_standard_scenario()

    status, assignments, objective, diagnostics = strategy.solve(
        benchmark["students"],
        benchmark["projects"],
        benchmark["fixed_assignments"],
    )

    assert status == "OPTIMAL"
    assert objective is not None
    assert len(assignments) == len(benchmark["students"])
    assert diagnostics["solver"] == "appsi_highs"
    assert all(assignment.preference_rank is not None for assignment in assignments)


@pytest.mark.xfail(
    raises=NotImplementedError,
    reason="TODO (Team B): Implement optimization solver and alternative generation",
)
def test_distinct_alternatives_generation() -> None:
    """Verifies AssignmentEngine produces distinct alternatives."""
    benchmark = demo_data.get_standard_scenario()
    engine = solvers.AssignmentEngine()

    run = engine.run_assignment(
        students=benchmark["students"],
        projects=benchmark["projects"],
        skills=benchmark["skills"],
        max_alternatives=3,
    )

    assert run.status == "COMPLETED"
    assert len(run.solutions) >= 2

    # Check distinctness: verify that each pair of solutions differs
    for i in range(len(run.solutions)):
        for j in range(i + 1, len(run.solutions)):
            pairs_i = {
                (a.student_id, a.project_id)
                for a in run.solutions[i].assignments
            }
            pairs_j = {
                (a.student_id, a.project_id)
                for a in run.solutions[j].assignments
            }
            assert (
                pairs_i != pairs_j
            ), f"Solution {i+1} and {j+1} are duplicate allocations!"


def test_strategy_excludes_previous_solution() -> None:
    """A no-good cut makes the next standard-scenario assignment differ."""
    benchmark = demo_data.get_standard_scenario()
    strategy = strategies.PreferenceOrientedSolver()

    status, assignments, _, _ = strategy.solve(
        benchmark["students"], benchmark["projects"]
    )
    first_pairs = [(a.student_id, a.project_id) for a in assignments]
    alternative_status, alternative, _, _ = strategy.solve(
        benchmark["students"],
        benchmark["projects"],
        excluded_solutions=[first_pairs],
    )

    assert status == "OPTIMAL"
    assert alternative_status == "OPTIMAL"
    assert first_pairs != [(a.student_id, a.project_id) for a in alternative]


def test_strategy_reports_infeasible_when_only_solution_is_excluded() -> None:
    """Excluding the sole valid assignment reports infeasibility."""
    students = [models.Student(id="S1", display_name="One")]
    projects = [
        models.Project(id="P1", title="Only", min_capacity=1, max_capacity=1)
    ]
    strategy = strategies.PreferenceOrientedSolver()

    status, assignments, _, _ = strategy.solve(students, projects)
    pairs = [(a.student_id, a.project_id) for a in assignments]
    alternative_status, alternative, objective, _ = strategy.solve(
        students, projects, excluded_solutions=[pairs]
    )

    assert status == "OPTIMAL"
    assert alternative_status == "INFEASIBLE"
    assert alternative == []
    assert objective is None
