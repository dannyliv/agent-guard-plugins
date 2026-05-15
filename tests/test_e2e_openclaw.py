"""Real end-to-end test: OpenCLAW platform loading the agent-guard plugin.

Marked `@pytest.mark.e2e` -- excluded from the default fast suite.

What this exercises (vs the mocked harness in test_integrations.py):
  * test_integrations.py mocks the platform side entirely.
  * THIS test loads the real OpenCLAW plugin SDK (`definePluginEntry`,
    `api.on("before_tool_call")`, the documented PluginHookBeforeToolCallEvent
    envelope and {block, blockReason} result) and routes a real tool call
    through the real Python `preaction_hook` + real HF classifier.

Prerequisites to run:
  * Node.js >= 22 and npm.
  * The `openclaw` npm package installed somewhere reachable, e.g.
        npm install --prefix /tmp/agp-e2e-openclaw-npm openclaw
  * agent-guard-plugins installed in a Python env (`pip install -e .[all]`).
  * Env vars:
        AGENT_GUARD_OPENCLAW_NODE_MODULES -> node_modules dir with `openclaw`
        AGENT_GUARD_PYTHON                -> python with agent_guard_plugins
        HF_TOKEN                          -> Hugging Face token (model download)

The harness scripts live in tests/e2e_results/openclaw_plugin/.
Captured evidence: tests/e2e_results/openclaw_e2e.json.
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

HERE = pathlib.Path(__file__).parent
PLUGIN_DIR = HERE / "e2e_results" / "openclaw_plugin"


@pytest.mark.e2e
def test_openclaw_real_plugin_hook():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    node_modules = os.environ.get("AGENT_GUARD_OPENCLAW_NODE_MODULES")
    if not node_modules or not pathlib.Path(node_modules, "openclaw").exists():
        pytest.skip("openclaw npm package not installed "
                    "(set AGENT_GUARD_OPENCLAW_NODE_MODULES)")
    # Link node_modules so `import openclaw/...` resolves from the harness dir.
    link = PLUGIN_DIR / "node_modules"
    if not link.exists():
        link.symlink_to(node_modules)
    env = {**os.environ,
           "AGENT_GUARD_PYTHON": os.environ.get("AGENT_GUARD_PYTHON", "python3")}
    proc = subprocess.run(
        [node, str(PLUGIN_DIR / "run-openclaw-e2e.mjs")],
        cwd=PLUGIN_DIR, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, f"harness failed:\n{proc.stdout}\n{proc.stderr}"

    result = json.loads((HERE / "e2e_results" / "openclaw_e2e.json").read_text())
    assert result["passed"] is True
    by_name = {t["name"]: t for t in result["tests"]}
    assert by_name["benign tool call proceeds"]["passed"] is True
    blocked = by_name["injection tool call blocked"]
    assert blocked["passed"] is True
    assert blocked["hook_result"]["block"] is True
