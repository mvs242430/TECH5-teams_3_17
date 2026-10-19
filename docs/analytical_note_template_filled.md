# Deliverable 6: Analytical Note & Mathematical Formulation
## Student Submission — TECH5 Collaborative Project

**Team:** [Team Name / Group Number]  
**Authors (Team B - Assignment Engine):** [Student Names & IDs]  
**Authors (Team A - Visualization & Recommender):** [Student Names & IDs]  
**Course:** TECH5 Programming & Application Design, NHH Norwegian School of Economics  
**Date:** [Submission Date]

> [!NOTE]
> Only the administrative header fields above are left open. Team members fill these in at submission. Everything else is our formulation. Each section ends with an **Implementation mapping** showing where the maths lives in `app/engine/solvers.py` (strategies and engine) and `app/engine/metrics.py` (indicators). If issue 0.5 is merged, the strategy classes live in `app/engine/strategies.py` and are imported by `solvers.py`.

---

## 1. Problem Definition & Mathematical Modeling Approach

### 1.1 Business Context & Decision Dilemma

Every semester the programme coordinator must place each student in exactly one project. Projects have a minimum and a maximum team size and may require certain skills at a minimum level. Some placements are already agreed before the allocation runs (fixed assignments). The coordinator therefore balances two legitimate but conflicting interests:

- **Collective project quality.** Partner organisations need teams that actually have the required skills.
- **Individual student satisfaction.** Students want projects they ranked highly, and motivation drops when they are placed far down their list.

These goals conflict because preferences tend to cluster: many students rank the same few projects first. Granting everyone's top choice overfills popular projects, often with under-qualified students, while niche projects fall below their minimum size. Optimising only for skills instead pushes students into projects they ranked low or not at all. No allocation is best on both criteria at once. The decision is a trade-off, and choosing where to sit on it is a policy choice that belongs to the coordinator, not to the algorithm.

Rezaeinia et al. (2022) document the same tension in a real course-allocation setting. We use that work only as context and do not reproduce their algorithm. Our system therefore (i) guarantees that every proposed allocation respects all hard rules, (ii) produces several genuinely different allocations that emphasise different priorities, and (iii) measures and explains the trade-offs between them.

### 1.2 Chosen Assignment Methodology & Academic Justification

**Chosen method: Mixed-Integer Linear Programming (MILP)**, modelled in Python with **PuLP** and solved by the open-source **CBC** branch-and-cut solver that ships with PuLP.

**Why MILP is appropriate:**

1. **Hard rules are guaranteed, not encouraged.** Exact allocation, capacity bounds, fixed assignments and mandatory skills are expressed as linear constraints. Every solution the solver returns satisfies all of them by construction, so no rule is ever "traded off" against preferences.
2. **Optimality is certified.** CBC returns a provably optimal allocation for the chosen objective, so no better allocation for that priority exists. Heuristics cannot make this claim.
3. **Infeasibility is proven.** If the rules cannot all be met, the solver returns status `Infeasible`. That is a mathematical proof, which we translate into a diagnostic for the coordinator (Edge case 13). A heuristic that finds nothing cannot distinguish "impossible" from "not found yet".
4. **Distinct alternatives are exact.** A single linear no-good cut (Balas & Jeroslow, 1972) removes a previously found allocation from the feasible set. The next solve is guaranteed to differ for at least one student. When no further allocation exists, the solver proves it, and we report fewer alternatives rather than duplicates (Edge cases 14–15).
5. **Deterministic and testable.** The same input always yields the same output, which our pytest suite and the reproducible demonstration (Deliverable 8) depend on.
6. **Computationally feasible in a single Python process.** The model has $|S|\cdot|P|$ binary variables (e.g. $60 \times 12 = 720$) and $|S| + 2|P| + |F| + t$ constraints, where $t$ is the number of cuts. This is a small MILP. Without cuts its LP relaxation is already integral (see §7.1), so CBC typically solves it at the root node. `pip install pulp` bundles the CBC binary, so no licence, server or network call is required, consistent with the in-process two-component architecture. The solve time is capped by `Config.PULP_TIME_LIMIT_SECONDS` (15 s) and the measured time is reported in `DiagnosticInfo.solve_time_seconds`.

**Why not the alternatives:**

