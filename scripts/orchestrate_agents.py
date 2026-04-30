#!/usr/bin/env python3
"""Plan/Do/See orchestration script for agent-driven development loops.

The script owns workflow structure and artifacts. External agents are invoked
through command templates, so this repo does not depend on a specific AI CLI.
When a command is not configured, the script writes the prompt and a placeholder
output file, then continues safely.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from typing import Iterable


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_ROOT
DEFAULT_HISTORY_ROOT = Path("docs/work-history")
DEFAULT_MIN_SCORE = 90
IGNORED_DIRS = {
    ".git",
    ".next",
    "node_modules",
    "docs/work-history",
}
IGNORED_SUFFIXES = {
    ".log",
    ".tsbuildinfo",
}
MAX_RESULT_OUTPUT_CHARS = 4000


@dataclass(frozen=True)
class AgentConfig:
    name: str
    command: str | None
    enabled: bool


@dataclass
class CommandResult:
    status: str
    return_code: int | None
    stdout: str
    stderr: str


def truncate_text(value: str | None, limit: int = MAX_RESULT_OUTPUT_CHARS) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}\n\n[truncated {len(value) - limit} chars]"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9가-힣_-]+", "-", value.strip()).strip("-")
    return slug[:60] or "agent-work"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def is_ignored(path: Path) -> bool:
    relative = path.resolve().relative_to(REPO_ROOT).as_posix()
    if any(relative == ignored or relative.startswith(f"{ignored}/") for ignored in IGNORED_DIRS):
        return True
    return path.suffix in IGNORED_SUFFIXES


def snapshot_files() -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file() or is_ignored(path):
            continue
        stat = path.stat()
        snapshot[rel(path)] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def diff_snapshot(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> list[str]:
    changed = sorted(
        path for path, signature in after.items()
        if before.get(path) != signature
    )
    removed = sorted(path for path in before if path not in after)
    return changed + [f"{path} (removed)" for path in removed]


def ensure_path_inside_repo(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside repository: {path}") from exc
    return resolved


def configure_workspace(value: str | None) -> None:
    global REPO_ROOT
    if not value:
        REPO_ROOT = SCRIPT_ROOT
        return

    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError(f"Workspace directory not found: {resolved}")
    REPO_ROOT = resolved


def repo_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return ensure_path_inside_repo(path)


def command_placeholders(command: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in Formatter().parse(command)
        if field_name
    }


def run_agent_command(
    config: AgentConfig,
    prompt_file: Path,
    output_file: Path,
    run_dir: Path,
    cycle_dir: Path,
    cycle: int,
) -> CommandResult:
    prompt_text = read_text(prompt_file)

    if not config.enabled:
        write_text(output_file, placeholder_output(config.name, "disabled"))
        return CommandResult("disabled", None, "", "")

    if not config.command:
        write_text(output_file, placeholder_output(config.name, "command-not-configured"))
        return CommandResult("command-not-configured", None, "", "")

    values = {
        "prompt_file": str(prompt_file),
        "output_file": str(output_file),
        "run_dir": str(run_dir),
        "cycle_dir": str(cycle_dir),
        "workspace": str(REPO_ROOT),
        "cycle": str(cycle),
        "agent": config.name,
    }
    command = config.command.format(**values)
    placeholders = command_placeholders(config.command)
    pipe_prompt = "prompt_file" not in placeholders

    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        input=prompt_text if pipe_prompt else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        shell=True,
        check=False,
    )

    if "output_file" not in placeholders:
        write_text(output_file, completed.stdout or "")
    elif not output_file.exists():
        write_text(
            output_file,
            "\n".join([
                f"# {config.name} output missing",
                "",
                "The configured command referenced `{output_file}` but did not create it.",
                "",
                "## Captured stdout",
                "```text",
                completed.stdout or "",
                "```",
                "",
                "## Captured stderr",
                "```text",
                completed.stderr or "",
                "```",
            ]),
        )

    return CommandResult(
        status="ok" if completed.returncode == 0 else "failed",
        return_code=completed.returncode,
        stdout=truncate_text(completed.stdout),
        stderr=truncate_text(completed.stderr),
    )


def placeholder_output(agent: str, reason: str) -> str:
    return "\n".join([
        f"# {agent} not executed",
        "",
        f"Reason: `{reason}`.",
        "",
        "Configure an agent command with CLI flags or environment variables:",
        "",
        "- `--plan-cmd` or `AGENT_PLAN_CMD`",
        "- `--do-cmd` or `AGENT_DO_CMD`",
        "- `--see-cmd` or `AGENT_SEE_CMD`",
        "- `--convention-cmd` or `AGENT_CONVENTION_CMD`",
        "",
        "Available placeholders: `{prompt_file}`, `{output_file}`, `{run_dir}`,",
        "`{cycle_dir}`, `{workspace}`, `{cycle}`, `{agent}`.",
    ])


def extract_json_metadata(markdown: str, expected_agent: str | None = None) -> dict:
    fenced = re.findall(r"```(?:json|orchestration)?\s*(\{.*?\})\s*```", markdown, re.DOTALL)
    matches: list[dict] = []
    for block in fenced:
        try:
            parsed = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and ("status" in parsed or "score" in parsed):
            if expected_agent is None or parsed.get("agent") == expected_agent:
                matches.append(parsed)
    return matches[-1] if matches else {}


def has_passed(metadata: dict, min_score: int) -> bool:
    status = str(metadata.get("status", "")).lower()
    score = metadata.get("score", -1)
    remaining = metadata.get("remaining_issue_count", metadata.get("remaining", 999))
    try:
        score_value = int(score)
        remaining_value = int(remaining)
    except (TypeError, ValueError):
        return False
    return status == "pass" and score_value >= min_score and remaining_value == 0


def build_plan_prompt(
    task_text: str,
    previous_see: str,
    previous_convention: str,
    cycle: int,
) -> str:
    return f"""# Plan Agent Prompt

