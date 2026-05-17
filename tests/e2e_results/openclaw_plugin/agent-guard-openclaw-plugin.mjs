// E2E harness shim: re-exports the REAL shippable Agent Guard OpenCLAW plugin
// from `openclaw-plugin/index.mjs`. The e2e harness (run-openclaw-e2e.mjs)
// loads this, so the end-to-end test exercises the exact artifact published as
// the `agent-guard-openclaw` npm plugin — the auto-registering before_tool_call
// plugin — not a hand-rolled copy.
//
// The real plugin bridges to Python via the openclaw_bridge module. The
// harness sets AGENT_GUARD_PYTHON to a Python env with agent_guard_plugins
// installed.
export { default } from "../../../openclaw-plugin/index.mjs";
