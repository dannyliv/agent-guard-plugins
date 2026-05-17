"""Content Guard — screen, block, and notify on risky web / unauthorized content.

Built on top of `guard()`, the V3.2 prompt-injection detector. Content Guard
adds a policy layer around it:

- A *trust list* of authorized channels (domains, tool names, channel ids).
  Content from a trusted source skips the model entirely.
- A configurable block threshold and a `block` / `warn` mode.
- A notify callback fired on every risky hit.
- A hook (`guarded()` / `@content_hook`) that wraps any content-returning
  callable so screening happens automatically on its return value.

Typical use: wrap a web fetch or a tool that reads third-party content. Pages
from unauthorized sources get screened; anything scoring at or above the
threshold is blocked (raise `BlockedContentError`) or, in `warn` mode, returned
with a warning logged and the notify callback fired.

Configure from code or from a file at `~/.agent-guard/content_guard.toml`
(TOML; a `.json` file at the same stem is also accepted) so the trust list,
threshold, and mode are tunable without touching code.

    from agent_guard_plugins.content_guard import ContentGuard, ContentGuardConfig

    cg = ContentGuard(ContentGuardConfig(
        authorized_channels={"internal-wiki", "docs.example.com"},
        block_threshold=0.85,
        mode="block",
    ))

    @cg.content_hook(source_arg="url")
    def fetch(url): ...

Blocked items are also recorded to the detections SQLite log, so they show up
in the `agent-guard-dashboard` feed alongside ordinary `guard()` detections.
"""
from __future__ import annotations

import json
import logging
import pathlib
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

from .core import GuardResult, _log_detection, guard

logger = logging.getLogger("agent_guard.content_guard")

# Default config file location. TOML is the primary format; a `.json` file at
# the same stem is also honored for environments without a TOML writer.
DEFAULT_CONFIG_PATH = pathlib.Path.home() / ".agent-guard" / "content_guard.toml"

# Returned in `warn`/`block` flows when content is blocked but the caller asked
# for a sanitized placeholder rather than an exception.
SANITIZED_PLACEHOLDER = (
    "[agent-guard: content removed — flagged as a possible prompt-injection "
    "attempt from an unauthorized source]"
)


class BlockedContentError(RuntimeError):
    """Raised by a `block`-mode hook when screened content is risky.

    Carries the `ScreenResult` so a caller catching it can inspect the score,
    source, and reason.
    """

    def __init__(self, result: ScreenResult):
        self.result = result
        super().__init__(
            f"blocked risky content from source={result.source!r}: "
            f"{result.reason} (score={result.score:.3f})"
        )


@dataclass
class ScreenResult:
    """Outcome of screening one piece of content.

    - `allowed`  : True if the content may flow on to the agent/model.
    - `blocked`  : True if it was withheld (always the inverse of `allowed`).
    - `score`    : injection probability from the detector (0.0 for trusted
                   sources that skipped the model).
    - `reason`   : short human-readable explanation.
    - `source`   : the source identifier passed to `screen()`.
    - `trusted`  : True if the source was on the authorized list (no model run).
    - `web`      : True if the content was treated as web-sourced.
    - `guard_result` : the underlying `GuardResult`, or None for trusted skips.
    """

    allowed: bool
    blocked: bool
    score: float
    reason: str
    source: str | None
    trusted: bool = False
    web: bool = False
    guard_result: GuardResult | None = None