## Agent Personality
You are the planning agent. You are precise, skeptical, and implementation-minded.
You do not edit code. Your output must be detailed enough that another capable
model, such as GPT-5.5 medium or stronger, can implement similar code without
asking for missing context.

## Main Context Summary
{task_text}

## Previous Review Feedback
{previous_see or "No previous see review."}

## Previous Convention Feedback
{previous_convention or "No previous convention review."}

## Mission
Create a development plan for cycle {cycle}.

The plan must include:
- Goal statement.
- Relevant repo files and boundaries.
- Exact implementation steps.
- Tests or checks to run.
- Artifact boundaries for checks. Prefer check commands that do not leave
  generated files in the repository; when unavoidable, include explicit cleanup.
- Numeric exit criteria. Every criterion must have an id, metric, target, and measurement method.
- Risks and assumptions.
- A "Do Agent Contract" that says exactly what the do agent may edit.

## Output Format
Write markdown. End with this JSON metadata block:

```json
{{
  "agent": "plan",
  "status": "ready",
  "score": 0,
  "remaining_issue_count": 0,
  "exit_criteria": [
    {{
      "id": "EC-1",
      "metric": "example measurable metric",
      "target": "numeric target",
      "measurement": "how see will measure it"
    }}
  ]
}}
```
"""


def build_do_prompt(task_text: str, plan_text: str, cycle: int) -> str:
    return f"""# Do Agent Prompt

## Agent Personality
You are the implementation agent. You are pragmatic, careful, and repo-native.
Only you may edit production code. Do not broaden scope beyond the plan. Preserve
unrelated user changes.

## Main Context Summary
{task_text}

## Plan For Cycle {cycle}
{plan_text}

## Mission
Implement the plan. Make the smallest code changes that satisfy the exit criteria.
After running checks, remove any generated artifacts that are outside the plan's
allowed write set.

## Required Output
After editing code, write this do report:
- Summary.
- Files changed.
- Commands run and results.
- Exit criteria self-check with numeric actual values.
- Remaining risks or blockers.

End with JSON metadata:

```json
{{
  "agent": "do",
  "status": "done",
  "score": 0,
  "remaining_issue_count": 0,
  "changed_files": []
}}
```
"""


def render_check_results(check_results: list[dict] | None) -> str:
    if not check_results:
        return "No orchestrator check commands were configured or run."
    return "```json\n" + json.dumps(check_results, ensure_ascii=False, indent=2) + "\n```"


def build_see_prompt(
    task_text: str,
    plan_text: str,
    do_text: str,
    convention_text: str,
    check_results: list[dict] | None,
    cycle: int,
) -> str:
    return f"""# See Agent Prompt