| Alternative | Reason for rejection |
|---|---|
| Pure LP / min-cost network flow | The base model is a transportation-type problem whose LP relaxation is integral. The no-good cuts needed for alternatives destroy this structure, so integrality must be enforced explicitly. That requires MILP. |
| Stable matching (Gale & Shapley, 1962) and student-project-allocation variants | These require two-sided ordinal preferences, but our projects state skill thresholds, not rankings of students. Stability with minimum quotas is NP-hard in general (Biró et al., 2010), and fixed assignments conflict with stability. |
| Metaheuristics (genetic algorithms, NSGA-II, local search) | Non-deterministic, with no optimality or infeasibility proof. They need repair operators to keep capacity constraints satisfied, and their results cannot be asserted exactly in automated tests. |
| Constraint programming (OR-Tools CP-SAT) | Technically viable, but it needs integer-scaled objective weights and a large extra dependency, with no benefit at this problem size. |

**Implementation mapping:** `requirements.txt` adds `pulp`. The strategies (§2.5) are concrete subclasses of `AssignmentStrategy` in `solvers.py`, and `AssignmentEngine.execute_run` orchestrates validation, solving, cuts, metrics and persistence (§2.6).

---

## 2. Mathematical Formulation

### 2.1 Index Sets & Dimensions
- $S = \{s_1, s_2, \dots, s_n\}$: Set of students in the cohort ($|S| = n$).
- $P = \{p_1, p_2, \dots, p_m\}$: Set of available semester projects ($|P| = m$).
- $K = \{k_1, k_2, \dots, k_q\}$: Set of evaluated technical skills ($|K| = q$).
- $F \subseteq S \times P$: Set of pre-allocated fixed assignment pairs $(s, p)$.
- $R_p = \{k \in K : \text{req}_{p,k} \ge 1\}$: skills actually required by project $p$.
- $M_p = \{k \in R_p : m_{p,k} = 1\}$: mandatory skills of project $p$.
- $E \subseteq S \times P$: **eligible pairs**, i.e. pairs where the student meets every mandatory requirement of the project:
  $$E = \{(s,p) \in S \times P : \text{skill}_{s,k} \ge \text{req}_{p,k} \;\; \forall k \in M_p\}$$
- $\mathcal{A} = \{A^{(1)}, \dots, A^{(t)}\}$: allocations already found in the current run, with $A^{(j)} = \{(s,p) : x^{(j)}_{s,p} = 1\}$ and $|A^{(j)}| = n$.

### 2.2 Model Parameters
- $l_p \in \mathbb{Z}_{\ge 0}$: Minimum headcount capacity for project $p$.
- $u_p \in \mathbb{Z}_{\ge 1}$: Maximum headcount capacity for project $p$ ($l_p \le u_p$).
- $r_{s,p} \in \{1, 2, \dots, |P|\} \cup \{|P|+1\}$: Stated preference rank of student $s$ for project $p$.
  We use the penalty rank $\rho = R + 1$ for unranked projects, where $R = \max_{s} |\text{pref}_s| \le |P|$ is the longest preference list in the cohort (`max_preferences` in code). When at least one student ranks every project, $\rho = |P| + 1$ exactly as in the template. Otherwise $\rho$ sits immediately below the worst rank anyone actually stated. This keeps unranked placements strictly worst without inflating the scale with ranks that nobody used.
- $w_{s,p}^{\text{pref}}$: Preference score or weight derived from rank $r_{s,p}$.
  **Scoring rule: normalised Borda count.**
  $$w_{s,p}^{\text{pref}} = \frac{\rho - r_{s,p}}{\rho - 1} \in [0, 1]$$
  A first choice scores $1$. Each step down the list costs the same $1/(\rho-1)$. An unranked project scores $0$. Edge case: if nobody ranked anything ($\rho = 1$), we set $w^{\text{pref}}_{s,p} = 0$. We normalise to $[0,1]$ so the score is on the same scale as $\sigma_{s,p}$, which makes the weight $\lambda$ in the balanced strategy directly interpretable (§2.5). The score is an affine transformation of rank, so maximising $\sum w^{\text{pref}} x$ is mathematically identical to minimising total rank regret $\sum r\,x$.
- $\text{skill}_{s,k} \in \{0, 1, 2, 3, 4, 5\}$: Declared proficiency level of student $s$ in skill $k$ (undeclared counts as $0$).
- $\text{req}_{p,k} \in \{0, 1, 2, 3, 4, 5\}$: Stated requirement level of project $p$ for skill $k$ ($0$ = no requirement).
- $m_{p,k} \in \{0, 1\}$: Binary flag indicating if skill $k$ is mandatory for project $p$.
- $\sigma_{s,p} \in [0, 1]$: Normalized skill-fit score of student $s$ assigned to project $p$.
  **Formula:** the average requirement-coverage ratio, capped at 1 per skill:
  $$\sigma_{s,p} = \begin{cases} 1 & \text{if } R_p = \emptyset \quad \text{(zero-requirement project)} \\[6pt] \dfrac{1}{|R_p|} \displaystyle\sum_{k \in R_p} \min\!\left(1, \dfrac{\text{skill}_{s,k}}{\text{req}_{p,k}}\right) & \text{otherwise} \end{cases}$$
  *Arguments for this definition:* (i) the cap at $1$ means over-qualification in one skill cannot hide a gap in another; (ii) partial credit (level 1 of required 2 gives $0.5$) separates "almost qualified" from "not at all"; (iii) a project with no requirements cannot be mis-staffed, so every student fits it fully ($\sigma = 1$) and no division by zero occurs (Edge case 4). *Example (unit test):* requirements Python 3 and SQL 2, student has Python 3 and SQL 1, so $\sigma = (1 + 0.5)/2 = 0.75$, with unmet skills `["sql"]`.
