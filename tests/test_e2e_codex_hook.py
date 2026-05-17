"""Real end-to-end test: the agent-guard Codex CLI PreToolUse/PostToolUse hook.

Marked `@pytest.mark.e2e` -- excluded from the default fast suite.

What this exercises (vs the mocked harness in test_cli_hook_bridge.py):
  * test_cli_hook_bridge.py mocks the platform.
  * THIS test runs the real installer (`codex_install.install`) into a temp
    CODEX_HOME, then spawns the installed hook script exactly as the Codex CLI
    would — feeding it a real PreToolUse event on stdin and reading the
    decision JSON back. The real V3.2 classifier runs inside the bridge.

The harness IS the realistic test: Codex's hook contract is the `hooks.json`
entry + the spawned command + the stdin/stdout JSON protocol, and the harness
exercises every link. Starting the `codex` binary itself adds nothing to hook
verification (the hook fires the same with or without a model backend) — see
tests/e2e_results/KNOWN_GAPS.md.

Captured evidence: tests/e2e_results/codex_hook/codex_hook_e2e.json.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

HERE = pathlib.Path(__file__).parent
HARNESS = HERE / "e2e_results" / "codex_hook" / "run_codex_hook_e2e.py"
RESULT_JSON = HERE / "e2e_results" / "codex_hook" / "codex_hook_e2e.json"


@pytest.mark.e2e
def test_codex_hook_real_install_and_screen():
    # The harness needs only agent-guard-plugins itself (no Codex binary), so
    # always run it live; it self-skips inside if the package is missing.
    proc = subprocess.run(
        ["python3", str(HARNESS)],
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, f"harness crashed:\n{proc.stderr}"

    result = json.loads(RESULT_JSON.read_text())
    assert result.get("error") is None, result.get("traceback", "")
    assert result["passed"] is True

    # The real installer produced a valid ~/.codex/hooks.json + hook script.
    install = result["install"]
    assert install["hook_script_exists"] is True
    assert install["hooks_json_valid"] is True

    # Benign tool call -> hook allows ({} decision).
    assert result["benign"]["blocked"] is False
    # Injection tool call -> hook denies via PreToolUse permissionDecision.
    assert result["injection"]["blocked"] is True
