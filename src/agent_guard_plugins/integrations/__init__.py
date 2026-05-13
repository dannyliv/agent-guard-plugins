"""Per-platform middleware: import only the one you need.

    from agent_guard_plugins.integrations.claude import guarded_messages_create
    from agent_guard_plugins.integrations.openai_codex import guarded_chat_completions_create
    from agent_guard_plugins.integrations.hermes import GuardedChatModel
    from agent_guard_plugins.integrations.openclaw import preaction_hook
"""
