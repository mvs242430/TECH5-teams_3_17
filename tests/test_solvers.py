"""Unit tests for optimization solvers and distinct alternative generation."""

import pathlib
import random
from typing import Any, Callable

import pyomo.environ as pyo
from pyomo.opt import SolverResults
import pytest

from app.contract import contract
from app.domain import models
from app.engine import solvers
from app.engine import strategies
from app.persistence import database
from app.persistence import repositories
from app.samples import demo_data


def test_assignment_strategy_abc() -> None:
    """Verifies that AssignmentStrategy cannot be instantiated directly."""
    with pytest.raises(TypeError):
        solvers.AssignmentStrategy()  # type: ignore[abstract]


def test_assignment_engine_initialization() -> None:
    """Verifies that AssignmentEngine initializes with the 3 registered strategies."""
    engine = solvers.AssignmentEngine()
    assert isinstance(engine, contract.AssignmentEngineContract)
    assert isinstance(engine.strategies, dict)
    assert set(engine.strategies.keys()) == {
        "PREFERENCE",
        "SKILL_FIT",
        "BALANCED",
    }


def test_assignment_engine_raises_not_implemented() -> None:
    """Verifies that execute_run completes on the standard scenario."""
    engine = solvers.AssignmentEngine()
    benchmark = demo_data.get_standard_scenario()
    request = contract.RunRequest(
        students=benchmark["students"],
        projects=benchmark["projects"],
        skills=benchmark["skills"],
        fixed_assignments=benchmark["fixed_assignments"],
    )
    run = engine.execute_run(request)
    assert run.status == "COMPLETED"
    assert len(run.solutions) >= 1


def test_base_model_solves_tiny_case() -> None:
    """Verifies that the Pyomo base model solves a 3-student, 2-project case."""
    students = [
        models.Student(id="S1", display_name="Student 1"),
        models.Student(id="S2", display_name="Student 2"),
        models.Student(id="S3", display_name="Student 3"),
    ]
    projects = [
        models.Project(id="P1", title="Project 1", max_capacity=2),
        models.Project(
            id="P2", title="Project 2", min_capacity=1, max_capacity=2
        ),
    ]

    model, variables = strategies._build_base_model(students, projects)

    results = model.solver.solve(model)
    assert (
        results.solver.termination_condition == pyo.TerminationCondition.optimal
    )
    assert sum(
        pyo.value(variables[student.id, project.id])
        for student in students
        for project in projects
    ) == len(students)


def test_base_model_honours_fixed_lock() -> None:
    """Verifies that fixed assignment locks force x[student, project] == 1."""
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
    assert (
        results.solver.termination_condition == pyo.TerminationCondition.optimal
    )
    assert pyo.value(variables["S1", "P2"]) == 1