@dataclass
class ContentGuardConfig:
    """Policy for `ContentGuard`.

    - `authorized_channels` : trusted source identifiers (domains, tool names,
      channel ids). Content whose `source` is in this set skips screening.
    - `block_threshold` : injection probability at or above which content is
      blocked. Defaults to 0.85 — deliberately higher than `guard()`'s 0.4
      flag threshold, because blocking is more disruptive than flagging.
    - `mode` : `"block"` raises `BlockedContentError` (or returns the sanitized
      placeholder) on a risky hit; `"warn"` lets the content through but logs
      and notifies.
    - `notify` : optional callable invoked with the `ScreenResult` on every
      risky hit (both modes). Use it to page, post to Slack, etc.
    - `screen_web` : when True (default), content marked web-sourced is always
      screened even if its source string happens to be on the trust list.
    - `log_path` : SQLite detections log; blocked items are written here so the
      dashboard shows them. None uses the package default.
    """

    authorized_channels: set[str] = field(default_factory=set)
    block_threshold: float = 0.85
    mode: str = "block"
    notify: Callable[[ScreenResult], None] | None = None
    screen_web: bool = True
    log_path: pathlib.Path | None = None

    def __post_init__(self):
        if self.mode not in ("block", "warn"):
            raise ValueError(f"mode must be 'block' or 'warn', got {self.mode!r}")
        if not 0.0 <= self.block_threshold <= 1.0:
            raise ValueError(
                f"block_threshold must be in [0, 1], got {self.block_threshold}"
            )
        # Accept any iterable of identifiers; normalize to a set of strings.
        if not isinstance(self.authorized_channels, set):
            self.authorized_channels = {str(c) for c in self.authorized_channels}

    @classmethod
    def from_file(
        cls,
        path: str | pathlib.Path | None = None,
        *,
        notify: Callable[[ScreenResult], None] | None = None,
    ) -> ContentGuardConfig:
        """Load config from a TOML or JSON file.

        `path` defaults to `~/.agent-guard/content_guard.toml`. If that file is
        absent a default-valued config is returned, so a missing file is not an
        error. A `notify` callable cannot be serialized to a file; pass it here
        to attach it to the loaded config.

        Recognized keys: `authorized_channels` (list), `block_threshold`
        (float), `mode` (str), `screen_web` (bool), `log_path` (str).
        """
        path = pathlib.Path(path) if path else DEFAULT_CONFIG_PATH
        data: dict[str, Any] = {}
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                data = json.loads(text)
            else:
                import tomllib

                data = tomllib.loads(text)
        elif path.suffix == ".toml":
            # Fall back to a sibling .json if the .toml is missing.
            alt = path.with_suffix(".json")
            if alt.exists():
                data = json.loads(alt.read_text(encoding="utf-8"))

        kwargs: dict[str, Any] = {}
        if "authorized_channels" in data:
            kwargs["authorized_channels"] = {
                str(c) for c in data["authorized_channels"]
            }
        if "block_threshold" in data:
            kwargs["block_threshold"] = float(data["block_threshold"])
        if "mode" in data:
            kwargs["mode"] = str(data["mode"])
        if "screen_web" in data:
            kwargs["screen_web"] = bool(data["screen_web"])
        if "log_path" in data and data["log_path"]:
            kwargs["log_path"] = pathlib.Path(str(data["log_path"]))
        if notify is not None:
            kwargs["notify"] = notify
        return cls(**kwargs)


