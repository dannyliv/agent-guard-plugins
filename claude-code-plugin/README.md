# Agent Guard — Claude Code plugin

Automatic prompt-injection screening for Claude Code tool calls. Once this
plugin is enabled, every tool call is screened by Agent Guard's Content Guard
engine — no manual wrapping, no `CLAUDE.md` step.

## What it does

The plugin registers two hooks in `hooks/hooks.json`:

- **PreToolUse** screens the tool's *input* params (a `WebFetch` prompt, a
  `WebSearch` query, a `Bash` command). This is the direct-injection surface —
  text a user or upstream content smuggled into the call. A risky input is
  *denied*: the tool never runs. File-path params (`file_path`, `path`, ...)
  are skipped, because a filesystem path is not injection content.
- **PostToolUse** screens the tool's *returned content* (`tool_response` — the
  page text a `WebFetch` pulled back, a file a `Read` loaded, an MCP tool's
  output). This is the indirect-prompt-injection surface: a malicious
  instruction hidden in third-party content. The tool already ran, so this
  cannot un-run it, but the hook returns `decision: "block"` plus
  `additionalContext`, so Claude is told the result is untrusted and does not
  act on the embedded instructions.

Both reuse the Content Guard engine and the `~/.agent-guard/content_guard.toml`
config — the same trust list, threshold, and `block`/`warn` mode as every other
Agent Guard integration.

## Install

Two halves: this plugin (the Claude Code seam) and the `agent-guard-plugins`
Python package (the screening engine).

```bash
pip install agent-guard-plugins
```

Then load the plugin into Claude Code. For local use / testing:

```bash
claude --plugin-dir /path/to/agent-guard-plugins/claude-code-plugin
```

For a persistent install, add the repo as a plugin marketplace and install
`agent-guard` through `/plugin`:

```
/plugin marketplace add dannyliv/agent-guard-plugins
/plugin install agent-guard
```

Any plugin can be installed straight from its Git repository whether or not it
is listed in the official Anthropic plugin directory. See the
[Claude Code plugin docs](https://code.claude.com/docs/en/plugins).

## How the bridge works

The hook command (`hooks/agent-guard-hook.sh`) is a thin shell seam. Claude
Code spawns it per tool call with the event JSON on stdin; it runs the Python
module `agent_guard_plugins.integrations.cli_hook_bridge`, which screens the
content and writes the decision JSON to stdout.

The same bridge serves the OpenAI Codex CLI — Codex's PreToolUse / PostToolUse
hook contract is identical.

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `AGENT_GUARD_PYTHON` | `python3` | Python executable that has `agent-guard-plugins` installed. |
| `AGENT_GUARD_CLI_HOOK_DISABLED` | unset | Set to `1`/`true` to load the plugin but screen nothing (kill switch). |

Screening policy (trust list, block threshold, `block`/`warn` mode) is tuned in
`~/.agent-guard/content_guard.toml` — see the main README's Content Guard
section.

## Fail-open

If Python is missing, the package is not installed, the model fails to load, or
the bridge times out, the hook returns an empty decision and the tool call
proceeds. A broken guard never wedges Claude Code.

## Maintainer and license

Maintained by [@dannyliv](https://github.com/dannyliv). Report issues or
vulnerabilities on the [main repository](https://github.com/dannyliv/agent-guard-plugins).
Licensed under Apache-2.0.
