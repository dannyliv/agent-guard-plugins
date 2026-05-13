"""OpenAI / Codex middleware. Pre-flights every user message through Agent Guard.

Works against both:
- the OpenAI Python SDK (`from openai import OpenAI`)
- the OpenAI Codex CLI (via the `openai` SDK under the hood)

Usage:
    from openai import OpenAI
    from agent_guard_plugins.integrations.openai_codex import guarded_chat_completions_create

    client = OpenAI()
    resp = guarded_chat_completions_create(
        client, model="gpt-5", messages=[{"role": "user", "content": text}],
    )
"""
from __future__ import annotations
from typing import Callable
from ..core import guard, GuardResult


def guarded_chat_completions_create(
    client, *,
    on_detection: Callable[[GuardResult, str], None] | None = None,
    block_threshold: float = 0.5,
    refusal_text: str = "I can't help with that request.",
    **create_kwargs,
):
    msgs = create_kwargs.get("messages", [])
    for msg in msgs:
        if msg.get("role") != "user":
            continue
        text = msg.get("content", "")
        if not isinstance(text, str):
            continue
        result = guard(text, threshold=block_threshold, source="openai_codex_middleware")
        if result.flagged:
            if on_detection:
                on_detection(result, text)
            class _Choice:
                def __init__(self):
                    self.index = 0
                    self.finish_reason = "agent_guard_blocked"
                    self.message = type("M", (), {"role": "assistant", "content": refusal_text})()
            class _Response:
                def __init__(self):
                    self.id = "agent-guard-blocked"
                    self.model = create_kwargs.get("model", "agent-guard")
                    self.choices = [_Choice()]
                    self.usage = type("U", (), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})()
                    self.agent_guard = result
            return _Response()
    return client.chat.completions.create(**create_kwargs)


# Codex CLI convenience: a function suitable for use as a pre-action hook
# in a custom Codex wrapper script. Returns (allow: bool, reason: str).
def codex_preexec(text: str, threshold: float = 0.4) -> tuple[bool, str]:
    """Designed for `codex` CLI integration. Call before executing each user prompt.

        from agent_guard_plugins.integrations.openai_codex import codex_preexec
        allow, reason = codex_preexec(user_input)
        if not allow:
            print(f"agent-guard blocked: {reason}")
            sys.exit(1)
    """
    r = guard(text, threshold=threshold, source="codex_preexec")
    return (not r.flagged), r.reason()
