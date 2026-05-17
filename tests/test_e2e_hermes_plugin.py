"""Real end-to-end test: the agent-guard plugin inside the real Hermes Agent.

Marked `@pytest.mark.e2e` -- excluded from the default fast suite.

What this exercises (vs the mocked harness in test_hermes_plugin.py):
  * test_hermes_plugin.py mocks the platform (a FakeCtx, patched classifier).
  * THIS test loads the genuine NousResearch/hermes-agent `PluginManager`,
    discovers the `agent-guard` plugin through its real `hermes_agent.plugins`
    entry point, and drives a tool call through the real
    `get_pre_tool_call_block_message()` gate — the function Hermes itself calls
    before every tool runs. The real V3.2 classifier runs inside the hook.

Prerequisites to run live:
  * The hermes-agent source importable, e.g.
        git clone --depth 1 https://github.com/NousResearch/hermes-agent \\
            /tmp/hermes-agent-src
    Point AGENT_GUARD_HERMES_SRC at it (defaults to /tmp/hermes-agent-src).
  * agent-guard-plugins installed (`pip install -e .[modernbert]`).

If the hermes-agent source is not importable the harness records an error and
this test skips. The harness lives in
tests/e2e_results/hermes_plugin/run_hermes_plugin_e2e.py.
Captured evidence: tests/e2e_results/hermes_plugin/hermes_plugin_e2e.json.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

import pytest

HERE = pathlib.Path(__file__).parent
HARNESS = HERE / "e2e_results" / "hermes_plugin" / "run_hermes_plugin_e2e.py"
RESULT_JSON = HERE / "e2e_results" / "hermes_plugin" / "hermes_plugin_e2e.json"


@pytest.mark.e2e
def test_hermes_plugin_real_pre_tool_call_gate():
    src = os.environ.get("AGENT_GUARD_HERMES_SRC", "/tmp/hermes-agent-src")
    hermes_available = pathlib.Path(src, "hermes_cli", "plugins.py").exists()

    if hermes_available:
        proc = subprocess.run(
            ["python3", str(HARNESS)],
            capture_output=True, text=True, timeout=600,
            env={**os.environ, "AGENT_GUARD_HERMES_SRC": src},
        )
        assert proc.returncode == 0, f"harness crashed:\n{proc.stderr}"
    elif not RESULT_JSON.exists():
        pytest.skip(
            "hermes-agent source not found (set AGENT_GUARD_HERMES_SRC) and "
            "no captured result JSON"
        )

    result = json.loads(RESULT_JSON.read_text())
    if result.get("error") and "hermes_cli" in str(result.get("error")):
        pytest.skip(f"hermes-agent not importable: {result['error']}")

    assert result.get("error") is None, result.get("traceback", "")
    assert result["passed"] is True

    # The real Hermes PluginManager loaded the plugin and registered the hook.
    load = result["plugin_load"]
    assert load["enabled"] is True
    assert "pre_tool_call" in load["hooks_registered"]

    # Benign tool call -> the real Hermes gate does NOT block.
    assert result["benign"]["blocked"] is False
    # Injection tool call -> the real Hermes gate blocks with an agent-guard
    # message.
    assert result["injection"]["blocked"] is True
    assert "agent-guard" in result["injection"]["block_message"]
