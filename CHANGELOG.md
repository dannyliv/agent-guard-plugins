# Changelog

All notable changes to `agent-guard-plugins`.

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
