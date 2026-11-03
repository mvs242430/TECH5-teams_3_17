"""End-to-end integration tests between Component A and Component B.

This module tests the integrated collaboration of the Visualization and
Recommendation Component (Component A) and the Assignment Engine (Component B)
through the internal Python contract, verifying data flow, fixed locks, reruns,
transparent recommendations, side-by-side comparisons, and infeasibility.
"""

import pathlib

import markupsafe

from app import create_app
from app.contract import contract
from app.engine import solvers
from app.persistence import repositories


def test_full_lifecycle_integration(tmp_path: pathlib.Path) -> None:
    """Tests complete lifecycle: seed, optimize, view, lock, and compare."""
    db_file = tmp_path / "test_integration_lifecycle.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Step 1: Seed benchmark cohort via Component A
    seed_res = client.post("/load-scenario/standard", follow_redirects=True)
    assert seed_res.status_code == 200
    assert b"Standard Cohort" in seed_res.data

    # Step 2: Trigger initial run through Component A -> Component B
    run_res = client.post(
        "/runs/trigger",
        data={
            "primary_strategy": "PREFERENCE",
            "max_alternatives": 3,
            "notes": "Initial benchmark run",
        },
        follow_redirects=True,
    )
    assert run_res.status_code == 200
    assert b"Optimization run completed" in run_res.data
    assert b"Generated Feasible Solutions" in run_res.data

    # Step 3: Verify solutions stored and queryable via Engine Contract
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    runs = engine.list_runs(limit=10)
    assert len(runs) >= 1
    run1 = runs[0]
    assert run1.status == "COMPLETED"
    assert len(run1.solutions) >= 2

    sol1_id = run1.solutions[0].id
    sol2_id = run1.solutions[1].id

    # Step 4: Component A renders solution detail from Engine result
    sol_view = client.get(f"/solutions/{sol1_id}")
    assert sol_view.status_code == 200
    assert b"Student-to-Project Allocations" in sol_view.data

    # Step 5: Component A renders transparent recommendations
    rec_view = client.get(f"/recommendations/{run1.id}")
    assert rec_view.status_code == 200
    assert b"Calculated Evidence" in rec_view.data
    assert b"Policy Advice" in rec_view.data

    # Step 6: Component A renders side-by-side solution comparison via Engine
    comp_view = client.get(f"/compare?sol1={sol1_id}&sol2={sol2_id}")
    assert comp_view.status_code == 200
    assert b"Side-by-Side Solution Comparison" in comp_view.data
    assert b"Trade-off Findings" in comp_view.data

    # Step 7: Introduce Fixed Assignment (lock S02 to P2) and trigger rerun
    lock_res = client.post(
        "/fixed-assignments/new",
        data={
            "student_id": "S02",
            "project_id": "P2",
            "status": "APPROVED",
            "reason": "Administrative research fellowship match",
        },
        follow_redirects=True,
    )
    assert lock_res.status_code == 200
    assert b"Fixed assignment created" in lock_res.data

    rerun_res = client.post(
        "/runs/trigger",
        data={
            "primary_strategy": "PREFERENCE",
            "max_alternatives": 3,
            "notes": "Rerun with locked S02->P2",
        },
        follow_redirects=True,
    )
    assert rerun_res.status_code == 200
    assert b"Optimization run completed" in rerun_res.data

    # Step 8: Verify that every solution in rerun strictly preserves lock
    runs_after = engine.list_runs(limit=10)
    assert len(runs_after) >= 2
    rerun_latest = engine.get_run(runs_after[0].id)
    assert rerun_latest is not None
    assert rerun_latest.id != run1.id
    for sol in rerun_latest.solutions:
        matching_asg = [
            a for a in sol.assignments if a.student_id == "S02"
        ]
        assert len(matching_asg) == 1
        assert matching_asg[0].project_id == "P2"
        assert matching_asg[0].is_fixed


