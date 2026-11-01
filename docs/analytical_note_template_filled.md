# Deliverable 6: Analytical Note & Mathematical Formulation
## Student Submission — TECH5 Collaborative Project

**Team:** Team 6 (Groups 3 and 17 — 5 Members)  
**Authors (Team B - Assignment Engine):** Daniel (B1), Torkil (B2), Marie (B3)  
**Authors (Team A - Visualization & Recommender):** Julia (A1), Tanver (A2)  
**Course:** TECH5 Programming & Application Design, NHH Norwegian School of Economics  
**Date:** 1 November 2026

---

## 1. Problem Definition & Mathematical Modeling Approach

### 1.1 Business Context & Decision Dilemma

Every semester, a programme coordinator must place each student on exactly one project. Each project has a minimum and a maximum number of students. Projects also list the skills they need, and some of these skills are mandatory. A few students may already be placed on a project before the run starts, for example because of an agreement with a partner.

The coordinator wants two things that often conflict:

- **Project quality (skill matching):** Project teams should have the skills the work needs.
- **Student satisfaction (preference rank):** Students should get a project they ranked high.

The conflict appears when many students want the same few projects. If we only follow preferences, popular projects can get students without the right skills. If we only follow skills, some students end up on projects they ranked low or did not rank at all. Our demo data shows this: one solution gives all 10 students their first choice with 98.3% skill fit, while another reaches 100% skill fit but gives two students their second choice.

No single answer is best on both goals. So our system does not decide for the coordinator. It finds solutions that follow all the rules, shows the numbers for each one, and lets the coordinator choose.

Rezaeinia et al. (2022) study a similar problem: assigning students to business projects in a master's programme in Norway, looking at both efficiency and fairness. We use their paper as background only. Our model is our own, and we did not copy their method.

### 1.2 Chosen Assignment Methodology & Academic Justification

**Chosen method:** Mixed-Integer Linear Programming (MILP). We write the model in Python with **Pyomo** (Hart et al., 2017) and solve it with the **HiGHS** solver (Huangfu & Hall, 2018).

In simple terms, MILP lets us say: "choose the assignment with the best score, and never break these rules." Each student–project pair is a yes/no decision, and all rules and scores are sums of these decisions. Because all our decisions are yes/no, our model is the pure integer case of MILP.

**Why Pyomo and HiGHS:** We learned both in the TECH4 course, so we could spend our time on the model instead of on learning a new tool. Both are free and install with `pip`, so nobody needs to install a separate solver program.

**Why MILP:** It meets the requirements we have for the solver:

| What the solver must do | How MILP does it |
| :--- | :--- |
| Give every student exactly one project | This is a rule in the model. A solution that breaks it is not allowed. |
| Respect minimum and maximum project size | This is also a rule in the model. |
| Keep fixed assignments | We set that decision to "yes" ($x = 1$). |
| Respect mandatory skills | We set the decision to "no" ($x = 0$) for students who lack the skill. |
| Return several solutions, never the same one twice | After each solution, we add one rule that forbids exactly that solution. The next solution must be different for at least one student. |
| Say so when no more solutions exist | The solver reports that no solution is left. We stop and show the solutions we found. We never add copies. |
| Say so when the rules cannot all be met | The solver reports the problem as infeasible instead of returning a bad solution. |
| Support different goals | The rules stay the same. Only the score we maximize changes. |
| Give the same result each time | Repeated runs of the demo with the same input gave identical solutions. This also keeps our automated tests stable. |

**Why it fits the size of our problem:** The model has one yes/no variable for each student–project pair. Our demo has 10 × 4 = 40 variables, and 60 students with 12 projects would give 720. The demo run with 3 solutions takes under 0.1 seconds. Section 7 shows tests with larger groups.

**Why it works in a single Python process:** HiGHS is called like a normal Python library through `highspy`. The Flask app and the solver run in the same Python process, so we need no separate server and no external program.

**Other methods we did not choose:** We did not build or test these. We left them out for the following reasons:

