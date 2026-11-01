# Deliverable: Week 3 Progress Report

**Project:** TECH5 Student-to-Project Assignment Decision Support System (DSS)  
**Team:** 6 (Groups 3 and 17 — 5 Members)  
**Repository:** [`mvs242430/TECH5-teams_3_17`](https://github.com/mvs242430/TECH5-teams_3_17)  
**Milestone:** Week 3 — *Robustness, Decision Support & Verification*  
**Date:** 1 November 2026  

> **Note for Marie:** sections marked ⟨to confirm⟩ are filled from what is on GitHub as of 1 Nov. Please correct them with what each person actually finished, then merge.

---

## 1. Week 3 Plan vs. Status

| Owner | Issue | Status | Evidence |
| :--- | :--- | :---: | :--- |
| **Julia (A1)** | `X2` bad-data walkthrough | ✅ Done (branch) | [`X2_solution.md`](../team_related/issues_solutions/X2_solution.md) · branch `x2-bad-data-walkthrough` |
| **Julia (A1)** | `X3` one full end-to-end test | ✅ Done (branch) | `test_x3_full_end_to_end_flow` · branch `x3-end-to-end-test` |
| **Julia (A1)** | `X6` Git evidence | ✅ Done (branch), 2 screenshots to add | [`git_evidence.md`](../git_evidence.md) · branch `x6-git-evidence` |
| **Julia (A1)** | help with `B3.6` testing evidence | ⏳ After merge | needs final `pytest -v` output from `main` |
| **Tanver (A2)** | `A2.4` role-access audit · `A2.5` architecture · `A2.6` demo script · `X4` clean-up | ⟨to confirm⟩ | `A2.5` on branch `feature/task-a2.5-architecture-and-design-documentation`, not on `main` yet |
| **Daniel (B1)** | `B1.4` indicators part of analytical note | ⟨to confirm⟩ | — |
| **Torkil (B2)** | `B2.4` formulation part of analytical note · help `A2.6` | ⟨to confirm⟩ | — |
| **Marie (B3)** | `A2.1.1` compare across cohorts (review follow-up) | ✅ Merged | [PR #50](https://github.com/mvs242430/TECH5-teams_3_17/pull/50) |
| **Marie (B3)** | `B3.5` contract · `B3.6` testing evidence · `X5` team reflection | ⟨to confirm⟩ | — |
| **Everyone** | `X7` final release check | ⏳ Not started | after all branches are merged |

## 2. What Julia's Week 3 work changed

### 2.1 X2 — every scenario with bad data

We loaded all four scenarios plus five extra bad inputs and checked whether the screen says **what is wrong** and **what to change**.

| Finding | Fix |
| :--- | :--- |
| Fixed-lock form with a student/project ID that no longer exists **crashed** (HTTP 500, SQLite foreign-key error). | The route now checks the IDs first and shows "Student 'X' does not exist. Pick a student from the list…". |
| Locking an already-locked student said "created" while silently **replacing** the old lock. | Message now says "was locked to P1 and is now locked to P2". |
| Every infeasibility reason was **shown twice** on the run page (engine stores it in both `reasons` and `errors`). | Template skips errors already listed as reasons. Engine output unchanged. |
| Failed runs said what is wrong but **not what to change**. | "What to change" box with links to Projects, Fixed Locks and Students pages. |
| Unknown scenario name, Student Viewer starting a run, empty database | Already handled well — no change. |

**Open question for Team B:** `validate_inputs` reports *"Mandatory requirement impossible"* even when the project has `min_capacity = 0` and could simply stay empty. Should the check only apply when `min_capacity ≥ 1`? (See `X2_solution.md` §4.)

5 new regression tests in `tests/test_visualization_component.py`.

### 2.2 X3 — one full end-to-end test

`test_x3_full_end_to_end_flow` follows one user through the **real** engine: standard scenario → run → ≥ 2 solutions → `/compare` → `/recommendations` → lock-and-rerun → the locked pair is in **every** new solution → infeasible scenario shows every reason on screen. It locks a student who moves between the two solutions, so the lock is actually tested.

### 2.3 X6 — Git evidence

[`docs/git_evidence.md`](../git_evidence.md) maps all 10 commit identities to the 5 members, lists merged work per person with commit/PR links, and gives three review examples (A1.2.1/A1.2.2 sub-issues, PR #48, B1 test restore).

## 3. Correction to the Week 2 report

The Week 2 report listed `0.2` (PR & issue templates) and `0.4` (README test counts) as done. The work exists on branches `0.2-templates` and `0.4-readme`, but **these two branches were never merged to `main`** (there is no `.github/` folder on `main`). They should be merged before `X7`.

## 4. Test Suite

```text
$ python -m pytest -q
⟨paste the real output from main after merging the Week 3 branches⟩
```

Week 2 ended at `99 passed`. Week 3 adds 6 test cases from Julia (5 for X2, 1 for X3) plus the A2.1.1 tests from PR #50.

## 5. Status Summary

| | Items |
| :--- | :--- |
| **Done** | X2, X3, X6 (on branches, waiting for review/merge); A2.1.1 (merged). |
| **In progress** | ⟨to confirm⟩ A2.4, A2.5, A2.6, X4, B1.4, B2.4, B3.5, B3.6, X5. |
| **Blocked** | Nothing blocked. X7 and B3.6 wait for all branches to be merged. |

## 6. Plan to Finish

1. Review and merge `x2-bad-data-walkthrough`, `x3-end-to-end-test`, `x6-git-evidence`, `0.2-templates`, `0.4-readme`.
2. Team B answers the `min_capacity = 0` question from X2.
3. Run `python -m pytest -v` on `main` → paste into `testing_and_quality.md` (B3.6).
4. `X7`: rehearse the 4-scenario demo twice, check all 9 deliverables have a file and owner, tag `v1.0`.

## 7. How We Used AI This Week

- **Walkthrough script for X2:** the AI drove the Flask test client through every scenario and printed what each screen says, which is how the crash and the duplicate lines were found. We checked each finding in the code before fixing it.
- **Tests first for each finding:** every X2 fix has its own test, and the X3 test was written from the exact steps in the issue prompt.
- **Git evidence from history:** the AI built `git_evidence.md` from `git log` / `git shortlog`; we checked the identity mapping ourselves.
- **What we checked ourselves:** that no existing test was changed, that the engine output (Component B contract) was not touched by the X2 fixes, and the final `pytest` run on our own machines.
