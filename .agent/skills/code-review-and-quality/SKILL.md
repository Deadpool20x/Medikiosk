---
name: code-review-and-quality
description: Use this skill whenever the user asks to review code, check for bugs, check for lint or type errors, audit a file or PR for quality, or before finalizing any feature. Covers lint/type diagnostics, logic review, security basics, and dependent-file impact check.
---

# Code Review and Quality

When this skill is loaded, perform a full review pass on the changed/specified code:

1. Lint and type errors — run the project's lint/typecheck command for the relevant workspace, list every error and warning, fix all of them.
2. Logic and edge cases — read the code logic, not just syntax. Look for unhandled null/undefined, off-by-one errors, missing await, unhandled promise rejection, missing error boundary.
3. Security basics — check for hardcoded secrets, missing input validation on user-facing API routes, missing auth checks on protected routes.
4. Dependent files — find every caller/importer of any changed function, type, or API route; confirm they still work with the change.
5. Report format — list issues found grouped by file, each tagged severity (blocker / should-fix / nit). Do not silently fix and hide what was wrong — show what was found and what was changed.

Do not stop at "no lint errors" — lint passing does not mean the code is correct. Always also do the logic review in step 2.
