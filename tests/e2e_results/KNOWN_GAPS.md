# Known gaps in the real end-to-end tests

The four `tests/test_e2e_*.py` tests exercise each platform against a real
runtime. This file records exactly what stays uncovered and why, so the
results are not over-read.

## OpenCLAW

Fully wired. The agent-guard OpenCLAW plugin
(`e2e_results/openclaw_plugin/agent-guard-openclaw-plugin.mjs`) is a real
OpenCLAW plugin built with the genuine `openclaw/plugin-sdk` `definePluginEntry`
API. It registers a `before_tool_call` hook through `api.on(...)`, and the
harness fires the documented `PluginHookBeforeToolCallEvent` shape and asserts
the documented `{ block, blockReason }` result.

Note on architecture: OpenCLAW is a Node/TypeScript platform, not a Python one.
There is no `pip install openclaw` and no Python hook API. A Python
`preaction_hook` cannot register directly as an OpenCLAW hook. The integration
is therefore a thin TypeScript plugin that bridges to the Python
`preaction_hook` via a subprocess. This is the realistic wiring and it is fully
exercised. The earlier "register `preaction_hook` as an OpenCLAW hook" framing
assumed a Python hook surface that OpenCLAW does not have; the bridge plugin is
the correct contract.

Not exercised: a full LLM-backed OpenCLAW gateway driving an end-to-end agent
turn. That needs a model backend and adds nothing to hook verification -- the
hook contract (`before_tool_call` event in, `{block}` decision out) is the
load-bearing surface and it is covered.

## Claude

Real inference path covered, with a backend caveat. No `ANTHROPIC_API_KEY` was
available in the test environment, so the test used the local Claude CLI
(`claude -p`) behind a duck-typed client shim (`e2e_results/claude_cli_shim.py`)
that matches the slice of the Anthropic SDK the adapter touches
(`client.messages.create`). The benign prompt was routed to real Claude
inference; the injection prompt was blocked with the real call suppressed.

Not exercised: the `anthropic` Python SDK's exact `Message` object. The shim
reproduces its shape (`.id`, `.type`, `.role`, `.content` text blocks,
`.stop_reason`). When an API key is present the test auto-selects the real SDK
backend instead (one low-cost haiku call, injection path = zero spend).

## Codex

Block path fully covered, benign model leg auth-gated. The real `codex-guarded`
wrapper (`e2e_results/codex_wrapper/codex-guarded`) runs `codex_preexec` before
the real OpenAI Codex CLI binary (`@openai/codex` 0.130.0).

- Injection path: `codex_preexec` returns `(False, reason)`, the wrapper exits
  non-zero, and the real `codex` binary is never invoked. Fully covered, zero
  spend, no OpenAI auth needed.
- Benign path: verified up to the real `codex` binary handoff -- the wrapper
  passes the gate and `codex exec` starts (it prints its banner and resolves
  `model: gpt-5.5`). The actual model response is **not covered** because no
  OpenAI credentials were available. The pre-exec hook, which is the integration
  surface under test, fires and allows correctly.

## Hermes

Fully wired on real GPU hardware. Real `NousResearch/Hermes-3-Llama-3.2-3B`
weights + tokenizer were loaded on a RunPod RTX 5090, wrapped with
`GuardedChatModel`, and run for real: the benign prompt produced real generated
text ("Paris..."), the injection prompt was blocked with model inference
suppressed. Evidence: `e2e_results/hermes_e2e.json`.

The pytest check (`test_e2e_hermes.py`) validates that captured JSON rather than
re-running on GPU, since CI has no GPU. To re-run the real model leg, execute
`e2e_results/hermes_pod/run_hermes_e2e.py` on any CUDA box.

## Adapter bug found and fixed during this run

`core.py` passed `reference_compile=False` as a `from_pretrained` model kwarg.
On transformers 5.x, `ModernBertForSequenceClassification.__init__()` rejects
that kwarg and the classifier fails to load. `reference_compile` is a ModernBERT
*config* field, not a constructor argument. Fixed by setting it on
`model.config` after load instead of passing it as a kwarg. Verified working on
both transformers 4.57.x (local) and 5.8.x (the RunPod pod).