- **PuLP with CBC:** This is the same kind of method. We chose Pyomo and HiGHS because we knew them from TECH4.
- **Stable matching** (Gale & Shapley, 1962): Both sides must rank each other, but our projects list skill requirements and do not rank students. Minimum team sizes and fixed assignments also do not fit the basic method.
- **Heuristic search**, for example genetic algorithms: It can find good solutions quickly, but it cannot prove that a solution is the best or that no solution exists.
- **Min-cost flow:** It can handle basic assignment, but it cannot include the rule that forbids an earlier solution.

**In the code:** [`requirements.txt`](../requirements.txt) lists `pyomo` and `highspy`. The model and the three strategies are in [`app/engine/strategies.py`](../app/engine/strategies.py). The `AssignmentStrategy` base class and the `AssignmentEngine` that runs everything are in [`app/engine/solvers.py`](../app/engine/solvers.py).

---

## 2. Mathematical Formulation

### 2.1 Index Sets & Dimensions

These are the sets we use in the model:

- $S = \{s_1, s_2, \dots, s_n\}$: Set of students in the cohort ($|S| = n$).
- $P = \{p_1, p_2, \dots, p_m\}$: Set of available semester projects ($|P| = m$).
- $K = \{k_1, k_2, \dots, k_q\}$: Set of evaluated technical skills ($|K| = q$).
- $F \subseteq S \times P$: Set of pre-allocated fixed assignment pairs $(s, p)$.
- $K_p \subseteq K$: Set of skills required by project $p$.
- $M_p \subseteq K_p$: Set of mandatory skills for project $p$, meaning all $k$ with $m_{p,k} = 1$.
- $A^{(j)} \subseteq S \times P$: The $j$-th solution found during a run, written as its list of $(s, p)$ pairs.

### 2.2 Model Parameters

- $l_p \in \mathbb{Z}_{\ge 0}$: Minimum headcount capacity for project $p$.
- $u_p \in \mathbb{Z}_{\ge 1}$: Maximum headcount capacity for project $p$ ($l_p \le u_p$).
- $r_{s,p} \in \{1, 2, \dots, |P|\} \cup \{|P|+1\}$: Stated preference rank of student $s$ for project $p$.

  Rank 1 is the student's first choice. Students do not have to rank every project. An unranked project gets a penalty score in the solver (see below). In the fairness measures it gets the rank $\rho$, which is the highest rank used by anyone in the cohort plus 1. This equals $|P|+1$ when at least one student ranked all projects.
- $R$: Length of the longest preference list in the cohort (at least 1). In our demo, $R = 3$.
- $w_{s,p}^{\text{pref}}$: Preference score or weight derived from rank $r_{s,p}$.

  We use a Borda-style score. A first choice gets the most points, each lower rank gets one point less, and an unranked project gets a large penalty:
  $$w_{s,p}^{\text{pref}} = \begin{cases} R - r_{s,p} + 1 & \text{if student } s \text{ ranked project } p \\ -2R & \text{if student } s \text{ did not rank project } p \end{cases}$$
  With $R = 3$, the points are 3, 2 and 1 for ranks 1, 2 and 3, and $-6$ for an unranked project. The penalty makes unranked projects very unattractive, but it does not forbid them. A student can still end up there if the rules leave no other option, or if the move gains enough points for other students.
- $\hat{w}_{s,p}^{\text{pref}}$: Preference score used in the balanced strategy.

  Preference points run from 1 to $R$, while skill fit runs from 0 to 1. To put both on the same scale, we divide the points by $R$:
  $$\hat{w}_{s,p}^{\text{pref}} = \begin{cases} \dfrac{R - r_{s,p} + 1}{R} & \text{if student } s \text{ ranked project } p \\ -1 & \text{if student } s \text{ did not rank project } p \end{cases}$$
  With $R = 3$, the scores are 1.00, 0.67 and 0.33 for ranks 1, 2 and 3, and $-1$ for an unranked project.
