"""Tests for Component A (Visualization & Recommendation) web workflows."""

import pathlib

import pytest

from app import create_app
from app.domain import models
from app.persistence import repositories


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


@pytest.mark.xfail(
    raises=NotImplementedError,
    reason="TODO (Team A): Implement comparison controller & view",
)
def test_compare_solutions_view(tmp_path: pathlib.Path) -> None:
    """Verifies solution comparison controller (Team A implementation)."""
    db_file = tmp_path / "test_comp.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    client.get("/compare?sol1=S1&sol2=S2")


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
