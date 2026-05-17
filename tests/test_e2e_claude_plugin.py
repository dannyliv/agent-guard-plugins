"""Real end-to-end test: the agent-guard plugin loaded by the real Claude Code.

Marked `@pytest.mark.e2e` -- excluded from the default fast suite.

What this exercises (vs the mocked harness in test_cli_hook_bridge.py):
  * test_cli_hook_bridge.py mocks the platform entirely.
  * THIS test runs the real `claude` CLI with `--plugin-dir` pointed at the
    shipped `claude-code-plugin/`, validates the plugin manifest with
    `claude plugin validate`, and drives a real tool call through the real
    PreToolUse + PostToolUse hooks registered from `hooks/hooks.json`. The
    real V3.2 classifier runs inside the bridge.

If the `claude` CLI is not on PATH, the test re-runs the harness which skips;
otherwise it runs the harness live. Either way the captured JSON is validated.

The harness lives in tests/e2e_results/claude_plugin/run_claude_plugin_e2e.py.
Captured evidence: tests/e2e_results/claude_plugin/claude_plugin_e2e.json.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

HERE = pathlib.Path(__file__).parent
HARNESS = HERE / "e2e_results" / "claude_plugin" / "run_claude_plugin_e2e.py"
RESULT_JSON = HERE / "e2e_results" / "claude_plugin" / "claude_plugin_e2e.json"


@pytest.mark.e2e
def test_claude_plugin_real_hooks():
    if shutil.which("claude") is None:
        if not RESULT_JSON.exists():
            pytest.skip("claude CLI not installed and no captured result JSON")
    else:
        # Run the harness live against the real Claude Code CLI.
        proc = subprocess.run(
            ["python3", str(HARNESS)],
            capture_output=True, text=True, timeout=600,
        )
        assert proc.returncode == 0, f"harness crashed:\n{proc.stderr}"

    result = json.loads(RESULT_JSON.read_text())
    assert result.get("error") is None, result.get("traceback", "")
    assert result["passed"] is True
    assert result["manifest_valid"] is True

    # Benign Read: both hooks ran, nothing blocked.
    benign = result["benign"]
    assert benign["post_ran"] is True
    assert benign["any_block"] is False

    # Injection file: PostToolUse fired and blocked acting on poisoned content.
    inj = result["injection"]
    assert inj["post_ran"] is True
    assert inj["post_blocked"] is True
