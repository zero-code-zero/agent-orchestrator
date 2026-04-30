# AGENTS.md

## Purpose

This repository provides a Python orchestration script for AI-led development
loops. Treat the script as infrastructure for a main AI session that delegates
work to `plan`, `do`, `see`, and `convention` agents.

## Reference Order

When working in this repo, read references in this order:

1. `README.md`: public contract and main AI invocation pattern.
2. `docs/agent-orchestration.md`: detailed workflow and CLI reference.
3. `docs/tasks/*.md`: task input templates and examples.
4. `docs/agent-presets/*.json`: provider/model/check presets.

## Agent Rules

- Prefer `--output-format json` when the script is called by another AI.
- Treat `summary.json` as the compact routing artifact for the main AI.
- Treat `run.json` as the full audit artifact.
- Keep task exit criteria numeric or objectively measurable.
- Only the `do` role should edit target project code.
- `plan`, `see`, and `convention` should be read-only roles.
- Do not commit `docs/work-history/**` unless explicitly requested.
- Do not commit temporary folders such as `.tmp/`, `__pycache__/`, or `*.pyc`.
- Preserve the `task_name/phase/cycle` artifact layout.
- Keep generated check commands from leaving artifacts inside the repo whenever possible.

## Validation

Before committing script changes, run a compile check that does not leave
`__pycache__` in the repository:

```powershell
python -c "import pathlib, py_compile, tempfile; cfile=pathlib.Path(tempfile.gettempdir()) / 'orchestrate_agents.check.pyc'; py_compile.compile('scripts/orchestrate_agents.py', cfile=str(cfile), doraise=True); cfile.unlink(missing_ok=True)"
```

When changing JSON presets, also validate them:

```powershell
python -m json.tool docs\agent-presets\default-codex.json
```

## Design Bias

Favor machine-readable contracts over human-only prose. Human usage can remain
possible, but README and script behavior should primarily help a main AI decide:

- whether the run completed,
- which review files to inspect,
- whether another cycle is needed,
- and what bounded changes were produced.
