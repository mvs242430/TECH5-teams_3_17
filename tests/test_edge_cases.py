"""Comprehensive edge case test suite for TECH5 Assignment System.

This module validates all 15 edge cases stipulated in Section 13 of the TECH5
specification:
1. Incomplete student preferences (ranking fewer projects than available).
2. Identical/tied preference profiles across multiple students.
3. Students with empty skill profiles.
4. Projects with zero skill requirements.
5. Student preferences referencing non-existent project IDs.
6. Entity profiles referencing unknown skill IDs.
7. Aggregate cohort capacity deficit (students > sum(max_capacity)).
8. Aggregate cohort minimum capacity excess (students < sum(min_capacity)).
9. Project capacity inversion (min_capacity > max_capacity).
10. Multiple conflicting fixed locks for the same student.
11. Fixed assignments exceeding a single project's capacity.
12. Project with impossible mandatory requirement.
13. Completely infeasible ILP formulation (solver returns INFEASIBLE).
14. Exactly one feasible solution exists (no spurious alternatives generated).
15. Strict avoidance of duplicate solutions via no-good integer cuts.
"""

import pathlib

import pytest

from app.domain import models
from app.domain import validation
from app.engine import solvers
from app.persistence import database
from app.persistence import repositories


def _engine(tmp_path: pathlib.Path) -> solvers.AssignmentEngine:
    """Returns an engine on a throwaway database, so locks do not leak."""
    db_manager = database.DatabaseManager(tmp_path / "edge_cases.db")
    return solvers.AssignmentEngine(
        run_repo=repositories.RunRepository(db_manager)
    )


def test_edge_case_1_incomplete_preferences() -> None:
    """Case 1: Student submits preferences for only a subset of projects."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=0, max_capacity=2),
        models.Project(id="P2", title="P2", min_capacity=0, max_capacity=2),
        models.Project(id="P3", title="P3", min_capacity=0, max_capacity=2),
    ]
    # S1 only ranks P1
    s1 = models.Student(
        id="S1",
        display_name="Student 1",
        preferences=[
            models.Preference(student_id="S1", project_id="P1", rank=1)
        ],
    )
    engine = solvers.AssignmentEngine()
    run = engine.run_assignment(
        students=[s1], projects=projects, skills=skills, max_alternatives=1
    )
    assert run.status == "COMPLETED"
    assert len(run.solutions) == 1
    assert run.solutions[0].assignments[0].student_id == "S1"


def test_edge_case_2_tied_preferences_across_students() -> None:
    """Case 2: All students have identical top-choice preference."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=0, max_capacity=1),
        models.Project(id="P2", title="P2", min_capacity=0, max_capacity=1),
    ]
    # Both students want P1 as rank 1
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[
            models.Preference("S1", "P1", 1),
            models.Preference("S1", "P2", 2),
        ],
    )
    s2 = models.Student(
        id="S2",
        display_name="S2",
        preferences=[
            models.Preference("S2", "P1", 1),
            models.Preference("S2", "P2", 2),
        ],
    )
    engine = solvers.AssignmentEngine()
    run = engine.run_assignment(
        students=[s1, s2], projects=projects, skills=skills, max_alternatives=2
    )
    assert run.status == "COMPLETED"
    assert len(run.solutions) >= 1
    # Check that capacity of P1 (1) is respected
    p1_allocations = [
        a for a in run.solutions[0].assignments if a.project_id == "P1"
    ]
    assert len(p1_allocations) == 1


def test_edge_case_3_zero_skills_student() -> None:
    """Case 3: Student has no declared skills against required project."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(
            id="P1",
            title="P1",
            min_capacity=0,
            max_capacity=2,
            requirements=[
                models.ProjectRequirement("P1", "py", minimum_level=2)
            ],
        )
    ]
    s1 = models.Student(
        id="S1",
        display_name="Novice Student",
        skills={},
        preferences=[models.Preference("S1", "P1", 1)],
    )
    res = validation.validate_cohort([s1], projects, skills, [])
    assert res.is_valid is True
    engine = solvers.AssignmentEngine()
    run = engine.run_assignment([s1], projects, skills, max_alternatives=1)
    assert run.status == "COMPLETED"
    assert run.solutions[0].assignments[0].skill_fit_score == 0.0


def test_edge_case_4_zero_requirements_project() -> None:
    """Case 4: Project specifies no skill requirements."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(
            id="P1",
            title="General Research",
            min_capacity=1,
            max_capacity=2,
            requirements=[],
        )
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        skills={"py": 3},
        preferences=[models.Preference("S1", "P1", 1)],
    )
    res = validation.validate_cohort([s1], projects, skills, [])
    assert res.is_valid is True
    engine = solvers.AssignmentEngine()
    run = engine.run_assignment([s1], projects, skills, max_alternatives=1)
    assert run.status == "COMPLETED"
    # Skill fit defaults to full neutral fit when requirements are empty
    assert run.solutions[0].assignments[0].skill_fit_score == 1.0