- $\text{skill}_{s,k} \in \{0, 1, 2, 3, 4, 5\}$: Declared proficiency level of student $s$ in skill $k$. A skill the student did not declare counts as level 0.
- $\text{req}_{p,k} \in \{0, 1, 2, 3, 4, 5\}$: Stated requirement level of project $p$ for skill $k$.
- $m_{p,k} \in \{0, 1\}$: Binary flag indicating if skill $k$ is mandatory for project $p$.
- $\sigma_{s,p} \in [0, 1]$: Normalized skill-fit score of student $s$ assigned to project $p$.

  For each required skill, we divide the student's level by the required level and cap the result at 1. Then we take the average over the required skills:
  $$\sigma_{s,p} = \begin{cases} 1 & \text{if } K_p = \emptyset \text{ (project with no requirements)} \\ \dfrac{1}{|K_p|} \displaystyle\sum_{k \in K_p} \min\left(1, \dfrac{\text{skill}_{s,k}}{\text{req}_{p,k}}\right) & \text{otherwise} \end{cases}$$
  The cap means that being very strong in one skill cannot hide a gap in another skill. For example, a project needs Python level 3 and SQL level 2, and a student has Python 5 and SQL 1. The score is $(1 + 0.5) / 2 = 0.75$. A project with no requirements gives every student a score of 1, so we never divide by zero. A single requirement with level 0 counts as fully met for the same reason.
- $\alpha \in [0, 1]$: Weight of preferences in the balanced strategy. We use $\alpha = 0.5$, so preferences and skills count the same. The value is set in the code, not in the app.

**In the code:** $\sigma_{s,p}$ is calculated by `calculate_assignment_skill_fit` in [`app/engine/metrics.py`](../app/engine/metrics.py). The preference scores are calculated by `calculate_cost_or_utility` in each strategy class in [`app/engine/strategies.py`](../app/engine/strategies.py).

### 2.3 Decision Variables

- $x_{s,p} \in \{0, 1\}$: Binary decision variable equal to $1$ if student $s$ is assigned to project $p$, and $0$ otherwise.

We do not need any auxiliary variables. All rules and goals use only $x_{s,p}$.

**In the code:** `_build_base_model` creates `model.x` with one binary variable per student–project pair.

### 2.4 Hard Mathematical Constraints

A solution is *feasible* if it follows all five rules below. If no solution can follow all of them, the problem is *infeasible*.

1. **Exact Allocation Constraint:**
   $$\sum_{p \in P} x_{s,p} = 1 \quad \forall s \in S$$
   *Explanation: Every student must receive exactly one project.*

2. **Project Headcount Capacity Bounds:**
   $$l_p \le \sum_{s \in S} x_{s,p} \le u_p \quad \forall p \in P$$
   *Explanation: Project enrollments must respect minimum and maximum quotas.*

   A project with $l_p = 0$ may stay empty.

3. **Administrative Fixed Allocations (Locks):**
   $$x_{s^*, p^*} = 1 \quad \forall (s^*, p^*) \in F$$
   *Explanation: Pre-assigned pairs must be strictly enforced.*

   These locks come from the coordinator, either before a run or through **Lock & Rerun** in the app.

4. **Mandatory Skill Qualification:**
   $$x_{s,p} = 0 \quad \text{for every pair } (s, p) \text{ where } \text{skill}_{s,k} < \text{req}_{p,k} \text{ for some } k \in M_p$$
   *Explanation:* A student who does not reach the mandatory level cannot join the project. This is stricter than asking for at least one qualified student, because every student on the project must qualify. So any project with students on it meets its mandatory requirements.

5. **Distinct Alternative Solutions (No-Good Integer Cuts):**
   $$\sum_{(s,p) \in A^{(j)}} x_{s,p} \le |S| - 1 \quad \text{for every earlier solution } A^{(j)}$$
   *Explanation:* The sum counts how many students keep the same project as in solution $j$. If all $|S|$ students kept their project, we would get the same solution again. Limiting the sum to $|S| - 1$ means at least one student must move. This rule is called a no-good cut (Balas & Jeroslow, 1972). We add one such rule for each solution we find.

**In the code:** Rules 1–4 are built in `_build_base_model`. Rule 5 is added in `_PyomoAssignmentStrategy.solve` from the list `excluded_solutions`.

### 2.5 Optimization Objectives & Strategies

