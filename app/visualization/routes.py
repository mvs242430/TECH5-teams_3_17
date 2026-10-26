"""Web routes and controller logic for Component A (Visualization).

This module provides interactive CRUD interfaces, scenario seeders, optimization
triggering, multi-solution visual comparisons, and recommendations.
"""

import collections
import csv
import io
import re
import sqlite3
from typing import Any

import flask
import markupsafe

from app.contract import contract
from app.contract import mocks
from app.domain import models
from app.engine import recommendations
from app.engine import solvers
from app.persistence import repositories
from app.samples import demo_data
from app.visualization import auth

web_bp = flask.Blueprint("visualization_web", __name__)


@web_bp.app_context_processor
def inject_template_globals() -> dict[str, Any]:
    """Injects authorization helpers and active role into templates."""
    return {
        "current_role": auth.get_current_role(),
        "all_roles": auth.UserRole.ALL_ROLES,
        "can_edit": auth.can_edit_cohort_data(),
        "can_optimize": auth.can_trigger_optimization(),
    }


@web_bp.post("/set-role")
def set_role() -> flask.Response:
    """Updates the active user role prototype."""
    role = flask.request.form.get("role", auth.UserRole.ADMIN)
    auth.set_current_role(role)
    role_name = auth.UserRole.ALL_ROLES.get(role, role)
    flask.flash(f"Switched role to {role_name}.", "info")
    target = flask.request.referrer or flask.url_for(
        "visualization_web.dashboard"
    )
    return flask.redirect(target)


@web_bp.get("/")
def dashboard() -> str:
    """Renders main dashboard overview with cohort metrics and runs."""
    stud_repo = repositories.StudentRepository()
    proj_repo = repositories.ProjectRepository()
    fixed_repo = repositories.FixedAssignmentRepository()
    run_repo = repositories.RunRepository()

    students = stud_repo.list_all()
    projects = proj_repo.list_all()
    fixed_assignments = fixed_repo.list_all()
    runs = run_repo.list_runs(limit=10)

    total_capacity = sum(p.max_capacity for p in projects)
    latest_run = runs[0] if runs else None

    return flask.render_template(
        "dashboard.html",
        student_count=len(students),
        project_count=len(projects),
        total_capacity=total_capacity,
        fixed_count=len(fixed_assignments),
        recent_runs=runs,
        latest_run=latest_run,
    )


# -----------------------------------------------------------------------------
# Students CRUD
# -----------------------------------------------------------------------------


@web_bp.get("/students")
def list_students() -> str:
    """Lists all students with their proficiencies and ranked preferences."""
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "students.html",
        students=students,
        projects=projects,
        skills=skills,
    )


@web_bp.get("/students/new")
def new_student_form() -> str:
    """Displays form to create a new student."""
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "student_form.html",
        student=None,
        projects=projects,
        skills=skills,
    )


def _check_valid_student_data(
    student_id: str,
    student_name: str,
    available_students: dict[str, str],
) -> bool:
    """Checks if the student data is valid
    Args:
        student_id: Target student identifier.
        student_name: Target student name.
        available_students: Map of existing students id and name.
    Returns:
        A list of invalid students.
    """
    

    valid = 1

    if student_id in available_students:
        valid = 0
    elif student_name in available_students.values():
        valid = 0


    return valid


def _parse_and_validate_preferences(
    student_id: str,
    pref_raw: str,
    available_projects: dict[str, models.Project],
) -> tuple[list[models.Preference], list[str]]:
    """Parses and validates comma-separated project preferences.

    Args:
        student_id: Target student identifier.
        pref_raw: Comma-separated project IDs string from user input.
        available_projects: Map of valid project ID to Project model.

    Returns:
        A tuple of (valid_preferences_list, invalid_project_ids_list).
    """
    raw_tokens = [p.strip() for p in pref_raw.split(",") if p.strip()]
    case_map = {p_id.upper(): p_id for p_id in available_projects}

    valid_prefs: list[models.Preference] = []
    invalid_ids: list[str] = []
    seen: set[str] = set()

    for token in raw_tokens:
        resolved_id = None
        if token in available_projects:
            resolved_id = token
        elif token.upper() in case_map:
            resolved_id = case_map[token.upper()]
        else:
            invalid_ids.append(token)
            continue

        if resolved_id not in seen:
            seen.add(resolved_id)
            valid_prefs.append(
                models.Preference(
                    student_id=student_id,
                    project_id=resolved_id,
                    rank=len(valid_prefs) + 1,
                )
            )

    return valid_prefs, invalid_ids


