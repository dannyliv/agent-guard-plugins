"""Auto-registering Hermes Agent plugin for Content Guard screening.

This is the Hermes equivalent of the OpenCLAW auto-plugin. The *Hermes Agent*
framework (NousResearch/hermes-agent) — not the Hermes-3 LLM weights — has a
first-class Python plugin system: a plugin is a directory with a `plugin.yaml`
manifest and an `__init__.py` exposing `register(ctx)`, OR a pip package that
exposes the `hermes_agent.plugins` entry-point group. A plugin registers
lifecycle hooks through `ctx.register_hook(...)`.

This plugin registers two hooks, covering both injection surfaces:

* `pre_tool_call` — screens the tool *input*. Hermes calls
  `get_pre_tool_call_block_message()` before every tool runs. The callback
  receives `pre_tool_call(tool_name, args, task_id, session_id, tool_call_id)`
  and blocks the call by returning
  `{"action": "block", "message": "<reason>"}`; `None` lets it proceed.
* `transform_tool_result` — screens the tool *result* (the indirect-injection
  surface: a malicious instruction hidden in fetched content). The callback
  receives `(tool_name, args, result, ...)` and may return a replacement
  string; returning the sanitized placeholder removes attacker instructions
  before the agent reads them. `None` leaves the result unchanged.

This module is the plugin. Wire it up one of two ways:

1. **As a pip plugin (recommended).** `agent-guard-plugins` declares this
   module under the `hermes_agent.plugins` entry-point group, so once the
   package is installed Hermes discovers it. Enable it once with
   `hermes plugins enable agent-guard` (standalone plugins are opt-in by
   Hermes design; this is the most-automatic wiring Hermes supports — there
   is no force-on for standalone plugins).

2. **As a directory plugin.** `agent_guard_plugins.integrations.hermes_plugin
   --install` writes `~/.hermes/plugins/agent-guard/` (a `plugin.yaml` plus an
   `__init__.py` that re-exports `register`), then `hermes plugins enable
   agent-guard`.

Screening reuses the same `ContentGuard` engine and
`~/.agent-guard/content_guard.toml` config as the OpenCLAW and CLI-hook
bridges. `AGENT_GUARD_HERMES_DISABLED=1` is the kill switch. The hook fails
open: any classifier error returns `None` (allow) so a broken guard never
wedges the agent loop — and Hermes itself already wraps every hook callback in
its own try/except.
"""
from __future__ import annotations

import os
import sys
from typing import Any

from ..content_guard import ContentGuard, ContentGuardConfig

# Kill switch. Set to a truthy value to load the plugin but screen nothing.
DISABLE_ENV = "AGENT_GUARD_HERMES_DISABLED"

# Tool names treated as web-sourced (always screened even if the source is on
# the authorized-channels trust list). Case-insensitive substring match.
WEB_TOOL_HINTS = (
    "web", "fetch", "search", "browse", "url", "http", "crawl", "scrape",
)

# Process-cached guard so repeated hook invocations reuse the loaded classifier.
_guard: ContentGuard | None = None


