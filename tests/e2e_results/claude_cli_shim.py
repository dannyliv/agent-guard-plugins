"""Real Claude inference shim for the agent-guard-plugins Claude adapter e2e.

No Anthropic API key is available in this environment, so this shim wraps the
locally installed Claude CLI (`claude -p`) behind a duck-typed object that
matches the slice of the Anthropic SDK the adapter touches: a `.messages.create`
method that returns an object with `.id`, `.type`, `.role`, `.content`
(list of text blocks), `.stop_reason`, and `.model`.

`guarded_messages_create` only needs `client.messages.create(**kwargs)`; this
shim satisfies that contract and routes the prompt through a real Claude
inference path (the local CLI), so the e2e exercises the adapter against real
Claude output rather than a mock.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

CLAUDE_CLI = "/Users/danny/.local/bin/claude"


@dataclass
class _TextBlock:
    text: str
    type: str = "text"


@dataclass
class _Message:
    id: str
    content: list
    model: str
    type: str = "message"
    role: str = "assistant"
    stop_reason: str = "end_turn"
    usage: object = field(default=None)


class _Messages:
    def create(self, *, model: str, messages: list, max_tokens: int = 256, **_):
        # Pull the last user message text; same extraction the adapter uses.
        prompt = ""
        for m in messages:
            if m.get("role") == "user":
                c = m.get("content", "")
                prompt = c if isinstance(c, str) else " ".join(
                    p.get("text", "") for p in c if isinstance(p, dict)
                )
        out = subprocess.run(
            [CLAUDE_CLI, "-p"], input=prompt, capture_output=True,
            text=True, timeout=120,
        )
        reply = out.stdout.strip() or "(empty)"
        return _Message(id="msg_cli_real", content=[_TextBlock(reply)], model=model)


class ClaudeCLIClient:
    """Duck-typed Anthropic client backed by the local Claude CLI."""

    def __init__(self):
        self.messages = _Messages()
