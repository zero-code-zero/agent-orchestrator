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

The top-level role boundary is intentionally CLI-based: `plan`, `do`, `see`, and
`convention` run as separate processes with their own prompts and artifacts.
Those agents may still use subagents internally, but each role remains
responsible for its own output instead of passing uncertainty to another shared
session.

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

During a run, `run.json` and `summary.json` are updated after each completed
stage. If an agent command times out or the parent process is interrupted, the
latest files should still show the last completed stage and the next action for
inspection.

Exit behavior:

- Exit code `0` when the run is complete, or when `--require-pass` is not set.
- Exit code `1` when `--require-pass` is set and the run does not meet the review threshold.

For AI agents, `SKILL.md` is the shortest operational entry point. It makes the
task markdown context summary mandatory before delegation.

## Skill Installation

This repository is also a Codex skill folder because it contains `SKILL.md` at
the root.

Install on Windows:

```powershell
$skillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills" } else { Join-Path $HOME ".codex\skills" }
New-Item -ItemType Directory -Force $skillsRoot | Out-Null
git clone git@github.com:zero-code-zero/agent-orchestrator.git (Join-Path $skillsRoot "agent-orchestrator")
```

Install on Linux:

```bash
SKILLS_ROOT="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_ROOT"
git clone git@github.com:zero-code-zero/agent-orchestrator.git "$SKILLS_ROOT/agent-orchestrator"
```

Update an installed skill:

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills\agent-orchestrator" } else { Join-Path $HOME ".codex\skills\agent-orchestrator" }
git -C $skillRoot pull
```

On Linux:

```bash
git -C "${CODEX_HOME:-$HOME/.codex}/skills/agent-orchestrator" pull
```

Start a new Codex session after installation or update so the skill metadata is
loaded.

## Skill Usage

Ask Codex to use the `agent-orchestrator` skill when a task should be delegated
through a structured development loop.

Example request:

```text
Use the agent-orchestrator skill. Summarize this conversation into a task file,
then run a plan/do/see/convention loop with JSON output.
```

The skill should:

1. Summarize the conversation into a self-contained `docs/tasks/*.md` file in
   the target workspace.
2. Run the bundled script with `--workspace` pointing at that target workspace.
3. Use `--output-format json`.
4. Read `summary.json`.
5. If `next_action` is `done`, report the result.
6. If `next_action` is `inspect_review_and_rerun`, read the review files and
   decide whether to rerun or ask for clarification.

Installed skill invocation shape:

```powershell
$skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills\agent-orchestrator" } else { Join-Path $HOME ".codex\skills\agent-orchestrator" }
python "$skillRoot\scripts\orchestrate_agents.py" `
  --workspace . `
  --task docs\tasks\my-task.md `
  --preset "$skillRoot\docs\agent-presets\default-codex.json" `
  --cycles 3 `
  --require-pass `
  --output-format json
```

On Linux:

```bash
SKILL_ROOT="${CODEX_HOME:-$HOME/.codex}/skills/agent-orchestrator"
python3 "$SKILL_ROOT/scripts/orchestrate_agents.py" \
  --workspace . \
  --task docs/tasks/my-task.md \
  --preset "$SKILL_ROOT/docs/agent-presets/default-codex.json" \
  --cycles 3 \
  --require-pass \
  --output-format json
```

## Requirements

- Python 3.10 or newer.
- No required third-party Python packages.
- Optional: Codex CLI for the default preset.
- Optional: Gemini CLI for mixed/provider experiments.

Python 3.9 and older are not supported because the script uses modern typing
syntax such as `str | None`.

## Model Baseline

The skill and default preset are designed around GPT-5.5-class behavior. The
default Codex preset uses `gpt-5.5` for `plan`, `do`, `see`, and `convention`.

Older or weaker models can still be used, but task files should be more explicit
about assumptions, rejected directions, scope boundaries, exit criteria, and
validation commands.

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
    "stages": [
      {
        "stage": "see",
        "kind": "agent",
        "status": "ok",
        "return_code": 0,
        "duration_ms": 12345,
        "artifact": "docs/work-history/example/phase1/cycle-01/see.md",
        "log": null,
        "error_summary": null
      }
    ],
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

`last_cycle.stages` is the normalized result stream for both agents and checks.
Common stage statuses are `ok`, `failed`, `timeout`, `skipped`, and
`missing_output`.

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

To avoid shell quoting issues, prefer `--check-file` with argv-style commands:

```json
{
  "checks": [
    {
      "name": "build",
      "cmd": ["npm", "run", "build"],
      "timeout_seconds": 300
    },
    {
      "name": "unit-tests",
      "cmd": ["npm", "test"]
    }
  ]
}
```

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --check-file docs\tasks\my-task.checks.json `
  --output-format json
```

Long-running agents and checks can be bounded:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --agent-timeout 900 `
  --check-timeout 300 `
  --output-format json
```

Per-agent overrides are also available: `--plan-timeout`, `--do-timeout`,
`--see-timeout`, and `--convention-timeout`. The same values can be placed in
presets with `agent_timeout_seconds`, `check_timeout_seconds`, or per-agent
`timeout_seconds`.

## Platform Notes

The script is cross-platform. The main differences are interpreter name and path
style:

- Windows: usually `python`, `py -3.10`, and backslash paths.
- Linux: usually `python3`, `python3.10`, and slash paths.

Prefer check commands that do not leave generated artifacts in the repository.
For Python compile checks, write the `.pyc` to a temp path and remove it.

## Documentation

See `docs/agent-orchestration.md` for the longer workflow reference.