def _is_disabled() -> bool:
    """True if screening is switched off via the environment."""
    return os.environ.get(DISABLE_ENV, "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def get_guard() -> ContentGuard:
    """Return a process-cached ContentGuard built from the config file."""
    global _guard
    if _guard is None:
        _guard = ContentGuard(ContentGuardConfig.from_file())
    return _guard


def _looks_web_sourced(tool_name: str) -> bool:
    """True if a tool name suggests it returns attacker-controlled web content."""
    name = (tool_name or "").lower()
    return any(hint in name for hint in WEB_TOOL_HINTS)


# Tool-arg keys that carry structural data, not untrusted instruction text.
# A filesystem path is not prompt-injection content — screening it produces
# false positives. The real untrusted content for a file-IO tool arrives in
# its result, screened by `transform_tool_result_hook`.
_NON_CONTENT_ARG_KEYS = frozenset(
    {
        "file_path",
        "filepath",
        "path",
        "notebook_path",
        "file",
        "files",
        "paths",
        "directory",
        "dir",
        "cwd",
        "filename",
        "target_file",
        "source",
        "destination",
    }
)


def _collect_text_parts(args: Any) -> list[str]:
    """Pull untrusted textual params out of a Hermes tool-call args dict.

    Strings, and strings nested one level inside lists or dict values, are the
    injection surface; numbers / booleans / structural keys are ignored. Keys
    in `_NON_CONTENT_ARG_KEYS` (filesystem paths) are skipped — a path is not
    injection content and screening it yields false positives.
    """
    parts: list[str] = []

    def _add(value: Any) -> None:
        if isinstance(value, str):
            if value:
                parts.append(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    parts.append(item)
                elif isinstance(item, dict):
                    for v in item.values():
                        if isinstance(v, str) and v:
                            parts.append(v)

    if isinstance(args, dict):
        for key, value in args.items():
            if str(key).lower() in _NON_CONTENT_ARG_KEYS:
                continue
            _add(value)
    return parts


def pre_tool_call_hook(
    tool_name: str = "",
    args: dict[str, Any] | None = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    **_: Any,
) -> dict[str, Any] | None:
    """Hermes `pre_tool_call` hook callback.

    Screens the tool call's textual params with Content Guard. Returns a
    `{"action": "block", "message": ...}` directive if the content is risky,
    or `None` to let the tool proceed.

    Never raises: any classifier failure returns `None` (fail open).
    """
    try:
        if _is_disabled():
            return None

        tool = tool_name or "unknown"
        parts = _collect_text_parts(args)
        if not parts:
            return None  # no text to screen

        content = "\n".join(parts)
        web = _looks_web_sourced(tool)

        guard = get_guard()
        result = guard.screen(content, source=tool, web=web)
        if result.blocked:
            return {
                "action": "block",
                "message": (
                    f"agent-guard blocked tool {tool!r}: {result.reason}"
                ),
            }
        return None  # allowed / warn-mode / trusted / below threshold
    except Exception:  # fail open — a broken guard must never wedge the loop
        return None


def _collect_result_text(result: Any) -> str:
    """Flatten a Hermes tool result into one screenable string.

    Tool results reach `transform_tool_result` as a string (usually JSON), but
    a dict / list shape is handled too for robustness.
    """
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("text", "content", "output", "stdout", "result"):
            if isinstance(result.get(key), str):
                return result[key]
        return "\n".join(_collect_text_parts(result))
    if isinstance(result, list):
        parts: list[str] = []
        for item in result:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                txt = item.get("text") or item.get("content")
                if isinstance(txt, str):
                    parts.append(txt)
        return "\n".join(parts)
    return ""


def transform_tool_result_hook(
    tool_name: str = "",
    args: dict[str, Any] | None = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    tool_call_id: str = "",
    **_: Any,
) -> str | None:
    """Hermes `transform_tool_result` hook callback.

    `pre_tool_call` screens the tool *input*; this screens the tool *result* —
    the indirect-prompt-injection surface (a malicious instruction hidden in a
    fetched web page, a file, or an MCP tool's output). If the result is risky
    in block mode, it is replaced with a sanitized placeholder so the agent
    never reads the attacker's instructions. Returning `None` leaves the result
    unchanged.

    Never raises: any classifier failure returns `None` (fail open).
    """
    try:
        if _is_disabled():
            return None

        tool = tool_name or "unknown"
        content = _collect_result_text(result)
        if not content.strip():
            return None  # no result text to screen

        web = _looks_web_sourced(tool)
        guard = get_guard()
        screen_result = guard.screen(content, source=tool, web=web)
        if screen_result.blocked:
            from ..content_guard import SANITIZED_PLACEHOLDER

            return (
                f"{SANITIZED_PLACEHOLDER}\n"
                f"[agent-guard flagged the result of tool {tool!r}: "
                f"{screen_result.reason}]"
            )
        return None  # allowed / warn-mode / trusted / below threshold
    except Exception:  # fail open — a broken guard must never wedge the loop
        return None


def register(ctx: Any) -> None:
    """Hermes plugin entry point.

    Hermes calls this with a `PluginContext`. We register two hooks so every
    tool call is screened automatically — no manual wrapping:

    - `pre_tool_call` screens the tool *input* and blocks risky calls outright.
    - `transform_tool_result` screens the tool *result* and replaces risky
      content with a sanitized placeholder (the indirect-injection defense).
    """
    ctx.register_hook("pre_tool_call", pre_tool_call_hook)
    ctx.register_hook("transform_tool_result", transform_tool_result_hook)


# --- directory-plugin installer ------------------------------------------

# Manifest for the directory-plugin form. `kind` defaults to "standalone";
# `provides_hooks` is informational metadata Hermes records on the manifest.
_PLUGIN_YAML = """\
name: agent-guard
version: "0.5.0"
description: "Automatic prompt-injection screening for Hermes tool calls. \
Registers a pre_tool_call hook (screens tool input, blocks risky calls) and a \
transform_tool_result hook (screens tool output, sanitizes flagged content) \
with Agent Guard's Content Guard engine."
author: "dannyliv"
provides_hooks:
  - pre_tool_call
  - transform_tool_result
"""

# The directory plugin's __init__.py just re-exports register() from this
# installed package, so the screening logic lives in one place.
_PLUGIN_INIT = '''\
"""agent-guard Hermes plugin — auto-installed by agent-guard-plugins.

Thin shim: the real screening logic lives in the installed Python package
``agent_guard_plugins.integrations.hermes_plugin``. This file only re-exports
its ``register`` so Hermes can load this directory as a plugin.
"""
from agent_guard_plugins.integrations.hermes_plugin import register

__all__ = ["register"]
'''


def install(target_dir: str | os.PathLike[str] | None = None) -> str:
    """Write the directory-plugin form into `~/.hermes/plugins/agent-guard/`.

    Returns the path written. After installing, run
    `hermes plugins enable agent-guard` to activate it (standalone Hermes
    plugins are opt-in by design).
    """
    import pathlib

    if target_dir is None:
        home = os.environ.get("HERMES_HOME")
        base = pathlib.Path(home) if home else pathlib.Path.home() / ".hermes"
        target_dir = base / "plugins" / "agent-guard"
    target = pathlib.Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "plugin.yaml").write_text(_PLUGIN_YAML, encoding="utf-8")
    (target / "__init__.py").write_text(_PLUGIN_INIT, encoding="utf-8")
    return str(target)


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point `agent-guard-hermes-install`.

    With `--install` (the default action) writes the directory plugin and
    prints the next step. The pip-plugin path needs no install step at all.
    """
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] not in ("--install", "install"):
        sys.stderr.write(
            "usage: agent-guard-hermes-install [--install]\n"
            "  Installs the agent-guard plugin into ~/.hermes/plugins/.\n"
            "  If agent-guard-plugins is pip-installed, Hermes already\n"
            "  discovers the plugin via its entry point — just run\n"
            "  `hermes plugins enable agent-guard`.\n"
        )
        return 2
    path = install()
    sys.stdout.write(
        f"agent-guard Hermes plugin installed at: {path}\n"
        f"Activate it with:  hermes plugins enable agent-guard\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
