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

## Claude — SDK middleware

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

## Claude — auto-wiring plugin (Claude Code)

Fully wired and verified live. The agent-guard Claude Code plugin
(`claude-code-plugin/`) is a real Claude Code plugin: a validated
`.claude-plugin/plugin.json` manifest plus a `hooks/hooks.json` that registers
**PreToolUse and PostToolUse** hooks. `tests/test_e2e_claude_plugin.py` loads
it into the real `claude` CLI via `--plugin-dir`, validates the manifest with
`claude plugin validate`, and drives real tool calls:

- benign file Read -> both hooks fire and return success, nothing blocked;
- injection-laden file Read -> the PreToolUse hook allows the path (a path is
  not injection content), the PostToolUse hook flags the poisoned file content
  (live V3.2 classifier, score ~1.0) and returns `decision: "block"` +
  `additionalContext`, so Claude is told the result is untrusted and does not
  act on the embedded instructions.

Design note: PreToolUse screens the tool *input* (a WebFetch prompt, a Bash
command) — the direct-injection surface. PostToolUse screens the tool *result*
(`tool_response` — page text, file contents, MCP output) — the
indirect-injection surface. Claude Code names the result field `tool_response`
(not the generic `tool_result`); the bridge accepts both. File-path-type input
keys (`file_path`, `path`, ...) are skipped at PreToolUse to avoid false
positives on paths that happen to contain words like "inject".

Not exercised: a full multi-turn agent run with a model backend driving many
tool calls. The hook contract (event in, decision out) is the load-bearing
surface and it is covered end to end.

## Codex — pre-exec wrapper

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

## Codex — auto-wiring hook (Codex CLI lifecycle hooks)

Fully wired and verified live. The Codex CLI auto-discovers lifecycle hooks
from `~/.codex/hooks.json`; there is no plugin manifest or `${PLUGIN_ROOT}`
placeholder, so the auto-wiring is a one-line install: `agent-guard-codex-install`
writes `~/.codex/hooks.json` (PreToolUse + PostToolUse entries) plus the hook
script. `tests/test_e2e_codex_hook.py` runs the real installer into a temp
`CODEX_HOME` and spawns the installed hook script exactly as Codex would —
feeding it a real PreToolUse event on stdin, reading the decision JSON back,
with the live V3.2 classifier inside the bridge. Benign call allowed, injection
call denied.

Not exercised live: starting the `codex` binary so Codex itself spawns the
hook. The hook contract is identical to Claude Code's (same `hooks.json`
schema, same stdin/stdout JSON), the Claude Code e2e exercises the host-spawns-
hook path against a real host, and the Codex harness exercises the
installer + hook-script + classifier chain. The only unverified link is Codex's
internal hook dispatch, which is Codex's code, not agent-guard's.

## Hermes — generic LLM wrapper

Fully wired on real GPU hardware. Real `NousResearch/Hermes-3-Llama-3.2-3B`
weights + tokenizer were loaded on a RunPod RTX 5090, wrapped with
`GuardedChatModel`, and run for real: the benign prompt produced real generated
text ("Paris..."), the injection prompt was blocked with model inference
suppressed. Evidence: `e2e_results/hermes_e2e.json`.

The pytest check (`test_e2e_hermes.py`) validates that captured JSON rather than
re-running on GPU, since CI has no GPU. To re-run the real model leg, execute
`e2e_results/hermes_pod/run_hermes_e2e.py` on any CUDA box.

## Hermes — auto-wiring plugin (Hermes Agent framework)

Fully wired and verified live. The *Hermes Agent* framework
(NousResearch/hermes-agent, distinct from the Hermes-3 LLM weights above) has a
first-class Python plugin system. The agent-guard plugin
(`agent_guard_plugins.integrations.hermes_plugin`) is discovered through the
`hermes_agent.plugins` entry point declared in `pyproject.toml`; its
`register(ctx)` registers a `pre_tool_call` hook (screens tool input, blocks
risky calls) and a `transform_tool_result` hook (screens tool output, replaces
flagged content with a sanitized placeholder).

`tests/test_e2e_hermes_plugin.py` loads the genuine hermes-agent
`PluginManager`, discovers the plugin through the real entry-point loader, and
drives a tool call through the real `get_pre_tool_call_block_message()` gate —
the function Hermes itself calls before every tool runs — with the live V3.2
classifier. Benign call allowed, injection call blocked with an agent-guard
message.

Hermes design note: standalone plugins are opt-in (`hermes plugins enable
agent-guard`); there is no force-on for standalone plugins, by Hermes design.
This is the most-automatic wiring Hermes supports — once the pip package is
installed, no directory install or code change is needed, just the one enable
command. The e2e harness loads the plugin directly via `PluginManager` to
exercise the discovery + hook path without needing the interactive enable step.

Not exercised live: a full Hermes agent turn with a model backend. The hook
contract (Hermes calls the gate, the gate runs the plugin hook, the hook
returns a block directive) is the load-bearing surface and it is covered end to
end against real Hermes code.

## Adapter bug found and fixed during this run

`core.py` passed `reference_compile=False` as a `from_pretrained` model kwarg.
On transformers 5.x, `ModernBertForSequenceClassification.__init__()` rejects
that kwarg and the classifier fails to load. `reference_compile` is a ModernBERT
*config* field, not a constructor argument. Fixed by setting it on
`model.config` after load instead of passing it as a kwarg. Verified working on
both transformers 4.57.x (local) and 5.8.x (the RunPod pod).
