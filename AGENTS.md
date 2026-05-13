# AGENTS.md — context for AI agents working on this repo

If you're an AI agent dispatched to modify or extend this repo, read this first.

## What this repo is

A Python package (`agent-guard-plugins`) that wraps the prompt-injection classifier published at [`dannyliv/agent-guard-modernbert-base`](https://huggingface.co/dannyliv/agent-guard-modernbert-base). It exposes a single `guard()` function plus four platform-specific middleware modules.

## What this repo is NOT

- Training code (lives in the SEPARATE private repo `dannyliv/agent-guard`).
- The model itself (lives on Hugging Face).
- A general-purpose safety toolkit. It does one thing: classify input text as injection / benign.

## Layout

```
src/agent_guard_plugins/
├── __init__.py        # public API: guard, GuardResult, LABELS, OWASP, ATLAS
├── core.py            # the guard() function + SQLite logging + lazy HF model load
├── dashboard/
│   └── app.py         # Flask viewer of ~/.agent-guard/detections.sqlite
└── integrations/
    ├── claude.py      # Anthropic SDK middleware
    ├── openai_codex.py # OpenAI SDK + Codex CLI middleware
    ├── hermes.py      # local HF causal LM wrapper
    └── openclaw.py    # OpenCLAW pre-action hook
tests/
└── test_basic.py
```

## Conventions

- All integrations import `from ..core import guard, GuardResult`. Do not duplicate the guard() logic.
- All integrations accept `threshold` (float, default 0.4) and an `on_detection` callback.
- All integrations log under a distinct `source=` so the dashboard can attribute detections.
- Public model artifacts are pinned in `core.DEFAULT_ADAPTER` and `core.DEFAULT_BASE`. Override via env (`AGENT_GUARD_MODEL`, `AGENT_GUARD_THRESHOLD`).

## How to add a new platform

1. Create `src/agent_guard_plugins/integrations/<platform>.py`.
2. Wrap the platform's user-message entry point. Call `guard(text, source="<platform>")` first.
3. If `result.flagged`, return a synthetic refusal response matching the platform's expected shape.
4. Add a `pytest` import test in `tests/test_basic.py`.
5. Add a section to `README.md` with a 5-line usage snippet.

## Gotchas

- ModernBERT requires `attn_implementation="eager"` and `reference_compile=False` on load (`transformers 4.48` auto-compile path has a known dynamo bug). `core.py` already sets these.
- `huggingface_hub` must be `<1.0` for `transformers 4.48` compatibility. If you bump deps, pin `huggingface_hub<1.0` in `pyproject.toml`.
- First call to `guard()` downloads ~10MB LoRA + ~150MB base. ~30s on cold cache. Subsequent calls are 50-150ms on CPU (18ms with ONNX).
- The SQLite log writer uses `check_same_thread=False`. Multiprocess concurrent writes are NOT safe; one process at a time.

## How to release

1. Bump `__version__` in `__init__.py` AND `version` in `pyproject.toml`.
2. `python -m build` (requires `pip install build`).
3. `twine upload dist/*` (after `pip install twine`).

## Related projects

- Training pipeline: `dannyliv/agent-guard` (private — same author).
- Model card: https://huggingface.co/dannyliv/agent-guard-modernbert-base
- ONNX export: `https://huggingface.co/dannyliv/agent-guard-modernbert-base/blob/main/onnx/model.onnx`

## Author intent

The plugin repo is the SHIPPING surface. Keep it tight, pip-installable, and platform-agnostic. The training repo is heavier; do not import from it.
