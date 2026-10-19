# Git Branching & Isolated QA Subagent Workflow Rule

## Core Principle
Every issue in `docs/team_related/issues/` must follow strict **One Issue = One Branch = One PR** isolation and must pass an **independent, zero-shared-context QA subagent audit** before any code is committed or pushed to the remote repository.

---

## 1. Pre-Implementation Gate: Always Start on a New Issue Branch

Before generating or editing any code for an issue in `docs/team_related/issues/`:

1. **Inspect Current Branch:** Run `git branch --show-current` and `git status --short`.
2. **Never Work on `main`:**
   - If the current branch is `main` (or another unrelated issue branch), you **must** create and switch to a dedicated feature branch before touching any code:
     ```bash
     git switch main
     git pull
     git switch -c <issue-code>-<short-topic>
     ```
   - Branch naming convention (matching `docs/team_related/onboarding_for_students.md`): lowercase issue code + short topic slug, e.g., `a1.1-skills`, `b1.1-skill-fit-gini`, `0.5-split-optimiser`.
3. **File Scope Lock:** Read the target issue file in `docs/team_related/issues/<ID>.md` and note the **Files** section. Never edit files outside the issue's allowed file list unless explicitly approved by the user.

---

## 2. Pre-Commit / Pre-Push Gate: Isolated `qa-tester` Subagent Verification

Whenever an issue implementation is finished—and **strictly before** running `git commit` or `git push`:

1. **Activate the `qa-tester` Skill:** Read `.agents/skills/qa-tester/SKILL.md`.
2. **Spawn the Isolated Subagent:**
   - Define and invoke the `qa-tester` subagent using `define_subagent` and `invoke_subagent`.
   - **Zero Shared Context:** Pass **only** the path to the issue file (e.g., `docs/team_related/issues/A1.1.md`). Never pass your implementation reasoning or conversation summary to the QA subagent.
3. **Block Commit/Push Until `PASS`:**
   - If `qa-tester` returns `FAIL`, resolve all findings first and re-run `qa-tester`.
   - Only when `qa-tester` returns `PASS` (confirming feature branch isolation, allowed file scope, intact tests, and passing `python -m pytest -q`) and the student confirms understanding under the **Explain-Before-Accept** policy may you proceed with `git add`, `git commit`, and `git push -u origin <branch-name>`.
4. **Never Force Push:** Never run `git push --force` or push directly to `main`.
