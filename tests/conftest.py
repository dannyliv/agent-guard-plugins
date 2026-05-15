"""Shared pytest config for the agent-guard-plugins test suite."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "slow: exercises the real Hugging Face classifier (model download / load).",
    )
