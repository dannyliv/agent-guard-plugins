"""OpenCLAW pre-action hook.

Designed to run inside the OpenCLAW agent before any tool call that consumes
external/untrusted content (email body, web page text, GitHub issue title, MCP
tool description, ClawHub skill manifest).

Wire as a hook in OpenCLAW's middleware chain. If flagged, the action is denied
and the event is logged for the dashboard.

Background: OpenCLAW had 512 vulnerabilities pre-rebrand, with most of the
indirect prompt-injection attack surface in 6 channels:
- email_summarize  - link_preview_render
- issue_triage
- skill_install
- mcp_tool_load
- web_page_summarize

Use `action_kind` to label which channel the content came from.
"""
from __future__ import annotations
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
    r = guard(content, threshold=threshold, source=f"openclaw:{action_kind}")
    return HookDecision(
        allow=not r.flagged,
        reason=r.reason(),
        probability=r.is_injection_prob,
        owasp=r.owasp,
        atlas=r.atlas,
    )
