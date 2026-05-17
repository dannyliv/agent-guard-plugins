# Agent Guard — OpenAI Codex CLI plugin

Automatic prompt-injection screening for OpenAI Codex CLI tool calls. Once this
plugin is installed, every tool call is screened by Agent Guard's Content Guard
engine — no manual wrapping, no `AGENTS.md` step.

## What it does

The plugin bundles two lifecycle hooks in `hooks/hooks.json`:

- **PreToolUse** screens the tool's *input* params (a web fetch prompt, a
  search query, a shell command). This is the direct-injection surface — text
  a user or upstream content smuggled into the call. A risky input is
  *denied*: the tool never runs. File-path params (`file_path`, `path`, ...)
  are skipped, because a filesystem path is not injection content.
- **PostToolUse** screens the tool's *returned content* (the page text a web
  fetch pulled back, a file that was loaded, an MCP tool's output). This is the
  indirect-prompt-injection surface: a malicious instruction hidden in
  third-party content. The tool already ran, so this cannot un-run it, but the
  hook flags the result as untrusted so Codex does not act on the embedded
  instructions.

Both reuse the Content Guard engine and the `~/.agent-guard/content_guard.toml`
config — the same trust list, threshold, and `block`/`warn` mode as every other
Agent Guard integration.

## Install

Two halves: this plugin (the Codex seam) and the `agent-guard-plugins` Python
package (the screening engine).

```bash
pip install agent-guard-plugins
```

Then add the repository as a Codex plugin marketplace and install `agent-guard`:

```
codex plugin marketplace add dannyliv/agent-guard-plugins
codex plugin install agent-guard
```

The repo ships `.agents/plugins/marketplace.json` pointing at this
`codex-plugin/` directory, so Codex discovers the plugin once the marketplace
is added.

### One-line hook installer (alternative)

If you do not want a marketplace plugin, the Python package also ships a
one-line installer that writes the same hooks into `~/.codex/hooks.json`
directly:

```bash
agent-guard-codex-install
```

## Configuration

Screening is on by default. Environment variables:

- `AGENT_GUARD_PYTHON` — python executable with `agent_guard_plugins`
  installed. Default: `python3`.
- `AGENT_GUARD_CLI_HOOK_DISABLED=1` — kill switch: the hook loads but screens
  nothing.

Trust list, threshold, and `block`/`warn` mode are read from
`~/.agent-guard/content_guard.toml`.

## Fail-open behavior

If Python is missing, the package is not installed, or the screening bridge
errors, the hook prints `{}` (allow) and exits 0. A broken guard must never
wedge Codex.

## Maintainer

dannyliv — <https://github.com/dannyliv/agent-guard-plugins>. File issues at
<https://github.com/dannyliv/agent-guard-plugins/issues>.

## License

Apache-2.0.
