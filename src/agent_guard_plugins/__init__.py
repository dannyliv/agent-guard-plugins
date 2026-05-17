"""Agent Guard Plugins — drop-in PI guards for AI agents.

Public API:
    from agent_guard_plugins import guard, GuardResult, LABELS, OWASP, ATLAS
    from agent_guard_plugins import ContentGuard, ContentGuardConfig
"""
from .content_guard import (
    BlockedContentError,
    ContentGuard,
    ContentGuardConfig,
    ScreenResult,
)
from .core import ATLAS, LABELS, OWASP, GuardResult, guard, guard_batch

__version__ = "0.3.0"
__all__ = [
    "guard",
    "guard_batch",
    "GuardResult",
    "LABELS",
    "OWASP",
    "ATLAS",
    "ContentGuard",
    "ContentGuardConfig",
    "ScreenResult",
    "BlockedContentError",
]