- $\lambda \in [0,1]$: preference weight in the balanced strategy (default $0.5$).
- $\varepsilon_1, \varepsilon_2 > 0$: small tie-break weights (§2.5).

**Implementation mapping:** $\sigma_{s,p}$ and the unmet list come from `metrics.calculate_assignment_skill_fit(student, project)`. $w^{\text{pref}}_{s,p}$ is computed from `student.get_preference_rank(project.id)` and `max_preferences`. Both are precomputed once per run into dictionaries keyed by `(student.id, project.id)` before the PuLP model is built.

### 2.3 Decision Variables
- $x_{s,p} \in \{0, 1\}$: Binary decision variable equal to $1$ if student $s$ is assigned to project $p$, and $0$ otherwise.
- **No auxiliary variables are required.** All rules and objectives are linear in $x$. Variables are created only for eligible pairs $(s,p) \in E$. This is equivalent to fixing the others to $0$, and it shrinks the model.

**Implementation mapping:** `x = pulp.LpVariable.dicts("x", eligible_pairs, cat="Binary")`. The reported `DiagnosticInfo.variables_count` is $|E| \le n\,m$.

### 2.4 Hard Mathematical Constraints

1. **Exact Allocation Constraint:**
   $$\sum_{p \in P} x_{s,p} = 1 \quad \forall s \in S$$
   *Explanation: Every student must receive exactly one project.* This uses an equality, not "$\le 1$", because the brief does not allow unassigned students.

2. **Project Headcount Capacity Bounds:**
   $$l_p \le \sum_{s \in S} x_{s,p} \le u_p \quad \forall p \in P$$
   *Explanation: Project enrollments must respect minimum and maximum quotas.* Setting $l_p = 0$ allows a project to stay empty.

3. **Administrative Fixed Allocations (Locks):**
   $$x_{s^*, p^*} = 1 \quad \forall (s^*, p^*) \in F$$
   *Explanation: Pre-assigned pairs must be strictly enforced.* Together with constraint 1, this automatically sets every other project of $s^*$ to $0$.

4. **Mandatory Skill Qualification:**
   $$x_{s,p} = 0 \quad \forall (s,p) \notin E \qquad \text{equivalently} \qquad x_{s,p} = 0 \;\text{ whenever } \exists k : m_{p,k}=1 \wedge \text{skill}_{s,k} < \text{req}_{p,k}$$
   *Explanation and argument:* we interpret "mandatory" **individually**: every student placed in a project must meet each of its mandatory requirements. This is the literal meaning of a hard prerequisite, and it is enforced by pruning ineligible pairs before solving, so it costs no extra constraints. Under this rule, coverage by at least one assigned student follows automatically whenever $\sum_s x_{s,p} \ge 1$. A project with $l_p \ge 1$ whose mandatory skill no student possesses is provably infeasible, and pre-flight validation reports it (Edge case 12). If a lock $(s^*,p^*) \in F$ is not eligible, the input contradicts itself and validation rejects it before solving.
   *Alternative interpretation (not adopted, noted for approval):* "at least one team member must qualify" would need coverage constraints $\sum_{s:\,(s,p)\in E} x_{s,p} \ge y_p$ with $y_p \ge \sum_s x_{s,p}/u_p$, plus binary $y_p$. [To be confirmed with the course responsible.]

5. **Distinct Alternative Solutions (No-Good Integer Cuts):**
   $$\sum_{(s,p) \in A^{(j)}} x_{s,p} \;\le\; n - 1 \qquad \forall A^{(j)} \in \mathcal{A}$$
   *Explanation and argument:* $A^{(j)}$ contains exactly one pair per student, so its left-hand side equals $n$ only if the new solution reproduces $A^{(j)}$ exactly. Limiting it to $n-1$ forces at least one student to change project, which is precisely the brief's definition of a distinct alternative. One linear row per found solution suffices, so the model grows by only one constraint per alternative. Because every student has exactly one project, a single changed student means at least two pairs differ: the old pair leaves and a new one enters.

