# TECH5 Project: Onboarding for Non-Developers

*Read this first. Written for business students working with an AI coding agent. Your tasks are in [`issues/`](issues/README.md).*

## 1.1 What are we building?

Imagine a coordinator has 60 students and 12 projects. Every student ranked their favourite projects and has some skills (Python, SQL…). Every project has a minimum and maximum number of seats and may need certain skills.

**Our app helps the coordinator decide who goes where.** It must:
1. Never break the rules (seat limits, required skills, projects already fixed by the administration).
2. Show **a few different good solutions** (not just one "magic answer").
3. Show the **trade-offs**: "Solution 2 gives better skill match but 3 students get a worse choice."
4. **Recommend** one and explain why.
5. **Say honestly when no solution exists** and why.

The grade question is: *"Would a real decision-maker understand and trust what our app tells them?"* — not only "does the code run?".

## 1.2 The app has two halves

| Half | Team | Think of it as | Folder |
|---|---|---|---|
| **Face** | Team A (2 people) | The web pages: forms, buttons, comparison screen | `app/visualization/` |
| **Brain** | Team B (3 people) | The maths that picks assignments and calculates scores | `app/engine/` |

They talk through one agreed list of functions (the "contract"). Until the Brain is ready, a **fake brain (mock)** lets Team A work. Do not change `app/contract/`, `app/domain/`, `app/persistence/` unless an issue says so.

## 1.3 Words you will hear

| Word | Simple meaning |
|---|---|
| Repository ("repo") | The project folder that Git tracks |
| Branch | Your own private copy to work in, so you don't break the team's version |
| Commit | A saved step with a short message |
| Pull Request (PR) | "Please check my work and add it to the main version" |
| Issue | One task card on GitHub |
| Test | A tiny program that checks our program works |
| xfail | A test that is *expected to fail* until the feature exists. Our job: build the feature, then delete the `@pytest.mark.xfail(...)` lines above that test |
| Route | A web address the app answers, e.g. `/skills/new` |
| Template | An HTML file that defines how a page looks |
| ILP | The maths method that finds the best assignment while obeying rules |
| Mock | A fake version used until the real one exists |

## 1.4 Set up your computer (once, ~30 min) — Issue 0.1

1. Install **Git**, **Python 3.10 or newer**, **VS Code** (or Cursor), and your AI assistant.
2. Get the project: `git clone <repo-url>` then open the folder in VS Code.
3. Open the terminal in VS Code and run:

   Mac / Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m pytest -q
   ```
   Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   python -m pytest -q
   ```
4. You must see: **`36 passed, 15 xfailed`**. That is correct. The goal at the end is `51 passed`.
5. Start the app: `python run.py`, open http://127.0.0.1:5000, click **Scenarios → Load → Launch run**. A yellow note "using mock engine" is normal now.
6. Post a screenshot of steps 4 and 5 in issue 0.1.

## 1.5 How every task works (the 9 steps)

1. Open your issue on GitHub. Read **What and why**.
2. Update your copy: `git switch main` then `git pull`.
3. Make your branch: `git switch -c a1-skills` (your code + short topic).
4. Open your AI agent in the project folder. Paste the **prompt** from the issue.
5. Let the AI make changes. Run `python -m pytest -q` and look at the result.
6. If it is a web page, run `python run.py` and click through it yourself.
7. Save: `git add -A` then `git commit -m "A1.1 add skills create and delete"`.
8. Upload: `git push -u origin a1-skills`, then open a Pull Request on GitHub. Write "Closes #<issue number>" and a screenshot.
9. A teammate reviews. If tests are green and they agree, click Merge.

**Never** work directly on `main`. **Never** use `git push --force`. If Git shows "conflict", stop, copy the message, and ask your AI agent and a teammate before doing anything.

## 1.6 Rules for working with the AI agent

1. **Give it the issue.** Paste the whole issue text, then the prompt.
2. **Tell it what it may touch.** Every prompt lists allowed files. The AI must not edit others.
3. **Small steps.** One function at a time. Run the tests after each.
4. **Don't let it cheat.** It must not delete tests, hard-code the expected answer, or hide errors. The only allowed test change: remove the `xfail` lines of the target test (and add new tests).
5. **Ask it to explain**: "Explain what you changed in 5 sentences for a business student." Paste that into your PR.
6. **Check with your own eyes.** For web pages, open the page. As Admin and as "Student Viewer" (role dropdown at top).
7. **Keep a log** in `docs/team_related/ai_usage_log.md`: date, issue, what the AI did, what it got wrong, how you fixed it. This is evidence for the final reflection.
8. If the AI is stuck after 3 tries, ask a teammate. Don't keep looping.

## 1.7 Where is what?

| I want to change… | Open |
|---|---|
| How a page looks | `app/visualization/templates/<page>.html` |
| What happens when a button is clicked | `app/visualization/routes.py` (search for the function name) |
| Who may do what | `app/visualization/auth.py` |
| Scores and fairness maths | `app/engine/metrics.py` |
| The assignment optimiser | `app/engine/strategies.py` (created in issue 0.5) |
| The "boss" that runs everything | `app/engine/solvers.py` |
| Rules about bad data | `app/domain/validation.py` |
| Test data | `app/samples/demo_data.py` |
| Checks | `tests/` |

## 1.8 Team habits
- Short stand-up Mon + Thu. One joint **Integration Day** each Wednesday (Team A tries Team B's latest).
- Review a teammate's PR within 24 h.
- One issue = one branch = one PR. Pull `main` before you start every session.
- Board columns: Backlog → Ready → In progress → In review → Done.
- **Done** means: all "Done when" boxes ticked + tests green + PR reviewed.
