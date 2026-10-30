"""Mathematical optimization solvers and Strategy Pattern skeleton for TECH5.

In compliance with Section 5 and Section 8 of the TECH5 specification,
Team B is responsible for proposing and implementing an approved assignment
method (e.g. Integer Linear Programming, heuristic search, or stable matching).

This module defines the abstract strategy base class and the AssignmentEngine
that implements AssignmentEngineContract.
"""

import abc
import datetime
import logging
import time
from typing import Any
import uuid

from app.contract import contract
from app.domain import models
from app.domain import validation
from app.engine import metrics
from app.persistence import repositories


class AssignmentStrategy(abc.ABC):
    """Abstract Base Class for student-to-project allocation strategies.

    Team B should derive concrete strategy subclasses implementing specific
    objective functions (e.g. preference satisfaction, skill fit, balanced).
    """

    def __init__(self, name: str, description: str) -> None:
        """Initializes the strategy with descriptive metadata.

        Args:
            name: Machine-readable identifier for the strategy.
            description: Human-readable explanation of the objective function.
        """
        self.name = name
        self.description = description

    @abc.abstractmethod
    def calculate_cost_or_utility(
        self,
        student: models.Student,
        project: models.Project,
        max_preferences: int,
    ) -> float:
        """Computes objective utility or cost weight for assigning student to project.

        Args:
            student: The candidate student.
            project: The target semester project.
            max_preferences: Maximum number of preferences ranked in cohort.

        Returns:
            Numerical weight reflecting desirability in optimization objective.
        """

    def solve(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        fixed_assignments: list[models.FixedAssignment] | None = None,
        excluded_solutions: list[list[tuple[str, str]]] | None = None,
    ) -> tuple[str, list[models.Assignment], float | None, dict[str, Any]]:
        """Solves the assignment problem under this strategy's formulation.

        In accordance with Section 8 of the specification, must:
        - Assign students to projects respecting capacities [min_cap, max_cap].
        - Enforce each student receives exactly one project allocation.
        - Strictly preserve pre-allocated fixed assignments.
        - Support integer no-good cuts (excluded_solutions) to guarantee distinct
          Pareto alternatives.

        Args:
            students: List of students in the cohort.
            projects: List of available semester projects.
            fixed_assignments: Pre-assigned student-project pairs that must hold.
            excluded_solutions: Previous solution allocations to cut out.

        Returns:
            A tuple of (solver_status, assignments, objective_value, diagnostics).

        Raises:
            NotImplementedError: To be implemented by Team B.
        """
        raise NotImplementedError(
            f"TODO (Team B): Implement solver logic for strategy '{self.name}'"
        )