def _parse_student_skills(
    valid_skill_ids: set[str],
) -> tuple[dict[str, int], list[str]]:
    """Reads ``skill_<id>`` fields from the form and validates them.

    A level of 0 (or an empty field) means the student does not have the
    skill. Levels must be whole numbers from 0 to 5, and only skills from
    the catalog are accepted.

    Args:
        valid_skill_ids: Identifiers of all skills in the catalog.

    Returns:
        A tuple of (skills_dict, error_messages). ``skills_dict`` maps
        skill id to level for every level above 0.
    """
    skills_dict: dict[str, int] = {}
    errors: list[str] = []
    for key, val in flask.request.form.items():
        if not key.startswith("skill_"):
            continue
        skill_id = key.removeprefix("skill_")
        raw = val.strip()
        if not raw:
            continue
        if skill_id not in valid_skill_ids:
            if raw != "0":
                errors.append(
                    f"Skill '{skill_id}' does not exist. Add it on the "
                    "Skills page first."
                )
            continue
        try:
            lvl = int(raw)
        except ValueError:
            errors.append(
                f"Level for skill '{skill_id}' must be a whole number "
                "between 0 and 5."
            )
            continue
        if not 0 <= lvl <= 5:
            errors.append(
                f"Level for skill '{skill_id}' is {lvl}; it must be "
                "between 0 (none) and 5."
            )
        elif lvl > 0:
            skills_dict[skill_id] = lvl
    return skills_dict, errors


def _find_repeated_preferences(
    pref_raw: str,
    available_projects: dict[str, models.Project],
) -> list[str]:
    """Finds projects that appear more than once in the preference list.

    Preferences are ranked by position, so listing a project twice would
    give it two ranks. Matching is case-insensitive, like the parser.

    Args:
        pref_raw: Comma-separated project IDs string from user input.
        available_projects: Map of valid project ID to Project model.

    Returns:
        Project IDs (catalog spelling) that are listed more than once.
    """
    case_map = {p_id.upper(): p_id for p_id in available_projects}
    seen: set[str] = set()
    repeated: list[str] = []
    for token in (p.strip() for p in pref_raw.split(",")):
        project_id = case_map.get(token.upper())
        if project_id is None:
            continue
        if project_id in seen and project_id not in repeated:
            repeated.append(project_id)
        seen.add(project_id)
    return repeated


def _validate_student_skills_and_preferences(
    student_id: str,
) -> tuple[dict[str, int], list[models.Preference], list[str], list[str]]:
    """Parses and validates skills and preferences of the student form.

    Shared by ``create_student`` and ``update_student`` so both apply the
    same rules (Issue A1.3).

    Args:
        student_id: Identifier of the student being created or edited.

    Returns:
        A tuple of (skills_dict, preferences, errors, warnings). Errors
        block saving; warnings are shown but the student is still saved.
    """
    valid_skill_ids = {s.id for s in repositories.SkillRepository().list_all()}
    skills_dict, errors = _parse_student_skills(valid_skill_ids)

    available_projects = {
        p.id: p for p in repositories.ProjectRepository().list_all()
    }
    pref_raw = flask.request.form.get("preferences_text", "")
    preferences, invalid_proj_ids = _parse_and_validate_preferences(
        student_id, pref_raw, available_projects
    )

    if invalid_proj_ids:
        valid_list = (
            ", ".join(sorted(available_projects.keys())) or "None available"
        )
        errors.append(
            f"Invalid project ID(s) in preferences: "
            f"{', '.join(invalid_proj_ids)}. "
            f"Available projects: {valid_list}."
        )

    repeated = _find_repeated_preferences(pref_raw, available_projects)
    if repeated:
        errors.append(
            f"Project(s) listed more than once in preferences: "
            f"{', '.join(repeated)}. Each project can have only one rank."
        )

    # Fewer than 3 choices is allowed, but the optimiser has less room to
    # find a good match, so we only warn. If the catalog has fewer than 3
    # projects, the student cannot list more than the catalog holds.
    recommended = min(3, len(available_projects))
    warnings: list[str] = []
    if not errors and len(preferences) < recommended:
        warnings.append(
            f"Only {len(preferences)} project preference(s) given; at "
            f"least {recommended} are recommended so the optimiser has "
            "alternatives."
        )

    return skills_dict, preferences, errors, warnings


@web_bp.post("/students/new")
def create_student() -> flask.Response:
    """Processes creation of a new student."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    s_id = flask.request.form.get("id", "").strip()
    name = flask.request.form.get("display_name", "").strip() or s_id

    available_students = {
        s.id: s.display_name for s in repositories.StudentRepository().list_all()
    }

    # Empty id is checked first: a duplicate check on "" is meaningless.
    if not s_id:
        flask.flash("Student ID cannot be empty.", "danger")
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )

    if not _check_valid_student_data(s_id, name, available_students):
        flask.flash(
            f"Student ID '{s_id}' or name '{name}' already exists.", "danger"
        )
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )

    skills_dict, preferences, errors, warnings = (
        _validate_student_skills_and_preferences(s_id)
    )
    if errors:
        for message in errors:
            flask.flash(message, "danger")
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )
    for message in warnings:
        flask.flash(f"Warning: {message}", "warning")

    student = models.Student(
        id=s_id,
        display_name=name,
        skills=skills_dict,
        preferences=preferences,
    )
    try:
        repositories.StudentRepository().save(student)
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while saving student: {exc}",
            "danger",
        )
        return flask.redirect(
            flask.url_for("visualization_web.new_student_form")
        )

    flask.flash(f"Student '{name}' ({s_id}) created successfully.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_students"))


@web_bp.get("/students/<student_id>/edit")
def edit_student_form(student_id: str) -> Any:
    """Displays form to edit an existing student."""
    student = repositories.StudentRepository().get_by_id(student_id)
    if not student:
        flask.flash(f"Student '{student_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "student_form.html",
        student=student,
        projects=projects,
        skills=skills,
    )


@web_bp.post("/students/<student_id>/edit")
def update_student(student_id: str) -> flask.Response:
    """Updates an existing student entity."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    name = (
        flask.request.form.get("display_name", "").strip() or student_id
    )

    if repositories.StudentRepository().get_by_id(student_id) is None:
        flask.flash(f"Student '{student_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    skills_dict, preferences, errors, warnings = (
        _validate_student_skills_and_preferences(student_id)
    )
    if errors:
        for message in errors:
            flask.flash(message, "danger")
        return flask.redirect(
            flask.url_for(
                "visualization_web.edit_student_form", student_id=student_id
            )
        )
    for message in warnings:
        flask.flash(f"Warning: {message}", "warning")

    student = models.Student(
        id=student_id,
        display_name=name,
        skills=skills_dict,
        preferences=preferences,
    )
    try:
        repositories.StudentRepository().save(student)
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while updating student: {exc}",
            "danger",
        )
        return flask.redirect(
            flask.url_for(
                "visualization_web.edit_student_form", student_id=student_id
            )
        )

    flask.flash(f"Student '{student_id}' updated.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_students"))