All three strategies use the same five rules. Only the score changes. In the code, each strategy class defines its own `calculate_cost_or_utility`, and the shared class `_PyomoAssignmentStrategy` builds and solves the model. This is the Strategy Pattern.

- **Strategy 1: Preference-Oriented (Minimize Regret)**
  $$\max Z_{\text{pref}} = \sum_{s \in S} \sum_{p \in P} w_{s,p}^{\text{pref}} \cdot x_{s,p}$$
  This gives students as many preference points as possible. More points means better ranks overall, so there is less regret. In the code: `PreferenceOrientedSolver` (`PREFERENCE`).

- **Strategy 2: Skill-Fit-Oriented (Maximize Quality)**
  $$\max Z_{\text{skill}} = \sum_{s \in S} \sum_{p \in P} \sigma_{s,p} \cdot x_{s,p}$$
  This gives the highest total skill fit, which is the same as the highest average skill fit. It does not look at preferences. In the code: `SkillFitOrientedSolver` (`SKILL_FIT`).

- **Strategy 3: Balanced Trade-Off (Compromise)**
  $$\max Z_{\text{balanced}} = \sum_{s \in S} \sum_{p \in P} \left[\alpha \, \hat{w}_{s,p}^{\text{pref}} + (1 - \alpha) \, \sigma_{s,p}\right] \cdot x_{s,p}, \quad \alpha = 0.5$$
  This scores each placement half on preferences and half on skill fit. In the code: `BalancedTradeoffSolver` (`BALANCED`).

### 2.6 How We Generate Several Solutions

The coordinator chooses a main strategy and how many solutions to generate (1 to 4 in the app). `AssignmentEngine.execute_run` then does the following:

1. It checks the input data. If the data is wrong or the run clearly cannot work, it stops and saves the reason.
2. It saves skills, projects, students and fixed assignments to the database.
3. It solves once for each solution. The first solve uses the main strategy, the next two use the other strategies, and then the order repeats.
4. After each solve, it calculates the indicators and adds a no-good cut for that solution. All cuts stay in place for the later solves.
5. If a strategy finds nothing, it tries the main strategy once more. If that also fails, it stops. With no solutions at all, the run is `INFEASIBLE`. Otherwise it returns the solutions it found.

**Demo result** (10 students, 4 projects with 1–3 seats each, main strategy `PREFERENCE`):

| Solution | Strategy | Mean rank $\bar{r}$ | Worst rank $r_{\max}$ | Gini $G$ | Mean skill fit $\bar{\sigma}$ |
| :--- | :--- | :---: | :---: | :---: | :---: |
| Alt 1 | `PREFERENCE` | 1.00 | 1 | 0.0000 | 98.3% |
| Alt 2 | `SKILL_FIT` | 1.20 | 2 | 0.1333 | 100.0% |
| Alt 3 | `BALANCED` | 1.10 | 2 | 0.0818 | 100.0% |

The cuts make sure these solutions are different, but not that each one is a real trade-off. For example, Alt 3 has the same skill fit as Alt 2 and a better mean rank (see Section 7).

---

## 3. Evaluation Indicators & Analytical Metrics

All measures below are implemented in `app/engine/metrics.py`. They are calculated after the solver is finished, by `compute_solution_indicators`, and they do not use Pyomo. We write $n_p = \sum_{s \in S} x_{s,p}$ for the number of students on project $p$.

### 3.1 Feasibility Indicators

These checks work as a second control of the solver's result. A solution counts as feasible only if the list `violations` is empty.

- Allocation completeness: $\sum_{s \in S} \sum_{p \in P} x_{s,p} = |S|$

  Every student appears exactly once, and all student and project IDs are known.
- Capacity compliance check for all $p \in P$

  We check that $l_p \le n_p \le u_p$.
- Fixed lock adherence check

  We check that every fixed student is on the fixed project.
- Mandatory requirement fulfillment count

  Each case where a student is below a mandatory level is added to `violations`, so this count should be zero.

### 3.2 Efficiency Indicators

