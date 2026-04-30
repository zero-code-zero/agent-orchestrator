# Task: Orchestration Smoke Note

## Main Context Summary

We are testing the plan/do/see/convention orchestration script with separate
headless agent processes. The goal must stay intentionally tiny so we can verify
the workflow without risking unrelated app changes.

The default preset for this smoke run should use Codex for agents.

## Goal

Create a small documentation note proving that the do agent can make a bounded
repo change through the orchestrator.

## Scope

Allowed:

- Create or update `docs/orchestration-smoke.md`.

Not allowed:

- Edit application source code.
- Edit package files.
- Change the reading engine.

## Main Exit Criteria

| id | metric | target | measurement |
| --- | --- | --- | --- |
| EC-1 | Smoke note file exists | 1 | Check that `docs/orchestration-smoke.md` exists |
| EC-2 | Required phrase count | >= 1 | Count occurrences of `orchestration smoke passed` in `docs/orchestration-smoke.md` |
| EC-3 | Python compile exit code | 0 | Run `python -c "import pathlib, py_compile, tempfile; cfile=pathlib.Path(tempfile.gettempdir()) / 'orchestrate_agents.orchestration-smoke.pyc'; py_compile.compile('scripts/orchestrate_agents.py', cfile=str(cfile), doraise=True); cfile.unlink(missing_ok=True)"` |

## Notes For Plan Agent

Keep the plan short and concrete. The do agent should only touch
`docs/orchestration-smoke.md`.

For EC-3, use the temp `.pyc` command above instead of plain
`python -m py_compile`, because plain `py_compile` can create
`scripts/__pycache__` inside the repository.
