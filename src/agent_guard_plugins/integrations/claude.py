"""Anthropic Claude middleware. Pre-flights every user message through Agent Guard.

Usage:
    from anthropic import Anthropic
    from agent_guard_plugins.integrations.claude import guarded_messages_create

    client = Anthropic()
    response = guarded_messages_create(
        client, model="claude-sonnet-4-6", max_tokens=1024,
        messages=[{"role": "user", "content": user_text}],
        on_detection=lambda r, t: print(f"BLOCKED: {r.reason()} :: {t[:80]}"),
    )

Returns the same shape as `client.messages.create()`. If blocked, returns a
synthetic refusal response with `.agent_guard` attached.
"""
from __future__ import annotations
import warnings
from typing import Callable
from ..core import guard, GuardResult


def guarded_messages_create(
    client, *,
    on_detection: Callable[[GuardResult, str], None] | None = None,
    block_threshold: float = 0.5,
    refusal_text: str = "I can't help with that request.",
    **create_kwargs,
):
    if create_kwargs.get("stream", False):
        raise NotImplementedError(
            "agent-guard-plugins does not support streaming in v0.1. "
            "Disable streaming or call core.guard() manually on each piece of content."
        )
    msgs = create_kwargs.get("messages", [])
    for msg in msgs:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            text = content
        else:
            text_parts = []
            for c in content:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text":
                    text_parts.append(c.get("text", ""))
                else:
                    warnings.warn(
                        "Non-text content was not classified by Agent Guard.",
                        stacklevel=2,
                    )
            text = " ".join(text_parts)
        result = guard(text, threshold=block_threshold, source="claude_middleware")
        if result.flagged:
            if on_detection:
                on_detection(result, text)
            class _Block:
                def __init__(self, t): self.type, self.text = "text", t
            class _Response:
                def __init__(self):
                    self.id = "agent-guard-blocked"
                    self.type = "message"
                    self.role = "assistant"
                    self.model = create_kwargs.get("model", "agent-guard")
                    self.content = [_Block(refusal_text)]
                    self.stop_reason = "agent_guard_blocked"
                    self.usage = type("U", (), {"input_tokens": 0, "output_tokens": 0})()
                    self.agent_guard = result
            return _Response()
    return client.messages.create(**create_kwargs)