## Agent Personality
You are the review agent. You are strict, empirical, and user-goal oriented.
Do not edit code. Compare the plan to the actual implementation. Prefer findings
with concrete file references and measurable evidence.

## Main Context Summary
{task_text}

## Plan For Cycle {cycle}
{plan_text}

## Do Report
{do_text}

## Orchestrator Check Results
These checks were run by the parent orchestration script after the do agent.
Treat return code `0` as empirical evidence. Inspect the referenced check log
only when the summary is insufficient.

{render_check_results(check_results)}

## Convention Feedback Already Known
{convention_text or "No convention feedback yet."}

## Mission
Review the code result against the plan and exit criteria.

You must include:
- Pass/fail for each numeric exit criterion.
- Findings ordered by severity.
- Any missing tests.
- Whether another cycle is needed.
- A compact handoff section for the next plan agent if not passed.

End with JSON metadata:

```json
{{
  "agent": "see",
  "status": "pass",
  "score": 100,
  "remaining_issue_count": 0,
  "exit_criteria_results": []
}}
```
"""


def build_convention_prompt(task_text: str, plan_text: str, do_text: str, see_text: str, cycle: int) -> str:
    return f"""# Code Convention Review Agent Prompt

## Agent Personality
You are the code convention comparison agent. You are boring in the best way:
consistent, concrete, and allergic to avoidable style drift.

## Main Context Summary
{task_text}

## Plan
{plan_text}

## Do Report
{do_text}

## See Review
{see_text}

## Mission
Review the implementation for repository conventions only:
- File placement and naming.
- Existing framework patterns.
- TypeScript/React style where relevant.
- Test/check command fit.
- Documentation/artifact boundaries.

Do not edit code. Produce findings and a numeric convention score from 0 to 100.

End with JSON metadata:

