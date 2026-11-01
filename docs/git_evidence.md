# Git Evidence (Issue X6)

**Repository:** [`mvs242430/TECH5-teams_3_17`](https://github.com/mvs242430/TECH5-teams_3_17)  
**State described:** `main` at [`aa6b2c5`](https://github.com/mvs242430/TECH5-teams_3_17/commit/aa6b2c5) (30 Oct 2026) — 45 non-merge commits, 17 merge commits.  
**How this file was made:** from `git log` / `git shortlog` on a full clone of `main` and all remote branches. Numbers will change as Week 3 work is merged; re-run the commands in §5 before submission.

---

## 1. Who is who in the history

GitHub shows more names than we have people. This table maps every Git identity to a team member.

| Team member | Role | Git identities used | Non-merge commits on `main` |
| :--- | :--- | :--- | :---: |
| Julia | A1 | `juliamarczewska`, `Julia Marczewska` (same NHH e-mail) | 8 |
| Tanver | A2 | `TanverAhammadHazari` | 4 |
| Daniel | B1 | `Daniel` | 4 |
| Torkil | B2 | `Torkil Tallberg` | 3 |
| Marie | B3 + integration | `mvs242430` (two machines), `majakov` | 24 |
| Course staff | starter package | `Julio C. Goez`, `Julio C. Góez` | 2 |

Marie also did most of the **integration merges** (17 of 17 merge commits are hers): each member's branch was merged into a `temp/test-…` branch, tests were run, then the result was merged to `main`.

## 2. Merged work per person

Links go to the commit on GitHub. GitHub pull requests are linked where the merge went through a PR.

### Julia (A1)
| Issue | Branch | Evidence |
| :--- | :--- | :--- |
| A1.2 projects CRUD | `a1.2-projects` | [`fd1595c`](https://github.com/mvs242430/TECH5-teams_3_17/commit/fd1595c) step 1 create + validation · [`f15e842`](https://github.com/mvs242430/TECH5-teams_3_17/commit/f15e842) step 2 edit/delete |
| A1.3 friendly messages | `a1.3-validation` | [`aaa2d61`](https://github.com/mvs242430/TECH5-teams_3_17/commit/aaa2d61) · [`eed61ec`](https://github.com/mvs242430/TECH5-teams_3_17/commit/eed61ec) solution note |
| A1.4 database docs | `a1.4-database-docs` | [`b568868`](https://github.com/mvs242430/TECH5-teams_3_17/commit/b568868) |
| Review fixes (ID format, 50-seat cap) | `a1-input-fixes` | [PR #48](https://github.com/mvs242430/TECH5-teams_3_17/pull/48) · [`53f973d`](https://github.com/mvs242430/TECH5-teams_3_17/commit/53f973d) |
| A1.5 Week 2 report | `w2-report-review` | [PR #49](https://github.com/mvs242430/TECH5-teams_3_17/pull/49) · [`6476b73`](https://github.com/mvs242430/TECH5-teams_3_17/commit/6476b73) · [`dd74a2b`](https://github.com/mvs242430/TECH5-teams_3_17/commit/dd74a2b) |
| 0.2 PR & issue templates | `0.2-templates` | **not yet on `main`** — branch only |
| 0.4 README test counts | `0.4-readme` | **not yet on `main`** — branch only |

### Tanver (A2)
| Issue | Branch | Evidence |
| :--- | :--- | :--- |
| A2.1 compare page | `feature/task-a2.1-my-compare-two-solutions-new-solution` | [`bffc014`](https://github.com/mvs242430/TECH5-teams_3_17/commit/bffc014) |
| A2.2 recommendations | `feature/task-a2.2-correcting-as-per-recommendation` | [`676236c`](https://github.com/mvs242430/TECH5-teams_3_17/commit/676236c) · [`0166178`](https://github.com/mvs242430/TECH5-teams_3_17/commit/0166178) |
| A2.3 lock & re-run | `feature/task-a2.3-lock-and-rerun-button` | [`a8ad07b`](https://github.com/mvs242430/TECH5-teams_3_17/commit/a8ad07b) |
| A2.5 architecture doc | `feature/task-a2.5-architecture-and-design-documentation` | branch only (not yet on `main`) |

### Daniel (B1)
| Issue | Branch | Evidence |
| :--- | :--- | :--- |
| B1.1–B1.3 metrics | `b1-1-skill-fit-gini` | [`485916f`](https://github.com/mvs242430/TECH5-teams_3_17/commit/485916f) · [`0f413b5`](https://github.com/mvs242430/TECH5-teams_3_17/commit/0f413b5) · [`71b31cb`](https://github.com/mvs242430/TECH5-teams_3_17/commit/71b31cb) |
| W2 report B1 section | same | [`9a115ae`](https://github.com/mvs242430/TECH5-teams_3_17/commit/9a115ae) |

### Torkil (B2)
| Issue | Branch | Evidence |
| :--- | :--- | :--- |
| B2.1 base model (Pyomo) | `Issue-B2.1-final-hopefully` | [`0ec8032`](https://github.com/mvs242430/TECH5-teams_3_17/commit/0ec8032) closes GitHub issue [#21](https://github.com/mvs242430/TECH5-teams_3_17/issues/21) |
| B2.2 three strategies | `Issue-B2.2` | [`12b4040`](https://github.com/mvs242430/TECH5-teams_3_17/commit/12b4040) closes [#22](https://github.com/mvs242430/TECH5-teams_3_17/issues/22) |
| B2.3 no-good cuts | `Issue-B2.3` | [`40c377e`](https://github.com/mvs242430/TECH5-teams_3_17/commit/40c377e) closes [#23](https://github.com/mvs242430/TECH5-teams_3_17/issues/23) |

### Marie (B3 + integration)
| Issue | Evidence |
| :--- | :--- |
| Onboarding, issue files, AGENTS rules | [`da7d6fe`](https://github.com/mvs242430/TECH5-teams_3_17/commit/da7d6fe) · [`0447732`](https://github.com/mvs242430/TECH5-teams_3_17/commit/0447732) · [`c3e16ca`](https://github.com/mvs242430/TECH5-teams_3_17/commit/c3e16ca) |
| A1.1 skills | [`142e262`](https://github.com/mvs242430/TECH5-teams_3_17/commit/142e262) |
| B3.1–B3.4 engine, diagnostics, edge cases | [`fea6b93`](https://github.com/mvs242430/TECH5-teams_3_17/commit/fea6b93) |
| Review sub-issues A1.2.1 / A1.2.2 and fixes | [`c49205f`](https://github.com/mvs242430/TECH5-teams_3_17/commit/c49205f) · [`24f48e9`](https://github.com/mvs242430/TECH5-teams_3_17/commit/24f48e9) |
| A2.1.1 compare across cohorts | [PR #50](https://github.com/mvs242430/TECH5-teams_3_17/pull/50) · [`288af51`](https://github.com/mvs242430/TECH5-teams_3_17/commit/288af51) |
| Integration merges (all `Merge …` commits) | see `git log --merges` |

## 3. Commit history

![Commit history on main](reports/git_history_w3.png)

> *To add:* screenshot of `git log --graph --oneline --all` (or GitHub → Insights → Network) saved as `docs/reports/git_history_w3.png`.

Activity by day on `main`: most work landed 25–27 Oct (52 of 62 commits), right before the Week 2 deadline. Week 3 work should be merged in smaller steps.

## 4. Examples of code review

Review happened in two ways: GitHub PR comments (#48–#50) and Marie's integration review before merging, which produced new sub-issues.

| Example | What was found | What changed |
| :--- | :--- | :--- |
| A1.2 review → sub-issues [`A1.2.1`](team_related/issues/A1.2.1.md), [`A1.2.2`](team_related/issues/A1.2.2.md) | A must-have skill left at level 0 was silently dropped; max capacity 0 crashed with a database error; the form lost skill settings on an empty ID | fixed in [`24f48e9`](https://github.com/mvs242430/TECH5-teams_3_17/commit/24f48e9) before merge |
| [PR #48](https://github.com/mvs242430/TECH5-teams_3_17/pull/48) | IDs with spaces/symbols and absurd seat numbers were accepted | ID format check (1–20 letters, digits, `_`, `-`) and 50-seat cap |
| B1 review | B1.1 edge cases had been added inside original starter tests | moved to separate tests, originals restored ([`a2c33dc`](https://github.com/mvs242430/TECH5-teams_3_17/commit/a2c33dc)) |

> *To add:* 1–2 screenshots of real review comments from PR #48–#50 on GitHub.

## 5. Commands to refresh this page

```bash
git fetch --all
git shortlog -sne origin/main --no-merges        # commits per identity
git log origin/main --merges --format='%h %ad %s' --date=short
git log --graph --oneline --all | head -60       # for the screenshot
```
