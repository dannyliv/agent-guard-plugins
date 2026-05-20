"""Installer for the OpenAI Codex CLI PreToolUse hook.

The Codex CLI auto-discovers lifecycle hooks from `~/.codex/hooks.json` (and a
repo-local `.codex/hooks.json`). Unlike Claude Code, Codex has no plugin
manifest and no `${PLUGIN_ROOT}` placeholder — a hook is a single `hooks.json`
entry pointing at a command. So the auto-wiring for Codex is a one-line install
step: this writes `~/.codex/hooks.json` plus the hook script that bridges to
the shared Content Guard engine.

This is the most-automatic integration Codex supports. There is no entry-point
or plugin-discovery mechanism that would let `pip install agent-guard-plugins`
register a Codex hook with zero steps; the `hooks.json` file is the contract,
and it must name an absolute command path. The installer resolves that path and
writes it once.

Console script: `agent-guard-codex-install`.

The installed hook fails open (Python missing / bridge error -> tool call
proceeds) and honors `AGENT_GUARD_CLI_HOOK_DISABLED=1` as a kill switch.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import stat
import sys

# The hook script written into ~/.codex/hooks/. Mirrors the shipped
# codex-hooks/agent-guard-pretooluse.sh but with no env-var indirection — the
# installer resolves the interpreter and path concretely.
_HOOK_SCRIPT = """\
#!/usr/bin/env bash
# Agent Guard — OpenAI Codex CLI PreToolUse hook (installed by
# agent-guard-codex-install). Screens each tool call's untrusted text params
# for prompt injection before the tool runs. Fails open on any error.
GUARD_PYTHON="${AGENT_GUARD_PYTHON:-%(python)s}"
EVENT="$(cat)"
if ! command -v "$GUARD_PYTHON" >/dev/null 2>&1; then
  printf '{}'
  exit 0
fi
OUT="$(printf '%%s' "$EVENT" | "$GUARD_PYTHON" -m agent_guard_plugins.integrations.cli_hook_bridge 2>/dev/null)"
if [[ $? -ne 0 || -z "$OUT" ]]; then
  printf '{}'
  exit 0
fi
printf '%%s' "$OUT"
exit 0
"""


def _codex_home() -> pathlib.Path:
    """Return the Codex config dir (`$CODEX_HOME` or `~/.codex`)."""
    env = os.environ.get("CODEX_HOME")
    return pathlib.Path(env) if env else pathlib.Path.home() / ".codex"


# Codex events screened: PreToolUse catches risky tool *input*, PostToolUse
# catches risky tool *output* (the indirect-injection surface).
_SCREENED_EVENTS = ("PreToolUse", "PostToolUse")


def _is_agent_guard(group: object) -> bool:
    """True if a hooks.json matcher group is a previously-installed agent-guard
    entry — used to make re-installs idempotent."""
    if not isinstance(group, dict):
        return False
    for h in group.get("hooks") or []:
        if isinstance(h, dict) and "agent-guard" in str(h.get("command", "")):
            return True
    return False


def _merge_hooks(existing: dict, hook_command: str) -> dict:
    """Merge agent-guard PreToolUse + PostToolUse entries into a hooks.json dict.

    Idempotent: any prior agent-guard entry (one naming our hook script) is
    replaced rather than duplicated. Other hooks the user configured for those
    events are preserved.
    """
    config = dict(existing) if isinstance(existing, dict) else {}
    hooks = dict(config.get("hooks") or {})

    for event in _SCREENED_EVENTS:
        groups = [g for g in (hooks.get(event) or []) if not _is_agent_guard(g)]
        groups.append(
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": hook_command,
                        "statusMessage": (
                            "agent-guard: screening tool content for "
                            "prompt injection"
                        ),
                        "timeout": 30,
                    }
                ],
            }
        )
        hooks[event] = groups

    config["hooks"] = hooks
    return config


def install(codex_home: str | os.PathLike[str] | None = None,
            python_executable: str | None = None) -> dict[str, str]:
    """Install the Codex PreToolUse hook.

    Writes `<codex_home>/hooks/agent-guard-pretooluse.sh` and merges a
    PreToolUse entry into `<codex_home>/hooks.json`. Returns the paths written.
    """
    home = pathlib.Path(codex_home) if codex_home else _codex_home()
    hooks_dir = home / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    python = python_executable or sys.executable or "python3"
    if not re.match(r'^[A-Za-z0-9_./ -]+$', python):
        raise ValueError(
            f"python_executable {python!r} contains unsafe characters. "
            "Only letters, digits, dots, underscores, slashes, spaces, and hyphens are allowed."
        )
    script_path = hooks_dir / "agent-guard-pretooluse.sh"
    script_path.write_text(_HOOK_SCRIPT % {"python": python}, encoding="utf-8")
    script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)

    hooks_json = home / "hooks.json"
    existing: dict = {}
    if hooks_json.exists():
        try:
            existing = json.loads(hooks_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    merged = _merge_hooks(existing, str(script_path))
    hooks_json.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")

    return {"hook_script": str(script_path), "hooks_json": str(hooks_json)}


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point `agent-guard-codex-install`."""
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in ("-h", "--help"):
        sys.stdout.write(
            "usage: agent-guard-codex-install\n"
            "  Installs the agent-guard PreToolUse hook into ~/.codex/.\n"
            "  Codex auto-discovers it from ~/.codex/hooks.json on next run.\n"
            "  Set AGENT_GUARD_CLI_HOOK_DISABLED=1 to disable screening.\n"
        )
        return 0
    paths = install()
    sys.stdout.write(
        "agent-guard Codex hook installed.\n"
        f"  hook script : {paths['hook_script']}\n"
        f"  hooks.json  : {paths['hooks_json']}\n"
        "Codex picks it up automatically on the next session.\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
