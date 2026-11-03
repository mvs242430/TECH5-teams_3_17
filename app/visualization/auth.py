"""Prototype authentication and role-based access control.

This module implements role-appropriate authorization required by Section 9
of the TECH5 specification, supporting Administrator, Programme Coordinator,
and Student Viewer roles.
"""

from typing import Any

import flask


class UserRole:
    """User role constants, full descriptions, and compact navbar labels."""

    ADMIN = "ADMIN"
    COORDINATOR = "COORDINATOR"
    STUDENT = "STUDENT"

    ALL_ROLES = {
        ADMIN: "Administrator (Full Control)",
        COORDINATOR: "Programme Coordinator (Runs & Analysis)",
        STUDENT: "Student Viewer (Read Only)",
    }

    NAV_LABELS = {
        ADMIN: "Administrator",
        COORDINATOR: "Coordinator",
        STUDENT: "Student",
    }


def get_current_role() -> str:
    """Retrieves the active user role from session.

    Returns:
        The active role string (defaults to ADMIN for convenience).
    """
    return flask.session.get("user_role", UserRole.ADMIN)


def set_current_role(role: str) -> None:
    """Updates the active user role in session.

    Args:
        role: Target role string.
    """
    if role in UserRole.ALL_ROLES:
        flask.session["user_role"] = role


def can_edit_cohort_data() -> bool:
    """Checks whether the current user has permission to modify cohort data.

    Returns:
        True if current role has edit permissions.
    """
    return get_current_role() in (UserRole.ADMIN,)


def can_trigger_optimization() -> bool:
    """Checks whether current user can execute optimization runs.

    Returns:
        True if user can run solver.
    """
    return get_current_role() in (UserRole.ADMIN, UserRole.COORDINATOR)


def can_view_student_records() -> bool:
    """Checks whether the current user may see individual student data.

    Student data means names, IDs, skills, preference rankings, fixed
    locks and each student's allocation. The Student Viewer sees only
    anonymized metrics, project descriptions and high-level allocation
    summaries (docs/architecture.md, section 6).

    Returns:
        True if the current role may see individual student records.
    """
    return get_current_role() in (UserRole.ADMIN, UserRole.COORDINATOR)


def can_switch_roles() -> bool:
    """Checks whether the current user may switch to any role.

    Only the Administrator switches active roles (docs/architecture.md,
    section 6), for example to check what a Student Viewer sees.

    Returns:
        True if the current role may choose any active role.
    """
    return get_current_role() == UserRole.ADMIN


def can_switch_to_role(role: str) -> bool:
    """Checks whether the current user may make `role` the active role.

    The prototype has no login, so every role may go back to
    Administrator. That step stands in for signing in again; without it a
    Student Viewer could never leave the role.

    Args:
        role: The role the user asks to switch to.

    Returns:
        True if the switch is allowed.
    """
    return can_switch_roles() or role == UserRole.ADMIN


def can_manage_fixed_assignments() -> bool:
    """Checks whether the current user may create or release fixed locks.

    Fixed assignments are solver inputs that the Programme Coordinator
    manages alongside runs (docs/architecture.md, section 6). This is a
    separate rule from running the solver, so a later change to one does
    not silently change the other.

    Returns:
        True if the current role may create or release fixed assignments.
    """
    return get_current_role() in (UserRole.ADMIN, UserRole.COORDINATOR)
