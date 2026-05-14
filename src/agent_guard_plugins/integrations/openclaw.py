"""OpenCLAW pre-action hook.

OpenCLAW (openclaw.ai) is an open-source local AI assistant by Peter Steinberger.
It supports 50+ integrations and runs locally on Mac, Windows, and Linux.

Designed to run inside the OpenCLAW agent before any tool call that consumes
external/untrusted content (email body, web page text, GitHub issue title, MCP
tool description, ClawHub skill manifest).

Wire as a hook in OpenCLAW's middleware chain. If flagged, the action is denied
and the event is logged for the dashboard.

The indirect prompt-injection attack surface includes these channels:
- email_summarize
- link_preview_render
- issue_triage
- skill_install
- mcp_tool_load
- web_page_summarize

Use `action_kind` to label which channel the content came from.
"""
from __future__ import annotations
import warnings
from dataclasses import dataclass
from ..core import guard


@dataclass
class HookDecision:
    allow: bool
    reason: str
    probability: float
    owasp: list[str]
    atlas: list[str]


def preaction_hook(content: str, *,
                   action_kind: str = "unknown",
                   threshold: float = 0.4) -> HookDecision:
    """Inspect untrusted content before OpenCLAW executes an action on it."""
    if not isinstance(content, str):
        warnings.warn(
            "Non-text content was not classified by Agent Guard.",
            stacklevel=2,
        )
        content = str(content)
    r = guard(content, threshold=threshold, source=f"openclaw:{action_kind}")
    return HookDecision(
        allow=not r.flagged,
        reason=r.reason(),
        probability=r.is_injection_prob,
        owasp=r.owasp,
        atlas=r.atlas,
    )