def test_edge_case_5_unknown_project_in_preferences() -> None:
    """Case 5: Student preferences reference non-existent project ID."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=1, max_capacity=2)
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[models.Preference("S1", "P999_GHOST", 1)],
    )
    res = validation.validate_cohort([s1], projects, skills, [])
    assert res.is_valid is False
    assert any("P999_GHOST" in err for err in res.errors)


def test_edge_case_6_unknown_skill_in_entity() -> None:
    """Case 6: Student or project references uncatalogued skill identifier."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(
            id="P1",
            title="P1",
            min_capacity=1,
            max_capacity=2,
            requirements=[
                models.ProjectRequirement(
                    project_id="P1",
                    skill_id="quantum_computing",
                    minimum_level=1,
                )
            ],
        )
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        skills={"cryptography": 5},
        preferences=[models.Preference("S1", "P1", 1)],
    )
    res = validation.validate_cohort([s1], projects, skills, [])
    assert any("quantum_computing" in w for w in res.warnings)
    assert any("cryptography" in w for w in res.warnings)


def test_edge_case_7_aggregate_capacity_deficit() -> None:
    """Case 7: Student cohort size exceeds sum of all project max capacities."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=0, max_capacity=1)
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[models.Preference("S1", "P1", 1)],
    )
    s2 = models.Student(
        id="S2",
        display_name="S2",
        preferences=[models.Preference("S2", "P1", 1)],
    )
    res = validation.validate_cohort([s1, s2], projects, skills, [])
    assert res.is_valid is False
    assert any("Insufficient overall capacity" in err for err in res.errors)


def test_edge_case_8_aggregate_min_capacity_excess() -> None:
    """Case 8: Cohort size is smaller than sum of project min capacities."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=2, max_capacity=3),
        models.Project(id="P2", title="P2", min_capacity=2, max_capacity=3),
    ]
    # Only 2 students, but min required is 4
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[models.Preference("S1", "P1", 1)],
    )
    s2 = models.Student(
        id="S2",
        display_name="S2",
        preferences=[models.Preference("S2", "P2", 1)],
    )
    res = validation.validate_cohort([s1, s2], projects, skills, [])
    assert res.is_valid is False
    assert any("below aggregate minimum" in err for err in res.errors)


def test_edge_case_9_capacity_inversion() -> None:
    """Case 9: A project has min_capacity strictly greater than max_capacity."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=5, max_capacity=2)
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[models.Preference("S1", "P1", 1)],
    )
    res = validation.validate_cohort([s1], projects, skills, [])
    assert res.is_valid is False
    assert any("exceeding max capacity" in err for err in res.errors)


def test_edge_case_10_conflicting_fixed_locks_same_student() -> None:
    """Case 10: Multiple contradictory fixed assignments for one student."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=0, max_capacity=2),
        models.Project(id="P2", title="P2", min_capacity=0, max_capacity=2),
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[
            models.Preference("S1", "P1", 1),
            models.Preference("S1", "P2", 2),
        ],
    )
    fixed = [
        models.FixedAssignment(student_id="S1", project_id="P1"),
        models.FixedAssignment(student_id="S1", project_id="P2"),
    ]
    res = validation.validate_cohort([s1], projects, skills, fixed)
    assert res.is_valid is False
    assert any("Contradictory fixed assignment" in err for err in res.errors)


def test_edge_case_11_fixed_locks_exceeding_project_capacity() -> None:
    """Case 11: Number of fixed locks for a project exceeds its max capacity."""
    skills = [models.Skill(id="py", name="Python")]
    projects = [
        models.Project(id="P1", title="P1", min_capacity=0, max_capacity=1)
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[models.Preference("S1", "P1", 1)],
    )
    s2 = models.Student(
        id="S2",
        display_name="S2",
        preferences=[models.Preference("S2", "P1", 1)],
    )
    fixed = [
        models.FixedAssignment(student_id="S1", project_id="P1"),
        models.FixedAssignment(student_id="S2", project_id="P1"),
    ]
    res = validation.validate_cohort([s1, s2], projects, skills, fixed)
    assert res.is_valid is False
    assert any("exceed its maximum capacity" in err for err in res.errors)


def test_edge_case_12_unavailable_mandatory_skill() -> None:
    """Case 12: Project has a mandatory skill that no student possesses."""
    skills = [
        models.Skill(id="rust", name="Rust"),
        models.Skill(id="py", name="Python"),
    ]
    projects = [
        models.Project(
            id="P1",
            title="Kernel Dev",
            min_capacity=1,
            max_capacity=2,
            requirements=[
                models.ProjectRequirement(
                    project_id="P1",
                    skill_id="rust",
                    minimum_level=4,
                    is_mandatory=True,
                )
            ],
        )
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        skills={"py": 3},  # No Rust!
        preferences=[models.Preference("S1", "P1", 1)],
    )
    res = validation.validate_cohort([s1], projects, skills, [])
    assert res.is_valid is False
    assert any("Mandatory requirement impossible" in err for err in res.errors)


