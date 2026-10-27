"""Tests for Component A (Visualization & Recommendation) web workflows."""

import pathlib

import pytest

from app import create_app
from app.contract import contract
from app.contract import mocks
from app.domain import models
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
