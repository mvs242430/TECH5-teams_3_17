"""Tests for Component A (Visualization & Recommendation) web workflows."""

import pathlib
from typing import Any

import pytest

from app import create_app
from app.contract import contract
from app.contract import mocks
from app.domain import models
from app.engine import strategies
from app.persistence import repositories
from app.samples import demo_data


def test_dashboard_loads(tmp_path: pathlib.Path) -> None:
    """Verifies dashboard overview page rendering."""
    db_file = tmp_path / "test_ui_dash.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    dash_res = client.get("/")
    assert dash_res.status_code == 200
    assert b"TECH5" in dash_res.data


def test_role_switcher(tmp_path: pathlib.Path) -> None:
    """Verifies role switching in session."""
    db_file = tmp_path / "test_role.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    res = client.post(
        "/set-role", data={"role": "STUDENT"}, follow_redirects=True
    )
    assert res.status_code == 200
    assert b"Switched role to Student Viewer" in res.data


def test_student_and_fixed_assignment_workflow(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies student and fixed-assignment creation workflows."""
    db_file = tmp_path / "test_stud_fixed.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Seed project P1 so student preference foreign key is valid
    repositories.ProjectRepository().save(
        models.Project(
            id="P1",
            title="FinTech Risk",
            min_capacity=1,
            max_capacity=2,
        )
    )

    # Create student
    res_stud = client.post(
        "/students/new",
        data={
            "id": "S1",
            "display_name": "Alice Chen",
            "preferences_text": "P1",
        },
        follow_redirects=True,
    )
    assert res_stud.status_code == 200
    assert b"Alice Chen" in res_stud.data

    # Create fixed assignment
    res_fixed = client.post(
        "/fixed-assignments/new",
        data={
            "student_id": "S1",
            "project_id": "P1",
            "status": "APPROVED",
            "reason": "Pre-matched",
        },
        follow_redirects=True,
    )
    assert res_fixed.status_code == 200
    assert b"Pre-matched" in res_fixed.data


def test_scenario_loading_and_optimization_trigger(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies benchmark scenario loading, execution, and result views."""
    db_file = tmp_path / "test_scenario_run.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Load standard benchmark
    load_res = client.post("/load-scenario/standard", follow_redirects=True)
    assert load_res.status_code == 200
    assert b"Standard Cohort" in load_res.data

    # Trigger optimization run (falls back to mock engine if solver unimplemented)
    run_res = client.post(
        "/runs/trigger",
        data={
            "primary_strategy": "PREFERENCE",
            "max_alternatives": 3,
        },
        follow_redirects=True,
    )
    assert run_res.status_code == 200
    assert b"Optimization run completed" in run_res.data

    runs = repositories.RunRepository().list_runs(limit=1)
    assert len(runs) == 1
    run = runs[0]
    assert len(run.solutions) >= 1

    # View solution detail
    sol_id = run.solutions[0].id
    sol_res = client.get(f"/solutions/{sol_id}")
    assert sol_res.status_code == 200
    assert b"Student-to-Project Allocations" in sol_res.data

    # View recommendations
    recs_res = client.get(f"/recommendations/{run.id}")
    assert recs_res.status_code == 200
    assert b"Transparent Decision Recommendations" in recs_res.data
    assert b"Calculated Evidence" in recs_res.data
    assert b"Policy Advice" in recs_res.data


def test_create_student_preference_validation(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies preference validation when creating a student."""
    db_file = tmp_path / "test_stud_pref_val.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    repositories.ProjectRepository().save(
        models.Project(
            id="P1",
            title="Project One",
            min_capacity=1,
            max_capacity=2,
        )
    )

    # 1. Invalid project preference should flash error and not crash
    res_invalid = client.post(
        "/students/new",
        data={
            "id": "S10",
            "display_name": "Test Student",
            "preferences_text": "P99, P100",
        },
        follow_redirects=True,
    )
    assert res_invalid.status_code == 200
    assert b"Invalid project ID(s) in preferences" in res_invalid.data

    # 2. Case-insensitive project preference should normalize and succeed
    res_valid = client.post(
        "/students/new",
        data={
            "id": "S10",
            "display_name": "Test Student",
            "preferences_text": "p1",
        },
        follow_redirects=True,
    )
    assert res_valid.status_code == 200
    assert b"created successfully" in res_valid.data

    saved = repositories.StudentRepository().get_by_id("S10")
    assert saved is not None
    assert len(saved.preferences) == 1
    assert saved.preferences[0].project_id == "P1"


def test_skills_crud_workflow(tmp_path: pathlib.Path) -> None:
    """Verifies skill CRUD workflow and authorization (Team A implementation)."""
    db_file = tmp_path / "test_skill.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # 1. Admin creates a new skill
    res = client.post(
        "/skills/new",
        data={
            "id": "py",
            "name": "Python",
            "description": "Python Programming",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"created successfully" in res.data

    saved = repositories.SkillRepository().get_by_id("py")
    assert saved is not None
    assert saved.id == "py"
    assert saved.name == "Python"
    assert saved.description == "Python Programming"

    # 2. Empty ID and invalid ID characters are rejected
    res_empty = client.post(
        "/skills/new",
        data={"id": "", "name": "Empty ID", "description": ""},
        follow_redirects=True,
    )
    assert res_empty.status_code == 200
    assert b"cannot be empty" in res_empty.data

    res_invalid = client.post(
        "/skills/new",
        data={"id": "Python-Bad!", "name": "Bad ID", "description": ""},
        follow_redirects=True,
    )
    assert res_invalid.status_code == 200
    assert b"may only contain lowercase letters" in res_invalid.data
    assert b"is-invalid" in res_invalid.data

    # 3. Duplicate skill ID is rejected and entered form data is retained
    res_dup = client.post(
        "/skills/new",
        data={
            "id": "py",
            "name": "Python Duplicate",
            "description": "Duplicate description",
        },
        follow_redirects=True,
    )
    assert res_dup.status_code == 200
    assert b"already exists" in res_dup.data
    assert b"Python Duplicate" in res_dup.data
    assert b"Duplicate description" in res_dup.data
    assert b"is-invalid" in res_dup.data
    # Verify original skill was not overwritten
    re_check = repositories.SkillRepository().get_by_id("py")
    assert re_check is not None
    assert re_check.name == "Python"

    # 4. Student Viewer is denied permission
    client.post("/set-role", data={"role": "STUDENT"}, follow_redirects=True)
    res_denied = client.post(
        "/skills/new",
        data={
            "id": "java",
            "name": "Java",
            "description": "Java Programming",
        },
        follow_redirects=True,
    )
    assert res_denied.status_code == 200
    assert b"Permission denied" in res_denied.data
    assert repositories.SkillRepository().get_by_id("java") is None

    # 5. Prevent deleting a skill in use by a student
    client.post("/set-role", data={"role": "ADMIN"}, follow_redirects=True)
    repositories.StudentRepository().save(
        models.Student(id="S1", display_name="Alice", skills={"py": 2})
    )
    res_in_use = client.post("/skills/py/delete", follow_redirects=True)
    assert res_in_use.status_code == 200
    assert b"still referenced by" in res_in_use.data
    assert repositories.SkillRepository().get_by_id("py") is not None

    # Remove student reference, then deletion succeeds
    repositories.StudentRepository().delete("S1")
    res_del = client.post("/skills/py/delete", follow_redirects=True)
    assert res_del.status_code == 200
    assert b"removed" in res_del.data
    assert repositories.SkillRepository().get_by_id("py") is None


def test_projects_crud_workflow(tmp_path: pathlib.Path) -> None:
    """Verifies project addition workflow (Team A implementation)."""
    db_file = tmp_path / "test_proj.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # 1. Admin login
    client.post("/set-role", data={"role": "ADMIN"}, follow_redirects=True)

    # Seed skill to associate with project requirement
    repositories.SkillRepository().save(
        models.Skill(id="py", name="Python", description="Python Programming")
    )

    # 2. Admin creates a new project with one mandatory requirement
    res = client.post(
        "/projects/new",
        data={
            "id": "P1",
            "title": "FinTech Risk",
            "description": "Risk analytics",
            "min_capacity": 1,
            "max_capacity": 2,
            "req_level_py": 3,
            "req_mand_py": 1,
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert (
        b"Project 'P1' created." in res.data
        or b"Project &#39;P1&#39; created." in res.data
    )

    saved = repositories.ProjectRepository().get_by_id("P1")
    assert saved is not None
    assert saved.id == "P1"
    assert saved.title == "FinTech Risk"
    assert saved.description == "Risk analytics"
    assert saved.min_capacity == 1
    assert saved.max_capacity == 2
    assert len(saved.requirements) == 1
    req = saved.requirements[0]
    assert req.skill_id == "py"
    assert req.minimum_level == 3
    assert req.is_mandatory is True

    # 3. Duplicate project ID is rejected and does not overwrite existing record
    res_dup = client.post(
        "/projects/new",
        data={
            "id": "P1",
            "title": "FinTech Risk Overwrite Attempt",
            "description": "Overwriting",
            "min_capacity": 2,
            "max_capacity": 4,
            "req_level_py": 5,
        },
        follow_redirects=True,
    )
    assert res_dup.status_code == 200
    assert b"already exists" in res_dup.data
    re_check = repositories.ProjectRepository().get_by_id("P1")
    assert re_check is not None
    assert re_check.title == "FinTech Risk"
    assert re_check.min_capacity == 1
    assert re_check.max_capacity == 2
    assert len(re_check.requirements) == 1
    assert re_check.requirements[0].minimum_level == 3

    # 4. min_capacity > max_capacity is rejected and not saved
    res_invalid = client.post(
        "/projects/new",
        data={
            "id": "P2",
            "title": "Invalid Capacity Project",
            "description": "Min exceeds max",
            "min_capacity": 5,
            "max_capacity": 2,
        },
        follow_redirects=True,
    )
    assert res_invalid.status_code == 200
    assert (
        b"Minimum capacity cannot exceed maximum capacity" in res_invalid.data
    )
    assert repositories.ProjectRepository().get_by_id("P2") is None

    # 5. Edit page shows the saved level
    res_get_edit = client.get("/projects/P1/edit")
    assert res_get_edit.status_code == 200
    assert b"FinTech Risk" in res_get_edit.data
    assert b'name="req_level_py"' in res_get_edit.data
    assert b'value="3"' in res_get_edit.data

    # 6. Admin edits the project (changes title, requirement level, unticks mandatory)
    res_edit = client.post(
        "/projects/P1/edit",
        data={
            "title": "FinTech Advanced Analytics",
            "description": "Updated risk analytics scope",
            "min_capacity": 2,
            "max_capacity": 4,
            "req_level_py": 4,
            # req_mand_py unticked / omitted
        },
        follow_redirects=True,
    )
    assert res_edit.status_code == 200
    assert (
        b"Project 'P1' updated." in res_edit.data
        or b"Project &#39;P1&#39; updated." in res_edit.data
    )

    updated = repositories.ProjectRepository().get_by_id("P1")
    assert updated is not None
    assert updated.title == "FinTech Advanced Analytics"
    assert updated.min_capacity == 2
    assert updated.max_capacity == 4
    assert len(updated.requirements) == 1
    req_updated = updated.requirements[0]
    assert req_updated.skill_id == "py"
    assert req_updated.minimum_level == 4
    assert req_updated.is_mandatory is False

    # 7. Seed student preference on P1 and verify delete cascades
    repositories.StudentRepository().save(
        models.Student(
            id="S1",
            display_name="Student One",
            preferences=[
                models.Preference(student_id="S1", project_id="P1", rank=1)
            ],
        )
    )

    res_del = client.post("/projects/P1/delete", follow_redirects=True)
    assert res_del.status_code == 200
    assert (
        b"Project 'P1' deleted" in res_del.data
        or b"Project &#39;P1&#39; deleted" in res_del.data
    )
    assert (
        b"1 student preferences removed" in res_del.data
        or b"student preferences removed" in res_del.data
    )
    assert repositories.ProjectRepository().get_by_id("P1") is None

    # 8. Student Viewer gets "Permission denied" on create, edit, and delete
    client.post("/set-role", data={"role": "STUDENT"}, follow_redirects=True)

    # Student Viewer denied on create
    res_student_create = client.post(
        "/projects/new",
        data={
            "id": "P_DENIED",
            "title": "Unauthorized Project",
            "min_capacity": 1,
            "max_capacity": 2,
        },
        follow_redirects=True,
    )
    assert res_student_create.status_code == 200
    assert b"Permission denied" in res_student_create.data
    assert repositories.ProjectRepository().get_by_id("P_DENIED") is None

    # Student Viewer denied on edit
    res_student_edit = client.post(
        "/projects/P1/edit",
        data={"title": "Unauthorized Edit"},
        follow_redirects=True,
    )
    assert res_student_edit.status_code == 200
    assert b"Permission denied" in res_student_edit.data

    # Student Viewer denied on delete
    res_student_delete = client.post(
        "/projects/P1/delete", follow_redirects=True
    )
    assert res_student_delete.status_code == 200
    assert b"Permission denied" in res_student_delete.data



def test_compare_solutions_view(tmp_path: pathlib.Path) -> None:
    """Verifies solution comparison controller (Team A implementation).

    Arrange: Seed a mock run with at least two solutions via
    MockAssignmentEngine so that real solution UUIDs are available in the
    test-isolated database.

    Act (happy path): GET /compare?sol1=<id>&sol2=<id> with both known IDs.
    Assert: HTTP 200 and the KPI card sentinel text 'Changed Student
    Allocations'.

    Act (unknown ID): GET /compare?sol1=bad-id&sol2=bad-id.
    Assert: HTTP 302 redirect, never an error page.
    """
    from app.contract import mocks as contract_mocks
    from app.contract import contract

    db_file = tmp_path / "test_comp.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # --- Arrange: seed a mock run with two solutions in the test DB. ---
    with app.app_context():
        # Build a minimal cohort so MockAssignmentEngine generates >= 2 solutions.
        students = [
            models.Student(id="S1", display_name="Alice"),
            models.Student(id="S2", display_name="Bob"),
        ]
        projects = [
            models.Project(
                id="P1", title="Alpha", min_capacity=1, max_capacity=2
            ),
            models.Project(
                id="P2", title="Beta", min_capacity=1, max_capacity=2
            ),
        ]
        req = contract.RunRequest(
            students=students,
            projects=projects,
            skills=[],
            fixed_assignments=[],
            strategy_key="PREFERENCE",
            max_alternatives=2,
        )
        run = contract_mocks.MockAssignmentEngine().execute_run(req)

    # We need at least two distinct solutions to compare.
    assert len(run.solutions) >= 2, (
        "MockAssignmentEngine must return at least 2 solutions for this test"
    )
    sol1_id = run.solutions[0].id
    sol2_id = run.solutions[1].id

    # --- Act (happy path): valid comparison. ---
    res = client.get(f"/compare?sol1={sol1_id}&sol2={sol2_id}")
    assert res.status_code == 200
    assert b"Changed Student Allocations" in res.data

    # --- Act (unknown IDs): must redirect, never raise a 500. ---
    bad_res = client.get("/compare?sol1=bad-id&sol2=bad-id")
    assert bad_res.status_code == 302


# -----------------------------------------------------------------------------
# Issue A1.3 - Friendly messages for bad data (one test per case)
# -----------------------------------------------------------------------------


@pytest.fixture
def seeded_client(tmp_path: pathlib.Path):
    """Admin test client with one skill and three projects in the catalog."""
    db_file = tmp_path / "test_bad_data.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()
    client.post("/set-role", data={"role": "ADMIN"}, follow_redirects=True)

    repositories.SkillRepository().save(
        models.Skill(id="py", name="Python", description="Python Programming")
    )
    for p_id in ("P1", "P2", "P3"):
        repositories.ProjectRepository().save(
            models.Project(
                id=p_id, title=f"Project {p_id}", min_capacity=1, max_capacity=3
            )
        )
    return client


def _post_project(client, **overrides):
    """Posts the new-project form with valid defaults plus overrides."""
    data = {
        "id": "PX",
        "title": "New Project",
        "description": "",
        "min_capacity": "1",
        "max_capacity": "3",
        "req_level_py": "0",
    }
    data.update(overrides)
    return client.post("/projects/new", data=data, follow_redirects=True)


def _post_student(client, **overrides):
    """Posts the new-student form with valid defaults plus overrides."""
    data = {
        "id": "SX",
        "display_name": "New Student",
        "skill_py": "2",
        "preferences_text": "P1, P2, P3",
    }
    data.update(overrides)
    return client.post("/students/new", data=data, follow_redirects=True)


def test_project_min_capacity_above_max_shows_message(seeded_client) -> None:
    """Min seats bigger than max seats is refused with a clear message."""
    res = _post_project(seeded_client, min_capacity="5", max_capacity="2")
    assert res.status_code == 200
    assert b"Minimum capacity cannot exceed maximum capacity" in res.data
    assert repositories.ProjectRepository().get_by_id("PX") is None


@pytest.mark.parametrize(
    ("min_cap", "max_cap", "expected"),
    [
        ("-1", "3", b"Capacities cannot be negative"),
        ("", "3", b"Minimum and maximum capacity are both required"),
        ("1", "", b"Minimum and maximum capacity are both required"),
        ("one", "3", b"Capacities must be whole numbers"),
        ("0", "0", b"Maximum capacity must be at least 1 seat"),
    ],
)
def test_project_negative_or_empty_capacity_shows_message(
    seeded_client, min_cap: str, max_cap: str, expected: bytes
) -> None:
    """Negative, empty or non-numeric capacity is refused, never crashes."""
    res = _post_project(seeded_client, min_capacity=min_cap, max_capacity=max_cap)
    assert res.status_code == 200
    assert expected in res.data
    assert repositories.ProjectRepository().get_by_id("PX") is None


def test_project_unknown_skill_shows_message(seeded_client) -> None:
    """A requirement for a skill that is not in the catalog is refused."""
    res = _post_project(seeded_client, req_level_rust="3")
    assert res.status_code == 200
    assert b"does not exist" in res.data
    assert repositories.ProjectRepository().get_by_id("PX") is None


@pytest.mark.parametrize("level", ["6", "-1", "abc"])
def test_project_skill_level_outside_range_shows_message(
    seeded_client, level: str
) -> None:
    """A required skill level outside 0-5 is refused instead of dropped."""
    res = _post_project(seeded_client, req_level_py=level)
    assert res.status_code == 200
    assert b"Required level for skill" in res.data
    assert repositories.ProjectRepository().get_by_id("PX") is None


def test_duplicate_project_id_shows_message(seeded_client) -> None:
    """Creating a project with an existing id does not overwrite it."""
    res = _post_project(seeded_client, id="P1", title="Overwritten")
    assert res.status_code == 200
    assert b"already exists" in res.data
    assert repositories.ProjectRepository().get_by_id("P1").title == "Project P1"


def test_student_unknown_skill_shows_message(seeded_client) -> None:
    """A skill level for a skill that is not in the catalog is refused."""
    res = _post_student(seeded_client, skill_rust="3")
    assert res.status_code == 200
    assert b"does not exist" in res.data
    assert repositories.StudentRepository().get_by_id("SX") is None


@pytest.mark.parametrize("level", ["7", "-2", "abc"])
def test_student_skill_level_outside_range_shows_message(
    seeded_client, level: str
) -> None:
    """A student skill level outside 0-5 is refused, never saved."""
    res = _post_student(seeded_client, skill_py=level)
    assert res.status_code == 200
    assert b"Level for skill" in res.data
    assert repositories.StudentRepository().get_by_id("SX") is None


def test_duplicate_student_id_shows_message(seeded_client) -> None:
    """Creating a student with an existing id does not overwrite it."""
    first = _post_student(seeded_client, id="S1", display_name="Alice")
    assert b"created successfully" in first.data

    res = _post_student(seeded_client, id="S1", display_name="Bob")
    assert res.status_code == 200
    assert b"already exists" in res.data
    assert repositories.StudentRepository().get_by_id("S1").display_name == (
        "Alice"
    )


def test_student_preference_for_unknown_project_shows_message(
    seeded_client,
) -> None:
    """A preference for a project that does not exist is refused."""
    res = _post_student(seeded_client, preferences_text="P1, P99, P2")
    assert res.status_code == 200
    assert b"Invalid project ID(s) in preferences: P99" in res.data
    assert repositories.StudentRepository().get_by_id("SX") is None


def test_student_same_project_ranked_twice_shows_message(seeded_client) -> None:
    """Listing a project twice (two ranks for one project) is refused."""
    res = _post_student(seeded_client, preferences_text="P1, P2, p1")
    assert res.status_code == 200
    assert b"listed more than once in preferences: P1" in res.data
    assert repositories.StudentRepository().get_by_id("SX") is None


def test_student_fewer_than_three_preferences_warns_but_saves(
    seeded_client,
) -> None:
    """Fewer than 3 preferences gives a warning, but the student is saved."""
    res = _post_student(seeded_client, preferences_text="P1")
    assert res.status_code == 200
    assert b"at least 3 are recommended" in res.data
    assert b"created successfully" in res.data
    saved = repositories.StudentRepository().get_by_id("SX")
    assert saved is not None
    assert [p.project_id for p in saved.preferences] == ["P1"]


def test_student_update_with_bad_data_keeps_old_values(seeded_client) -> None:
    """Editing a student with a bad skill level keeps the saved data."""
    _post_student(seeded_client, id="S2", display_name="Carla")
    res = seeded_client.post(
        "/students/S2/edit",
        data={
            "display_name": "Carla",
            "skill_py": "9",
            "preferences_text": "P3, P2, P1",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Level for skill" in res.data
    saved = repositories.StudentRepository().get_by_id("S2")
    assert saved.get_skill_level("py") == 2
    assert [p.project_id for p in saved.preferences] == ["P1", "P2", "P3"]


def test_project_mandatory_skill_requires_level(seeded_client) -> None:
    """Ticking Mandatory with skill level 0 is rejected on create and edit (A1.2.1)."""
    # 1. Create with mandatory ticked but level 0
    res_create = _post_project(
        seeded_client, req_level_py="0", req_mand_py="1"
    )
    assert res_create.status_code == 200
    assert b"Cannot mark skill" in res_create.data
    assert b"mandatory without selecting a required minimum level" in res_create.data
    assert b'name="req_mand_py" value="1" checked' in res_create.data
    assert repositories.ProjectRepository().get_by_id("PX") is None

    # 2. Edit existing project P1 with mandatory ticked and level 0
    res_edit = seeded_client.post(
        "/projects/P1/edit",
        data={
            "title": "Project P1 Edited",
            "description": "",
            "min_capacity": "1",
            "max_capacity": "3",
            "req_level_py": "0",
            "req_mand_py": "1",
        },
        follow_redirects=True,
    )
    assert res_edit.status_code == 200
    assert b"Cannot mark skill" in res_edit.data
    p1 = repositories.ProjectRepository().get_by_id("P1")
    assert p1 is not None
    assert p1.title == "Project P1"
    assert len(p1.requirements) == 0


def test_projects_edge_cases_and_full_layers(tmp_path: pathlib.Path) -> None:
    """Verifies empty-ID state retention, catalog badges, edit prefill, and DB cascades (A1.2.2)."""
    db_file = tmp_path / "test_proj_layers.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()
    client.post("/set-role", data={"role": "ADMIN"}, follow_redirects=True)

    repositories.SkillRepository().save(
        models.Skill(id="py", name="Python", description="Python Programming")
    )
    repositories.SkillRepository().save(
        models.Skill(id="sql", name="SQL", description="Database Querying")
    )

    # 1. Empty project ID retains entered skill levels and mandatory checkboxes
    res_empty_id = client.post(
        "/projects/new",
        data={
            "id": "",
            "title": "Draft Project",
            "description": "Draft scope",
            "min_capacity": "1",
            "max_capacity": "3",
            "req_level_py": "4",
            "req_mand_py": "1",
        },
        follow_redirects=True,
    )
    assert res_empty_id.status_code == 200
    assert b"Project ID cannot be empty" in res_empty_id.data
    assert b'name="req_level_py" min="0" max="5" class="form-control" value="4"' in res_empty_id.data
    assert b'name="req_mand_py" value="1" checked' in res_empty_id.data

    # 2. Create project with mandatory (py=4) and nice-to-have (sql=2) requirements
    res_create = client.post(
        "/projects/new",
        data={
            "id": "P10",
            "title": "Data Platform",
            "description": "End-to-end lakehouse",
            "min_capacity": "1",
            "max_capacity": "3",
            "req_level_py": "4",
            "req_mand_py": "1",
            "req_level_sql": "2",
        },
        follow_redirects=True,
    )
    assert res_create.status_code == 200
    assert b"1 &ndash; 3 seats" in res_create.data
    assert b"py: L4 (Must-have)" in res_create.data
    assert b"sql: L2 (Nice-to-have)" in res_create.data

    # Verify raw SQLite rows in projects and project_requirements
    db = repositories.ProjectRepository().db
    proj_rows = db.execute_query(
        "SELECT id, title, min_capacity, max_capacity FROM projects WHERE id = ?;",
        ("P10",),
    )
    assert len(proj_rows) == 1
    assert proj_rows[0]["min_capacity"] == 1
    assert proj_rows[0]["max_capacity"] == 3

    req_rows = db.execute_query(
        "SELECT skill_id, minimum_level, is_mandatory FROM project_requirements "
        "WHERE project_id = ? ORDER BY skill_id ASC;",
        ("P10",),
    )
    assert len(req_rows) == 2
    assert dict(req_rows[0]) == {
        "skill_id": "py",
        "minimum_level": 4,
        "is_mandatory": 1,
    }
    assert dict(req_rows[1]) == {
        "skill_id": "sql",
        "minimum_level": 2,
        "is_mandatory": 0,
    }

    # 3. Edit form pre-fills checked attribute for mandatory py and not for sql
    res_edit_get = client.get("/projects/P10/edit")
    assert res_edit_get.status_code == 200
    assert b'name="req_mand_py" value="1" checked>' in res_edit_get.data
    assert b'name="req_mand_sql" value="1" >' in res_edit_get.data

    # 4. Edit project to remove sql (req_level_sql=0) and verify SQLite sync
    res_edit_post = client.post(
        "/projects/P10/edit",
        data={
            "title": "Data Platform v2",
            "description": "Updated lakehouse",
            "min_capacity": "2",
            "max_capacity": "4",
            "req_level_py": "5",
            "req_mand_py": "1",
            "req_level_sql": "0",
        },
        follow_redirects=True,
    )
    assert res_edit_post.status_code == 200
    assert b"2 &ndash; 4 seats" in res_edit_post.data
    assert b"py: L5 (Must-have)" in res_edit_post.data
    assert b"sql: L2" not in res_edit_post.data

    req_rows_after = db.execute_query(
        "SELECT skill_id, minimum_level, is_mandatory FROM project_requirements "
        "WHERE project_id = ?;",
        ("P10",),
    )
    assert len(req_rows_after) == 1
    assert req_rows_after[0]["skill_id"] == "py"
    assert req_rows_after[0]["minimum_level"] == 5

    # 5. Seed student preference and fixed assignment, then delete P10 and verify cascades
    repositories.StudentRepository().save(
        models.Student(
            id="S100",
            display_name="Cascade Student",
            preferences=[
                models.Preference(student_id="S100", project_id="P10", rank=1)
            ],
        )
    )
    repositories.FixedAssignmentRepository().save(
        models.FixedAssignment(
            student_id="S100",
            project_id="P10",
            status="APPROVED",
            reason="Lock test",
        )
    )

    res_del = client.post("/projects/P10/delete", follow_redirects=True)
    assert res_del.status_code == 200
    assert (
        db.execute_query("SELECT * FROM projects WHERE id = 'P10';") == []
    )
    assert (
        db.execute_query(
            "SELECT * FROM project_requirements WHERE project_id = 'P10';"
        )
        == []
    )
    assert (
        db.execute_query("SELECT * FROM preferences WHERE project_id = 'P10';")
        == []
    )
    assert (
        db.execute_query(
            "SELECT * FROM fixed_assignments WHERE project_id = 'P10';"
        )
        == []
    )


# -----------------------------------------------------------------------------
# Issue A2.3 - "Lock and re-run" button works properly
# -----------------------------------------------------------------------------


def test_student_viewer_cannot_lock_and_rerun(tmp_path: pathlib.Path) -> None:
    """Verifies that Student Viewer role cannot perform lock and re-run."""
    db_file = tmp_path / "test_lock_denied.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # 1. Seed standard scenario and trigger an initial run
    client.post("/load-scenario/standard", follow_redirects=True)
    engine = mocks.MockAssignmentEngine()
    req = contract.RunRequest(
        students=repositories.StudentRepository().list_all(),
        projects=repositories.ProjectRepository().list_all(),
        skills=repositories.SkillRepository().list_all(),
        strategy_key="PREFERENCE",
        max_alternatives=2,
    )
    run = engine.execute_run(req)
    assert run.solutions
    sol_id = run.solutions[0].id

    # 2. Switch role to STUDENT
    client.post("/set-role", data={"role": "STUDENT"}, follow_redirects=True)

    # 3. Attempt lock and re-run
    res = client.post(
        f"/solutions/{sol_id}/lock-and-rerun",
        data={"student_id": "S01", "project_id": "P1"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Permission denied for current role." in res.data

    # 4. Verify no fixed assignment was created
    fixed = repositories.FixedAssignmentRepository().list_all()
    assert len(fixed) == 0

    # 5. Verify no rerun was created
    runs = repositories.RunRepository().list_runs()
    assert len(runs) == 1


def test_lock_and_rerun_creates_exactly_one_fixed_assignment_and_preserves_strategy(
    tmp_path: pathlib.Path,
) -> None:
    """Verifies locking creates exactly one lock, keeps strategy, and reports changes."""
    db_file = tmp_path / "test_lock_rerun.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # 1. Seed standard scenario and execute initial run with EGALITARIAN strategy
    client.post("/load-scenario/standard", follow_redirects=True)
    engine = mocks.MockAssignmentEngine()
    req = contract.RunRequest(
        students=repositories.StudentRepository().list_all(),
        projects=repositories.ProjectRepository().list_all(),
        skills=repositories.SkillRepository().list_all(),
        strategy_key="EGALITARIAN",
        max_alternatives=2,
    )
    run = engine.execute_run(req)
    assert run.solutions
    sol = run.solutions[0]
    initial_assigned_proj = sol.assignments[0].project_id
    target_student = sol.assignments[0].student_id

    # Choose a different project to lock to
    all_projects = repositories.ProjectRepository().list_all()
    other_proj = next(
        p.id for p in all_projects if p.id != initial_assigned_proj
    )

    # 2. As Admin or Coordinator, trigger lock and re-run
    client.post(
        "/set-role", data={"role": "COORDINATOR"}, follow_redirects=True
    )
    res = client.post(
        f"/solutions/{sol.id}/lock-and-rerun",
        data={"student_id": target_student, "project_id": other_proj},
        follow_redirects=True,
    )
    assert res.status_code == 200

    # 3. Assert exactly one fixed assignment exists
    fixed_assignments = repositories.FixedAssignmentRepository().list_all()
    assert len(fixed_assignments) == 1
    assert fixed_assignments[0].student_id == target_student
    assert fixed_assignments[0].project_id == other_proj

    # 4. Assert strategy was preserved in the rerun
    runs = repositories.RunRepository().list_runs()
    assert len(runs) == 2
    latest_run = runs[0]
    assert latest_run.configuration.get("primary_strategy") == "EGALITARIAN"

    # 5. Assert the flash message shows changed students count and link to /compare
    assert b"students changed compared with the previous run" in res.data
    assert b"/compare" in res.data



# -----------------------------------------------------------------------------
# A1 follow-up - ID format and project size limits (review feedback)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize("bad_id", ["P 1", "P1!", "Ä1", "P" * 21])
def test_project_id_with_invalid_format_shows_message(
    seeded_client, bad_id: str
) -> None:
    """Project IDs with spaces, symbols or more than 20 characters are refused."""
    res = _post_project(seeded_client, id=bad_id)
    assert res.status_code == 200
    assert b"may only contain letters, digits" in res.data
    assert repositories.ProjectRepository().get_by_id(bad_id) is None
    # The rest of the form is kept so the user does not retype it.
    assert b"New Project" in res.data


@pytest.mark.parametrize("good_id", ["P10", "P_DATA-2", "p" * 20])
def test_project_id_with_valid_format_is_saved(
    seeded_client, good_id: str
) -> None:
    """Short codes with letters, digits, '_' and '-' are still accepted."""
    _post_project(seeded_client, id=good_id)
    assert repositories.ProjectRepository().get_by_id(good_id) is not None


@pytest.mark.parametrize(
    ("min_cap", "max_cap"), [("1000", "1000"), ("1", "51"), ("51", "60")]
)
def test_project_capacity_above_limit_shows_message(
    seeded_client, min_cap: str, max_cap: str
) -> None:
    """Unrealistic seat numbers (above 50) are refused with a clear message."""
    res = _post_project(seeded_client, min_capacity=min_cap, max_capacity=max_cap)
    assert res.status_code == 200
    assert b"Capacities cannot exceed 50 seats per project" in res.data
    assert repositories.ProjectRepository().get_by_id("PX") is None


def test_project_capacity_at_limit_is_saved(seeded_client) -> None:
    """Exactly 50 seats is still allowed."""
    _post_project(seeded_client, min_capacity="50", max_capacity="50")
    saved = repositories.ProjectRepository().get_by_id("PX")
    assert saved is not None
    assert saved.max_capacity == 50


@pytest.mark.parametrize("bad_id", ["S 1", "S1;", "S" * 21])
def test_student_id_with_invalid_format_shows_message(
    seeded_client, bad_id: str
) -> None:
    """Student IDs follow the same format rule as project IDs."""
    res = _post_student(seeded_client, id=bad_id)
    assert res.status_code == 200
    assert b"may only contain letters, digits" in res.data
    assert repositories.StudentRepository().get_by_id(bad_id) is None


# -----------------------------------------------------------------------------
# Issue A2.1.1 - Compare page with solutions from different cohorts
# -----------------------------------------------------------------------------


@pytest.fixture
def real_engine_client(tmp_path: pathlib.Path):
    """Admin test client on an empty database, using the real engine."""
    db_file = tmp_path / "test_compare_cohort.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    return app.test_client()


def _run_engine(client) -> models.AssignmentRun:
    """Triggers one run through the web route and returns that new run."""
    repo = repositories.RunRepository()
    known_ids = {run.id for run in repo.list_runs(limit=100)}
    client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 3},
        follow_redirects=True,
    )
    new_id = next(
        run.id for run in repo.list_runs(limit=100) if run.id not in known_ids
    )
    return repo.get_run(new_id)


def _load_and_run(client, scenario: str = "standard") -> models.AssignmentRun:
    """Loads a benchmark scenario, then runs the engine on it."""
    client.post(f"/load-scenario/{scenario}", follow_redirects=True)
    return _run_engine(client)


def test_compare_same_cohort_across_runs_still_works(
    real_engine_client,
) -> None:
    """Two runs of the same students compare normally."""
    first = _load_and_run(real_engine_client)
    second = _run_engine(real_engine_client)

    res = real_engine_client.get(
        f"/compare?sol1={first.solutions[0].id}"
        f"&sol2={second.solutions[1].id}"
    )

    assert res.status_code == 200
    assert b"Changed Student Allocations" in res.data


def test_compare_shows_worst_rank_delta(real_engine_client) -> None:
    """The page shows the worst-rank change, signed as B minus A."""
    run = _load_and_run(real_engine_client)
    alt_1, alt_2 = run.solutions[0], run.solutions[1]
    delta = (
        alt_2.indicators["fairness"]["worst_rank"]
        - alt_1.indicators["fairness"]["worst_rank"]
    )
    assert delta == 1

    res = real_engine_client.get(f"/compare?sol1={alt_1.id}&sol2={alt_2.id}")

    page = res.get_data(as_text=True)
    card = page.split("&Delta; Worst Rank", maxsplit=1)[1].split(
        "kpi-sub", maxsplit=1
    )[0]
    assert "text-danger" in card
    assert "+1" in card
    assert "Worst individual preference rank worsened by 1." in page


def test_compare_shows_improved_worst_rank_as_good(real_engine_client) -> None:
    """Swapping A and B flips the sign and the colour of the same change."""
    run = _load_and_run(real_engine_client)
    alt_1, alt_2 = run.solutions[0], run.solutions[1]

    res = real_engine_client.get(f"/compare?sol1={alt_2.id}&sol2={alt_1.id}")

    card = res.get_data(as_text=True).split(
        "&Delta; Worst Rank", maxsplit=1
    )[1].split("kpi-sub", maxsplit=1)[0]
    assert "text-success" in card
    assert "-1" in card


def test_recommendations_do_not_claim_mathematical_optimality(
    real_engine_client,
) -> None:
    """A recommendation is the best alternative of the run, nothing more."""
    run = _load_and_run(real_engine_client)

    res = real_engine_client.get(f"/recommendations/{run.id}")

    assert res.status_code == 200
    assert b"mathematically optimal" not in res.data
    assert b"alternatives for that focus" in res.data


def test_lock_and_rerun_stopped_by_time_limit_does_not_claim_infeasible(
    real_engine_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rerun that stops without a proof warns without saying impossible."""
    run = _load_and_run(real_engine_client)
    assignment = run.solutions[0].assignments[0]
    monkeypatch.setattr(
        strategies._PyomoAssignmentStrategy,
        "solve",
        lambda *args, **kwargs: (
            "TIME_LIMIT",
            [],
            None,
            {"termination_condition": "maxTimeLimit"},
        ),
    )

    res = real_engine_client.post(
        f"/solutions/{run.solutions[0].id}/lock-and-rerun",
        data={
            "student_id": assignment.student_id,
            "project_id": assignment.project_id,
        },
        follow_redirects=True,
    )

    assert res.status_code == 200
    assert b"that the lock is impossible" in res.data
    assert b"could not find a feasible solution" not in res.data
    assert repositories.RunRepository().list_runs()[0].status == "FAILED"


def _lock_first_assignment(client: Any, run: models.AssignmentRun) -> Any:
    """Posts Lock & Rerun for the first assignment of the first solution."""
    solution = run.solutions[0]
    return client.post(
        f"/solutions/{solution.id}/lock-and-rerun",
        data={
            "student_id": solution.assignments[0].student_id,
            "project_id": solution.assignments[0].project_id,
        },
        follow_redirects=True,
    )


def _assert_rerun_is_not_reported_as_success(page: bytes) -> None:
    """Checks that a rerun with no solution warns and shows the saved lock."""
    assert b"students changed" not in page
    assert b"Compare with previous run" not in page
    assert b"alert-success" not in page
    assert b"is still locked to Project" in page
    assert b"Review fixed locks" in page


@pytest.mark.parametrize(
    ("solver_status", "run_status", "expected_warning"),
    [
        ("TIME_LIMIT", "FAILED", b"that the lock is impossible"),
        ("INFEASIBLE", "INFEASIBLE", b"could not find a feasible solution"),
    ],
)
def test_lock_and_rerun_without_solution_is_not_a_success(
    real_engine_client,
    monkeypatch: pytest.MonkeyPatch,
    solver_status: str,
    run_status: str,
    expected_warning: bytes,
) -> None:
    """A rerun that ends in the solver with no allocation only warns."""
    run = _load_and_run(real_engine_client)
    monkeypatch.setattr(
        strategies._PyomoAssignmentStrategy,
        "solve",
        lambda *args, **kwargs: (solver_status, [], None, {}),
    )

    res = _lock_first_assignment(real_engine_client, run)

    assert repositories.RunRepository().list_runs()[0].status == run_status
    assert expected_warning in res.data
    _assert_rerun_is_not_reported_as_success(res.data)


def test_lock_and_rerun_over_capacity_is_not_a_success(
    real_engine_client,
) -> None:
    """A real lock that overfills a project only warns."""
    solution = _load_and_run(real_engine_client).solutions[0]
    project = repositories.ProjectRepository().list_all()[0]
    student_ids = [s.id for s in repositories.StudentRepository().list_all()]
    fixed_repo = repositories.FixedAssignmentRepository()
    for student_id in student_ids[: project.max_capacity]:
        fixed_repo.save(
            models.FixedAssignment(
                student_id=student_id,
                project_id=project.id,
                status="APPROVED",
                reason="Fills the project for this test.",
            )
        )

    res = real_engine_client.post(
        f"/solutions/{solution.id}/lock-and-rerun",
        data={
            "student_id": student_ids[project.max_capacity],
            "project_id": project.id,
        },
        follow_redirects=True,
    )

    assert repositories.RunRepository().list_runs()[0].status == "INFEASIBLE"
    assert b"could not find a feasible solution" in res.data
    _assert_rerun_is_not_reported_as_success(res.data)


def test_failed_run_page_does_not_blame_constraints(
    real_engine_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run with no proof says so, and does not point at the constraints."""
    real_engine_client.post("/load-scenario/standard", follow_redirects=True)
    monkeypatch.setattr(
        strategies._PyomoAssignmentStrategy,
        "solve",
        lambda *args, **kwargs: ("TIME_LIMIT", [], None, {}),
    )

    run = _run_engine(real_engine_client)
    res = real_engine_client.get(f"/runs/{run.id}")

    assert run.status == "FAILED"
    assert b"Review constraint diagnostics" not in res.data
    assert b"does not mean the constraints are wrong" in res.data


def test_infeasible_run_page_still_points_to_constraints(
    real_engine_client,
) -> None:
    """An infeasible run keeps the pointer to its constraint diagnostics."""
    run = _load_and_run(real_engine_client, "infeasible")

    res = real_engine_client.get(f"/runs/{run.id}")

    assert run.status == "INFEASIBLE"
    assert b"Review constraint diagnostics" in res.data


def _stop_early_on_solve(
    monkeypatch: pytest.MonkeyPatch, solve_number: int
) -> None:
    """Makes one solve of a run stop early, keeping its real allocation."""
    real_solve = strategies._PyomoAssignmentStrategy.solve
    solves_done: list[int] = []

    def solve(self, *args: Any, **kwargs: Any) -> Any:
        solves_done.append(1)
        status, assignments, objective, diagnostics = real_solve(
            self, *args, **kwargs
        )
        if len(solves_done) == solve_number:
            status = "FEASIBLE"
            diagnostics = {
                **diagnostics,
                "termination_condition": "maxTimeLimit",
            }
        return status, assignments, objective, diagnostics

    monkeypatch.setattr(strategies._PyomoAssignmentStrategy, "solve", solve)


def test_solution_page_warns_only_on_unproven_solution(
    real_engine_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the alternative that stopped early carries the warning."""
    _stop_early_on_solve(monkeypatch, solve_number=2)
    run = _load_and_run(real_engine_client)
    proven, unproven = run.solutions[0], run.solutions[1]

    proven_res = real_engine_client.get(f"/solutions/{proven.id}")
    unproven_res = real_engine_client.get(f"/solutions/{unproven.id}")

    assert b"not proven optimal" not in proven_res.data
    assert b"not proven optimal" in unproven_res.data


def test_recommendations_name_unproven_alternatives(
    real_engine_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The recommendations page names the alternative that stopped early."""
    _stop_early_on_solve(monkeypatch, solve_number=2)
    run = _load_and_run(real_engine_client)

    res = real_engine_client.get(f"/recommendations/{run.id}")

    assert b"Not proven optimal: Alt 2." in res.data


def test_proven_run_has_no_unproven_notes(real_engine_client) -> None:
    """A normal run shows no unproven note on either page."""
    run = _load_and_run(real_engine_client)

    solution_res = real_engine_client.get(f"/solutions/{run.solutions[0].id}")
    recommendations_res = real_engine_client.get(f"/recommendations/{run.id}")

    assert b"not proven optimal" not in solution_res.data
    assert b"Not proven optimal" not in recommendations_res.data


def test_compare_different_students_shows_message(real_engine_client) -> None:
    """A 10-student and an 11-student solution give a message, not a crash."""
    before = _load_and_run(real_engine_client)
    real_engine_client.post(
        "/students/new",
        data={
            "id": "S11",
            "display_name": "New Student",
            "preferences_text": "P1, P2, P3",
        },
        follow_redirects=True,
    )
    after = _run_engine(real_engine_client)

    res = real_engine_client.get(
        f"/compare?sol1={before.solutions[0].id}"
        f"&sol2={after.solutions[0].id}",
        follow_redirects=True,
    )

    assert res.status_code == 200
    assert b"cover different students" in res.data
    assert b"Changed Student Allocations" not in res.data


def test_compare_after_scenario_reload_shows_message(
    real_engine_client,
) -> None:
    """An old solution emptied by a reload gives a message, not a crash."""
    old = _load_and_run(real_engine_client)
    new = _load_and_run(real_engine_client)

    res = real_engine_client.get(
        f"/compare?sol1={old.solutions[0].id}&sol2={new.solutions[0].id}",
        follow_redirects=True,
    )

    assert res.status_code == 200
    assert b"no longer has any assignments" in res.data
    assert b"Changed Student Allocations" not in res.data


def test_compare_two_emptied_solutions_shows_message(
    real_engine_client,
) -> None:
    """Two emptied solutions give a message instead of a blank comparison."""
    old = _load_and_run(real_engine_client)
    real_engine_client.post("/load-scenario/standard", follow_redirects=True)

    res = real_engine_client.get(
        f"/compare?sol1={old.solutions[0].id}&sol2={old.solutions[1].id}",
        follow_redirects=True,
    )

    assert res.status_code == 200
    assert b"no longer has any assignments" in res.data
    assert b"Changed Student Allocations" not in res.data


def test_compare_dropdown_hides_emptied_solutions(real_engine_client) -> None:
    """Only solutions that still have assignments can be selected."""
    old = _load_and_run(real_engine_client)
    new = _load_and_run(real_engine_client)

    res = real_engine_client.get("/compare")

    assert res.status_code == 200
    page = res.get_data(as_text=True)
    assert all(sol.id in page for sol in new.solutions)
    assert not any(sol.id in page for sol in old.solutions)


def test_solution_ids_with_assignments_skips_emptied_solutions(
    real_engine_client,
) -> None:
    """The repository lists solutions with assignments, not emptied ones."""
    old = _load_and_run(real_engine_client)
    new = _load_and_run(real_engine_client)

    ids = repositories.RunRepository().list_solution_ids_with_assignments()

    assert {sol.id for sol in new.solutions} == ids
    assert not ids & {sol.id for sol in old.solutions}


# -----------------------------------------------------------------------------
# Role checks on routes that delete data (clear data, clear solutions,
# load scenario)
# -----------------------------------------------------------------------------

PERMISSION_DENIED = b"Permission denied for current role."


@pytest.fixture
def standard_client(tmp_path: pathlib.Path) -> Any:
    """Test client with the standard benchmark and one saved mock run.

    The data is seeded as the default Admin role; each test then switches
    to the role it checks.
    """
    db_file = tmp_path / "test_delete_roles.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()
    client.post("/load-scenario/standard", follow_redirects=True)
    mocks.MockAssignmentEngine().execute_run(
        contract.RunRequest(
            students=repositories.StudentRepository().list_all(),
            projects=repositories.ProjectRepository().list_all(),
            skills=repositories.SkillRepository().list_all(),
            strategy_key="PREFERENCE",
            max_alternatives=2,
        )
    )
    return client


def _switch_role(client: Any, role: str) -> None:
    """Switches the active role of the test client."""
    client.post("/set-role", data={"role": role}, follow_redirects=True)


def _student_ids() -> set[str]:
    """Returns the IDs of all students in the database."""
    return {s.id for s in repositories.StudentRepository().list_all()}


def _run_ids() -> list[str]:
    """Returns the IDs of all saved runs in the database."""
    return [r.id for r in repositories.RunRepository().list_runs(limit=100)]


@pytest.mark.parametrize("role", ["COORDINATOR", "STUDENT"])
def test_clear_data_is_denied_for_non_admin(
    standard_client, role: str
) -> None:
    """Only the Administrator may wipe the cohort; the data stays."""
    students_before = _student_ids()
    projects_before = len(repositories.ProjectRepository().list_all())
    assert students_before and projects_before
    _switch_role(standard_client, role)

    res = standard_client.post("/clear-data", follow_redirects=True)

    assert res.status_code == 200
    assert PERMISSION_DENIED in res.data
    assert res.request.path == "/"
    assert _student_ids() == students_before
    assert len(repositories.ProjectRepository().list_all()) == projects_before


def test_clear_data_still_works_for_admin(standard_client) -> None:
    """The Administrator can still wipe the cohort."""
    _switch_role(standard_client, "ADMIN")

    res = standard_client.post("/clear-data", follow_redirects=True)

    assert res.status_code == 200
    assert b"All cohort data cleared." in res.data
    assert _student_ids() == set()
    assert repositories.ProjectRepository().list_all() == []


@pytest.mark.parametrize("role", ["COORDINATOR", "STUDENT"])
def test_load_scenario_is_denied_for_non_admin(
    standard_client, role: str
) -> None:
    """Loading a scenario first wipes the cohort, so only the Admin may."""
    # A student that no scenario contains shows whether the wipe ran.
    repositories.StudentRepository().save(
        models.Student(id="S_KEEP", display_name="Not in any scenario")
    )
    students_before = _student_ids()
    _switch_role(standard_client, role)

    res = standard_client.post("/load-scenario/fixed", follow_redirects=True)

    assert res.status_code == 200
    assert PERMISSION_DENIED in res.data
    assert res.request.path == "/"
    assert _student_ids() == students_before
    assert repositories.FixedAssignmentRepository().list_all() == []


def test_load_scenario_still_works_for_admin(standard_client) -> None:
    """The Administrator can still replace the cohort with a scenario."""
    repositories.StudentRepository().save(
        models.Student(id="S_KEEP", display_name="Not in any scenario")
    )
    _switch_role(standard_client, "ADMIN")

    res = standard_client.post("/load-scenario/fixed", follow_redirects=True)

    assert res.status_code == 200
    assert b"loaded successfully" in res.data
    assert "S_KEEP" not in _student_ids()
    assert len(repositories.FixedAssignmentRepository().list_all()) == 1


def test_load_unknown_scenario_keeps_cohort(standard_client) -> None:
    """A mistyped scenario name is refused before anything is deleted."""
    students_before = _student_ids()
    projects_before = len(repositories.ProjectRepository().list_all())
    assert students_before and projects_before
    _switch_role(standard_client, "ADMIN")

    res = standard_client.post("/load-scenario/typo", follow_redirects=True)

    assert res.status_code == 200
    assert b"Unknown scenario" in res.data
    assert _student_ids() == students_before
    assert len(repositories.ProjectRepository().list_all()) == projects_before


def test_clear_solutions_is_denied_for_student_viewer(standard_client) -> None:
    """A Student Viewer cannot delete runs; the saved run stays."""
    runs_before = _run_ids()
    assert runs_before
    _switch_role(standard_client, "STUDENT")

    res = standard_client.post("/clear-solutions", follow_redirects=True)

    assert res.status_code == 200
    assert PERMISSION_DENIED in res.data
    assert res.request.path == "/"
    assert _run_ids() == runs_before


@pytest.mark.parametrize("role", ["ADMIN", "COORDINATOR"])
def test_clear_solutions_still_works_for_run_roles(
    standard_client, role: str
) -> None:
    """Roles that can create runs can delete them; the cohort stays."""
    students_before = _student_ids()
    _switch_role(standard_client, role)

    res = standard_client.post("/clear-solutions", follow_redirects=True)

    assert res.status_code == 200
    assert b"All solutions cleared." in res.data
    assert _run_ids() == []
    assert _student_ids() == students_before


@pytest.mark.parametrize(
    ("role", "sees_cohort_buttons", "sees_clear_solutions"),
    [
        ("ADMIN", True, True),
        ("COORDINATOR", False, True),
        ("STUDENT", False, False),
    ],
)
def test_delete_buttons_shown_only_to_allowed_roles(
    standard_client,
    role: str,
    sees_cohort_buttons: bool,
    sees_clear_solutions: bool,
) -> None:
    """Dashboard and scenarios pages hide buttons the role cannot use."""
    _switch_role(standard_client, role)

    dashboard = standard_client.get("/").get_data(as_text=True)
    scenarios = standard_client.get("/scenarios").get_data(as_text=True)

    assert ("/load-scenario/" in dashboard) is sees_cohort_buttons
    assert ("/load-scenario/" in scenarios) is sees_cohort_buttons
    assert ("/clear-data" in scenarios) is sees_cohort_buttons
    assert ("/clear-solutions" in dashboard) is sees_clear_solutions


# -----------------------------------------------------------------------------
# Issue A2.4 - Who can do what (access check)
# -----------------------------------------------------------------------------

# Every POST route that changes data, with form data that an allowed role
# could post successfully. "{solution_id}" is replaced by a saved solution.
MUTATING_ROUTES = [
    (
        "/students/new",
        {"id": "S_NEW", "display_name": "New", "preferences_text": "P1"},
    ),
    (
        "/students/S01/edit",
        {"display_name": "Renamed", "preferences_text": "P1, P2, P3"},
    ),
    ("/students/S01/delete", {}),
    (
        "/projects/new",
        {
            "id": "P_NEW",
            "title": "New",
            "min_capacity": "1",
            "max_capacity": "3",
        },
    ),
    (
        "/projects/P1/edit",
        {"title": "Renamed", "min_capacity": "1", "max_capacity": "3"},
    ),
    ("/projects/P1/delete", {}),
    ("/skills/new", {"id": "go", "name": "Go", "description": ""}),
    ("/skills/rust/delete", {}),
    ("/fixed-assignments/new", {"student_id": "S01", "project_id": "P2"}),
    ("/fixed-assignments/S02/delete", {}),
    ("/load-scenario/fixed", {}),
    ("/clear-data", {}),
    ("/clear-solutions", {}),
    (
        "/runs/trigger",
        {"primary_strategy": "PREFERENCE", "max_alternatives": "1"},
    ),
    (
        "/solutions/{solution_id}/lock-and-rerun",
        {"student_id": "S01", "project_id": "P2"},
    ),
]

# POST routes that change only the session, never the database.
SESSION_ONLY_ENDPOINTS = {"visualization_web.set_role"}


def _seed_mutation_targets() -> str:
    """Adds rows the routes above act on and returns a saved solution ID.

    Adds a skill no project requires (so it can be deleted) and one fixed
    lock (so it can be released).

    Returns:
        The ID of the first solution of the run saved by `standard_client`.
    """
    repositories.SkillRepository().save(
        models.Skill(id="rust", name="Rust", description="")
    )
    repositories.FixedAssignmentRepository().save(
        models.FixedAssignment(student_id="S02", project_id="P2")
    )
    return repositories.RunRepository().list_runs()[0].solutions[0].id


def _db_snapshot() -> dict[str, list[tuple[Any, ...]]]:
    """Returns every row of every table, so any change to the data shows."""
    db = repositories.ProjectRepository().db
    tables = db.execute_query(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
    )
    snapshot: dict[str, list[tuple[Any, ...]]] = {}
    for table in tables:
        rows = db.execute_query(f"SELECT * FROM {table['name']};")
        # Sort by repr so rows with NULLs still sort without a TypeError.
        snapshot[table["name"]] = sorted(
            (tuple(row) for row in rows), key=repr
        )
    return snapshot


@pytest.mark.parametrize(("path", "form"), MUTATING_ROUTES)
def test_student_viewer_cannot_mutate(
    standard_client, path: str, form: dict[str, str]
) -> None:
    """A Student Viewer is refused on every data route; nothing changes."""
    solution_id = _seed_mutation_targets()
    before = _db_snapshot()
    _switch_role(standard_client, "STUDENT")

    res = standard_client.post(
        path.format(solution_id=solution_id), data=form, follow_redirects=True
    )

    assert res.status_code == 200
    assert PERMISSION_DENIED in res.data
    assert _db_snapshot() == before


@pytest.mark.parametrize(("path", "form"), MUTATING_ROUTES)
def test_admin_post_to_mutating_route_changes_data(
    standard_client, path: str, form: dict[str, str]
) -> None:
    """Control: each request above does change data for an allowed role.

    Without this, "nothing changed" in the Student Viewer test could come
    from bad form data rather than from the role check.
    """
    solution_id = _seed_mutation_targets()
    before = _db_snapshot()
    _switch_role(standard_client, "ADMIN")

    res = standard_client.post(
        path.format(solution_id=solution_id), data=form, follow_redirects=True
    )

    assert res.status_code == 200
    assert PERMISSION_DENIED not in res.data
    assert _db_snapshot() != before


def test_mutating_route_list_covers_every_post_route(standard_client) -> None:
    """A new POST route fails this test until it is added to the list."""
    url_map = standard_client.application.url_map
    adapter = url_map.bind("localhost")
    listed = {
        adapter.match(path.format(solution_id="x"), method="POST")[0]
        for path, _ in MUTATING_ROUTES
    }
    registered = {
        rule.endpoint
        for rule in url_map.iter_rules()
        if "POST" in rule.methods
    }

    assert listed | SESSION_ONLY_ENDPOINTS == registered


@pytest.mark.parametrize("role", ["ADMIN", "COORDINATOR"])
def test_lock_roles_can_create_fixed_assignment(
    standard_client, role: str
) -> None:
    """Admin and Coordinator may lock a student to a project."""
    _switch_role(standard_client, role)

    res = standard_client.post(
        "/fixed-assignments/new",
        data={"student_id": "S01", "project_id": "P2", "reason": "Sponsor"},
        follow_redirects=True,
    )

    assert res.status_code == 200
    assert b"Fixed assignment created" in res.data
    locks = repositories.FixedAssignmentRepository().list_all()
    assert [(fa.student_id, fa.project_id) for fa in locks] == [("S01", "P2")]


@pytest.mark.parametrize("role", ["ADMIN", "COORDINATOR"])
def test_lock_roles_can_release_fixed_assignment(
    standard_client, role: str
) -> None:
    """Admin and Coordinator may release an existing lock."""
    repositories.FixedAssignmentRepository().save(
        models.FixedAssignment(student_id="S02", project_id="P2")
    )
    _switch_role(standard_client, role)

    res = standard_client.post(
        "/fixed-assignments/S02/delete", follow_redirects=True
    )

    assert res.status_code == 200
    assert b"Fixed assignment for student &#39;S02&#39; removed." in res.data
    assert repositories.FixedAssignmentRepository().list_all() == []


@pytest.mark.parametrize(
    ("role", "sees_lock_controls"),
    [("ADMIN", True), ("COORDINATOR", True), ("STUDENT", False)],
)
def test_lock_controls_shown_only_to_lock_roles(
    standard_client, role: str, sees_lock_controls: bool
) -> None:
    """Lock form, Release and Lock & Rerun buttons follow the role check."""
    solution_id = _seed_mutation_targets()
    _switch_role(standard_client, role)

    locks_page = standard_client.get("/fixed-assignments").get_data(
        as_text=True
    )
    solution_page = standard_client.get(
        f"/solutions/{solution_id}"
    ).get_data(as_text=True)

    assert ('action="/fixed-assignments/new"' in locks_page) is (
        sees_lock_controls
    )
    assert ("/fixed-assignments/S02/delete" in locks_page) is (
        sees_lock_controls
    )
    assert ("/lock-and-rerun" in solution_page) is sees_lock_controls
