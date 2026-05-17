"""JSON bridge between the OpenCLAW (Node.js) plugin and Content Guard.

OpenCLAW plugins run in Node.js; the Content Guard screening engine is Python.
The shippable OpenCLAW plugin (`openclaw-plugin/` in this repo) calls into this
module once per tool call to screen the tool's untrusted text params.

Two entry points:

- `screen_payload(payload)` — pure function. Takes a dict describing one
  `before_tool_call` event (tool name, text parts, web flag), runs Content
  Guard, and returns a JSON-serializable verdict dict.
- `main()` — console script `agent-guard-openclaw`. Reads one JSON request
  from stdin, writes one JSON verdict to stdout. This is the process the
  Node plugin spawns.

The verdict dict shape (stable contract the Node plugin depends on):

    {
      "ok": true,
      "block": bool,         # block the tool call
      "blockReason": str,    # human-readable, set when block is true
      "score": float,        # injection probability (0.0 for trusted skips)
      "trusted": bool,       # source was on the authorized-channels list
      "mode": "block"|"warn",
      "source": str|null
    }

On any internal error the verdict is `{"ok": false, "block": false,
"error": ...}` — the plugin fails OPEN (never blocks a tool call because the
guard itself crashed), matching the existing adapters' fail-open behavior.

Config comes from `ContentGuardConfig.from_file()` so the trust list,
threshold, and mode stay tunable via `~/.agent-guard/content_guard.toml`
without touching plugin code.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

from ..content_guard import ContentGuard, ContentGuardConfig

# Set this env var to a falsy-ish value to disable screening entirely. The Node
# plugin also honors its own disable flag; this is the Python-side backstop.
DISABLE_ENV = "AGENT_GUARD_OPENCLAW_DISABLED"

# A cached ContentGuard so repeated calls in one process reuse the config and
# the loaded classifier. The console-script path is one-shot, but a long-lived
# host could import and call `screen_payload` many times.
_guard: ContentGuard | None = None


def _is_disabled() -> bool:
    """True if screening is switched off via the environment."""
    val = os.environ.get(DISABLE_ENV, "").strip().lower()
    return val in ("1", "true", "yes", "on")


def get_guard() -> ContentGuard:
    """Return a process-cached ContentGuard built from the config file."""
    global _guard
    if _guard is None:
        _guard = ContentGuard(ContentGuardConfig.from_file())
    return _guard


def screen_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Screen one OpenCLAW tool-call payload and return a verdict dict.

    Expected `payload` keys:
    - `parts` : list[str] — the textual params of the tool call (required).
      A single `text` string is also accepted as a convenience.
    - `tool_name` : str — the OpenCLAW tool name; used as the screening source
      so the dashboard can attribute the detection and so an operator can put
      a trusted tool name on the authorized-channels list.
    - `web` : bool — whether the content is web-sourced (web fetch / search /
      page summarize). Web content is always screened even if the source is
      trusted, per `ContentGuardConfig.screen_web`. Defaults to False.

    Never raises: any failure produces a fail-open verdict.
    """
    try:
        if _is_disabled():
            return {
                "ok": True,
                "block": False,
                "blockReason": "",
                "score": 0.0,
                "trusted": False,
                "mode": "disabled",
                "source": payload.get("tool_name"),
            }

        parts = payload.get("parts")
        if parts is None and "text" in payload:
            parts = [payload["text"]]
        if not isinstance(parts, list):
            parts = []
        content = "\n".join(str(p) for p in parts if isinstance(p, str) and p)

        tool_name = payload.get("tool_name") or "unknown"
        web = bool(payload.get("web", False))

        guard = get_guard()
        result = guard.screen(content, source=tool_name, web=web)
        return {
            "ok": True,
            "block": result.blocked,
            "blockReason": (
                f"agent-guard blocked tool '{tool_name}': {result.reason}"
                if result.blocked
                else ""
            ),
            "score": round(result.score, 4),
            "trusted": result.trusted,
            "mode": guard.config.mode,
            "source": tool_name,
        }
    except Exception as exc:  # fail open — a broken guard must not wedge the agent
        return {
            "ok": False,
            "block": False,
            "blockReason": "",
            "score": 0.0,
            "trusted": False,
            "mode": "error",
            "source": payload.get("tool_name") if isinstance(payload, dict) else None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point `agent-guard-openclaw`.

    Reads one JSON object from stdin, writes one JSON verdict to stdout,
    exits 0. Used by the OpenCLAW Node plugin as a one-shot subprocess.
    """
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
    except json.JSONDecodeError as exc:
        sys.stdout.write(
            json.dumps(
                {
                    "ok": False,
                    "block": False,
                    "blockReason": "",
                    "score": 0.0,
                    "trusted": False,
                    "mode": "error",
                    "source": None,
                    "error": f"invalid JSON request: {exc}",
                }
            )
        )
        return 0

    verdict = screen_payload(payload)
    sys.stdout.write(json.dumps(verdict))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