class ContentGuard:
    """Screens content against a `ContentGuardConfig` policy.

    `screen()` is the core call. `guarded()` and `content_hook()` wrap a
    content-returning callable so screening happens automatically.
    """

    def __init__(self, config: ContentGuardConfig | None = None):
        self.config = config or ContentGuardConfig()

    # -- core ---------------------------------------------------------------

    def is_authorized(self, source: str | None) -> bool:
        """True if `source` is a trusted channel that skips screening."""
        return source is not None and source in self.config.authorized_channels

    def screen(
        self,
        content: str,
        source: str | None = None,
        *,
        web: bool = False,
    ) -> ScreenResult:
        """Screen one piece of content.

        - If `source` is an authorized channel (and not overridden by a
          web-source rule), the content is allowed without running the model.
        - Otherwise the PI detector runs. A score at or above
          `config.block_threshold` blocks the content and fires `notify`.

        `web=True` marks the content as web-sourced. With `config.screen_web`
        on (default), web content is always screened even if its `source` is
        on the trust list — a defense against trusting an attacker-controlled
        page just because its domain was allow-listed elsewhere.
        """
        cfg = self.config
        force_screen = web and cfg.screen_web

        if self.is_authorized(source) and not force_screen:
            return ScreenResult(
                allowed=True,
                blocked=False,
                score=0.0,
                reason=f"trusted source {source!r}, screening skipped",
                source=source,
                trusted=True,
                web=web,
            )

        if not content or not isinstance(content, str):
            return ScreenResult(
                allowed=True,
                blocked=False,
                score=0.0,
                reason="empty or non-text content, nothing to screen",
                source=source,
                web=web,
            )

        # Run the existing detector. Tag the log source so the dashboard can
        # attribute it; guard() also writes its own detection row.
        log_source = f"content-guard:{source}" if source else "content-guard"
        gr = guard(content, source=log_source)
        score = gr.is_injection_prob
        risky = score >= cfg.block_threshold

        if not risky:
            return ScreenResult(
                allowed=True,
                blocked=False,
                score=score,
                reason=(
                    f"score {score:.3f} below block_threshold "
                    f"{cfg.block_threshold:.2f}"
                ),
                source=source,
                web=web,
                guard_result=gr,
            )

        # Risky: block in block-mode, allow-with-warning in warn-mode.
        blocked = cfg.mode == "block"
        detail = gr.reason()
        reason = (
            f"score {score:.3f} >= block_threshold {cfg.block_threshold:.2f} "
            f"({detail})"
        )
        result = ScreenResult(
            allowed=not blocked,
            blocked=blocked,
            score=score,
            reason=reason,
            source=source,
            web=web,
            guard_result=gr,
        )
        self._on_risky(content, result)
        return result

    # -- hook / wrapper -----------------------------------------------------

    def guarded(
        self,
        fn: Callable[..., Any],
        *,
        source: str | None = None,
        source_arg: str | None = None,
        web: bool = False,
    ) -> Callable[..., Any]:
        """Wrap a content-returning callable so its result is screened.

        The wrapped function runs, then its return value is screened with
        `screen()`. In `block` mode a risky result raises `BlockedContentError`;
        in `warn` mode the (possibly risky) content is returned unchanged.

        Source resolution, in priority order:
        1. `source` — a fixed identifier for every call.
        2. `source_arg` — the name of a parameter of `fn` whose value is the
           per-call source (e.g. `source_arg="url"` for a fetch function).
        3. otherwise the source is `None` (always screened).

        `web=True` marks every return value as web-sourced.
        """
        import inspect

        sig = None
        if source_arg is not None:
            try:
                sig = inspect.signature(fn)
            except (ValueError, TypeError):
                sig = None

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            call_source = source
            if call_source is None and source_arg is not None and sig is not None:
                try:
                    bound = sig.bind_partial(*args, **kwargs)
                    bound.apply_defaults()
                    raw = bound.arguments.get(source_arg)
                    if raw is not None:
                        call_source = str(raw)
                except TypeError:
                    call_source = None

            content = fn(*args, **kwargs)
            return self.apply(content, source=call_source, web=web)

        wrapper.__wrapped_by_content_guard__ = True  # type: ignore[attr-defined]
        return wrapper

    def content_hook(
        self,
        *,
        source: str | None = None,
        source_arg: str | None = None,
        web: bool = False,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator form of `guarded()`.

            @cg.content_hook(source_arg="url", web=True)
            def fetch(url): ...
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            return self.guarded(fn, source=source, source_arg=source_arg, web=web)

        return decorator

    def apply(
        self,
        content: str,
        source: str | None = None,
        *,
        web: bool = False,
    ) -> Any:
        """Screen `content` and enforce the policy.

        Returns the original content when allowed. When blocked: raises
        `BlockedContentError` in `block` mode, returns `SANITIZED_PLACEHOLDER`
        only if you would rather not raise — `block` mode raises by default.
        In `warn` mode the content is returned unchanged.
        """
        result = self.screen(content, source, web=web)
        if result.blocked:
            raise BlockedContentError(result)
        return content

    def sanitize(
        self,
        content: str,
        source: str | None = None,
        *,
        web: bool = False,
    ) -> tuple[str, ScreenResult]:
        """Like `apply()` but never raises.

        Returns `(content, result)` when allowed, or
        `(SANITIZED_PLACEHOLDER, result)` when the content is risky in
        `block` mode. Useful for pipelines that must not throw.
        """
        result = self.screen(content, source, web=web)
        if result.blocked:
            return SANITIZED_PLACEHOLDER, result
        return content, result

    # -- internals ----------------------------------------------------------

    def _on_risky(self, content: str, result: ScreenResult) -> None:
        """Log, record to the dashboard DB, and fire the notify callback."""
        verb = "BLOCKED" if result.blocked else "WARN"
        logger.warning(
            "content-guard %s source=%s score=%.3f reason=%s",
            verb,
            result.source,
            result.score,
            result.reason,
        )
        # Record blocked items to the detections SQLite log so they appear in
        # the dashboard feed. guard() already logged its own row; this adds an
        # explicit content-guard-attributed row marking the policy decision.
        if result.blocked and result.guard_result is not None:
            try:
                _log_detection(
                    content,
                    result.guard_result,
                    f"content-guard:blocked:{result.source}",
                )
            except Exception as e:  # pragma: no cover - logging must not break flow
                logger.warning("content-guard dashboard log failed: %s", e)

        if self.config.notify is not None:
            try:
                self.config.notify(result)
            except Exception as e:  # pragma: no cover - notify must not break flow
                logger.warning("content-guard notify callback failed: %s", e)


# Module-level convenience: a default guard plus thin wrappers, so callers who
# do not need a custom config can use Content Guard in one import.
_default_guard = ContentGuard()


def configure(
    config: ContentGuardConfig | None = None,
    *,
    from_file: bool = False,
) -> ContentGuard:
    """Set the module-level default `ContentGuard` and return it.

    Pass `from_file=True` to load `~/.agent-guard/content_guard.toml`.
    """
    global _default_guard
    if from_file and config is None:
        config = ContentGuardConfig.from_file()
    _default_guard = ContentGuard(config)
    return _default_guard


def screen(content: str, source: str | None = None, *, web: bool = False) -> ScreenResult:
    """Screen content with the module-level default `ContentGuard`."""
    return _default_guard.screen(content, source, web=web)


def guarded(fn: Callable[..., Any], **kwargs: Any) -> Callable[..., Any]:
    """Wrap `fn` with the module-level default `ContentGuard`."""
    return _default_guard.guarded(fn, **kwargs)


__all__ = [
    "BlockedContentError",
    "ContentGuard",
    "ContentGuardConfig",
    "ScreenResult",
    "SANITIZED_PLACEHOLDER",
    "DEFAULT_CONFIG_PATH",
    "configure",
    "screen",
    "guarded",
]
