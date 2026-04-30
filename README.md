# Agent Orchestrator

A Python orchestration script for AI-led development loops.

The intended caller is usually a main AI session. The script gives that main
model a stable way to delegate work into separated roles:

- `plan`: converts the main context into a measurable implementation plan.
- `do`: implements the plan. This is the only role expected to edit code.
- `see`: reviews the result against the plan and exit criteria.
- `convention`: checks style, placement, and artifact boundaries.

Failed reviews feed the next cycle, so the main model can inspect structured
results and decide whether to continue, summarize, or ask the user a sharper
question.

## Runtime Contract

Input:

- A task markdown file, usually written by the main AI.
- Optional JSON preset for providers, models, checks, task name, and phase.
- Optional deterministic check commands.

Output:

- `docs/work-history/<task_name>/<phase>/run.json`: full run manifest.
- `docs/work-history/<task_name>/<phase>/summary.json`: compact machine-readable summary.
- Optional JSON stdout with `--output-format json`.
- Per-cycle prompt and response files for every role.

Exit behavior:

- Exit code `0` when the run is complete, or when `--require-pass` is not set.
- Exit code `1` when `--require-pass` is set and the run does not meet the review threshold.

## Requirements

- Python 3.10 or newer.
- No required third-party Python packages.
- Optional: Codex CLI for the default preset.
- Optional: Gemini CLI for mixed/provider experiments.

Python 3.9 and older are not supported because the script uses modern typing
syntax such as `str | None`.

## Main AI Invocation

Recommended invocation shape:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --preset docs\agent-presets\default-codex.json `
  --cycles 3 `
  --require-pass `
  --output-format json
```

The same contract on Linux:

```bash
python3 scripts/orchestrate_agents.py \
  --task docs/tasks/my-task.md \
  --preset docs/agent-presets/default-codex.json \
  --cycles 3 \
  --require-pass \
  --output-format json
```

The JSON stdout is intentionally compact:

```json
{
  "schema_version": 1,
  "completed": true,
  "exit_code": 0,
  "next_action": "done",
  "run_dir": "docs/work-history/example/phase1",
  "run_json": "docs/work-history/example/phase1/run.json",
  "summary_json": "docs/work-history/example/phase1/summary.json",
  "cycles_run": 1,
  "last_cycle": {
    "review_files": [
      "docs/work-history/example/phase1/cycle-01/see.md",
      "docs/work-history/example/phase1/cycle-01/convention.md"
    ],
    "see": {
      "status": "pass",
      "score": 100,
      "remaining_issue_count": 0
    },
    "convention": {
      "status": "pass",
      "score": 100,
      "remaining_issue_count": 0
    }
  }
}
```

Use `next_action` as the main branch point:

- `done`: summarize the result to the user.
- `inspect_review_and_rerun`: read `last_cycle.review_files`, update the task or preset if needed, and run another cycle.

To write a second copy of the compact summary for the main AI, use:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --summary-file docs\latest-orchestration-summary.json `
  --output-format json
```

## Task Markdown

The main AI should write the task file before invoking the orchestrator.

Use this shape:

```md
# Task: Short Work Name

## Main Context Summary

Summarize what the user wants, rejected directions, constraints, and relevant
repo facts.

## Goal

State the target outcome in one or two sentences.

## Scope

Allowed:

- Files, modules, or behavior the do agent may change.

Not allowed:

- Boundaries the do agent must not cross.

## Main Exit Criteria

| id | metric | target | measurement |
| --- | --- | --- | --- |
| EC-1 | Build exit code | 0 | Run `npm run build` |
```

Exit criteria should be numeric or objectively measurable.

## Artifact Layout

Runs are grouped by task and phase:

```text
docs/work-history/
  task_name/
    phase1_work-summary/
      task.md
      run.json
      summary.json
      cycle-01/
        plan.prompt.md
        plan.md
        do.prompt.md
        do.md
        see.prompt.md
        see.md
        convention.prompt.md
        convention.md
```

## Presets

- `docs/agent-presets/default-codex.json`: Codex for every agent, currently using `gpt-5.5`.
- `docs/agent-presets/mixed-codex-gemini.json`: example mixed-provider preset.

Provider and model settings can be overridden per run:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --plan-provider gemini `
  --plan-model "gemini-2.5-pro" `
  --do-provider codex `
  --do-model "gpt-5.5" `
  --output-format json
```

## Checks

Use `--check-cmd` for deterministic validation:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --check-cmd "npm run build" `
  --check-cmd "npm test" `
  --output-format json
```

Check results are passed into `see`, so the review agent can use parent-run
evidence instead of rerunning commands unnecessarily.

## Platform Notes

The script is cross-platform. The main differences are interpreter name and path
style:

- Windows: usually `python`, `py -3.10`, and backslash paths.
- Linux: usually `python3`, `python3.10`, and slash paths.

Prefer check commands that do not leave generated artifacts in the repository.
For Python compile checks, write the `.pyc` to a temp path and remove it.

## Documentation

See `docs/agent-orchestration.md` for the longer workflow reference.