**Implementation mapping:** each constraint is one `model += ...` line in `AssignmentStrategy.solve`. The cuts are built from the `excluded_solutions: list[list[tuple[str, str]]]` argument, which receives the `(student_id, project_id)` pairs of earlier solutions. `DiagnosticInfo.constraints_count` reports $n + 2m + |F| + t$.

### 2.5 Optimization Objectives & Strategies

All strategies share constraints 1–5. Only the objective differs, so each strategy implements only `calculate_cost_or_utility`, while the model-building code is shared (Strategy Pattern).

- **Strategy 1: Preference-Oriented (Minimize Regret)**, key `PREFERENCE`
  $$\max Z_{\text{pref}} = \sum_{s \in S}\sum_{p \in P} w^{\text{pref}}_{s,p}\,x_{s,p} \;+\; \varepsilon_1 \sum_{s \in S}\sum_{p \in P} \sigma_{s,p}\,x_{s,p}, \qquad \varepsilon_1 = \frac{1}{2\,n\,(\rho-1)}$$
  *Argument:* the first term is total normalised preference, equivalent to minimising total rank regret. The second term only breaks ties between equally preferred allocations in favour of better skill fit, which makes results deterministic and sensible. **Proof that the tie-break never overrides preference:** every $w^{\text{pref}}$ is a multiple of $1/(\rho-1)$, so two allocations with different preference totals differ by at least $1/(\rho-1)$. The tie-break term lies in $[0, n\varepsilon_1] = [0, \tfrac{1}{2(\rho-1)}]$, which is strictly less than that gap.

- **Strategy 2: Skill-Fit-Oriented (Maximize Quality)**, key `SKILL_FIT`
  $$\max Z_{\text{skill}} = \sum_{s \in S}\sum_{p \in P} \sigma_{s,p}\,x_{s,p} \;+\; \varepsilon_2 \sum_{s \in S}\sum_{p \in P} w^{\text{pref}}_{s,p}\,x_{s,p}, \qquad \varepsilon_2 = 10^{-4}$$
  *Argument:* maximising total skill fit equals maximising $\bar{\sigma}$, since $n$ is fixed. Preference breaks ties, so that among equally qualified allocations students get the ones they prefer. ($\sigma$ is real-valued, so no exact separation bound exists here. $\varepsilon_2$ is chosen far below any meaningful $\sigma$ difference at our data resolution, where skill levels are integers from 1 to 5.)

- **Strategy 3: Balanced Trade-Off (Compromise)**, key `BALANCED`
  $$\max Z_{\text{balanced}} = \sum_{s \in S}\sum_{p \in P} \Big[\lambda\, w^{\text{pref}}_{s,p} + (1-\lambda)\,\sigma_{s,p}\Big]\,x_{s,p}, \qquad \lambda = 0.5$$
  *Argument:* both criteria lie in $[0,1]$ per student, so $\lambda$ reads directly as "share of importance given to preference". This weighted-sum scalarisation has a key property: for any $\lambda \in (0,1)$ the optimum is **Pareto-efficient** with respect to (total preference, total skill fit). No other feasible allocation is at least as good on both and strictly better on one. Otherwise that allocation would have a higher $Z_{\text{balanced}}$, which contradicts optimality.

**Implementation mapping:** `PreferenceOrientedSolver`, `SkillFitOrientedSolver` and `BalancedTradeoffSolver` subclass `AssignmentStrategy`. Each returns its per-pair weight from `calculate_cost_or_utility(student, project, max_preferences)`, and the shared `solve` sets `model += pulp.lpSum(weight[s,p] * x[s,p] ...)` with `pulp.LpMaximize`. They are registered in `AssignmentEngine.__init__` under `self.strategies = {"PREFERENCE": ..., "SKILL_FIT": ..., "BALANCED": ...}`.

### 2.6 Alternative-Generation Procedure (engine orchestration)

Let $\pi_1$ be the strategy requested in `RunRequest.strategy_key`, and $\pi_2, \pi_3$ the other two in fixed order (`PREFERENCE` → `SKILL_FIT` → `BALANCED`). With $K$ = `max_alternatives`:

