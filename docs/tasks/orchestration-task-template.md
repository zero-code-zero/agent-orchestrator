# Task: Replace With Short Goal

## Main Context Summary

Write the main agent's conversation summary here. Include:

- What the user wants.
- What direction is explicitly rejected.
- Known constraints.
- Current repo facts that matter.

## Goal

State the target outcome in one or two sentences.

## Phase

Recommended artifact path:

```text
docs/work-history/<task_name>/<phase_number>_<short-work-summary>/
```

Example:

```text
docs/work-history/reading-engine-simplification/phase1_reduce-output-noise/
```

## Scope

Allowed:

- List files, modules, or behavior the do agent may change.

Not allowed:

- List boundaries the do agent must not cross.

## Main Exit Criteria

Every exit criterion must be measurable.

| id | metric | target | measurement |
| --- | --- | --- | --- |
| EC-1 | Build exit code | 0 | Run `npm run build` |
| EC-2 | TypeScript exit code | 0 | Run `npx tsc --noEmit` |

## Notes For Plan Agent

Add anything the plan agent must preserve or pay special attention to.