@web_bp.post("/students/<student_id>/delete")
def delete_student(student_id: str) -> flask.Response:
    """Deletes a student."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_students"))

    repositories.StudentRepository().delete(student_id)
    flask.flash(f"Student '{student_id}' removed.", "info")
    return flask.redirect(flask.url_for("visualization_web.list_students"))


# -----------------------------------------------------------------------------
# Projects CRUD
# -----------------------------------------------------------------------------


@web_bp.get("/projects")
def list_projects() -> str:
    """Displays project catalog and capacity definitions."""
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "projects.html", projects=projects, skills=skills
    )


@web_bp.get("/projects/new")
def new_project_form() -> str:
    """Displays form to create a semester project."""
    skills = repositories.SkillRepository().list_all()
    return flask.render_template(
        "project_form.html", project=None, skills=skills
    )


def _parse_and_validate_project_form(
    project_id: str,
    skills: list[models.Skill],
) -> tuple[
    models.Project | None,
    dict[str, Any],
    dict[str, int],
    dict[str, bool],
    str | None,
]:
    """Parses and validates project attributes and skill requirements from request.

    Args:
        project_id: Identifier of the project being created or edited.
        skills: List of catalogued skills to evaluate against the form.

    Returns:
        A tuple of (project, form_data, req_levels, req_mands, error_message).
        If validation fails, project is None and error_message contains the reason.
    """
    title = flask.request.form.get("title", "").strip()
    description = flask.request.form.get("description", "").strip()
    min_capacity_raw = flask.request.form.get("min_capacity", "").strip()
    max_capacity_raw = flask.request.form.get("max_capacity", "").strip()

    req_levels: dict[str, int] = {}
    req_mands: dict[str, bool] = {}
    # A1.3: collect skill-level problems instead of silently dropping them.
    skill_errors: list[str] = []

    for skill in skills:
        level_raw = flask.request.form.get(f"req_level_{skill.id}", "").strip()
        is_mand = bool(flask.request.form.get(f"req_mand_{skill.id}"))
        try:
            level = int(level_raw) if level_raw else 0
        except ValueError:
            level = 0
            skill_errors.append(
                f"Required level for skill '{skill.id}' must be a whole "
                "number between 0 and 5."
            )
        else:
            if not 0 <= level <= 5:
                skill_errors.append(
                    f"Required level for skill '{skill.id}' is {level}; "
                    "it must be between 0 (not required) and 5."
                )
            elif is_mand and level == 0:
                skill_errors.append(
                    f"Cannot mark skill '{skill.name}' ({skill.id}) as "
                    "mandatory without selecting a required minimum level "
                    "(1-5)."
                )
        req_levels[skill.id] = level
        req_mands[skill.id] = is_mand

    # A1.3: a requirement for a skill that is not in the catalog cannot be
    # saved (foreign key), so tell the user instead of ignoring it.
    known_skill_ids = {skill.id for skill in skills}
    for key, value in flask.request.form.items():
        if not key.startswith("req_level_"):
            continue
        skill_id = key.removeprefix("req_level_")
        if skill_id not in known_skill_ids and value.strip() not in ("", "0"):
            skill_errors.append(
                f"Skill '{skill_id}' does not exist. Add it on the Skills "
                "page first."
            )

    form_data = {
        "id": project_id,
        "title": title,
        "description": description,
        "min_capacity": min_capacity_raw,
        "max_capacity": max_capacity_raw,
    }

    if not title:
        return (
            None,
            form_data,
            req_levels,
            req_mands,
            "Project title cannot be empty.",
        )

    if not min_capacity_raw or not max_capacity_raw:
        return (
            None,
            form_data,
            req_levels,
            req_mands,
            "Minimum and maximum capacity are both required.",
        )

    try:
        min_capacity = int(min_capacity_raw)
        max_capacity = int(max_capacity_raw)
    except (ValueError, TypeError):
        return (
            None,
            form_data,
            req_levels,
            req_mands,
            "Capacities must be whole numbers.",
        )

    if min_capacity < 0 or max_capacity < 0:
        return (
            None,
            form_data,
            req_levels,
            req_mands,
            "Capacities cannot be negative.",
        )

    if min_capacity > max_capacity:
        return (
            None,
            form_data,
            req_levels,
            req_mands,
            "Minimum capacity cannot exceed maximum capacity.",
        )

    if max_capacity < 1:
        return (
            None,
            form_data,
            req_levels,
            req_mands,
            "Maximum capacity must be at least 1 seat.",
        )

    if skill_errors:
        return (
            None,
            form_data,
            req_levels,
            req_mands,
            " ".join(skill_errors),
        )

    requirements = [
        models.ProjectRequirement(
            project_id=project_id,
            skill_id=skill.id,
            minimum_level=req_levels[skill.id],
            is_mandatory=req_mands[skill.id],
        )
        for skill in skills
        if 1 <= req_levels[skill.id] <= 5
    ]

    project = models.Project(
        id=project_id,
        title=title,
        description=description,
        min_capacity=min_capacity,
        max_capacity=max_capacity,
        requirements=requirements,
    )
    return project, form_data, req_levels, req_mands, None


@web_bp.post("/projects/new")
def create_project() -> flask.Response:
    """Processes creation of a new semester project.

    Validates project metadata (ID, title, capacities) and constructs
    the associated skill requirements matrix before persisting via
    ProjectRepository.

    Returns:
        Redirect response to the project catalog view upon successful creation,
        or a re-rendered form response with danger flash messages if validation fails.
    """
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    project_id = flask.request.form.get("id", "").strip()
    skills = repositories.SkillRepository().list_all()

    if not project_id:
        flask.flash("Project ID cannot be empty.", "danger")
        _, form_data, req_levels, req_mands, _ = (
            _parse_and_validate_project_form("", skills)
        )
        return flask.make_response(
            flask.render_template(
                "project_form.html",
                project=None,
                skills=skills,
                form_data=form_data,
                req_levels=req_levels,
                req_mands=req_mands,
            )
        )

    project_repo = repositories.ProjectRepository()
    if project_repo.get_by_id(project_id) is not None:
        flask.flash(f"Project ID '{project_id}' already exists.", "danger")
        _, form_data, req_levels, req_mands, _ = (
            _parse_and_validate_project_form(project_id, skills)
        )
        return flask.make_response(
            flask.render_template(
                "project_form.html",
                project=None,
                skills=skills,
                form_data=form_data,
                req_levels=req_levels,
                req_mands=req_mands,
            )
        )

    project, form_data, req_levels, req_mands, error = (
        _parse_and_validate_project_form(project_id, skills)
    )
    if error or project is None:
        flask.flash(error or "Validation failed.", "danger")
        return flask.make_response(
            flask.render_template(
                "project_form.html",
                project=None,
                skills=skills,
                form_data=form_data,
                req_levels=req_levels,
                req_mands=req_mands,
            )
        )

    try:
        project_repo.save(project)
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while saving project: {exc}", "danger"
        )
        return flask.make_response(
            flask.render_template(
                "project_form.html",
                project=None,
                skills=skills,
                form_data=form_data,
                req_levels=req_levels,
                req_mands=req_mands,
            )
        )

    flask.flash(f"Project '{project_id}' created.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_projects"))


@web_bp.get("/projects/<project_id>/edit")
def edit_project_form(project_id: str) -> Any:
    """Displays form to edit a project."""
    project = repositories.ProjectRepository().get_by_id(project_id)
    if not project:
        flask.flash(f"Project '{project_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    skills = repositories.SkillRepository().list_all()
    req_levels = {r.skill_id: r.minimum_level for r in project.requirements}
    req_mands = {r.skill_id: r.is_mandatory for r in project.requirements}
    return flask.render_template(
        "project_form.html",
        project=project,
        skills=skills,
        req_levels=req_levels,
        req_mands=req_mands,
    )


@web_bp.post("/projects/<project_id>/edit")
def update_project(project_id: str) -> flask.Response:
    """Updates an existing project entity."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    project_repo = repositories.ProjectRepository()
    existing_project = project_repo.get_by_id(project_id)
    if not existing_project:
        flask.flash(f"Project '{project_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    skills = repositories.SkillRepository().list_all()
    project, form_data, req_levels, req_mands, error = (
        _parse_and_validate_project_form(project_id, skills)
    )
    if error or project is None:
        flask.flash(error or "Validation failed.", "danger")
        return flask.make_response(
            flask.render_template(
                "project_form.html",
                project=existing_project,
                skills=skills,
                form_data=form_data,
                req_levels=req_levels,
                req_mands=req_mands,
            )
        )

    try:
        project_repo.save(project)
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while updating project: {exc}", "danger"
        )
        return flask.make_response(
            flask.render_template(
                "project_form.html",
                project=existing_project,
                skills=skills,
                form_data=form_data,
                req_levels=req_levels,
                req_mands=req_mands,
            )
        )

    flask.flash(f"Project '{project_id}' updated.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_projects"))