```
1. outcome = validate_inputs(request)
   if not valid / not feasible → run.status = INVALID_INPUT or INFEASIBLE, 0 solutions, reasons stored
2. found = []
3. for k = 1..K:
       strategy = π_((k−1) mod 3 + 1)
       status, assignments, obj, diag = strategy.solve(..., excluded_solutions=found)
       if status == "Infeasible":
           if k == 1: run.status = INFEASIBLE (solver proof), record reasons; stop
           else: stop  # no further distinct allocation exists, reported honestly
       if time limit reached without a solution: record warning; stop
       found.append(pairs(assignments)); indicators = metrics.compute_solution_indicators(...)
4. run.status = COMPLETED; run.diagnostics["distinct_alternatives"] = len(found); persist via run_repo
```

*Argument:* alternative 1 is optimal for the coordinator's chosen priority. Alternatives 2 and 3 are optimal for the *other* priorities, under the condition that they differ from what was already shown. The comparison page therefore shows real trade-offs rather than three near-identical allocations, which is what the k-th-best solutions of a single objective would usually give. Every solution is feasible and distinct by construction. Verification: Edge case 14 (one feasible allocation) gives 1 solution; Edge case 15 (exactly two permutations) gives 2 solutions, because the third solve is proven infeasible.

**Implementation mapping:** `AssignmentEngine.execute_run` in `solvers.py`. Each `models.Solution` stores its own `strategy_name` and `alternative_number`.

---

## 3. Evaluation Indicators & Analytical Metrics

All indicators are computed after solving, from the allocation itself, by `metrics.compute_solution_indicators(students, projects, assignments, fixed_assignments)`. They are independent of the solver, so they also act as a correctness check. Notation: $p(s)$ is the project of $s$, $r_s = r_{s,p(s)}$, $\sigma_s = \sigma_{s,p(s)}$, and $n_p = \sum_s x_{s,p}$.

### 3.1 Feasibility Indicators
- Allocation completeness: $\sum_{s \in S} \sum_{p \in P} x_{s,p} = |S|$, and no student appears twice.
- Capacity compliance check for all $p \in P$: $l_p \le n_p \le u_p$. Each violation is listed with its project and direction (under or over).
- Fixed lock adherence check: $x_{s^*,p^*} = 1 \;\forall (s^*,p^*) \in F$. Broken locks are listed.
- Mandatory requirement fulfillment count: $\big|\{s : (s, p(s)) \notin E\}\big|$, which must be $0$.
- `feasibility.is_feasible` $=$ all four checks pass, and `feasibility.violations` lists the failures in plain language.

*Argument:* the solver already enforces these rules. Recomputing them independently guards against modelling bugs and lets Team A display a verifiable "all rules satisfied" badge.

### 3.2 Efficiency Indicators
- **Mean Skill-Fit Score ($\bar{\sigma}$):**
  $$\bar{\sigma} = \frac{1}{|S|} \sum_{s \in S} \sum_{p \in P} \sigma_{s,p} \cdot x_{s,p}$$
- **Mean Preference Rank ($\bar{r}$):**
  $$\bar{r} = \frac{1}{|S|} \sum_{s \in S} \sum_{p \in P} r_{s,p} \cdot x_{s,p}$$
  Unranked placements count as $\rho$, so they visibly worsen $\bar{r}$ rather than being silently ignored.
- **Unmet soft requirements:** $\displaystyle\sum_{s \in S} \big|\{k \in R_{p(s)} \setminus M_{p(s)} : \text{skill}_{s,k} < \text{req}_{p(s),k}\}\big|$. This counts how many optional skill needs were left unmet across all teams and is used by recommendation Priority 2.

*Unit-test check:* skill fits $(1.0, 0.8)$ give $\bar{\sigma} = 0.9$, and ranks $(1, 2)$ give $\bar{r} = 1.5$.

### 3.3 Fairness Indicators

1. **Rank Distribution:** Histogram vector $[c_1, c_2, \dots, c_{|P|}, c_{\text{unranked}}]$ where $c_k$ is the number of students assigned to their $k$-th choice.
2. **Unranked Allocation Count ($U$):** Count of students allocated outside their submitted preference list, $U = c_{\text{unranked}}$. It is also reported as $100\,U/n$ %.
3. **Worst Assigned Rank ($r_{\max}$):**
   $$r_{\max} = \max_{(s,p) : x_{s,p}=1} r_{s,p}$$
