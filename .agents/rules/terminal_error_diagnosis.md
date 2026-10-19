# Terminal Error Verification & Direct Output Rule

## Core Directive
When a user or teammate pastes a terminal error message, stack trace, or failure snippet into the Antigravity IDE chat:

**You must NOT guess or attempt to resolve the issue based solely on the pasted text.**  
**You must directly reproduce and inspect the actual terminal output using your command execution tool before diagnosing or modifying code.**

---

## Required Workflow for Handling Pasted Errors

1. **Direct Terminal Verification (Mandatory First Action):**
   - Proactively execute the relevant command in the terminal (e.g., `pytest <failing_test>`, `python -m pytest -q`, `python run.py`, `pip check`, or the specific script).
   - Capture the full, untruncated `stdout`, `stderr`, and exit code directly from the system environment.

2. **Root-Cause Traceback Inspection:**
   - Examine the exact file path and line numbers indicated in the live traceback.
   - Use `view_file` to inspect the source code surrounding the failure site before making assumptions.

3. **Explain Before Modifying:**
   - Adhere to the *Explain-Before-Accept* policy: explain *why* the error occurred and what architectural or logical flaw caused it before proposing an edit.

4. **Verify the Fix in the Terminal:**
   - After applying any fix, immediately re-run the terminal command to confirm that the error is genuinely resolved and that no regressions were introduced.
   - Only declare the task fixed once the command exits cleanly (`exit code 0` or expected test pass).
