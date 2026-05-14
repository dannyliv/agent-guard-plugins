# Contributing

## Adding a new integration

1. Create `src/agent_guard_plugins/integrations/<name>.py`. Follow the pattern in `claude.py`:
   - Accept the SDK client as the first argument.
   - Extract user-role text from the message list.
   - Call `guard(text, source="<name>_middleware")`.
   - Return a blocked response (with `stop_reason` or equivalent) if `result.flagged`.
   - Pass through to the real SDK call otherwise.
2. Add an example to `examples/<name>_guard.py`. Keep it under 30 lines, self-contained, and runnable with fake credentials.
3. Update `src/agent_guard_plugins/integrations/__init__.py` with an import comment.
4. Update the integrations table in `README.md`.

## Running tests

```bash
pip install -e ".[modernbert]" pytest
pytest tests/ -v -m "not slow"
```

The `slow` mark loads the real HuggingFace model (~30s first run). Skip it in CI or when iterating locally with `-m "not slow"`.

## Voice rules

These apply to all docstrings, inline comments, and documentation:

- No em-dashes or en-dashes. Use commas, colons, or parentheses.
- No throat-clearers: "Here's what", "It's worth noting", "Importantly".
- No weak adverbs: really, just, simply, actually, importantly.
- Active voice. Short sentences.

## Cutting a release

1. Bump `version` in `pyproject.toml` and `__version__` in `src/agent_guard_plugins/__init__.py`. Keep them in sync.
2. Commit: `git commit -m "chore: bump version to X.Y.Z"`.
3. Tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. The `publish-pypi.yml` workflow picks up the tag and publishes to PyPI via OIDC trusted publishing. No API token needed.