4. **Team's Proposed Fairness Indicator: Gini coefficient of assigned ranks**
   $$G = \frac{\sum_{i=1}^n \sum_{j=1}^n |r_i - r_j|}{2 n \sum_{i=1}^n r_i}, \qquad 0 \le G \le \frac{n-1}{n}$$
   **Interpretation.** $G$ is half the mean absolute difference between any two students' ranks, divided by the mean rank. $G = 0$ means every student received the same rank, i.e. perfect equality of outcome. As $G$ rises, outcomes become more unequal: some students got their top choices while others ended far down their lists.
   **Why this metric captures inequality.** (i) It compares *every pair* of students, so it reflects the whole distribution rather than only the extremes ($r_{\max}$) or the centre ($\bar{r}$). (ii) It is scale-normalised and does not depend on cohort size, so values are comparable across runs and cohorts. (iii) It is the standard inequality measure in economics and familiar to a business-school audience. (iv) It is well defined because every rank is $\ge 1$, so the denominator is never zero.
   **Caveat (critical reflection).** $G$ is scale-invariant: "everyone got their 3rd choice" also gives $G = 0$. A low $G$ therefore does not mean a good outcome, only an equal one. It must be read alongside $\bar{r}$ and $r_{\max}$, and the UI always shows them together. As a non-scale-invariant complement we also report the **rank variance** $\operatorname{Var}(r) = \frac{1}{n}\sum_s (r_s - \bar{r})^2$, which recommendation Priority 3 uses as its second criterion.
   *Unit-test check:* ranks $[2,2,2,2]$ give $G = 0$, and $[1,1,1,10]$ give $G = \tfrac{54}{2\cdot 4 \cdot 13} \approx 0.52 \in (0,1)$.

### 3.4 Capacity Utilization Metrics
- Per-project utilization percentage:
  $$\text{Util}_p = \frac{\sum_{s \in S} x_{s,p}}{u_p} \times 100\%$$
- Aggregate cohort capacity slack and tightness:
  $$\text{Util} = \frac{\sum_{p} n_p}{\sum_{p} u_p} \times 100\% = \frac{n}{\sum_p u_p} \times 100\%, \qquad \text{slack} = \sum_p u_p - n$$
  Per project we also report the slack above the minimum, $n_p - l_p$, and flag tight projects: **full** ($n_p = u_p$) or **at minimum** ($n_p = l_p > 0$). A cohort with slack $0$ has no room to reallocate, which explains why few distinct alternatives may exist.

*Unit-test check:* 2 students in one project with $u_p = 2$ gives $\text{Util} = 100\%$.

**Implementation mapping:** `compute_solution_indicators` returns `{"feasibility": {...}, "efficiency": {"mean_skill_fit", "unmet_soft_requirements_count", ...}, "fairness": {"mean_rank", "worst_rank", "unranked_count", "unranked_pct", "rank_distribution", "rank_gini", "rank_variance"}, "capacity": {"overall_utilization_pct", "projects": {...}}}`. $G$ comes from `metrics.calculate_gini(ranks)`, with $G = 0$ returned for an empty or all-zero list for safety.

---

## 4. Trade-Off Analysis & Solution Comparison

### 4.1 Comparative Delta Formulation
`metrics.compare_two_solutions(solution_a, solution_b)` computes all deltas as "B minus A":
$$\Delta \bar{\sigma} = \bar{\sigma}_B - \bar{\sigma}_A$$
$$\Delta \bar{r} = \bar{r}_B - \bar{r}_A$$
$$\Delta r_{\max} = r_{\max, B} - r_{\max, A}$$
$$\Delta G = G_B - G_A$$
$$\Delta U = U_B - U_A$$
**Reading convention shown in the UI:** $\Delta\bar{\sigma} > 0$ is an improvement (better skill fit). For $\Delta\bar{r}$, $\Delta r_{\max}$, $\Delta G$ and $\Delta U$, positive values are a deterioration (worse ranks, more inequality, more unranked students). Each delta is colour-coded by this convention, so the coordinator sees at a glance *what improves and what worsens*. That is the core question of the brief.

### 4.2 Allocation Diff & Displaced Student Identification
- **Changed Assignments:** $\{(s, p_A, p_B) : x_{s, p_A}^{(A)} = 1 \land x_{s, p_B}^{(B)} = 1 \land p_A \ne p_B\}$. `is_distinct` is true iff this set is non-empty, and `changed_students_count` is its size.
- **Worsened Students ($\Delta r_s > 0$):** Students whose preference rank worsened in Solution B, where $\Delta r_s = r_s^{B} - r_s^{A}$.
- **Improved Students ($\Delta r_s < 0$):** Students whose preference rank improved in Solution B.
- **Unchanged-rank movers ($\Delta r_s = 0$, $p_A \ne p_B$):** students who moved project at the same rank. They are reported separately so no movement is hidden.

*Argument:* aggregate deltas show *how much* changes, and the diff shows *who* is affected, which is the second core question of the brief. The coordinator can then judge whether a gain in $\bar{\sigma}$ is worth the specific students it displaces.