def test_base_model_forbids_students_below_mandatory_skill() -> None:
    """Verifies that mandatory skill requirements forbid unqualified students."""
    students = [
        models.Student(
            id="S1", display_name="Student 1", skills={"python": 1}
        ),
        models.Student(
            id="S2", display_name="Student 2", skills={"python": 3}
        ),
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
    assert (
        results.solver.termination_condition == pyo.TerminationCondition.optimal
    )
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
    """Verifies each strategy produces a valid optimal allocation on Standard."""
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
    assert all(
        assignment.preference_rank is not None for assignment in assignments
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


# -----------------------------------------------------------------------------
# Honest solver stop reasons
# -----------------------------------------------------------------------------


def _engine(tmp_path: pathlib.Path) -> solvers.AssignmentEngine:
    """Returns an engine on a throwaway database."""
    db_manager = database.DatabaseManager(tmp_path / "stop_reasons.db")
    return solvers.AssignmentEngine(
        run_repo=repositories.RunRepository(db_manager)
    )


def _tiny_cohort() -> tuple[list[models.Student], list[models.Project]]:
    """Builds a two-student cohort that HiGHS solves instantly."""
    students = [
        models.Student(id="S1", display_name="One"),
        models.Student(id="S2", display_name="Two"),
    ]
    projects = [
        models.Project(id="P1", title="P1", max_capacity=2),
        models.Project(id="P2", title="P2", max_capacity=2),
    ]
    return students, projects


def _large_cohort() -> tuple[list[models.Student], list[models.Project]]:
    """Builds a cohort that HiGHS cannot finish within a zero-second limit."""
    picker = random.Random(7)
    projects = [
        models.Project(
            id=f"P{index}", title=f"P{index}", min_capacity=5, max_capacity=15
        )
        for index in range(30)
    ]
    students = []
    for index in range(300):
        student_id = f"S{index}"
        ranked = picker.sample(projects, 5)
        students.append(
            models.Student(
                id=student_id,
                display_name=student_id,
                preferences=[
                    models.Preference(student_id, project.id, rank)
                    for rank, project in enumerate(ranked, start=1)
                ],
            )
        )
    return students, projects


class _SolverWithForcedStop:
    """Runs the real HiGHS solve, then reports a chosen stop reason."""

    def __init__(
        self, real_solver: Any, condition: pyo.TerminationCondition
    ) -> None:
        """Stores the real solver and the stop reason to report."""
        self.real_solver = real_solver
        self.condition = condition

    def solve(self, *args: Any, **kwargs: Any) -> Any:
        """Solves for real and replaces the reported stop reason."""
        result = self.real_solver.solve(*args, **kwargs)
        result.solver.termination_condition = self.condition
        result.solver.status = pyo.SolverStatus.aborted
        return result


class _CrashingSolver:
    """Stands in for a solver that fails while solving."""

    def solve(self, *args: Any, **kwargs: Any) -> Any:
        """Raises the error a failing solver would raise."""
        raise RuntimeError("HiGHS crashed")


def _replace_solver(
    monkeypatch: pytest.MonkeyPatch, make_solver: Callable[[Any], Any]
) -> None:
    """Makes every model built from now on use a replaced solver."""
    real_build = strategies._build_base_model

    def build(*args: Any, **kwargs: Any) -> tuple[Any, Any]:
        """Builds the real model, then swaps its solver."""
        model, variables = real_build(*args, **kwargs)
        model.solver = make_solver(model.solver)
        return model, variables

    monkeypatch.setattr(strategies, "_build_base_model", build)


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        (pyo.TerminationCondition.optimal, "OPTIMAL"),
        (pyo.TerminationCondition.infeasible, "INFEASIBLE"),
        (pyo.TerminationCondition.infeasibleOrUnbounded, "INFEASIBLE"),
        (pyo.TerminationCondition.maxTimeLimit, "TIME_LIMIT"),
        (pyo.TerminationCondition.maxIterations, "NOT_SOLVED"),
        (pyo.TerminationCondition.unknown, "NOT_SOLVED"),
        (pyo.TerminationCondition.error, "NOT_SOLVED"),
    ],
)
def test_stop_without_allocation_claims_only_what_was_proved(
    condition: pyo.TerminationCondition, expected: str
) -> None:
    """Without a stored solution, only a proof may say INFEASIBLE."""
    result = SolverResults()
    result.solver.termination_condition = condition

    assert strategies._classify_solver_stop(result) == expected


def test_time_limit_reaches_highs(monkeypatch: pytest.MonkeyPatch) -> None:
    """A zero-second limit really stops HiGHS, and nothing is claimed."""
    monkeypatch.setattr(strategies.Config, "PULP_TIME_LIMIT_SECONDS", 0)
    students, projects = _large_cohort()

    status, assignments, objective, diagnostics = (
        strategies.PreferenceOrientedSolver().solve(students, projects)
    )

    assert status == "TIME_LIMIT"
    assert assignments == []
    assert objective is None
    assert diagnostics["termination_condition"] == "maxTimeLimit"


def test_run_stopped_by_time_limit_is_failed_not_infeasible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """A run with no allocation and no proof ends FAILED, and that is saved."""
    monkeypatch.setattr(strategies.Config, "PULP_TIME_LIMIT_SECONDS", 0)
    students, projects = _large_cohort()
    engine = _engine(tmp_path)

    run = engine.run_assignment(students, projects, max_alternatives=1)

    assert run.status == contract.RunStatus.FAILED.value
    assert run.solutions == []
    assert run.diagnostics["solver_status"] == "TIME_LIMIT"
    assert run.diagnostics["termination_condition"] == "maxTimeLimit"
    assert "does not prove" in run.diagnostics["reasons"][0]
    assert "Solver proved" not in run.diagnostics["reasons"][0]
    assert engine.get_run(run.id).status == contract.RunStatus.FAILED.value


@pytest.mark.parametrize(
    "condition",
    [
        pyo.TerminationCondition.feasible,
        pyo.TerminationCondition.maxTimeLimit,
    ],
)
def test_stop_with_allocation_is_feasible_not_optimal(
    monkeypatch: pytest.MonkeyPatch, condition: pyo.TerminationCondition
) -> None:
    """A stop that holds an allocation keeps it, labelled FEASIBLE."""
    _replace_solver(
        monkeypatch, lambda real: _SolverWithForcedStop(real, condition)
    )
    students, projects = _tiny_cohort()

    status, assignments, objective, diagnostics = (
        strategies.PreferenceOrientedSolver().solve(students, projects)
    )

    assert status == "FEASIBLE"
    assert len(assignments) == len(students)
    assert objective is not None
    assert diagnostics["termination_condition"] == str(condition)