- **Mean Skill-Fit Score ($\bar{\sigma}$):**
  $$\bar{\sigma} = \frac{1}{|S|} \sum_{s \in S} \sum_{p \in P} \sigma_{s,p} \cdot x_{s,p}$$
  This shows how well students' skills match their projects, from 0 to 1. Higher is better.
- **Mean Preference Rank ($\bar{r}$):**
  $$\bar{r} = \frac{1}{|S|} \sum_{s \in S} \sum_{p \in P} r_{s,p} \cdot x_{s,p}$$
  Lower is better. Our code makes one change to this formula. Students on an unranked project have no real rank, so we leave them out of the average and count them in $U$ instead (Section 3.3):
  $$\bar{r} = \frac{1}{|S_{\text{ranked}}|} \sum_{s \in S_{\text{ranked}}} \sum_{p \in P} r_{s,p} \cdot x_{s,p}$$
  Here $S_{\text{ranked}}$ is the set of students placed on a project they ranked. If this set is empty, the code returns 0. Because of this change, $\bar{r}$ must always be read together with $U$.
- **Unmet soft requirements:** The number of non-mandatory requirements that assigned students do not reach. We use it as a tie-breaker in Section 5.2.

### 3.3 Fairness Indicators

Following Section 6.3 of the specification, we report the rank distribution, the unranked count, the worst assigned rank, and one proposed fairness indicator. In the worst rank, the Gini coefficient and the rank variance, a student on an unranked project counts with rank $\rho$ (Section 2.2).

1. **Rank Distribution:** Histogram vector $[c_1, c_2, \dots, c_{|P|}, c_{\text{unranked}}]$ where $c_k$ is the number of students assigned to their $k$-th choice.

   Our code stores this as, for example, `{"rank_1": 8, "rank_2": 2}`, and it stores $c_{\text{unranked}}$ separately as `unranked_count`.
2. **Unranked Allocation Count ($U$):** Count of students allocated outside their submitted preference list.

   We also report this as a percentage of all students.
3. **Worst Assigned Rank ($r_{\max}$):**
   $$r_{\max} = \max_{(s,p) : x_{s,p}=1} r_{s,p}$$
   This is the worst result for any single student. An average can look good even if one student gets a very bad result.
4. **Team's Proposed Fairness Indicator: Gini Coefficient of Ranks ($G$):**
   $$G = \frac{\sum_{i=1}^n \sum_{j=1}^n |r_i - r_j|}{2 n \sum_{i=1}^n r_i}$$
   **What it shows:** The formula compares the ranks of all pairs of students. $G = 0$ means that all students have the same rank. A higher $G$ means bigger differences between students.

   **Why we chose it:** The mean rank does not show how ranks are spread between students, and the worst rank only looks at one student. Gini uses all students. Together, $\bar{r}$, $r_{\max}$ and $G$ show the average, the worst case and the spread.

   **Example:** In Alt 2, 8 students have rank 1 and 2 students have rank 2. There are $8 \times 2 = 16$ pairs with a difference of 1. The double sum counts each pair twice, so the top of the fraction is 32. The bottom is $2 \times 10 \times 12 = 240$. This gives $G = 32 / 240 = 0.1333$.

   **Weakness:** Gini measures differences relative to the average. If all students get their third choice, $G = 0$ even though nobody is happy. The ranks $[3, 4]$ also get a lower Gini (0.071) than the better ranks $[1, 2]$ (0.167). So we always read $G$ together with $\bar{r}$ and $r_{\max}$. We also calculate the rank variance, which gives 0.25 in both of these examples because the spread is the same:
   $$\text{Var}(r) = \frac{1}{n} \sum_{i=1}^n (r_i - \mu)^2, \quad \text{where } \mu \text{ is the mean of all } n \text{ ranks}$$

### 3.4 Capacity Utilization Metrics

- Per-project utilization percentage:
  $$\text{Util}_p = \frac{\sum_{s \in S} x_{s,p}}{u_p} \times 100\%$$
