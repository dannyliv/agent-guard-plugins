# Changelog

All notable changes to `agent-guard-plugins`.

## 0.5.0

### Added

Automatic Content Guard screening for **Claude Code, the OpenAI Codex CLI, and
the Hermes Agent framework** — the same no-manual-wrapping outcome the 0.4.0
OpenCLAW plugin gave OpenCLAW. Each platform's real auto-wiring mechanism is
used; no faked plugins.

- **Automatic Claude Code screening.** An installable Claude Code plugin
  (`claude-code-plugin/`): a `.claude-plugin/plugin.json` manifest plus a
  `hooks/hooks.json` that registers **PreToolUse and PostToolUse** hooks.
  Claude Code discovers and activates the plugin on install; the hooks then
  run on every tool call.
  - PreToolUse screens the tool *input* (a `WebFetch` prompt, a `WebSearch`
    query, a `Bash` command) and *denies* risky calls — the tool never runs.
  - PostToolUse screens the tool *result* (`tool_response` — fetched page
    text, file contents, MCP output), the indirect-prompt-injection surface,
    and returns `decision: "block"` so Claude is told not to act on flagged
    content.
- **Automatic Codex CLI screening.** A one-line installer
  (`agent-guard-codex-install`) writes `~/.codex/hooks.json` (PreToolUse +
  PostToolUse entries) plus the hook script. The Codex CLI auto-discovers
  lifecycle hooks from `~/.codex/hooks.json`; it has no plugin manifest, so a
  one-line install is the most-automatic wiring it supports. Codex's hook
  contract is identical to Claude Code's, so both share one bridge.
- **Automatic Hermes Agent screening.** An auto-registering plugin for the
  *Hermes Agent* framework (NousResearch/hermes-agent — the agent framework,
  not the Hermes-3 LLM weights the existing `GuardedChatModel` wraps). The
  package declares `agent_guard_plugins.integrations.hermes_plugin` under the
  `hermes_agent.plugins` entry-point group, so Hermes discovers it once the
  package is installed; `hermes plugins enable agent-guard` activates it.
  `agent-guard-hermes-install` also writes a directory-plugin form into
  `~/.hermes/plugins/`. The plugin registers a `pre_tool_call` hook (screens
  tool input, blocks risky calls via `{"action": "block", ...}`) and a
  `transform_tool_result` hook (screens tool output, replaces flagged content
  with a sanitized placeholder).
- `agent_guard_plugins.integrations.cli_hook_bridge`: the shared Python half
  of the Claude Code plugin and the Codex hook — a JSON-in / JSON-out
  screening function plus the `agent-guard-cli-hook` console script the host
  spawns per tool call. It handles both PreToolUse and PostToolUse.
- All integrations reuse the same `ContentGuard` engine and
  `~/.agent-guard/content_guard.toml` config as the OpenCLAW bridge — one
  trust list / threshold / mode tunes screening across every platform. Each
  fails open (a missing Python, model-load failure, or timeout never blocks a
  tool call) and ships a kill switch (`AGENT_GUARD_CLI_HOOK_DISABLED=1`,
  `AGENT_GUARD_HERMES_DISABLED=1`) — screening is on by default but not forced.
- File-path-type tool-input keys (`file_path`, `path`, ...) are skipped at the
  pre-call stage: a path is not injection content, and screening it caused
  false positives on paths containing words like "inject". The real untrusted
  content for a file-IO tool is its result, screened post-call.
- Tests: `tests/test_cli_hook_bridge.py` and `tests/test_hermes_plugin.py`
  cover the decision contract, trust list, fail-open, kill switch, the
  PreToolUse/PostToolUse split, and the path-skip behavior. Real-runtime e2e
  tests (`tests/test_e2e_claude_plugin.py`, `tests/test_e2e_codex_hook.py`,
  `tests/test_e2e_hermes_plugin.py`) exercise the shipped artifacts against the
  real `claude` CLI, the real Codex installer + hook script, and the genuine
  hermes-agent `PluginManager`, each with the live V3.2 classifier.

## 0.4.0

### Added