@web_bp.post("/projects/<project_id>/delete")
def delete_project(project_id: str) -> flask.Response:
    """Deletes a project from the catalog, cascading to preferences."""
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    project_repo = repositories.ProjectRepository()
    existing = project_repo.get_by_id(project_id)
    if not existing:
        flask.flash(f"Project '{project_id}' not found.", "warning")
        return flask.redirect(flask.url_for("visualization_web.list_projects"))

    try:
        # Count student preferences referencing this project before cascade delete
        pref_rows = project_repo.db.execute_query(
            "SELECT COUNT(*) AS cnt FROM preferences WHERE project_id = ?;",
            (project_id,),
        )
        pref_count = pref_rows[0]["cnt"] if pref_rows else 0

        project_repo.delete(project_id)
        if pref_count > 0:
            msg = (
                f"Project '{project_id}' deleted "
                f"({pref_count} student preferences removed)."
            )
        else:
            msg = f"Project '{project_id}' deleted."
        flask.flash(msg, "info")
    except Exception as exc:
        flask.flash(f"Error deleting project '{project_id}': {exc}", "danger")

    return flask.redirect(flask.url_for("visualization_web.list_projects"))


# -----------------------------------------------------------------------------
# Skills CRUD & Preferences Editor
# -----------------------------------------------------------------------------


