# Changelog

All notable changes to `agent-guard-plugins`.

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
