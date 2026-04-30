# Agent Orchestrator

A small Python orchestration script for running separated AI development roles:
`plan`, `do`, `see`, and `convention`.

The main idea is simple:

- The main session writes a task markdown file.
- `plan` turns that context into a measurable implementation plan.
- `do` implements the plan.
- `see` reviews the result against the plan and exit criteria.
- `convention` checks repository style and artifact boundaries.
- Failed reviews feed the next cycle.

Only the `do` phase is expected to edit project code.

## Requirements

- Python 3.10 or newer
- Optional: Codex CLI for the default preset
- Optional: Gemini CLI for mixed/provider experiments

The script uses modern Python typing syntax such as `str | None`, so Python
3.9 and older are not supported. There are no required third-party Python
packages.

Check your Python version:

```powershell
python --version
```

On Linux:

```bash
python3 --version
```

## Quick Start

Clone the repository:

```powershell
git clone git@github.com:zero-code-zero/agent-orchestrator.git
cd agent-orchestrator
```

Create a task file:

```powershell
Copy-Item docs\tasks\orchestration-task-template.md docs\tasks\my-task.md
```

Run one dry orchestration cycle that creates prompts and history artifacts:

```powershell
python scripts\orchestrate_agents.py --task docs\tasks\my-task.md --cycles 1
```

Run with the Codex preset:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\orchestration-smoke-add-note.md `
  --preset docs\agent-presets\default-codex.json `
  --cycles 3 `
  --require-pass
```

## Windows Usage

PowerShell examples use backticks for line continuation:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --preset docs\agent-presets\default-codex.json `
  --cycles 3 `
  --require-pass
```

If `python` points to the wrong version, use the Python launcher:

```powershell
py -3.10 scripts\orchestrate_agents.py --task docs\tasks\my-task.md --cycles 1
```

Compile-check the script without leaving `__pycache__` in the repo:

```powershell
python -c "import pathlib, py_compile, tempfile; cfile=pathlib.Path(tempfile.gettempdir()) / 'orchestrate_agents.check.pyc'; py_compile.compile('scripts/orchestrate_agents.py', cfile=str(cfile), doraise=True); cfile.unlink(missing_ok=True)"
```

## Linux Usage

Shell examples use backslashes for line continuation:

```bash
python3 scripts/orchestrate_agents.py \
  --task docs/tasks/my-task.md \
  --preset docs/agent-presets/default-codex.json \
  --cycles 3 \
  --require-pass
```

You can also run the script directly:

```bash
chmod +x scripts/orchestrate_agents.py
./scripts/orchestrate_agents.py --task docs/tasks/my-task.md --cycles 1
```

If `python3` is older than 3.10, call a specific interpreter such as
`python3.10` or `python3.11`.

Compile-check the script without leaving `__pycache__` in the repo:

```bash
python3 -c "import pathlib, py_compile, tempfile; cfile=pathlib.Path(tempfile.gettempdir()) / 'orchestrate_agents.check.pyc'; py_compile.compile('scripts/orchestrate_agents.py', cfile=str(cfile), doraise=True); cfile.unlink(missing_ok=True)"
```

## Artifact Layout

Runs are written under `docs/work-history`:

```text
docs/work-history/
  task_name/
    phase1_work-summary/
      task.md
      run.json
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

Provider and model settings can also be overridden with CLI flags such as:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --codex `
  --codex-model "gpt-5.5"
```

## Checks

Use `--check-cmd` for deterministic validation commands:

```powershell
python scripts\orchestrate_agents.py `
  --task docs\tasks\my-task.md `
  --check-cmd "npm run build" `
  --check-cmd "npm test"
```

Check results are passed into `see`, so the review agent can use parent-run
evidence instead of rerunning commands unnecessarily.

## Documentation

See `docs/agent-orchestration.md` for the full workflow notes and command
reference.