class AssignmentEngine(contract.AssignmentEngineContract):
    """Main Assignment Engine orchestrating validation, execution, and persistence.

    Implements the internal component contract (AssignmentEngineContract)
    connecting Component B to Component A.
    """

    def __init__(
        self, run_repo: repositories.RunRepository | None = None
    ) -> None:
        """Initializes the AssignmentEngine with persistence repositories.

        Args:
            run_repo: Optional repository for persisting runs and solutions.
        """
        from app.engine import strategies

        self.run_repo = (
            run_repo if run_repo is not None else repositories.RunRepository()
        )
        self.strategies: dict[str, AssignmentStrategy] = {
            "PREFERENCE": strategies.PreferenceOrientedSolver(),
            "SKILL_FIT": strategies.SkillFitOrientedSolver(),
            "BALANCED": strategies.BalancedTradeoffSolver(),
        }

    def validate_inputs(
        self, request: contract.RunRequest
    ) -> contract.ValidationOutcome:
        """Validates cohort and constraints before attempting optimization.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            ValidationOutcome with validity, feasibility, errors, and warnings.
        """
        val_result = validation.validate_cohort(
            students=request.students,
            projects=request.projects,
            skills=request.skills,
            fixed_assignments=request.fixed_assignments,
        )
        return contract.ValidationOutcome(
            is_valid=val_result.is_valid,
            is_feasible=val_result.is_feasible,
            errors=list(val_result.errors),
            warnings=list(val_result.warnings),
            infeasibility_reasons=list(val_result.infeasibility_reasons),
        )

    def execute_run(
        self, request: contract.RunRequest
    ) -> models.AssignmentRun:
        """Executes the assignment algorithm, calculates metrics, and persists run.

        In accordance with Section 8 of the specification, Team B must:
        1. Synchronize entities to maintain relational integrity.
        2. Validate cohort feasibility.
        3. Run assignment solver(s) to generate one or more distinct alternatives.
        4. Calculate indicators for each alternative using app.engine.metrics.
        5. Persist run and solutions via self.run_repo.
        6. Return populated models.AssignmentRun.

        Args:
            request: The run request containing students, projects, etc.

        Returns:
            The created AssignmentRun populated with alternative solutions.
        """
        start_time = time.perf_counter()
        run_id = str(uuid.uuid4())
        created_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Ensure schema exists for standalone unit tests running outside Flask.
        self.run_repo.db.initialize_schema()

        primary_strategy = (
            request.strategy_key
            if request.strategy_key in self.strategies
            else "PREFERENCE"
        )
        num_vars = len(request.students) * len(request.projects)
        num_constraints = len(request.students) + 2 * len(request.projects) + len(
            request.fixed_assignments or []
        )
        config_dict: dict[str, Any] = {
            "max_alternatives": request.max_alternatives,
            "primary_strategy": request.strategy_key,
            "strategy_key": request.strategy_key,
            "engine": "AssignmentEngine",
            "notes": request.notes,
        }

        val_outcome = self.validate_inputs(request)

        # Case A: Pre-solver mathematical infeasibility (e.g., capacity deficit).
        if not val_outcome.is_feasible:
            reasons = list(val_outcome.infeasibility_reasons)
            if not reasons and val_outcome.errors:
                reasons = list(val_outcome.errors)
            elapsed = round(time.perf_counter() - start_time, 4)
            run = models.AssignmentRun(
                id=run_id,
                created_at=created_at,
                status=contract.RunStatus.INFEASIBLE.value,
                configuration=config_dict,
                solutions=[],
                diagnostics={
                    "solver_status": "INFEASIBLE",
                    "strategy": primary_strategy,
                    "solve_time_seconds": elapsed,
                    "variables": num_vars,
                    "constraints": num_constraints,
                    "alternatives_found": 0,
                    "distinct_alternatives": 0,
                    "reasons": reasons,
                    "errors": list(val_outcome.errors),
                    "warnings": list(val_outcome.warnings),
                    "notes": request.notes,
                    "message": (
                        "Run proved mathematically infeasible before solver "
                        "execution."
                    ),
                },
            )
            self.run_repo.save_run(run)
            return run

        # Case B: Structural validation errors (e.g., contradictory fixed locks).
        if not val_outcome.is_valid:
            elapsed = round(time.perf_counter() - start_time, 4)
            run = models.AssignmentRun(
                id=run_id,
                created_at=created_at,
                status=contract.RunStatus.INVALID_INPUT.value,
                configuration=config_dict,
                solutions=[],
                diagnostics={
                    "solver_status": "INVALID_INPUT",
                    "strategy": primary_strategy,
                    "solve_time_seconds": elapsed,
                    "variables": num_vars,
                    "constraints": num_constraints,
                    "alternatives_found": 0,
                    "distinct_alternatives": 0,
                    "reasons": list(val_outcome.errors),
                    "errors": list(val_outcome.errors),
                    "warnings": list(val_outcome.warnings),
                    "notes": request.notes,
                    "message": (
                        "Input cohort failed pre-solver validation checks."
                    ),
                },
            )
            self.run_repo.save_run(run)
            return run

        # Synchronize skills, projects, students, and fixed assignments to DB
        # so foreign-key constraints on solutions and assignments are satisfied.
        skill_repo = repositories.SkillRepository(db=self.run_repo.db)
        known_skill_ids: set[str] = set()
        for sk in request.skills or []:
            skill_repo.save(sk)
            known_skill_ids.add(sk.id)

        # Ensure any uncatalogued skills referenced by students or projects are
        # also present in the skills table to satisfy foreign-key constraints.
        for proj in request.projects:
            for req in proj.requirements:
                if req.skill_id not in known_skill_ids:
                    skill_repo.save(
                        models.Skill(id=req.skill_id, name=req.skill_id)
                    )
                    known_skill_ids.add(req.skill_id)
        for stud in request.students:
            for sk_id in stud.skills:
                if sk_id not in known_skill_ids:
                    skill_repo.save(models.Skill(id=sk_id, name=sk_id))
                    known_skill_ids.add(sk_id)

        proj_repo = repositories.ProjectRepository(db=self.run_repo.db)
        for proj in request.projects:
            proj_repo.save(proj)

        stud_repo = repositories.StudentRepository(db=self.run_repo.db)
        for stud in request.students:
            stud_repo.save(stud)

        if request.fixed_assignments:
            fixed_repo = repositories.FixedAssignmentRepository(
                db=self.run_repo.db
            )
            for fa in request.fixed_assignments:
                fixed_repo.save(fa)

        # Build strategy rotation starting with the requested primary strategy
        # so multi-alternative runs explore preference, skill-fit, and balanced
        # perspectives while enforcing integer no-good cuts across all solves.
        strategy_order = [primary_strategy] + [
            key
            for key in ("PREFERENCE", "SKILL_FIT", "BALANCED")
            if key != primary_strategy and key in self.strategies
        ]
        max_alts = max(1, request.max_alternatives)
        solutions: list[models.Solution] = []
        excluded_solutions: list[list[tuple[str, str]]] = []
        last_solver_diag: dict[str, Any] = {}

        for alt_idx in range(max_alts):
            strat_key = strategy_order[alt_idx % len(strategy_order)]
            strategy = self.strategies[strat_key]
            solver_status, assignments, obj_val, sol_diag = strategy.solve(
                students=request.students,
                projects=request.projects,
                fixed_assignments=request.fixed_assignments,
                excluded_solutions=excluded_solutions,
            )
            last_solver_diag = sol_diag

            if solver_status != "OPTIMAL" or not assignments:
                # If switching strategy failed to find a new solution, try the
                # primary strategy once more with the current no-good cuts.
                if strat_key != primary_strategy:
                    primary_solver = self.strategies[primary_strategy]
                    (
                        solver_status,
                        assignments,
                        obj_val,
                        sol_diag,
                    ) = primary_solver.solve(
                        students=request.students,
                        projects=request.projects,
                        fixed_assignments=request.fixed_assignments,
                        excluded_solutions=excluded_solutions,
                    )
                    strat_key = primary_strategy
                    last_solver_diag = sol_diag

                if solver_status != "OPTIMAL" or not assignments:
                    break

            indicators = metrics.compute_solution_indicators(
                students=request.students,
                projects=request.projects,
                assignments=assignments,
                fixed_assignments=request.fixed_assignments,
            )
            sol = models.Solution(
                id=str(uuid.uuid4()),
                run_id=run_id,
                alternative_number=len(solutions) + 1,
                strategy_name=strat_key,
                objective_value=(
                    round(float(obj_val), 4) if obj_val is not None else 0.0
                ),
                assignments=assignments,
                indicators=indicators,
                warnings=list(val_outcome.warnings),
                diagnostics=sol_diag,
            )
            solutions.append(sol)
            excluded_solutions.append(
                [(a.student_id, a.project_id) for a in assignments]
            )

        elapsed = round(time.perf_counter() - start_time, 4)

        if not solutions:
            reasons = list(val_outcome.infeasibility_reasons)
            if not reasons:
                reasons = [
                    "Solver proved the MILP formulation infeasible under the "
                    "combined capacity, mandatory skill, and fixed-lock "
                    "constraints. Try relaxing mandatory skill levels, "
                    "reducing project minimum capacities, or removing fixed "
                    "locks."
                ]
            run = models.AssignmentRun(
                id=run_id,
                created_at=created_at,
                status=contract.RunStatus.INFEASIBLE.value,
                configuration=config_dict,
                solutions=[],
                diagnostics={
                    "solver_status": "INFEASIBLE",
                    "strategy": primary_strategy,
                    "solve_time_seconds": elapsed,
                    "variables": last_solver_diag.get(
                        "num_variables", num_vars
                    ),
                    "constraints": last_solver_diag.get(
                        "num_constraints", num_constraints
                    ),
                    "alternatives_found": 0,
                    "distinct_alternatives": 0,
                    "reasons": reasons,
                    "errors": list(val_outcome.errors),
                    "warnings": list(val_outcome.warnings),
                    "notes": request.notes,
                    "message": (
                        "Solver could not find a feasible allocation "
                        "satisfying all hard constraints."
                    ),
                },
            )
            self.run_repo.save_run(run)
            return run

        run = models.AssignmentRun(
            id=run_id,
            created_at=created_at,
            status=contract.RunStatus.COMPLETED.value,
            configuration=config_dict,
            solutions=solutions,
            diagnostics={
                "solver_status": "Optimal",
                "strategy": primary_strategy,
                "solve_time_seconds": elapsed,
                "variables": last_solver_diag.get("num_variables", num_vars),
                "constraints": last_solver_diag.get(
                    "num_constraints", num_constraints
                ),
                "solution_count": len(solutions),
                "alternatives_found": len(solutions),
                "distinct_alternatives": len(solutions),
                "reasons": [],
                "warnings": list(val_outcome.warnings),
                "notes": request.notes,
                "message": (
                    f"Optimization completed in {elapsed}s with "
                    f"{len(solutions)} distinct alternative(s)."
                ),
            },
        )
        self.run_repo.save_run(run)
        return run

    def run_assignment(
        self,
        students: list[models.Student],
        projects: list[models.Project],
        skills: list[models.Skill] | None = None,
        fixed_assignments: list[models.FixedAssignment] | None = None,
        strategy_name: str = "PREFERENCE",
        max_alternatives: int = 3,
        notes: str = "",
    ) -> models.AssignmentRun:
        """Convenience method delegating to execute_run via RunRequest.

        Args:
            students: Student profiles.
            projects: Project specifications.
            skills: Optional skills catalog.
            fixed_assignments: Optional pre-allocated locks.
            strategy_name: Strategy key name.
            max_alternatives: Max solutions to generate.
            notes: Administrative description or notes for the run.

        Returns:
            The created AssignmentRun.
        """
        req = contract.RunRequest(
            students=students,
            projects=projects,
            skills=skills or [],
            fixed_assignments=fixed_assignments or [],
            strategy_key=strategy_name,
            max_alternatives=max_alternatives,
            notes=notes,
        )
        return self.execute_run(req)

    def list_runs(self, limit: int = 20) -> list[models.AssignmentRun]:
        """Retrieves historical assignment runs from repository.

        Args:
            limit: Maximum number of runs to retrieve.

        Returns:
            List of historical AssignmentRun domain objects.
        """
        return self.run_repo.list_runs(limit=limit)

    def get_run(self, run_id: str) -> models.AssignmentRun | None:
        """Retrieves a specific run by identifier.

        Args:
            run_id: Unique run identifier.

        Returns:
            The AssignmentRun object, or None if not found.
        """
        return self.run_repo.get_run(run_id)

    def get_solution(self, solution_id: str) -> models.Solution | None:
        """Retrieves a specific solution and its student allocations.

        Args:
            solution_id: Unique solution identifier.

        Returns:
            The Solution object with assignments, or None if not found.
        """
        return self.run_repo.get_solution(solution_id)

    def compare_solutions(
        self, solution_a_id: str, solution_b_id: str
    ) -> models.RunComparison:
        """Compares two alternative solutions side-by-side using metrics module.

        Args:
            solution_a_id: Identifier of the baseline solution.
            solution_b_id: Identifier of the comparison solution.

        Returns:
            RunComparison containing delta metrics and changed assignments.

        Raises:
            KeyError: If either solution cannot be found.
            ValueError: If the two solutions do not contain the same students.
        """
        sol_a = self.run_repo.get_solution(solution_a_id)
        sol_b = self.run_repo.get_solution(solution_b_id)
        if sol_a is None or sol_b is None:
            raise KeyError(
                f"Solutions not found: {solution_a_id}, {solution_b_id}"
            )
        comp_dict = metrics.compare_two_solutions(sol_a, sol_b)
        return models.RunComparison.from_dict(comp_dict)