def test_infeasible_cohort_integration(tmp_path: pathlib.Path) -> None:
    """Tests handling and UI presentation of mathematically infeasible runs."""
    db_file = tmp_path / "test_infeasible_integration.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()

    # Load infeasible scenario (capacity deficit: 6 seats for 10 students)
    load_res = client.post("/load-scenario/infeasible", follow_redirects=True)
    assert load_res.status_code == 200
    assert b"Capacity Deficit" in load_res.data

    # Trigger run through Component A
    run_res = client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 2},
        follow_redirects=True,
    )
    assert run_res.status_code == 200
    # Engine diagnosed infeasibility and Component A communicated error
    assert (
        b"Run failed or proved mathematically infeasible" in run_res.data
        or b"INFEASIBLE" in run_res.data
    )

    # Verify run persisted with INFEASIBLE status and reasons in diagnostics
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()
    runs = engine.list_runs(limit=1)
    assert len(runs) == 1
    assert runs[0].status == "INFEASIBLE"
    assert runs[0].diagnostics


def test_x3_full_end_to_end_flow(tmp_path: pathlib.Path) -> None:
    """X3: one user journey through the real engine, start to finish.

    Standard scenario -> run -> at least 2 solutions -> compare two of them
    -> recommendations -> lock one student with lock-and-rerun -> the lock
    is kept in every new solution -> infeasible scenario shows its reasons.
    No mock engine is used: every run goes through AssignmentEngine.
    """
    db_file = tmp_path / "test_x3_end_to_end.db"
    app = create_app({"TESTING": True, "DATABASE_PATH": db_file})
    client = app.test_client()
    engine: contract.AssignmentEngineContract = solvers.AssignmentEngine()

    # 1. Load the standard scenario.
    res = client.post("/load-scenario/standard", follow_redirects=True)
    assert res.status_code == 200
    assert b"Standard Cohort" in res.data

    # 2. Trigger a run through the web client.
    res = client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 3},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"not yet implemented" not in res.data  # real engine, no mock
    first_run = engine.get_run(engine.list_runs(limit=1)[0].id)
    assert first_run is not None
    assert first_run.status == "COMPLETED"

    # 3. At least two solutions.
    assert len(first_run.solutions) >= 2
    sol_a, sol_b = first_run.solutions[0], first_run.solutions[1]

    # 4. Compare two of them.
    res = client.get(f"/compare?sol1={sol_a.id}&sol2={sol_b.id}")
    assert res.status_code == 200
    assert b"Side-by-Side Solution Comparison" in res.data

    # 5. Recommendations page opens.
    res = client.get(f"/recommendations/{first_run.id}")
    assert res.status_code == 200

    # 6. Lock one student via lock-and-rerun. Prefer a student whose project
    #    differs between the two solutions, so the lock actually matters.
    projects_in_a = {a.student_id: a.project_id for a in sol_a.assignments}
    to_lock = next(
        (a for a in sol_b.assignments
         if projects_in_a.get(a.student_id) != a.project_id),
        sol_b.assignments[0],
    )
    res = client.post(
        f"/solutions/{sol_b.id}/lock-and-rerun",
        data={
            "student_id": to_lock.student_id,
            "project_id": to_lock.project_id,
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"locked to Project" in res.data

    # 7. The locked pair is in every solution of the new run.
    new_run = engine.get_run(engine.list_runs(limit=1)[0].id)
    assert new_run is not None
    assert new_run.id != first_run.id
    assert new_run.status == "COMPLETED"
    assert new_run.solutions
    for sol in new_run.solutions:
        locked = [
            a for a in sol.assignments if a.student_id == to_lock.student_id
        ]
        assert len(locked) == 1
        assert locked[0].project_id == to_lock.project_id
        assert locked[0].is_fixed

    # 8. Load the infeasible scenario; the run page shows the reasons.
    client.post("/load-scenario/infeasible", follow_redirects=True)
    res = client.post(
        "/runs/trigger",
        data={"primary_strategy": "PREFERENCE", "max_alternatives": 2},
        follow_redirects=True,
    )
    assert res.status_code == 200
    bad_run = engine.list_runs(limit=1)[0]
    assert bad_run.status == "INFEASIBLE"
    assert bad_run.diagnostics["reasons"]
    for reason in bad_run.diagnostics["reasons"]:
        # The page escapes text the same way Jinja does.
        assert str(markupsafe.escape(reason)).encode() in res.data
