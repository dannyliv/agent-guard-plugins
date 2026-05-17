# agent-guard-openclaw

Automatic prompt-injection screening for [OpenCLAW](https://openclaw.ai) tool
calls. This is the OpenCLAW plugin half of
[`agent-guard-plugins`](https://github.com/dannyliv/agent-guard-plugins).

## What it does

Once installed, OpenCLAW discovers and activates this plugin automatically
(`activation.onStartup: true`). It registers a `before_tool_call` hook that
runs on every tool call. The hook collects the tool's textual params (web page
text, search results, email body, GitHub issue text, MCP tool output, and
similar untrusted content) and screens them with the Content Guard engine from
`agent-guard-plugins`. Risky content blocks the tool call before the agent
acts on it. Trusted / authorized channels are skipped per your Content Guard
config.

No manual wrapping. No AGENTS.md step. Install it and it is active.

## Install

The plugin needs both the npm package (the OpenCLAW seam) and the Python
package (the screening engine):

```bash
# Python screening engine — provides the `agent-guard-openclaw` bridge
pip install agent-guard-plugins

# OpenCLAW plugin — auto-registers the before_tool_call hook
openclaw plugins install agent-guard-openclaw
```

## Configuration

Screening policy (trust list, block threshold, block/warn mode) lives in the
Content Guard config file at `~/.agent-guard/content_guard.toml`. See the
`agent-guard-plugins` README for that file's schema. The plugin itself reads:

| Env var                          | Default   | Purpose                                                          |
| --------------------------------- | --------- | ---------------------------------------------------------------- |
| `AGENT_GUARD_OPENCLAW_DISABLED`   | unset     | `1`/`true` loads the plugin but screens nothing (kill switch).   |
| `AGENT_GUARD_PYTHON`              | `python3` | Python executable that has `agent_guard_plugins` installed.      |
| `AGENT_GUARD_OPENCLAW_TIMEOUT_MS` | `15000`   | Per-tool-call budget for the screening subprocess.               |

## Fail-open

If the screening bridge cannot run (Python missing, model load failure,
timeout), the hook returns no decision and the tool call proceeds. A broken
guard never wedges the agent.
