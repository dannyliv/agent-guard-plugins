#!/usr/bin/env bash
# Agent Guard — Claude Code tool-call screening hook command.
#
# Registered for both PreToolUse and PostToolUse. Claude Code spawns this per
# tool call, hands it the event as JSON on stdin, and reads one JSON decision
# back on stdout. The screening engine is Python; this script is the thin seam
# that bridges to it. The bridge inspects `hook_event_name` and screens the
# tool input (PreToolUse) or the tool result (PostToolUse) accordingly.
#
# It runs the `agent_guard_plugins.integrations.cli_hook_bridge` module shipped
# by the `agent-guard-plugins` Python package (one short-lived process per tool
# call, JSON in / JSON out).
#
# FAIL OPEN: if Python is missing, the package is not installed, or the bridge
# errors, this prints `{}` (allow) and exits 0 — a broken guard must never
# wedge Claude Code.
#
# Env:
#   AGENT_GUARD_PYTHON          python executable with agent_guard_plugins
#                               installed. Default: python3.
#   AGENT_GUARD_CLI_HOOK_DISABLED  "1"/"true" -> hook loads but screens
#                               nothing (kill switch; not forced on).

GUARD_PYTHON="${AGENT_GUARD_PYTHON:-python3}"

# Read the event from stdin once (the bridge needs it on its own stdin).
EVENT="$(cat)"

# Resolve the interpreter; fail open if absent.
if ! command -v "$GUARD_PYTHON" >/dev/null 2>&1; then
  printf '{}'
  exit 0
fi

# Run the bridge. On any non-zero exit or empty output, fail open.
OUT="$(printf '%s' "$EVENT" | "$GUARD_PYTHON" -m agent_guard_plugins.integrations.cli_hook_bridge 2>/dev/null)"
if [[ $? -ne 0 || -z "$OUT" ]]; then
  printf '{}'
  exit 0
fi

printf '%s' "$OUT"
exit 0