- Aggregate cohort capacity slack and tightness
  $$\text{Util}_{\text{overall}} = \frac{|S|}{\sum_{p \in P} u_p} \times 100\%, \qquad \text{Slack} = \sum_{p \in P} u_p - |S|$$
  In our demo, 10 students share 12 seats, which gives 83.3% utilization and a slack of 2 seats. Low slack means the problem is tight, so there are fewer ways to move students around.

**In the code:** `calculate_gini` and `compute_solution_indicators` in [`app/engine/metrics.py`](../app/engine/metrics.py), tested in [`tests/test_metrics.py`](../tests/test_metrics.py).

---

## 4. Trade-Off Analysis & Solution Comparison

### 4.1 Comparative Delta Formulation

The system computes performance deltas between Solution A and Solution B as B minus A:
$$\Delta \bar{\sigma} = \bar{\sigma}_B - \bar{\sigma}_A$$
$$\Delta \bar{r} = \bar{r}_B - \bar{r}_A$$
$$\Delta r_{\max} = r_{\max, B} - r_{\max, A}$$
$$\Delta G = G_B - G_A$$

A positive $\Delta \bar{\sigma}$ is good, because skill fit improves. A positive $\Delta \bar{r}$, $\Delta r_{\max}$ or $\Delta G$ is bad for students, because ranks get worse or more unequal.

**Example:** Going from Alt 1 to Alt 2 gives $\Delta \bar{\sigma} = +0.0167$, $\Delta \bar{r} = +0.20$, $\Delta r_{\max} = +1$ and $\Delta G = +0.1333$. Skill fit improves a little, and students pay for it with worse ranks.

**In the code:** `compare_two_solutions` calculates $\Delta \bar{\sigma}$, $\Delta \bar{r}$ and $\Delta G$, and also the change in unranked students, $\Delta U = U_B - U_A$. It does not calculate $\Delta r_{\max}$. The worst rank of each solution is shown on the run page, so the coordinator can read the difference there. Solutions can only be compared if they contain the same students.

### 4.2 Allocation Diff & Displaced Student Identification

Student re-allocations are classified as follows:

- **Changed Assignments:** $\{(s, p_A, p_B) : x_{s, p_A}^{(A)} = 1 \land x_{s, p_B}^{(B)} = 1 \land p_A \ne p_B\}$
- **Worsened Students ($\Delta r_s > 0$):** Students whose preference rank worsened in Solution B.
- **Improved Students ($\Delta r_s < 0$):** Students whose preference rank improved in Solution B.

For each student who moves, $\Delta r_s$ is the student's rank in B minus the rank in A. A student who moves to a project with the same rank counts as changed, but not as worsened or improved. If a project is unranked, the comparison uses the highest rank seen in A or B plus 1.

The code also writes short summary sentences, for example *"Average skill fit improved by 1.67%."* and *"2 students worsened their preference rank."* The `/compare` page shows these together with the list of students who moved.

**In the code:** `compare_two_solutions` in [`app/engine/metrics.py`](../app/engine/metrics.py). The `/compare` page is in [`app/visualization/routes.py`](../app/visualization/routes.py).

---

## 5. Transparent Recommendation Rules

In accordance with Section 9 of the specification, our recommendations separate calculated evidence from advice across distinct policy priorities.

The rules are in `generate_recommendations` in [`app/engine/recommendations.py`](../app/engine/recommendations.py). Each priority compares the solutions on a fixed list of measures. This is called lexicographic order: we compare on the first measure, and we only look at the next measure if there is a tie. There is no hidden total score, and each priority picks one solution from the run.

### 5.1 Policy Priority 1: Student Preference Maximization
- **Quantitative Selection Criterion:** Lexicographic minimization of unranked count $U$, then $\bar{r}$, then $r_{\max}$.
- **Calculated Evidence Reported:** $\bar{r}$, $U$, $r_{\max}$ and $\bar{\sigma}$.
- **Administrative Advice & Trade-Off Warning:** Use this when student satisfaction and few appeals matter most. Check $\bar{\sigma}$ and the unmet soft requirements, because the project teams may have weaker skills.