@web_bp.get("/skills")
def list_skills() -> str:
    """Lists skill catalog records."""
    skills = repositories.SkillRepository().list_all()
    return flask.render_template("skills.html", skills=skills)


@web_bp.post("/skills/new")
def create_skill() -> flask.Response:
    """Processes creation of a new skill record in the catalog.

    Validates that the identifier is non-empty, contains only lowercase
    alphanumerics and underscores, and is not already registered.

    Returns:
        Redirect response to the skill catalog view.
    """
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_skills"))

    skill_id = flask.request.form.get("id", "").strip()
    name = flask.request.form.get("name", "").strip()
    description = flask.request.form.get("description", "").strip()

    if not skill_id:
        flask.flash("Skill ID cannot be empty.", "danger")
        skills = repositories.SkillRepository().list_all()
        return flask.make_response(
            flask.render_template(
                "skills.html",
                skills=skills,
                form_data={
                    "id": skill_id,
                    "name": name,
                    "description": description,
                },
                has_id_error=True,
            )
        )

    if not re.fullmatch(r"[a-z0-9_]+", skill_id):
        flask.flash(
            "Skill ID may only contain lowercase letters, digits, and underscores.",
            "danger",
        )
        skills = repositories.SkillRepository().list_all()
        return flask.make_response(
            flask.render_template(
                "skills.html",
                skills=skills,
                form_data={
                    "id": skill_id,
                    "name": name,
                    "description": description,
                },
                has_id_error=True,
            )
        )

    skill_repo = repositories.SkillRepository()
    if skill_repo.get_by_id(skill_id) is not None:
        flask.flash(f"Skill ID '{skill_id}' already exists.", "danger")
        skills = skill_repo.list_all()
        return flask.make_response(
            flask.render_template(
                "skills.html",
                skills=skills,
                form_data={
                    "id": skill_id,
                    "name": name,
                    "description": description,
                },
                has_id_error=True,
            )
        )

    skill_name = name or skill_id
    skill = models.Skill(id=skill_id, name=skill_name, description=description)
    try:
        skill_repo.save(skill)
    except sqlite3.IntegrityError as exc:
        flask.flash(
            f"Database constraint error while saving skill: {exc}",
            "danger",
        )
        skills = skill_repo.list_all()
        return flask.make_response(
            flask.render_template(
                "skills.html",
                skills=skills,
                form_data={
                    "id": skill_id,
                    "name": name,
                    "description": description,
                },
                has_id_error=True,
            )
        )

    flask.flash(f"Skill '{skill_name}' ({skill_id}) created successfully.", "success")
    return flask.redirect(flask.url_for("visualization_web.list_skills"))


@web_bp.post("/skills/<skill_id>/delete")
def delete_skill(skill_id: str) -> flask.Response:
    """Deletes a skill record from the catalog if not in use.

    Args:
        skill_id: Target skill identifier to delete.

    Returns:
        Redirect response to the skill catalog view.
    """
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_skills"))

    skill_repo = repositories.SkillRepository()
    skill = skill_repo.get_by_id(skill_id)
    if not skill:
        flask.flash(f"Skill '{skill_id}' not found.", "warning")
        return flask.redirect(flask.url_for("visualization_web.list_skills"))

    # Verify skill is not in use by any student or project
    students_using = [
        s.display_name
        for s in repositories.StudentRepository().list_all()
        if skill_id in s.skills
    ]
    projects_using = [
        p.title
        for p in repositories.ProjectRepository().list_all()
        if any(req.skill_id == skill_id for req in p.requirements)
    ]

    if students_using or projects_using:
        reasons: list[str] = []
        if students_using:
            reasons.append(f"{len(students_using)} student(s)")
        if projects_using:
            reasons.append(f"{len(projects_using)} project(s)")
        flask.flash(
            f"Cannot delete skill '{skill_id}': still referenced by {' and '.join(reasons)}.",
            "danger",
        )
        return flask.redirect(flask.url_for("visualization_web.list_skills"))

    try:
        skill_repo.delete(skill_id)
    except sqlite3.IntegrityError as exc:
        flask.flash(f"Database error while deleting skill: {exc}", "danger")
        return flask.redirect(flask.url_for("visualization_web.list_skills"))

    flask.flash(f"Skill '{skill_id}' removed.", "info")
    return flask.redirect(flask.url_for("visualization_web.list_skills"))


