"""Agent Guard Plugins — drop-in PI guards for AI agents.

Public API:
    from agent_guard_plugins import guard, GuardResult, LABELS, OWASP, ATLAS
"""
from .core import guard, guard_batch, GuardResult, LABELS, OWASP, ATLAS

__version__ = "0.1.1"
__all__ = ["guard", "guard_batch", "GuardResult", "LABELS", "OWASP", "ATLAS"]
