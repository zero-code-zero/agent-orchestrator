---
name: agent-orchestrator
description: Use when Codex needs to run or prepare an AI-led development loop with separated plan, do, see, and convention agents; when a user wants headless Codex/Gemini orchestration, repeatable implementation-review cycles, task history, or a main AI that must summarize conversation context into a task markdown before delegating work.
---

# Agent Orchestrator

Use this skill to turn a user goal or conversation context into a bounded
`plan -> do -> see -> convention` development loop.

## Hard Rule

Do not invoke `scripts/orchestrate_agents.py` until a task markdown file exists.
The task file is the contract between the main AI and the delegated agents.

The task file must be self-contained. Do not rely on phrases like "as above",
"the previous discussion", or "the current request" without restating the
important details.

## Task Summary Contract

Before running the orchestrator, write or update a task file under `docs/tasks/`.
Include:

- What the user wants.
- What the user rejected or disliked.
- Current repo facts that matter.
- Files or areas likely in scope.
- Files or areas explicitly out of scope.
- Constraints, risks, and assumptions.
- Numeric or objectively measurable exit criteria.
- Suggested validation commands.

Minimum shape:

```md
# Task: Short Work Name

## Main Context Summary

Self-contained summary of the user's goal, constraints, rejected directions,
and relevant repo state.

## Goal

One or two sentences describing the target outcome.

## Scope

Allowed:

- Paths, modules, or behavior the do agent may change.

Not allowed:

- Boundaries the do agent must not cross.

## Main Exit Criteria

| id | metric | target | measurement |
| --- | --- | --- | --- |
| EC-1 | Example measurable result | 0 | Example command or inspection |
```

If the task cannot be summarized without guessing high-impact intent, ask the
user a short clarification question before running the orchestrator.

## Run Pattern

Prefer JSON output for AI callers:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --preset docs\agent-presets\default-codex.json `
  --cycles 3 `
  --require-pass `
  --output-format json
```

On Linux, use `python3` and slash paths:

```bash
python3 scripts/orchestrate_agents.py \
  --task docs/tasks/my-task.md \
  --preset docs/agent-presets/default-codex.json \
  --cycles 3 \
  --require-pass \
  --output-format json
```

## Interpret Results

Read JSON stdout or `summary.json`.

- If `next_action` is `done`, report the result to the user.
- If `next_action` is `inspect_review_and_rerun`, read
  `last_cycle.review_files`, update the task/preset only if needed, then rerun
  or ask the user for clarification.

Use `run.json` only when the compact summary is insufficient.

## File Discipline

- Do not commit `docs/work-history/**` unless the user explicitly asks for run
  history to be versioned.
- Do not commit `.tmp/`, `__pycache__/`, or `*.pyc`.
- Preserve the `task_name/phase/cycle` artifact layout.
- Only the `do` role should edit target project code.
- Treat `plan`, `see`, and `convention` as read-only roles.

## Validation

Before committing script changes, run a compile check that does not leave
`__pycache__` in the repo:

```powershell
python -c "import pathlib, py_compile, tempfile; cfile=pathlib.Path(tempfile.gettempdir()) / 'orchestrate_agents.check.pyc'; py_compile.compile('scripts/orchestrate_agents.py', cfile=str(cfile), doraise=True); cfile.unlink(missing_ok=True)"
```

When changing presets, validate JSON:

```powershell
python -m json.tool docs\agent-presets\default-codex.json
```