@web_bp.get("/preferences")
def preferences_overview() -> str:
    """Displays cross-table preference matrix."""
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    return flask.render_template(
        "preferences.html", students=students, projects=projects
    )


# -----------------------------------------------------------------------------
# Fixed Assignments & Reruns
# -----------------------------------------------------------------------------


@web_bp.get("/fixed-assignments")
def list_fixed_assignments() -> str:
    """Lists administrative pre-allocated constraints."""
    fixed = repositories.FixedAssignmentRepository().list_all()
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    return flask.render_template(
        "fixed_assignments.html",
        fixed_assignments=fixed,
        students=students,
        projects=projects,
    )


@web_bp.post("/fixed-assignments/new")
def create_fixed_assignment() -> flask.Response:
    """Locks a student to a designated project."""
    target = flask.url_for("visualization_web.list_fixed_assignments")
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied.", "danger")
        return flask.redirect(target)

    s_id = flask.request.form.get("student_id", "").strip()
    p_id = flask.request.form.get("project_id", "").strip()
    reason = flask.request.form.get("reason", "").strip()
    status = flask.request.form.get("status", "APPROVED").strip()

    if not s_id or not p_id:
        flask.flash("Student and Project must be selected.", "warning")
        return flask.redirect(target)

    repositories.FixedAssignmentRepository().save(
        models.FixedAssignment(
            student_id=s_id, project_id=p_id, status=status, reason=reason
        )
    )
    flask.flash(
        f"Fixed assignment created: Student {s_id} locked to Project {p_id}. "
        "A new run is required to recalculate allocations.",
        "success",
    )
    return flask.redirect(target)


@web_bp.post("/fixed-assignments/<student_id>/delete")
def delete_fixed_assignment(student_id: str) -> flask.Response:
    """Removes a locked allocation."""
    target = flask.url_for("visualization_web.list_fixed_assignments")
    if not auth.can_edit_cohort_data():
        flask.flash("Permission denied.", "danger")
        return flask.redirect(target)

    repositories.FixedAssignmentRepository().delete(student_id)
    flask.flash(f"Fixed assignment for student '{student_id}' removed.", "info")
    return flask.redirect(target)


# -----------------------------------------------------------------------------
# Scenarios & Data Seeding
# -----------------------------------------------------------------------------


@web_bp.get("/scenarios")
def scenarios_page() -> str:
    """Displays benchmark scenarios loader."""
    return flask.render_template("scenarios.html")


@web_bp.post("/load-scenario/<scenario_name>")
def load_scenario(scenario_name: str) -> flask.Response:
    """Populates database with a designated reproducible benchmark cohort."""
    repo_run = repositories.RunRepository()
    repo_run.clear_all_cohort_data()

    if scenario_name == "standard":
        data = demo_data.get_standard_scenario()
    elif scenario_name == "fixed":
        data = demo_data.get_fixed_assignment_scenario()
    elif scenario_name == "infeasible":
        data = demo_data.get_infeasible_scenario()
    elif scenario_name == "conflicting":
        data = demo_data.get_conflicting_fixed_scenario()
    else:
        flask.flash(f"Unknown scenario: '{scenario_name}'.", "warning")
        return flask.redirect(flask.url_for("visualization_web.scenarios_page"))

    skill_repo = repositories.SkillRepository()
    for s in data["skills"]:
        skill_repo.save(s)

    proj_repo = repositories.ProjectRepository()
    for p in data["projects"]:
        proj_repo.save(p)

    stud_repo = repositories.StudentRepository()
    for st in data["students"]:
        stud_repo.save(st)

    fixed_repo = repositories.FixedAssignmentRepository()
    for fa in data.get("fixed_assignments", []):
        fixed_repo.save(fa)

    flask.flash(
        f"Benchmark '{data['scenario_name']}' loaded successfully! "
        f"{data['description']}",
        "success",
    )
    return flask.redirect(flask.url_for("visualization_web.dashboard"))


@web_bp.post("/clear-data")
def clear_data() -> flask.Response:
    """Clears all cohort and constraint data."""
    repositories.RunRepository().clear_all_cohort_data()
    flask.flash("All cohort data cleared.", "info")
    return flask.redirect(flask.url_for("visualization_web.dashboard"))


# -----------------------------------------------------------------------------
# Runs & Solutions
# -----------------------------------------------------------------------------