### 5.2 Policy Priority 2: Project Delivery & Technical Competence
- **Quantitative Selection Criterion:** Maximization of mean skill fit $\bar{\sigma}$. If there is a tie, we pick the solution with the fewest unmet soft requirements.
- **Calculated Evidence Reported:** $\bar{\sigma}$, the number of unmet soft requirements, and $\bar{r}$.
- **Administrative Advice & Trade-Off Warning:** Use this when partners or the project work need strong skills. Students may get worse ranks, so check $\bar{r}$ and the students who moved on `/compare` before deciding.

### 5.3 Policy Priority 3: Balanced & Egalitarian Compromise
- **Quantitative Selection Criterion:** Gini minimization. We pick the lowest $G$, then the lowest $\text{Var}(r)$, then the lowest $\bar{r}$.
- **Calculated Evidence Reported:** $G$, $\text{Var}(r)$, $\bar{\sigma}$ and $\bar{r}$.
- **Administrative Advice & Trade-Off Warning:** Use this when the main goal is to treat students equally and avoid that a few students get a much worse result. This rule only looks at ranks, not skills, and all students can be equally badly off. So always check $\bar{r}$ and $\bar{\sigma}$ as well.

In the app, Priority 2 is called *Project Skill Quality & Delivery Assurance* and Priority 3 is called *Balanced & Egalitarian Allocation*.

**Demo result:**

| Priority | Recommended solution | Main reason |
| :--- | :--- | :--- |
| 1. Student preferences | Alt 1 | Lowest mean rank (1.00) |
| 2. Project skills | Alt 2 | Highest skill fit (100.0%) and 0 unmet soft requirements |
| 3. Equal outcomes | Alt 1 | Lowest Gini (0.0000) |

Priority 3 is not the same as the `BALANCED` strategy. It picks Alt 1 instead of Alt 3 because it measures how equal the ranks are, not how well preferences and skills are combined.

---

## 6. Assumptions, Boundary Conditions & Edge Cases

Our operational assumptions are:

1. **Student Submission Incompleteness:** How unranked projects are penalized. Students may rank only some projects, or none at all, which gives a warning. Unranked projects can still be assigned. They get the score $-2R$ in `PREFERENCE`, $-1$ in `BALANCED`, and the rank $\rho$ in the fairness measures. `SKILL_FIT` does not use preferences, so it gives no penalty. (Edge Case 1)
2. **Ties in Preferences:** How students with identical preference lists are handled. There is no special rule, no priority order and no lottery. Project capacity limits how many students get a popular project, and the solver chooses the assignment with the best total score. (Edge Case 2) If several assignments have the same score, the solver picks one of them. The same input in the same order gives the same result, but a new order of students can give a different solution. When we shuffled the students in the demo data three times, the first solution stayed the same, while Alt 2 or Alt 3 changed in two of the three cases.
3. **Skill Levels:** Handling students with zero declared skills or projects with zero requirements. A student with no declared skills has level 0 in all skills. This gives $\sigma_{s,p} = 0$ on a project with requirements, but the student can still join if no skill is mandatory. (Edge Case 3) A project with no requirements gives $\sigma_{s,p} = 1$ to every student. (Edge Case 4) A skill that is not in the catalogue gives a warning, not an error. (Edge Case 6)
4. **Feasibility Boundaries:** Exact conditions under which the problem is proved mathematically infeasible. We find these in two steps.

   **Before the solver** (`validate_cohort`), the run stops with status `INFEASIBLE` if:
   - There are more students than seats: $|S| > \sum_{p \in P} u_p$. (Edge Case 7)
   - There are too few students to fill the minimums: $|S| < \sum_{p \in P} l_p$. (Edge Case 8)
   - More students are fixed to a project than its maximum allows. (Edge Case 11)
   - No student meets a mandatory skill level for a project. (Edge Case 12) This check also stops the run when $l_p = 0$, even though that project could stay empty. So here the check is stricter than the model.

   **In the solver**, HiGHS finds the rules that are fine alone but impossible together. (Edge Case 13) One example is two projects that both need the only student with a mandatory skill. Another is a student who is fixed to a project without having its mandatory skill. Both pass the first step. We ran both examples, and both ended as `INFEASIBLE` with 0 solutions.

   **Wrong data** is a different case. The run stops with status `INVALID_INPUT` for empty lists, duplicate IDs, an unknown project in a preference list (Edge Case 5), a minimum above the maximum or a maximum of 0 or less (Edge Case 9), and one student fixed to two projects (Edge Case 10). If one of the capacity checks above also fails, the status is `INFEASIBLE`.

   **Too few solutions:** If fewer solutions exist than the coordinator asked for, the no-good cuts make the model infeasible at that point. We then return only the solutions we found, with no copies. (Edge Cases 14–15)

