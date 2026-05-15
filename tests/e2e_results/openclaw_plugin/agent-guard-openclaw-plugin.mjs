// Real OpenCLAW plugin: registers a before_tool_call hook that routes the
// tool's untrusted text params through agent-guard-plugins' Python
// preaction_hook. This is the genuine OpenCLAW plugin contract -- the same
// definePluginEntry / api.on("before_tool_call") the gateway loads.
//
// The hook blocks the tool call (returns { block: true, blockReason }) when
// the classifier flags the content as a prompt injection.
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFileSync } from "node:child_process";

// Path to the venv python that has agent_guard_plugins installed.
const GUARD_PYTHON = process.env.AGENT_GUARD_PYTHON || "python3";

function runPreactionHook(content, actionKind) {
  // One-shot call into the Python adapter. Returns the HookDecision as JSON.
  const code =
    "import json,sys;" +
    "from agent_guard_plugins.integrations.openclaw import preaction_hook;" +
    "d=preaction_hook(sys.argv[1], action_kind=sys.argv[2]);" +
    "print(json.dumps({'allow':d.allow,'reason':d.reason,'probability':d.probability,'owasp':d.owasp,'atlas':d.atlas}))";
  const out = execFileSync(GUARD_PYTHON, ["-c", code, content, actionKind], {
    encoding: "utf8",
    env: { ...process.env },
  });
  return JSON.parse(out.trim().split("\n").pop());
}

export default definePluginEntry({
  id: "agent-guard",
  name: "Agent Guard",
  description: "Prompt-injection guard for OpenCLAW tool calls.",
  register(api) {
    api.on(
      "before_tool_call",
      (event) => {
        // Inspect the textual params of the tool call. These carry the
        // untrusted content (email body, web page text, issue title, ...).
        const parts = [];
        for (const v of Object.values(event.params ?? {})) {
          if (typeof v === "string") parts.push(v);
        }
        const content = parts.join("\n");
        if (!content) return;
        const decision = runPreactionHook(content, event.toolName ?? "unknown");
        if (!decision.allow) {
          return {
            block: true,
            blockReason: `agent-guard blocked: ${decision.reason}`,
          };
        }
        // allow -> return nothing (hook is observation-pass)
      },
      { priority: 90 },
    );
  },
});