@web_bp.post("/runs/trigger")
def trigger_run() -> flask.Response:
    """Submits current cohort data to Service A to generate allocations."""
    if not auth.can_trigger_optimization():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    max_alts = int(flask.request.form.get("max_alternatives", 3))
    strat = flask.request.form.get("primary_strategy", "PREFERENCE")

    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    fixed = repositories.FixedAssignmentRepository().list_all()

    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    req = contract.RunRequest(
        students=students,
        projects=projects,
        skills=skills,
        fixed_assignments=fixed,
        strategy_key=strat,
        max_alternatives=max_alts,
    )
    val_outcome = engine.validate_inputs(req)
    for warning_msg in val_outcome.warnings:
        flask.flash(f"Warning: {warning_msg}", "warning")
    try:
        run = engine.execute_run(req)
    except NotImplementedError:
        flask.flash(
            "Notice: AssignmentEngine.execute_run() is not yet implemented by "
            "Team B. Running with MockAssignmentEngine for demonstration.",
            "info",
        )
        mock_engine = mocks.MockAssignmentEngine()
        run = mock_engine.execute_run(req)

    if run.status == "COMPLETED":
        flask.flash(
            f"Optimization run completed! Found {len(run.solutions)} "
            "distinct alternative solutions.",
            "success",
        )
    elif run.status == "INFEASIBLE":
        flask.flash(
            "Solver could not find a feasible solution under the specified "
            "hard constraints. Inspect diagnostics below.",
            "warning",
        )
    else:
        flask.flash(f"Run ended with status: {run.status}.", "danger")

    return flask.redirect(
        flask.url_for("visualization_web.view_run", run_id=run.id)
    )