```json
{{
  "agent": "convention",
  "status": "pass",
  "score": 100,
  "remaining_issue_count": 0
}}
```
"""


def write_manifest(path: Path, data: dict) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def compact_agent_status(metadata: dict) -> dict:
    if not metadata:
        return {
            "status": "missing",
            "score": None,
            "remaining_issue_count": None,
        }
    return {
        "status": metadata.get("status"),
        "score": metadata.get("score"),
        "remaining_issue_count": metadata.get("remaining_issue_count", metadata.get("remaining")),
    }


def build_run_summary(manifest: dict, run_dir: Path, exit_code: int) -> dict:
    cycles = manifest.get("cycles", [])
    last_cycle = cycles[-1] if cycles else {}
    artifacts = last_cycle.get("artifacts", {}) if isinstance(last_cycle, dict) else {}
    results = last_cycle.get("results", {}) if isinstance(last_cycle, dict) else {}
    metadata = last_cycle.get("metadata", {}) if isinstance(last_cycle, dict) else {}
    completed = bool(manifest.get("completed", False))
    next_action = "done" if completed else "inspect_review_and_rerun"
    review_files = [
        path for key, path in artifacts.items()
        if key in {"see", "convention"} and path
    ]
    return {
        "schema_version": 1,
        "completed": completed,
        "exit_code": exit_code,
        "next_action": next_action,
        "run_name": manifest.get("run_name"),
        "task_name": manifest.get("task_name"),
        "phase": manifest.get("phase"),
        "task_file": manifest.get("task_file"),
        "run_dir": manifest.get("run_dir"),
        "run_json": rel(run_dir / "run.json"),
        "summary_json": rel(run_dir / "summary.json"),
        "cycles_run": len(cycles),
        "max_cycles": manifest.get("max_cycles"),
        "min_score": manifest.get("min_score"),
        "last_cycle": {
            "cycle": last_cycle.get("cycle") if isinstance(last_cycle, dict) else None,
            "artifacts": artifacts,
            "review_files": review_files,
            "checks": results.get("checks", []),
            "see": compact_agent_status(metadata.get("see", {})),
            "convention": compact_agent_status(metadata.get("convention", {})),
        },
    }


def run_check_commands(commands: Iterable[str], cycle_dir: Path) -> list[dict]:
    results: list[dict] = []
    for index, command in enumerate(commands, start=1):
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            shell=True,
            check=False,
        )
        log_file = cycle_dir / f"check-{index}.log"
        write_text(
            log_file,
            "\n".join([
                f"$ {command}",
                "",
                "## stdout",
                completed.stdout or "",
                "",
                "## stderr",
                completed.stderr or "",
            ]),
        )
        results.append({
            "command": command,
            "return_code": completed.returncode,
            "log": rel(log_file),
        })
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run plan/do/see development agent cycles.")
    parser.add_argument("--task", required=True, help="Markdown file with main context summary and task goals.")
    parser.add_argument("--workspace", default=None, help="Target workspace root. Defaults to the directory above this script.")
    parser.add_argument("--preset", default=None, help="JSON preset file for providers, models, commands, and checks.")
    parser.add_argument("--task-name", default=None, help="Stable task folder name under history root.")
    parser.add_argument("--phase", default=None, help="Phase folder name, for example `phase1_smoke-note`.")
    parser.add_argument("--run-name", default=None, help="Human-readable run name. Defaults to task filename.")
    parser.add_argument("--history-root", default=str(DEFAULT_HISTORY_ROOT), help="Where workflow artifacts are stored.")
    parser.add_argument("--cycles", type=int, default=None, help="Maximum loop cycles.")
    parser.add_argument("--min-score", type=int, default=None, help="Minimum see score for completion.")
    parser.add_argument("--require-pass", action="store_true", help="Exit non-zero when see does not pass.")
    parser.add_argument("--output-format", choices=["text", "json"], default="text", help="Final stdout format for the main caller.")
    parser.add_argument("--summary-file", default=None, help="Optional extra JSON summary path to write inside the repository.")
    parser.add_argument("--plan", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--do", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--see", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--convention", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--readonly-guard", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--checks", action=argparse.BooleanOptionalAction, default=None, help="Enable or disable preset/check commands.")
    parser.add_argument("--codex", action="store_true", help="Use local `codex exec` command templates for missing agent commands.")
    parser.add_argument("--codex-model", default=None, help="Optional model passed to `codex exec -m`.")
    parser.add_argument("--gemini", action="store_true", help="Use local `gemini` command templates for missing agent commands.")
    parser.add_argument("--gemini-model", default=None, help="Optional model passed to `gemini -m`.")
    parser.add_argument("--plan-provider", choices=["codex", "gemini"], default=os.getenv("AGENT_PLAN_PROVIDER"))
    parser.add_argument("--do-provider", choices=["codex", "gemini"], default=os.getenv("AGENT_DO_PROVIDER"))
    parser.add_argument("--see-provider", choices=["codex", "gemini"], default=os.getenv("AGENT_SEE_PROVIDER"))
    parser.add_argument("--convention-provider", choices=["codex", "gemini"], default=os.getenv("AGENT_CONVENTION_PROVIDER"))
    parser.add_argument("--plan-model", default=os.getenv("AGENT_PLAN_MODEL"))
    parser.add_argument("--do-model", default=os.getenv("AGENT_DO_MODEL"))
    parser.add_argument("--see-model", default=os.getenv("AGENT_SEE_MODEL"))
    parser.add_argument("--convention-model", default=os.getenv("AGENT_CONVENTION_MODEL"))
    parser.add_argument("--plan-cmd", default=os.getenv("AGENT_PLAN_CMD"))
    parser.add_argument("--do-cmd", default=os.getenv("AGENT_DO_CMD"))
    parser.add_argument("--see-cmd", default=os.getenv("AGENT_SEE_CMD"))
    parser.add_argument("--convention-cmd", default=os.getenv("AGENT_CONVENTION_CMD"))
    parser.add_argument(
        "--check-cmd",
        action="append",
        default=[],
        help="Shell command to run after do/see. May be specified multiple times.",
    )
    return parser.parse_args()


def load_preset(path: str | None) -> dict:
    if not path:
        return {}

    preset_file = repo_path(path)
    if not preset_file.exists():
        raise FileNotFoundError(f"Preset JSON not found: {preset_file}")

    with preset_file.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError("Preset JSON must be an object")

    return data


def preset_agent_value(preset: dict, agent: str, key: str) -> str | None:
    agents = preset.get("agents", {})
    if not isinstance(agents, dict):
        return None
    agent_config = agents.get(agent, {})
    if not isinstance(agent_config, dict):
        return None
    value = agent_config.get(key)
    return str(value) if value is not None else None


def preset_bool(preset: dict, key: str, default: bool) -> bool:
    value = preset.get(key)
    if value is None:
        return default
    return bool(value)


def preset_int(preset: dict, key: str, default: int) -> int:
    value = preset.get(key)
    if value is None:
        return default
    return int(value)


def merge_checks(cli_checks: list[str], preset: dict) -> list[str]:
    preset_checks = preset.get("check_cmds", preset.get("checks", []))
    if isinstance(preset_checks, str):
        preset_checks = [preset_checks]
    if not isinstance(preset_checks, list):
        preset_checks = []
    return [str(check) for check in preset_checks] + cli_checks


def codex_command(sandbox: str, model: str | None) -> str:
    model_arg = f' -m "{model}"' if model else ""
    return (
        'codex exec '
        '-C "{workspace}" '
        '--skip-git-repo-check '
        f'--sandbox {sandbox} '
        f'{model_arg} '
        '-o "{output_file}" '
        '-'
    )


def gemini_command(approval_mode: str, model: str | None) -> str:
    model_arg = f' -m "{model}"' if model else ""
    return (
        'gemini '
        f'{model_arg} '
        f'--approval-mode {approval_mode} '
        '-p "" '
        '--output-format text '
    )


def global_provider(args: argparse.Namespace) -> str | None:
    if args.codex and args.gemini:
        raise ValueError("Choose only one global preset: --codex or --gemini")
    if args.codex:
        return "codex"
    if args.gemini:
        return "gemini"
    return None


def command_for_provider(agent: str, provider: str | None, model: str | None) -> str | None:
    if provider is None:
        return None

    if provider == "codex":
        sandbox = "workspace-write" if agent == "do" else "read-only"
        return codex_command(sandbox, model)

    if provider == "gemini":
        approval_mode = "auto_edit" if agent == "do" else "plan"
        return gemini_command(approval_mode, model)

    raise ValueError(f"Unsupported provider for {agent}: {provider}")


def resolve_agent_command(
    agent: str,
    explicit_command: str | None,
    provider: str | None,
    agent_model: str | None,
    default_provider: str | None,
    default_codex_model: str | None,
    default_gemini_model: str | None,
) -> str | None:
    if explicit_command:
        return explicit_command

    resolved_provider = provider or default_provider
    if not resolved_provider:
        return None

    model = agent_model
    if not model and resolved_provider == "codex":
        model = default_codex_model
    if not model and resolved_provider == "gemini":
        model = default_gemini_model

    return command_for_provider(agent, resolved_provider, model)


def main() -> int:
    args = parse_args()
    configure_workspace(args.workspace)
    preset = load_preset(args.preset)
    args.cycles = int(args.cycles if args.cycles is not None else preset_int(preset, "cycles", 1))
    args.min_score = int(args.min_score if args.min_score is not None else preset_int(preset, "min_score", DEFAULT_MIN_SCORE))
    args.plan = args.plan if args.plan is not None else preset_bool(preset, "run_plan", preset_bool(preset, "plan", True))
    args.do = args.do if args.do is not None else preset_bool(preset, "run_do", preset_bool(preset, "do", True))
    args.see = args.see if args.see is not None else preset_bool(preset, "run_see", preset_bool(preset, "see", True))
    args.convention = args.convention if args.convention is not None else preset_bool(preset, "run_convention", preset_bool(preset, "convention", True))
    args.readonly_guard = args.readonly_guard if args.readonly_guard is not None else preset_bool(preset, "readonly_guard", True)
    checks_enabled = args.checks if args.checks is not None else preset_bool(preset, "checks_enabled", True)
    args.check_cmd = merge_checks(args.check_cmd, preset) if checks_enabled else []

    task_file = repo_path(args.task)
    if not task_file.exists():
        raise FileNotFoundError(f"Task markdown not found: {task_file}")

    task_text = read_text(task_file)
    task_name = slugify(args.task_name or preset.get("task_name") or task_file.stem)
    phase_name = slugify(args.phase or preset.get("phase") or args.run_name or f"phase1_{task_file.stem}")
    run_name = slugify(args.run_name or phase_name)
    task_dir = repo_path(Path(args.history_root) / task_name)
    run_dir = task_dir / phase_name
    if run_dir.exists():
        run_dir = task_dir / f"{phase_name}-{now_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=False)
    write_text(run_dir / "task.md", task_text)

    default_provider = global_provider(args) or (str(preset["provider"]) if preset.get("provider") is not None else None)
    if default_provider not in {None, "codex", "gemini"}:
        raise ValueError(f"Unsupported preset provider: {default_provider}")

    configs = {
        "plan": AgentConfig(
            "plan",
            resolve_agent_command(
                "plan",
                args.plan_cmd or preset_agent_value(preset, "plan", "cmd"),
                args.plan_provider or preset_agent_value(preset, "plan", "provider"),
                args.plan_model or preset_agent_value(preset, "plan", "model"),
                default_provider,
                args.codex_model,
                args.gemini_model,
            ),
            args.plan,
        ),
        "do": AgentConfig(
            "do",
            resolve_agent_command(
                "do",
                args.do_cmd or preset_agent_value(preset, "do", "cmd"),
                args.do_provider or preset_agent_value(preset, "do", "provider"),
                args.do_model or preset_agent_value(preset, "do", "model"),
                default_provider,
                args.codex_model,
                args.gemini_model,
            ),
            args.do,
        ),
        "see": AgentConfig(
            "see",
            resolve_agent_command(
                "see",
                args.see_cmd or preset_agent_value(preset, "see", "cmd"),
                args.see_provider or preset_agent_value(preset, "see", "provider"),
                args.see_model or preset_agent_value(preset, "see", "model"),
                default_provider,
                args.codex_model,
                args.gemini_model,
            ),
            args.see,
        ),
        "convention": AgentConfig(
            "convention",
            resolve_agent_command(
                "convention",
                args.convention_cmd or preset_agent_value(preset, "convention", "cmd"),
                args.convention_provider or preset_agent_value(preset, "convention", "provider"),
                args.convention_model or preset_agent_value(preset, "convention", "model"),
                default_provider,
                args.codex_model,
                args.gemini_model,
            ),
            args.convention,
        ),
    }

    manifest: dict = {
        "run_name": run_name,
        "task_name": task_name,
        "phase": phase_name,
        "task_file": rel(task_file),
        "task_dir": rel(task_dir),
        "run_dir": rel(run_dir),
        "preset_file": rel(repo_path(args.preset)) if args.preset else None,
        "started_at": dt.datetime.now().isoformat(),
        "max_cycles": args.cycles,
        "min_score": args.min_score,
        "cycles": [],
    }
    write_manifest(run_dir / "run.json", manifest)

    previous_see = ""
    previous_convention = ""
    completed = False

    for cycle in range(1, args.cycles + 1):
        cycle_dir = run_dir / f"cycle-{cycle:02d}"
        cycle_dir.mkdir(parents=True, exist_ok=False)
        cycle_entry: dict = {"cycle": cycle, "artifacts": {}, "results": {}}

        plan_prompt = build_plan_prompt(task_text, previous_see, previous_convention, cycle)
        plan_prompt_file = cycle_dir / "plan.prompt.md"
        plan_file = cycle_dir / "plan.md"
        write_text(plan_prompt_file, plan_prompt)

        before = snapshot_files()
        plan_result = run_agent_command(configs["plan"], plan_prompt_file, plan_file, run_dir, cycle_dir, cycle)
        after = snapshot_files()
        if args.readonly_guard:
            plan_changes = [path for path in diff_snapshot(before, after) if not path.startswith(rel(run_dir))]
            if plan_changes:
                write_text(cycle_dir / "plan.readonly-warning.md", "\n".join(["# Plan changed repository files", "", *plan_changes]))
        cycle_entry["results"]["plan"] = plan_result.__dict__
        cycle_entry["artifacts"]["plan"] = rel(plan_file)

        plan_text = read_text(plan_file)

        do_prompt = build_do_prompt(task_text, plan_text, cycle)
        do_prompt_file = cycle_dir / "do.prompt.md"
        do_file = cycle_dir / "do.md"
        write_text(do_prompt_file, do_prompt)
        do_result = run_agent_command(configs["do"], do_prompt_file, do_file, run_dir, cycle_dir, cycle)
        cycle_entry["results"]["do"] = do_result.__dict__
        cycle_entry["artifacts"]["do"] = rel(do_file)

        check_results = run_check_commands(args.check_cmd, cycle_dir)
        if check_results:
            cycle_entry["results"]["checks"] = check_results

        do_text = read_text(do_file)

        convention_text = ""
        see_text = ""
        if configs["see"].enabled:
            see_prompt = build_see_prompt(task_text, plan_text, do_text, previous_convention, check_results, cycle)
            see_prompt_file = cycle_dir / "see.prompt.md"
            see_file = cycle_dir / "see.md"
            write_text(see_prompt_file, see_prompt)
            before = snapshot_files()
            see_result = run_agent_command(configs["see"], see_prompt_file, see_file, run_dir, cycle_dir, cycle)
            after = snapshot_files()
            if args.readonly_guard:
                see_changes = [path for path in diff_snapshot(before, after) if not path.startswith(rel(run_dir))]
                if see_changes:
                    write_text(cycle_dir / "see.readonly-warning.md", "\n".join(["# See changed repository files", "", *see_changes]))
            see_text = read_text(see_file)
            cycle_entry["results"]["see"] = see_result.__dict__
            cycle_entry["artifacts"]["see"] = rel(see_file)

        if configs["convention"].enabled:
            convention_prompt = build_convention_prompt(task_text, plan_text, do_text, see_text, cycle)
            convention_prompt_file = cycle_dir / "convention.prompt.md"
            convention_file = cycle_dir / "convention.md"
            write_text(convention_prompt_file, convention_prompt)
            before = snapshot_files()
            convention_result = run_agent_command(configs["convention"], convention_prompt_file, convention_file, run_dir, cycle_dir, cycle)
            after = snapshot_files()
            if args.readonly_guard:
                convention_changes = [path for path in diff_snapshot(before, after) if not path.startswith(rel(run_dir))]
                if convention_changes:
                    write_text(cycle_dir / "convention.readonly-warning.md", "\n".join(["# Convention changed repository files", "", *convention_changes]))
            convention_text = read_text(convention_file)
            cycle_entry["results"]["convention"] = convention_result.__dict__
            cycle_entry["artifacts"]["convention"] = rel(convention_file)

        see_metadata = extract_json_metadata(see_text, "see") if cycle_entry["results"].get("see", {}).get("status") == "ok" else {}
        convention_metadata = extract_json_metadata(convention_text, "convention") if cycle_entry["results"].get("convention", {}).get("status") == "ok" else {}
        cycle_entry["metadata"] = {
            "see": see_metadata,
            "convention": convention_metadata,
        }
        manifest["cycles"].append(cycle_entry)
        write_manifest(run_dir / "run.json", manifest)

        previous_see = see_text
        previous_convention = convention_text

        see_passed = not configs["see"].enabled or has_passed(see_metadata, args.min_score)
        convention_passed = not configs["convention"].enabled or has_passed(convention_metadata, args.min_score)
        if see_passed and convention_passed:
            completed = True
            break

    manifest["completed"] = completed
    manifest["finished_at"] = dt.datetime.now().isoformat()
    manifest["run_hash"] = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    exit_code = 0 if completed or not args.require_pass else 1
    summary = build_run_summary(manifest, run_dir, exit_code)
    write_manifest(run_dir / "run.json", manifest)
    write_manifest(run_dir / "summary.json", summary)
    if args.summary_file:
        write_manifest(repo_path(args.summary_file), summary)

    if args.output_format == "json":
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"Run artifacts: {rel(run_dir)}")
        print(f"Completed: {completed}")
        print(f"Summary: {rel(run_dir / 'summary.json')}")
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"orchestrator error: {exc}", file=sys.stderr)
        raise