def _assert_solver_proves_infeasible(
    engine: solvers.AssignmentEngine,
    students: list[models.Student],
    projects: list[models.Project],
    fixed: list[models.FixedAssignment] | None = None,
) -> None:
    """Asserts validation passes and HiGHS itself proves infeasibility."""
    res = validation.validate_cohort(
        students, projects, fixed_assignments=fixed
    )
    assert res.is_valid is True
    assert res.is_feasible is True

    run = engine.run_assignment(
        students, projects, fixed_assignments=fixed, max_alternatives=2
    )

    assert run.status == "INFEASIBLE"
    assert run.solutions == []
    assert run.diagnostics["solver_status"] == "INFEASIBLE"
    # Only a real solve sets this; the validator's early exit has no such key.
    assert run.diagnostics["termination_condition"] == "infeasible"


def _mandatory_rust(project_id: str) -> list[models.ProjectRequirement]:
    """Returns a mandatory level-2 Rust requirement for one project."""
    return [
        models.ProjectRequirement(
            project_id=project_id,
            skill_id="rust",
            minimum_level=2,
            is_mandatory=True,
        )
    ]


def test_edge_case_13_two_projects_need_the_only_qualified_student(
    tmp_path: pathlib.Path,
) -> None:
    """Case 13: Each project is fine alone, but both need the same student."""
    projects = [
        models.Project(
            id=project_id,
            title=project_id,
            min_capacity=1,
            max_capacity=2,
            requirements=_mandatory_rust(project_id),
        )
        for project_id in ("P1", "P2")
    ]
    students = [
        models.Student(id="S1", display_name="S1", skills={"rust": 3}),
        models.Student(id="S2", display_name="S2", skills={"rust": 1}),
    ]

    _assert_solver_proves_infeasible(_engine(tmp_path), students, projects)


def test_edge_case_13_fixed_student_lacks_mandatory_skill(
    tmp_path: pathlib.Path,
) -> None:
    """Case 13: A lock forces a student onto a project that forbids them."""
    projects = [
        models.Project(
            id="P1",
            title="P1",
            min_capacity=1,
            max_capacity=2,
            requirements=_mandatory_rust("P1"),
        ),
        models.Project(id="P2", title="P2", min_capacity=0, max_capacity=2),
    ]
    students = [
        models.Student(id="S1", display_name="S1", skills={"rust": 3}),
        models.Student(id="S2", display_name="S2", skills={"rust": 1}),
    ]
    fixed = [models.FixedAssignment(student_id="S2", project_id="P1")]

    _assert_solver_proves_infeasible(
        _engine(tmp_path), students, projects, fixed
    )


def test_edge_case_13_no_feasible_solution() -> None:
    """Case 13: Mathematical infeasibility detection by solver."""
    skills = [models.Skill(id="py", name="Python")]
    # P1 requires min 2 students, but only 1 student exists
    projects = [
        models.Project(id="P1", title="P1", min_capacity=2, max_capacity=2)
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[models.Preference("S1", "P1", 1)],
    )
    engine = solvers.AssignmentEngine()
    run = engine.run_assignment([s1], projects, skills, max_alternatives=2)
    assert run.status == "INFEASIBLE"
    assert len(run.solutions) == 0


def test_edge_case_14_single_feasible_solution() -> None:
    """Case 14: Only exactly 1 feasible allocation exists."""
    skills = [models.Skill(id="py", name="Python")]
    # Exactly 1 student, 1 project with cap 1
    projects = [
        models.Project(id="P1", title="P1", min_capacity=1, max_capacity=1)
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[models.Preference("S1", "P1", 1)],
    )
    engine = solvers.AssignmentEngine()
    run = engine.run_assignment([s1], projects, skills, max_alternatives=3)
    assert run.status == "COMPLETED"
    # Even though max_alternatives was 3, exactly 1 solution exists
    assert len(run.solutions) == 1
    assert run.diagnostics.get("distinct_alternatives") == 1


def test_edge_case_15_duplicate_avoidance_no_good_cuts() -> None:
    """Case 15: Distinct alternatives guarantee via no-good cuts."""
    skills = [models.Skill(id="py", name="Python")]
    # 2 students, 2 projects (cap 1 each): exactly 2 permutations
    projects = [
        models.Project(id="P1", title="P1", min_capacity=1, max_capacity=1),
        models.Project(id="P2", title="P2", min_capacity=1, max_capacity=1),
    ]
    s1 = models.Student(
        id="S1",
        display_name="S1",
        preferences=[
            models.Preference("S1", "P1", 1),
            models.Preference("S1", "P2", 2),
        ],
    )
    s2 = models.Student(
        id="S2",
        display_name="S2",
        preferences=[
            models.Preference("S2", "P1", 1),
            models.Preference("S2", "P2", 2),
        ],
    )
    engine = solvers.AssignmentEngine()
    run = engine.run_assignment([s1, s2], projects, skills, max_alternatives=3)
    assert run.status == "COMPLETED"
    # Exactly 2 distinct solutions exist, requested 3
    assert len(run.solutions) == 2

    # Verify solutions are strictly distinct
    sol1_alloc = {
        (a.student_id, a.project_id) for a in run.solutions[0].assignments
    }
    sol2_alloc = {
        (a.student_id, a.project_id) for a in run.solutions[1].assignments
    }
    assert sol1_alloc != sol2_alloc