@web_bp.get("/runs/<run_id>")
def view_run(run_id: str) -> Any:
    """Displays results, alternative solutions, and diagnostics of a run."""
    run = repositories.RunRepository().get_run(run_id)
    if not run:
        flask.flash(f"Run '{run_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    recs = recommendations.generate_recommendations(run.solutions)

    return flask.render_template(
        "run_detail.html",
        run=run,
        recommendations=recs,
    )


@web_bp.get("/solutions/<solution_id>")
def view_solution(solution_id: str) -> Any:
    """Displays complete student assignment details for a solution."""
    repo = repositories.RunRepository()
    solution = repo.get_solution(solution_id)
    if not solution:
        flask.flash(f"Solution '{solution_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    run = repo.get_run(solution.run_id)
    students = {s.id: s for s in repositories.StudentRepository().list_all()}
    projects = {p.id: p for p in repositories.ProjectRepository().list_all()}

    return flask.render_template(
        "solution_detail.html",
        solution=solution,
        run=run,
        students=students,
        projects=projects,
    )


@web_bp.post("/solutions/<solution_id>/lock-and-rerun")
def lock_and_rerun(solution_id: str) -> flask.Response:
    """Locks a student assignment from a solution and triggers a new run."""
    if not auth.can_trigger_optimization():
        flask.flash("Permission denied for current role.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    student_id = flask.request.form.get("student_id")
    project_id = flask.request.form.get("project_id")

    if not student_id or not project_id:
        flask.flash("Student and Project required.", "warning")
        return flask.redirect(
            flask.url_for(
                "visualization_web.view_solution", solution_id=solution_id
            )
        )

    repo = repositories.RunRepository()
    original_solution = repo.get_solution(solution_id)
    if not original_solution:
        flask.flash(f"Solution '{solution_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    original_run = repo.get_run(original_solution.run_id)
    strategy_key = "PREFERENCE"
    max_alternatives = 3
    if original_run and original_run.configuration:
        strategy_key = (
            original_run.configuration.get("primary_strategy")
            or original_run.configuration.get("strategy_key")
            or original_run.configuration.get("strategy")
            or "PREFERENCE"
        )
        max_alternatives = int(
            original_run.configuration.get("max_alternatives", 3)
        )

    # Persist as fixed assignment
    fixed_repo = repositories.FixedAssignmentRepository()
    fixed_repo.save(
        models.FixedAssignment(
            student_id=student_id,
            project_id=project_id,
            status="APPROVED",
            reason=f"Locked interactively from Solution {solution_id[:8]}.",
        )
    )

    # Immediately trigger rerun via Component B (Assignment Engine)
    students = repositories.StudentRepository().list_all()
    projects = repositories.ProjectRepository().list_all()
    skills = repositories.SkillRepository().list_all()
    fixed = fixed_repo.list_all()

    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    req = contract.RunRequest(
        students=students,
        projects=projects,
        skills=skills,
        fixed_assignments=fixed,
        strategy_key=strategy_key,
        max_alternatives=max_alternatives,
        notes=f"Re-run after locking student {student_id} to project {project_id}.",
    )
    val_outcome = engine.validate_inputs(req)
    for warning_msg in val_outcome.warnings:
        flask.flash(f"Warning: {warning_msg}", "warning")

    try:
        new_run = engine.execute_run(req)
    except NotImplementedError:
        new_run = mocks.MockAssignmentEngine().execute_run(req)

    # Calculate student allocation shift compared with previous solution
    changed_count = 0
    new_solution_id: str | None = None
    if new_run.solutions:
        new_solution = new_run.solutions[0]
        new_solution_id = new_solution.id
        try:
            comparison = engine.compare_solutions(solution_id, new_solution.id)
            changed_count = comparison.changed_students_count
        except (NotImplementedError, Exception):
            try:
                comparison = mocks.MockAssignmentEngine().compare_solutions(
                    solution_id, new_solution.id
                )
                changed_count = comparison.changed_students_count
            except Exception:
                orig_map = {
                    a.student_id: a.project_id
                    for a in original_solution.assignments
                }
                new_map = {
                    a.student_id: a.project_id
                    for a in new_solution.assignments
                }
                changed_count = sum(
                    1
                    for s_id, p_id in new_map.items()
                    if orig_map.get(s_id) != p_id
                )

    compare_url = (
        flask.url_for(
            "visualization_web.compare_solutions",
            sol1=solution_id,
            sol2=new_solution_id,
        )
        if new_solution_id
        else flask.url_for("visualization_web.compare_solutions")
    )
    compare_link_html = (
        f'<a href="{compare_url}" style="color: inherit; text-decoration: '
        f'underline; font-weight: 600; margin-left: 0.5rem;">'
        f"Compare with previous run &rarr;</a>"
    )
    flask.flash(
        markupsafe.Markup(
            f"Student {student_id} locked to Project {project_id}. "
            f"{changed_count} students changed compared with the previous run."
            f" {compare_link_html}"
        ),
        "success",
    )
    if new_run.status == "INFEASIBLE":
        flask.flash(
            "Solver could not find a feasible solution with this lock.",
            "warning",
        )

    return flask.redirect(
        flask.url_for("visualization_web.view_run", run_id=new_run.id)
    )

@web_bp.post("/clear-solutions")
def clear_solutions() -> flask.Response:
    """Clears all solutions in the current run."""
    repositories.RunRepository().clear_all_current_solutions()
    flask.flash("All solutions cleared.", "info")
    return flask.redirect(flask.url_for("visualization_web.dashboard"))

# -----------------------------------------------------------------------------
# Comparison & Recommendations
# -----------------------------------------------------------------------------


@web_bp.get("/compare")
def compare_solutions() -> Any:
    """Renders side-by-side comparative analysis of two solutions.

    Reads ``sol1`` and ``sol2`` query parameters. With no IDs the page shows
    only the selector dropdowns.  With an unrecognised ID a ``danger`` flash
    message is issued and the user is redirected back to the empty selector.
    With two valid IDs the comparison is fetched from
    ``AssignmentEngine.compare_solutions``; if that raises
    ``NotImplementedError`` the ``MockAssignmentEngine`` is used instead
    (mirroring the fallback pattern in ``trigger_run``).

    Returns:
        Rendered ``compare.html`` with ``sol_a``, ``sol_b``, ``comparison``,
        and ``all_solutions`` context variables.
    """
    # Build the flat list of all solutions across recent runs for the dropdowns.
    run_repo = repositories.RunRepository()
    recent_runs = run_repo.list_runs(limit=50)
    all_solutions: list[models.Solution] = [
        sol for run in recent_runs for sol in run.solutions
    ]

    # Read the two requested solution IDs from the query string.
    sol1_id = flask.request.args.get("sol1", "").strip()
    sol2_id = flask.request.args.get("sol2", "").strip()

    # No IDs supplied — render the selector only (no comparison panel).
    if not sol1_id or not sol2_id:
        return flask.render_template(
            "compare.html",
            sol_a=None,
            sol_b=None,
            comparison=None,
            all_solutions=all_solutions,
        )

    # Resolve solution objects; redirect on unknown ID.
    sol_a = run_repo.get_solution(sol1_id)
    if not sol_a:
        flask.flash(
            f"Solution '{sol1_id}' not found. Please select a valid solution.",
            "danger",
        )
        return flask.redirect(flask.url_for("visualization_web.compare_solutions"))

    sol_b = run_repo.get_solution(sol2_id)
    if not sol_b:
        flask.flash(
            f"Solution '{sol2_id}' not found. Please select a valid solution.",
            "danger",
        )
        return flask.redirect(flask.url_for("visualization_web.compare_solutions"))

    # Delegate comparison to the engine; fall back to the mock on
    # NotImplementedError (same pattern as trigger_run / lock_and_rerun).
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    try:
        comparison = engine.compare_solutions(sol1_id, sol2_id)
    except NotImplementedError:
        flask.flash(
            "Notice: AssignmentEngine.compare_solutions() is not yet implemented "
            "by Team B. Running with MockAssignmentEngine for demonstration.",
            "info",
        )
        comparison = mocks.MockAssignmentEngine().compare_solutions(
            sol1_id, sol2_id
        )

    return flask.render_template(
        "compare.html",
        sol_a=sol_a,
        sol_b=sol_b,
        comparison=comparison,
        all_solutions=all_solutions,
    )


@web_bp.get("/recommendations/<run_id>")
def view_recommendations(run_id: str) -> Any:
    """Displays transparent recommendations with evidence and advice."""
    run = repositories.RunRepository().get_run(run_id)
    if not run:
        flask.flash(f"Run '{run_id}' not found.", "danger")
        return flask.redirect(flask.url_for("visualization_web.dashboard"))

    recs = recommendations.generate_recommendations(run.solutions)

    return flask.render_template(
        "recommendations.html",
        run=run,
        recommendations=recs,
    )