*Unit-test check:* S1 and S2 swap projects, with ranks $(1,1)$ changing to $(3,2)$ and fits $(0.5, 0.6)$ changing to $(1.0, 0.9)$. Result: 2 changed students, $\Delta\bar{\sigma} = 0.95 - 0.55 = +0.40$, $\Delta\bar{r} = 2.5 - 1.0 = +1.5$, and 2 worsened students. Generated summary: *"Solution B raises mean skill fit by 0.40, but 2 students receive a worse-ranked project (mean rank +1.5)."*

**Implementation mapping:** the returned keys are `is_distinct`, `changed_students_count`, `changed_assignments`, `delta_mean_skill_fit`, `delta_mean_rank`, `rank_worsened_count` (plus `delta_metrics` and `trade_off_summary`), consumed by `AssignmentEngine.compare_solutions` and the `/compare` page.

---

## 5. Transparent Recommendation Rules

Recommendations (`app/engine/recommendations.py`) are deliberately rule-based and inspectable. Each one lists the **criteria** (the rule applied), the **evidence** (numbers computed in §3) and the **advice** (a normative judgement, clearly labelled as such). The system recommends one solution *per policy priority*. It never chooses the priority itself, because that is the coordinator's value judgement.

### 5.1 Policy Priority 1: Student Preference Maximization
- **Quantitative Selection Criterion:** lexicographic minimization of the unranked count $U$, then mean rank $\bar{r}$, then worst rank $r_{\max}$:
  $$\text{arg lexmin}_{\text{solutions}} \;(U,\; \bar{r},\; r_{\max})$$
  *Argument:* placing a student outside their list is the most serious satisfaction failure, so it is checked first. The average comes next, and the worst case breaks remaining ties.
- **Calculated Evidence Reported:** $\bar{r}$; $U$; $r_{\max}$; and $\bar{\sigma}$, to make visible what is given up on skills.
- **Administrative Advice & Trade-Off Warning:** Adopt when student satisfaction, programme morale and avoiding appeals are the main goals. *Warning:* skill coverage may be lower. Check the unmet soft-requirement count, especially for external-client projects.

### 5.2 Policy Priority 2: Project Delivery & Technical Competence
- **Quantitative Selection Criterion:** maximization of mean skill fit $\bar{\sigma}$, with ties broken by the fewest unmet soft requirements:
  $$\text{arg lexmax}_{\text{solutions}} \;(\bar{\sigma},\; -\text{unmet}_{\text{soft}})$$
- **Calculated Evidence Reported:** $\bar{\sigma}$; unmet soft requirements; $\bar{r}$, to make visible what is given up on preferences.
- **Administrative Advice & Trade-Off Warning:** Adopt when partner organisations or client deliverables demand strong technical capability. *Warning:* more students may receive low-ranked or unranked projects. Check $U$ and the list of worsened students before adopting.

### 5.3 Policy Priority 3: Balanced & Egalitarian Compromise
- **Quantitative Selection Criterion:** lexicographic minimization of the rank Gini $G$, then rank variance, then mean rank:
  $$\text{arg lexmin}_{\text{solutions}} \;(G,\; \operatorname{Var}(r),\; \bar{r})$$
  *Argument:* this priority targets *equality of outcome*. $G$ measures it directly. Variance and the mean then break ties and guard against the scale-invariance caveat of §3.3.
- **Calculated Evidence Reported:** $G$; $\operatorname{Var}(r)$; $\bar{\sigma}$; $\bar{r}$.
- **Administrative Advice & Trade-Off Warning:** Adopt when the committee wants a fair compromise that avoids extreme individual disadvantage. *Warning:* a low $G$ can coexist with a mediocre average rank, so confirm $\bar{r}$ and $r_{\max}$ are acceptable.

---

## 6. Assumptions, Boundary Conditions & Edge Cases

