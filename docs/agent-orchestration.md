# Agent Orchestration Workflow

This repo keeps agent workflow artifacts in `docs/work-history`.

Artifacts are grouped as:

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

## Roles

- Main: talks with the user, resolves ambiguity, and writes the task markdown.
- Plan: turns the main context into a self-contained implementation plan.
- Do: implements the plan and writes the do report. This is the only role that should edit code.
- See: compares the plan against the implementation and writes a review.
- Convention: runs after see and checks whether the result follows repo conventions.

## Task File

Create a markdown file for each task, for example:

```md
# Task: Simplify Reading Engine Output

## Main Context Summary
The user wants the reading engine to behave as a simple structural translator,
not as a verbose narrative generator.

## Goal
Reduce output complexity while keeping card structure available internally.

## Main Exit Criteria
| id | metric | target | measurement |
| --- | --- | --- | --- |
| EC-1 | Result sections | <= 4 | Count visible section headings in sample output |
| EC-2 | Build status | 0 | `npm run build` exit code |
```

Exit criteria should be numeric or objectively measurable.

## Running

Generate prompts and artifact folders only:

```powershell
python scripts/orchestrate_agents.py --task docs/tasks/example.md --cycles 1
```

Specify task and phase folders:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --task-name reading-engine-simplification `
  --phase phase1_reduce-output-noise `
  --cycles 1
```

Use the local Codex CLI as all agents:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --codex `
  --cycles 3 `
  --check-cmd "npm run build"
```

Optionally pass a model:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --codex `
  --codex-model "gpt-5.5" `
  --cycles 3
```

The Codex preset uses:

- Plan: `codex exec --sandbox read-only`
- Do: `codex exec --sandbox workspace-write`
- See: `codex exec --sandbox read-only`
- Convention: `codex exec --sandbox read-only`

Use the local Gemini CLI as all agents:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --gemini `
  --cycles 3 `
  --check-cmd "npm run build"
```

Optionally pass a model:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --gemini `
  --gemini-model "gemini-2.5-pro" `
  --cycles 3
```

The Gemini preset uses:

- Plan: `gemini --approval-mode plan`
- Do: `gemini --approval-mode auto_edit`
- See: `gemini --approval-mode plan`
- Convention: `gemini --approval-mode plan`

You can also choose a separate headless provider per agent:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --plan-provider gemini `
  --plan-model "gemini-2.5-pro" `
  --do-provider codex `
  --do-model "gpt-5.5" `
  --see-provider codex `
  --convention-provider gemini `
  --cycles 3
```

Provider selection priority:

1. Explicit command, such as `--plan-cmd`.
2. Per-agent provider, such as `--plan-provider gemini`.
3. Global preset, `--codex` or `--gemini`.
4. Placeholder prompt generation when no command/provider is configured.

Per-agent providers can also be set with environment variables:

- `AGENT_PLAN_PROVIDER`
- `AGENT_DO_PROVIDER`
- `AGENT_SEE_PROVIDER`
- `AGENT_CONVENTION_PROVIDER`
- `AGENT_PLAN_MODEL`
- `AGENT_DO_MODEL`
- `AGENT_SEE_MODEL`
- `AGENT_CONVENTION_MODEL`

## JSON Presets

Long provider setups can be stored in JSON and passed with `--preset`:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --preset docs/agent-presets/mixed-codex-gemini.json
```

The Codex-default preset is available at `docs/agent-presets/default-codex.json`.

Presets may also provide `task_name` and `phase`:

```json
{
  "task_name": "orchestration-smoke",
  "phase": "phase1_create-smoke-note"
}
```

To load a preset without running its check commands, add `--no-checks`.

Example preset:

```json
{
  "cycles": 3,
  "min_score": 90,
  "readonly_guard": true,
  "agents": {
    "plan": { "provider": "gemini", "model": "gemini-2.5-pro" },
    "do": { "provider": "codex", "model": "gpt-5.5" },
    "see": { "provider": "codex", "model": "gpt-5.5" },
    "convention": { "provider": "gemini", "model": "gemini-2.5-pro" }
  },
  "check_cmds": [
    "npx tsc --noEmit",
    "npm run build"
  ]
}
```

CLI arguments override preset values for the same field. For example,
`--do-provider gemini` overrides `agents.do.provider` from the preset.

Run with external agent command templates:

```powershell
$env:AGENT_PLAN_CMD = "your-plan-agent --input {prompt_file} --output {output_file}"
$env:AGENT_DO_CMD = "your-do-agent --input {prompt_file} --output {output_file}"
$env:AGENT_SEE_CMD = "your-see-agent --input {prompt_file} --output {output_file}"
$env:AGENT_CONVENTION_CMD = "your-convention-agent --input {prompt_file} --output {output_file}"

python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --cycles 3 `
  --check-cmd "npm run build"
```

For CI-style usage where an unfinished see review should fail the command, add
`--require-pass`.

## AI Main Output

When the caller is a main AI model, prefer JSON stdout:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --preset docs/agent-presets/default-codex.json `
  --cycles 3 `
  --require-pass `
  --output-format json
```

The script always writes a compact machine-readable summary next to `run.json`:

```text
docs/work-history/<task_name>/<phase>/summary.json
```

The summary includes:

- `completed`
- `exit_code`
- `next_action`
- `run_dir`
- `run_json`
- `summary_json`
- `cycles_run`
- `last_cycle.review_files`
- compact `see` and `convention` status objects

Use `next_action` as the main routing signal:

- `done`: report the result to the user.
- `inspect_review_and_rerun`: read the review files and start another cycle or ask for clarification.

To write an extra summary copy for a surrounding agent runtime, pass:

```powershell
python scripts/orchestrate_agents.py `
  --task docs/tasks/example.md `
  --summary-file docs/latest-orchestration-summary.json `
  --output-format json
```

Available command placeholders:

- `{prompt_file}`
- `{output_file}`
- `{run_dir}`
- `{cycle_dir}`
- `{workspace}`
- `{cycle}`
- `{agent}`

If a command does not mention `{prompt_file}`, the prompt is piped through stdin.
If a command does not mention `{output_file}`, stdout is written to the output file.

## Completion

The loop stops early when the see report ends with JSON metadata like:

```json
{
  "agent": "see",
  "status": "pass",
  "score": 90,
  "remaining_issue_count": 0
}
```

The default minimum score is `90`; change it with `--min-score`.
