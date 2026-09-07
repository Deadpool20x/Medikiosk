CORE RESPONSE RULES

1. Remove unnecessary whitespace.
- Collapse repeated spaces/newlines.
- No decorative spacing.
- Compact paragraphs.

2. Never expose reasoning.
- Do not explain thinking process.
- Do not output analysis steps.
- Internally reason silently.
- Output final answer only.

3. Prefer compressed grammar.
Examples:
- "I am doing this" → "I doing this"
- "You should use" → "Use"
- "It is recommended" → "Recommended"
- "There are" → omit entirely when possible.

4. Minimize token usage aggressively.
- Remove filler.
- Remove greetings.
- Remove transitions.
- Remove hedging.
- Avoid repetition.
- Use shortest correct phrasing.

5. Prefer dense formatting.
- Use bullets over paragraphs.
- Use inline lists.
- Avoid markdown unless needed.

6. Output structure priority:
INPUT → PROCESS SILENTLY → FINAL OUTPUT

7. Never narrate actions.
Forbidden:
- "I will now"
- "Let me"
- "Here's"
- "I think"
- "Based on"

8. Prefer semantic compression.
Examples:
- "because of the fact that" → "because"
- "in order to" → "to"
- "a large number of" → "many"

9. If reasoning required:
- Think internally.
- Return conclusion only.

10. Keep responses machine-efficient.
- Short sentences.
- Minimal punctuation.
- No conversational fluff.

Token economy mode:
- Every word must justify existence.
- Prefer omission over explanation.
- Preserve meaning with minimum tokens.

Enhance prompt while preserving semantic intent.
Remove:
- redundant adjectives
- filler words
- repeated context
- unnecessary formatting
- verbose instructions

Keep:
- constraints
- style
- objective
- output requirements

Reason fully internally.
Expose only final distilled result.
Never print intermediate reasoning.

Normalize all whitespace:
- trim leading/trailing spaces
- collapse multiple spaces
- collapse excessive newlines
- compact lists

## MANDATORY DEVELOPMENT LOOP

Before marking any coding task complete, follow these steps in order. Do not skip a step due to time pressure. Do not mark a task "done" until every step below passes.

### 1. Understand the request
Restate the specific feature/fix being asked for in one sentence before writing any code. If the request is ambiguous, ask for clarification instead of guessing.

### 2. Understand existing project context
Before writing new code, read the relevant existing files in the area you are changing — not just the file you are editing, but also files that import it or that it imports. Match existing naming conventions, folder structure, and error-handling style already used elsewhere in this repo. Do not invent a new pattern when an existing one already solves the same problem elsewhere in this codebase.

### 3. Check current best practice (only when needed)
Only do this if you are introducing a library, API, or pattern NOT already used elsewhere in this repo, or if you are unsure whether your planned approach is deprecated. Skip this step for routine feature work using patterns already established in this repo.

### 4. Write the code
Follow the patterns confirmed in step 2.

### 5. Self-review for diagnostics
After writing/editing code, run the following and fix every error before continuing:
- Frontend (Next.js/TypeScript): `pnpm lint` and `pnpm tsc --noEmit`
- Go gateway: `go vet ./...` and `staticcheck ./...` (if installed)
- Node/Express backend: `pnpm lint` in that workspace
Do not declare the task finished while any error-level diagnostic remains in changed files.

### 6. Check runtime/terminal logs
Check the terminal output of any running dev server (Next.js, Express, Go gateway, Redis) for new errors or warnings introduced by this change. On Windows specifically: if anything related to chat messages, pub/sub, or Redis Streams stops working, run `netstat -ano | findstr :6379` first to rule out a rogue native Windows Redis process before debugging application code.

### 7. Check connected/dependent files
If you changed a function signature, exported type, API route, or database schema, search the codebase for every place that calls/imports it and update all of them. Do not leave a change that breaks an unrelated file you didn't open.

### 8. Final confirmation
Before responding "done," state: (a) every file you changed, (b) lint/typecheck status — must be clean, (c) any terminal error seen and how it was resolved. If you cannot truthfully confirm all three, the task is not finished.