1. **Student Submission Incompleteness:** unranked projects receive the penalty rank $\rho = R+1$ and preference score $w^{\text{pref}} = 0$. They are allowed (so a feasible allocation is never blocked by short lists) but are always the least preferred option for every objective, and every such placement is counted in $U$ and shown in the rank distribution (Edge case 1).
2. **Ties in Preferences:** identical preference lists are valid input. Capacity determines how many students can share a top choice. Among equally optimal allocations the tie-break term chooses, and any residual ties are resolved deterministically by the fixed variable ordering, so repeated runs give identical results. No student is favoured by identity in the model, but which of two identical students receives the scarce seat is arbitrary but reproducible. We disclose this rather than hide it (Edge case 2).
3. **Skill Levels:** a student with no declared skills has level $0$ everywhere. They are eligible for every project without mandatory requirements and score $\sigma = 0$ on projects with requirements, so skill-oriented objectives steer them to low-requirement projects. A project with zero requirements gives $\sigma = 1$ to every student (Edge cases 3–4). Requirement levels of $0$ are treated as "not required".
4. **Feasibility Boundaries:** the problem is **provably infeasible** exactly when no $x$ satisfies constraints 1–4. Pre-flight validation (`app/domain/validation.py`) detects the following sufficient conditions and gives a readable reason for each:
   - $n > \sum_p u_p$: more students than seats (Edge case 7);
   - $n < \sum_p l_p$: too few students to fill minimums (Edge case 8);
   - $l_p > u_p$ for some $p$ (Edge case 9);
   - one student locked to two projects (Edge case 10);
   - $|\{s : (s,p) \in F\}| > u_p$: locks overfill a project (Edge case 11);
   - a mandatory requirement that no student meets while $l_p \ge 1$ (Edge case 12);
   - a lock on an ineligible pair.

   Any remaining infeasibility (e.g. the eligible students cannot fill all minimums at once) is proven by the solver and reported as `INFEASIBLE` with 0 solutions (Edge case 13). If the cut model becomes infeasible at step $k > 1$, the run is still `COMPLETED` with $k-1$ solutions and `distinct_alternatives` $= k-1$ (Edge cases 14–15).

---

## 7. Limitations & Analytical Deficiencies

1. **Computational Complexity:** MILP is NP-hard in general, and each extra alternative adds one cut and a full re-solve. Two structural facts keep our instances easy. First, constraints 1–4 form a transportation-type system with a totally unimodular matrix, so without cuts the LP relaxation is integral and CBC often closes at the root node. Second, the model is small ($|S|\cdot|P|$ variables). The cuts break total unimodularity, so solve time can grow with many alternatives or with cohorts of thousands of students. Mitigations: the solver time limit, keeping $K \le 3$, pruning ineligible pairs, and switching to HiGHS through PuLP if needed.
2. **Linear Preference Assumptions:** the Borda score assumes equal value for every step down the list: moving from 1st to 2nd choice "costs" as much as moving from 5th to 6th. Real students probably care much more about their top choices. A convex scoring such as $w = 2^{-(r-1)}$ would capture this and still be linear in $x$, but the shape is a value judgement we would need to justify and validate with students. Borda is also sensitive to list length, which is why we normalise by $\rho$.
3. **Individual vs. Team Synergies:** $\sigma_{s,p}$ evaluates each student separately and sums the results. It ignores collective effects: one strong member can cover a skill for the whole team; skills can complement each other; diversity, prior collaboration and conflicts matter. Modelling these needs team-level coverage variables (still MILP) or quadratic pair terms, which significantly increases model size and data needs.
4. **Static Allocation:** the model allocates once, from a snapshot of data. It cannot anticipate drop-outs, late enrolments or mid-semester project cancellations. The supported mitigation is "lock and re-run": current placements are added to $F$ and only the affected students are re-optimised. The re-run is still a new static solve, not a dynamic policy.

**Further reflections:**

5. **Self-reported data:** skill levels are declared, not verified, so the skill objective is only as good as students' self-assessment. Over-reporting is directly rewarded by the skill strategy.
6. **Weight choice:** $\lambda = 0.5$ looks neutral, but it is itself a value choice. Different $\lambda$ give different Pareto points, and the coordinator should see this rather than treat $\lambda$ as technical.
7. **Fairness is measured, not optimised:** $G$ is non-linear and is reported, not optimised directly. A linear extension would bound or minimise the worst rank, via $r_{s,p}\,x_{s,p} \le z \;\forall s,p$ with $\min z$. This remains within MILP and is a natural fourth strategy.

---

## References

- Balas, E., & Jeroslow, R. (1972). Canonical cuts on the unit hypercube. *SIAM Journal on Applied Mathematics*, 23(1), 61–69.
- Biró, P., Fleiner, T., Irving, R. W., & Manlove, D. F. (2010). The College Admissions problem with lower and common quotas. *Theoretical Computer Science*, 411(34–36), 3136–3153.
- Gale, D., & Shapley, L. S. (1962). College admissions and the stability of marriage. *The American Mathematical Monthly*, 69(1), 9–15.
- Postek, K., Zocca, A., Gromicho, J., & Kantor, J. (2024). *Hands-On Mathematical Optimization with Python*. Cambridge University Press. https://mobook.github.io/MO-book/
- Rezaeinia, N., et al. (2022). [Insert the full verified reference as given in the project brief.]
- PuLP: https://coin-or.github.io/pulp/ · CBC: https://github.com/coin-or/Cbc