---

## 7. Limitations & Analytical Deficiencies

The main limitations of our analytical model are:

1. **Computational Complexity:** Scalability limits as $|S|$ and $|P|$ grow. The number of variables is $|S| \cdot |P|$, and each extra solution is a new solve with one more rule. We tested larger groups with 3 solutions each:

   | Students × projects | Variables | Time |
   | :--- | :---: | :---: |
   | 60 × 12 | 720 | 0.10 s |
   | 200 × 20 | 4,000 | 0.42 s |
   | 500 × 30 | 15,000 | 1.29 s |
   | 1,000 × 40 | 40,000 | 3.53 s |

   These tests used random data on one computer, with no mandatory skills, and the time includes saving to the database. Harder data may take longer, because integer problems can become slow in the worst case. Each solve has a limit of 15 seconds. If the solver reached this limit, the code would treat the result as infeasible, even though nothing was proved. This did not happen in our tests.
2. **Linear Preference Assumptions:** Limitations of Borda count vs. non-linear student utilities. Our points treat every step the same, so moving from rank 1 to 2 costs as much as moving from rank 3 to 4. Real students may care much more about their top choices. A score that halves the points for each lower rank would show this, and the model would still be linear.
3. **Individual vs. Team Synergies:** Individual skill evaluation vs. collective team diversity. Both $\sigma_{s,p}$ and rule 4 look at one student at a time. One strong machine learning student and one strong web student can be a good team, even if neither has both skills. Our model cannot see this. Modelling team skills would need extra variables.
4. **Static Allocation:** Inability to capture dynamic scheduling or mid-semester changes. The model uses the data at one point in time, and it does not plan for students dropping out or projects changing. **Lock & Rerun** helps here, because the coordinator can lock the placements that should stay and solve again.
5. **Declared skills:** Skill levels are declared, not tested. If students overstate their skills, `SKILL_FIT` rewards this.
6. **The 50/50 weight:** $\alpha = 0.5$ is our choice, not a fact. Another weight would give another balanced solution.
7. **Fairness is measured, not optimized:** $G$ and $r_{\max}$ are calculated after solving. No strategy tries to improve them directly.
8. **Different does not mean better:** A no-good cut only forces a different solution. In the demo, Alt 3 has the same skill fit as Alt 2 and a better mean rank, because `SKILL_FIT` ignores preferences and several solutions tie at 100%. Priority 2 still recommends Alt 2, because its tie-break does not look at ranks. The coordinator should therefore always check `/compare`.

---

## References

- Balas, E., & Jeroslow, R. (1972). Canonical cuts on the unit hypercube. *SIAM Journal on Applied Mathematics*, 23(1), 61–69.
- Gale, D., & Shapley, L. S. (1962). College admissions and the stability of marriage. *The American Mathematical Monthly*, 69(1), 9–15.
- Hart, W. E., Laird, C. D., Watson, J.-P., Woodruff, D. L., Hackebeil, G. A., Nicholson, B. L., & Siirola, J. D. (2017). *Pyomo — Optimization Modeling in Python* (2nd ed.). Springer. https://www.pyomo.org/
- Huangfu, Q., & Hall, J. A. J. (2018). Parallelizing the dual revised simplex method. *Mathematical Programming Computation*, 10(1), 119–142. https://highs.dev/
- Rezaeinia, N., Góez, J. C., & Guajardo, M. (2022). Efficiency and fairness criteria in the assignment of students to projects. *Annals of Operations Research*, 319(2), 1717–1735. https://doi.org/10.1007/s10479-021-04001-7