def test_run_with_unproven_solution_says_so(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """A usable but unproven allocation completes without claiming optimality."""
    _replace_solver(
        monkeypatch,
        lambda real: _SolverWithForcedStop(
            real, pyo.TerminationCondition.maxTimeLimit
        ),
    )
    students, projects = _tiny_cohort()

    run = _engine(tmp_path).run_assignment(
        students, projects, max_alternatives=1
    )

    assert run.status == contract.RunStatus.COMPLETED.value
    assert len(run.solutions) == 1
    assert run.diagnostics["solver_status"] == "Feasible"
    assert (
        "Feasible but not proven optimal: Alt 1."
        in run.diagnostics["message"]
    )
    assert any("not proven optimal" in w for w in run.solutions[0].warnings)


def test_proven_optimal_run_keeps_optimal_status(
    tmp_path: pathlib.Path,
) -> None:
    """A normal run still reports Optimal, with no unproven-solution notice."""
    students, projects = _tiny_cohort()

    run = _engine(tmp_path).run_assignment(
        students, projects, max_alternatives=1
    )

    assert run.diagnostics["solver_status"] == "Optimal"
    assert "not proven optimal" not in run.diagnostics["message"]
    assert run.solutions[0].warnings == run.diagnostics["warnings"]


def test_solver_crash_is_not_reported_as_infeasible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """A solver failure proves nothing, so the run ends FAILED."""
    _replace_solver(monkeypatch, lambda real: _CrashingSolver())
    students, projects = _tiny_cohort()

    status, assignments, objective, diagnostics = (
        strategies.PreferenceOrientedSolver().solve(students, projects)
    )
    run = _engine(tmp_path).run_assignment(
        students, projects, max_alternatives=1
    )

    assert status == "NOT_SOLVED"
    assert assignments == []
    assert objective is None
    assert diagnostics["error"] == "HiGHS crashed"
    assert run.status == contract.RunStatus.FAILED.value
    assert run.diagnostics["solver_status"] == "NOT_SOLVED"


class _TimesOutOnSecondSolve(strategies.PreferenceOrientedSolver):
    """Solves normally once, then behaves as if the time limit was reached."""

    def solve(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        fixed_assignments: list[models.FixedAssignment] | None = None,
        excluded_solutions: list[list[tuple[str, str]]] | None = None,
    ) -> tuple[str, list[models.Assignment], float | None, dict[str, Any]]:
        """Reports a time-limit stop on any solve with a no-good cut."""
        if excluded_solutions:
            return "TIME_LIMIT", [], None, {"solver": "appsi_highs"}
        return super().solve(students, projects, fixed_assignments)


def test_alternative_search_stopped_by_time_limit_warns(
    tmp_path: pathlib.Path,
) -> None:
    """Fewer alternatives after a time limit is flagged as possibly incomplete."""
    students, projects = _tiny_cohort()
    engine = _engine(tmp_path)
    engine.strategies = {"PREFERENCE": _TimesOutOnSecondSolve()}

    run = engine.run_assignment(students, projects, max_alternatives=3)

    assert run.status == contract.RunStatus.COMPLETED.value
    assert len(run.solutions) == 1
    assert run.diagnostics["solver_status"] == "Optimal"
    assert any(
        "further distinct alternatives may exist" in warning
        for warning in run.diagnostics["warnings"]
    )


class _AlwaysTimesOut(strategies.SkillFitOrientedSolver):
    """Behaves as if every solve reached the time limit."""

    def solve(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        fixed_assignments: list[models.FixedAssignment] | None = None,
        excluded_solutions: list[list[tuple[str, str]]] | None = None,
    ) -> tuple[str, list[models.Assignment], float | None, dict[str, Any]]:
        """Reports a time-limit stop without solving."""
        return "TIME_LIMIT", [], None, {"solver": "appsi_highs"}


def test_retry_with_primary_strategy_sets_the_final_status(
    tmp_path: pathlib.Path,
) -> None:
    """A timed-out strategy does not hide the retry's proof that none are left."""
    students = [models.Student(id="S1", display_name="One")]
    projects = [
        models.Project(id="P1", title="Only", min_capacity=1, max_capacity=1)
    ]
    engine = _engine(tmp_path)
    engine.strategies["SKILL_FIT"] = _AlwaysTimesOut()

    run = engine.run_assignment(students, projects, max_alternatives=2)

    assert len(run.solutions) == 1
    assert not any(
        "further distinct alternatives" in warning
        for warning in run.diagnostics["warnings"]
    )


def test_exhausted_alternatives_do_not_warn(tmp_path: pathlib.Path) -> None:
    """When cuts prove nothing else exists, the shorter list is complete."""
    students = [models.Student(id="S1", display_name="One")]
    projects = [
        models.Project(id="P1", title="Only", min_capacity=1, max_capacity=1)
    ]

    run = _engine(tmp_path).run_assignment(
        students, projects, max_alternatives=3
    )

    assert run.status == contract.RunStatus.COMPLETED.value
    assert len(run.solutions) == 1
    assert not any(
        "further distinct alternatives" in warning
        for warning in run.diagnostics["warnings"]
    )
