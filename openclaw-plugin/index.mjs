// Agent Guard — OpenCLAW plugin (automatic prompt-injection screening).
//
// This is the auto-wiring layer the OpenCLAW maintainers' own feedback asked
// for: "build the OpenCLAW plugin that hooks into before_tool_call or wraps
// the web fetch/search tool results". Once this package is installed
// (`openclaw plugins install agent-guard-openclaw`), OpenCLAW discovers it via
// the `openclaw` field in package.json + the openclaw.plugin.json manifest,
// and `activation.onStartup: true` activates it. No manual wrapping, no
// AGENTS.md step.
//
// What it does: registers a `before_tool_call` hook. On every tool call,
// it collects the textual params (the untrusted content: web page text,
// search results, email body, GitHub issue text, MCP tool output, ...) and
// runs the agent-guard Content Guard screening engine on them. Risky content
// blocks the tool call; trusted/authorized channels are skipped per the
// existing ContentGuardConfig at ~/.agent-guard/content_guard.toml.
//
// Content Guard is Python; this plugin is the Node.js seam OpenCLAW loads. It
// bridges to Python by spawning the `agent-guard-openclaw` console script
// shipped by the `agent-guard-plugins` Python package (one short-lived process
// per tool call, JSON in / JSON out).
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { execFileSync } from "node:child_process";

// ---------------------------------------------------------------------------
// Configuration (all optional — sensible defaults, fully overridable)
// ---------------------------------------------------------------------------
//
// AGENT_GUARD_OPENCLAW_DISABLED   "1"/"true" -> plugin loads but screens
//                                 nothing (kill switch; not forced on users).
// AGENT_GUARD_PYTHON              python executable that has
//                                 agent_guard_plugins installed. Default
//                                 "python3".
// AGENT_GUARD_OPENCLAW_TIMEOUT_MS per-call budget for the Python bridge.
//                                 Default 15000.
//
// Tool names treated as web-sourced (always screened even if the source is on
// the authorized-channels trust list). Matched as case-insensitive substrings
// so e.g. "web_search", "web_fetch", "browser_fetch_url" all qualify.
const WEB_TOOL_HINTS = [
  "web",
  "fetch",
  "search",
  "browse",
  "url",
  "http",
  "crawl",
  "scrape",
];

function isDisabled() {
  const v = String(process.env.AGENT_GUARD_OPENCLAW_DISABLED ?? "")
    .trim()
    .toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "on";
}

function looksWebSourced(toolName) {
  const name = String(toolName ?? "").toLowerCase();
  return WEB_TOOL_HINTS.some((hint) => name.includes(hint));
}

// Collect the untrusted textual content from a tool call's params. Strings
// (and strings nested one level inside arrays) are the injection surface;
// numbers / booleans / structural keys are ignored.
function collectTextParts(params) {
  const parts = [];
  for (const value of Object.values(params ?? {})) {
    if (typeof value === "string") {
      if (value) parts.push(value);
    } else if (Array.isArray(value)) {
      for (const item of value) {
        if (typeof item === "string" && item) parts.push(item);
      }
    }
  }
  return parts;
}

// One-shot call into the Python Content Guard bridge. Returns the verdict
// object. Fails OPEN: any spawn/parse error returns a non-blocking verdict so
// a broken guard never wedges the agent.
function screenViaPython(parts, toolName, web) {
  const python = process.env.AGENT_GUARD_PYTHON || "python3";
  const timeoutMs = Number(
    process.env.AGENT_GUARD_OPENCLAW_TIMEOUT_MS || 15000,
  );
  const request = JSON.stringify({
    parts,
    tool_name: toolName ?? "unknown",
    web: Boolean(web),
  });
  try {
    const out = execFileSync(
      python,
      ["-m", "agent_guard_plugins.integrations.openclaw_bridge"],
      {
        input: request,
        encoding: "utf8",
        timeout: timeoutMs,
        env: { ...process.env },
        maxBuffer: 4 * 1024 * 1024,
      },
    );
    const verdict = JSON.parse(out.trim().split("\n").pop() || "{}");
    return verdict;
  } catch (err) {
    // Fail open. Surface the reason on the verdict for diagnostics only.
    return {
      ok: false,
      block: false,
      blockReason: "",
      error: `agent-guard bridge failed: ${err?.message ?? err}`,
    };
  }
}

export default definePluginEntry({
  id: "agent-guard",
  name: "Agent Guard",
  description:
    "Automatic prompt-injection screening for OpenCLAW tool calls. " +
    "Screens web fetch/search results and other untrusted tool content " +
    "before the agent acts on them.",
  register(api) {
    api.on(
      "before_tool_call",
      (event) => {
        if (isDisabled()) return; // kill switch — observe nothing, block nothing

        const toolName = event?.toolName ?? "unknown";
        const parts = collectTextParts(event?.params);
        if (parts.length === 0) return; // no text to screen — allow

        const web = looksWebSourced(toolName);
        const verdict = screenViaPython(parts, toolName, web);

        if (verdict?.block === true) {
          return {
            block: true,
            blockReason:
              verdict.blockReason ||
              `agent-guard blocked tool '${toolName}': flagged as a possible ` +
                `prompt-injection attempt`,
          };
        }
        // allow / warn-mode / trusted / fail-open -> return nothing
      },
      // Run early so a malicious tool call is screened before lower-priority
      // hooks observe it.
      { priority: 90 },
    );
  },
});
