"""Per-platform middleware: import only the one you need.

    from agent_guard_plugins.integrations.claude import guarded_messages_create
    from agent_guard_plugins.integrations.openai_codex import guarded_chat_completions_create
    from agent_guard_plugins.integrations.hermes import GuardedChatModel
    from agent_guard_plugins.integrations.openclaw import preaction_hook

For OpenCLAW, automatic screening (no manual call) is available via the
installable OpenCLAW plugin under `openclaw-plugin/`; its Python half is
`agent_guard_plugins.integrations.openclaw_bridge`.
"""