- **Automatic OpenCLAW screening.** An installable OpenCLAW plugin
  (`openclaw-plugin/`, published to npm as `agent-guard-openclaw`) that wires
  Content Guard into OpenCLAW with no code change. OpenCLAW discovers it via
  the `openclaw` field in `package.json` plus the `openclaw.plugin.json`
  manifest; `activation.onStartup: true` activates it at gateway startup.
  - The plugin registers a `before_tool_call` hook. On every tool call it
    collects the tool's textual params (web page text, search results, email
    body, GitHub issue text, MCP tool output) and screens them. Risky content
    blocks the tool call; authorized channels are skipped per the existing
    `~/.agent-guard/content_guard.toml` config. Web-sourced tools (fetch /
    search / browse) are always screened even when the source is trusted.
  - `agent_guard_plugins.integrations.openclaw_bridge`: the Python half of the
    plugin. A JSON-in / JSON-out screening function plus a console script
    (`agent-guard-openclaw`) that the Node plugin spawns once per tool call.
  - Both halves fail open: a missing Python, model-load failure, or timeout
    never blocks a tool call. `AGENT_GUARD_OPENCLAW_DISABLED=1` is a kill
    switch — screening is on by default but not forced.
- Tests for the auto-wiring: `tests/test_openclaw_bridge.py` (verdict
  contract, trust list, fail-open, kill switch, console-script stdin/stdout)
  and `openclaw-plugin/test/plugin.test.mjs` (real OpenCLAW SDK registration,
  `before_tool_call` screening, block/allow contract). The real-runtime e2e
  test now exercises the shipped plugin artifact directly.

## 0.3.1

### Fixed

- `ContentGuardConfig.from_file()` now loads TOML on Python 3.10. The bare
  `import tomllib` (Python 3.11+ stdlib) is replaced with a version-safe import
  that falls back to the `tomli` backport, now a conditional dependency on 3.10.

## 0.3.0

### Added

- **Content Guard** (`agent_guard_plugins.content_guard`), a configurable
  policy layer over `guard()` that screens, blocks, and notifies on risky
  content from web pages, tools, and other unauthorized channels.
  - `ContentGuardConfig`: an authorized-channels trust list (sources that skip
    screening), a `block_threshold` (default 0.85), a `block` / `warn` mode, a
    `notify` callback, and a `screen_web` flag. Loadable from
    `~/.agent-guard/content_guard.toml` (or a JSON file) via
    `ContentGuardConfig.from_file()`.
  - `ContentGuard.screen()` returns a `ScreenResult` (allowed/blocked, score,
    reason, source). Trusted sources are allowed without running the model;
    everything else runs the V3.2 detector.
  - A hook: `ContentGuard.guarded()` / `@ContentGuard.content_hook` wraps any
    content-returning callable so its output is screened automatically. Risky
    content raises `BlockedContentError` in `block` mode, or returns a
    sanitized placeholder via `sanitize()`.
  - Blocked items are recorded to the detections SQLite log and appear in the
    `agent-guard-dashboard` feed.
- `ContentGuard`, `ContentGuardConfig`, `ScreenResult`, and
  `BlockedContentError` are exported from the top-level package.

### Fixed

- The package version is now bumped in both `pyproject.toml` and
  `src/agent_guard_plugins/__init__.py`. The 0.2.0 release left
  `__init__.py.__version__` behind; both are kept in sync from 0.3.0 on.

## 0.2.0

The served classifier moved from V2 to V3.2 on both Hugging Face repos.

### Changed

- `guard()` now loads the V3.2 model. V3.2 fixes the V2 GCG jailbreak weakness:
  the precomputed-replay attack-success rate dropped from 100% to about 0 to 31
  percent. V3.2 also raises the benign false-positive rate over V2 (ModernBERT
  3.2 percent, DeBERTa 1.6 percent at threshold 0.5). The tradeoff is disclosed
  on both model cards. Threshold-tune against your own benign traffic, or use a
  higher threshold, if false positives matter for your deployment.
- The Hugging Face repos now ship a merged full model at the repo root. The
  default load path uses that merged model directly and no longer needs `peft`
  at runtime. The standalone LoRA adapter is still published under `adapter/`.

### Fixed

- `guard()` failed against the V3.2 repos with `Can't find 'adapter_config.json'`.
  V2 published the LoRA adapter at the repo root; V3.2 moved it to `adapter/`.
  The default path now loads the merged model from the repo root instead.
- `AGENT_GUARD_USE_ONNX=1` is now implemented. Earlier releases documented the
  flag but the ONNX code path did not exist. It loads the `onnx/` export and
  runs CPU inference at about 13 to 18 ms per call with no `torch` dependency.

### Added

- `AGENT_GUARD_USE_ADAPTER=1` loads the standalone LoRA adapter onto the base
  encoder, for users who want the adapter rather than the merged model.
- An empty `AGENT_GUARD_LOG_PATH` now disables detection logging, as documented.

## 0.1.2

- Initial PyPI release. Claude, OpenAI Codex, Hermes, and OpenCLAW middleware.
