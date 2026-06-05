# Agent Instructions

## 1. Think Before Coding

- State assumptions before changing behavior.
- Ask when requirements are ambiguous, especially for instrument behavior or user-facing workflows.
- Surface tradeoffs instead of silently choosing when multiple valid interpretations exist.
- Push back on risky or overbroad changes.

## 2. Keep Changes Simple

- Implement the minimum code needed for the requested behavior.
- Do not add speculative features, generic frameworks, or one-use abstractions.
- Do not add configurability unless the request or project handoff requires it.
- If a change becomes large, reassess whether a smaller fix satisfies the goal.

## 3. Make Surgical Edits

- Touch only files required by the task.
- Match the existing style and structure.
- Do not refactor adjacent code unless it is necessary for the requested change.
- Remove only unused imports, variables, or helpers created by your own changes.
- Mention unrelated dead code or cleanup opportunities; do not delete them unless asked.

## 4. Define Success Criteria

- Convert each task into verifiable checks before implementation.
- For bug fixes, prefer a test or focused reproduction that fails before the fix and passes after it.
- For refactors, verify behavior before and after where practical.
- For multi-step work, keep the plan short and tie every step to a concrete check.
