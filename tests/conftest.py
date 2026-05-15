"""Shared pytest config for the agent-guard-plugins test suite.

Test markers (`slow`, `e2e`) are registered in pyproject.toml under
[tool.pytest.ini_options]. The default suite runs `-m "not slow and not e2e"`.
"""
