# Contribution plan — shipping Agent Guard as a listed plugin

This document is the per-platform path to get the Agent Guard Content Guard
integration listed as an official or discoverable plugin on each of the four
platforms it supports: Claude Code, OpenCLAW, OpenAI Codex, and the Hermes
Agent framework.

Each section states the submission target, the requirements, the current
readiness of this repository, and the open gaps. All paths below were
confirmed against each platform's own documentation, not third-party blogs.

## Summary table

| Platform     | Submission target                          | Self-serve today? | Readiness    |
| ------------ | ------------------------------------------- | ----------------- | ------------ |
| Claude Code  | `anthropics/claude-plugins-official` (form) | Yes (form)        | Ready        |
| OpenCLAW     | ClawHub registry (`clawhub package publish`)| Yes               | Ready        |
| OpenAI Codex | Codex Plugin Directory                      | Not yet           | Partial gap  |
| Hermes Agent | PyPI + entry point (no central registry)    | Yes (PyPI)        | Ready        |

---

## 1. Claude Code (Anthropic)

**What exists.** Anthropic runs an official, managed plugin directory at the
GitHub repository `anthropics/claude-plugins-official`. External plugins live
in its `external_plugins/` directory, separate from Anthropic's own.

**How to submit.** Third-party plugins are submitted through the plugin
directory submission form at `https://clau.de/plugin-directory-submission`
(also reachable from the Claude Console). The plugin is then reviewed against
quality and security standards. Review typically takes a few days. The plugin
can be distributed directly from its Git repository the whole time, listed or
not — `/plugin marketplace add <owner>/<repo>` works against any repo that
ships a `.claude-plugin/marketplace.json`.

**Requirements.**

- A `.claude-plugin/plugin.json` manifest that follows the specification.
- All files the manifest references must be present.
- The plugin must not access resources outside its own directory.
- A README that explains installation and usage.
- A LICENSE file.
- Skill or hook instructions must be clear and well-structured.

**Current readiness — ready.**

- `claude-code-plugin/.claude-plugin/plugin.json` is present and passes
  `claude plugin validate` (verified).
- `claude-code-plugin/hooks/hooks.json` registers PreToolUse and PostToolUse
  hooks; both reference `hooks/agent-guard-hook.sh`, which is present.
- `claude-code-plugin/README.md` documents what the plugin does, install
  (pip package plus `/plugin` marketplace install), configuration, fail-open
  behavior, and the maintainer/contact.
- The repository ships `LICENSE` (Apache-2.0) and a root
  `.claude-plugin/marketplace.json` so the repo itself is installable as a
  marketplace.
- The hook bridge spawns only the `agent_guard_plugins` Python module and the
  shell script inside the plugin directory; it does not reach outside the
  plugin's own tree.

**Open gaps — none blocking.** Submission is the only remaining step: fill in
the directory submission form pointing at this repository and the
`claude-code-plugin/` path.

---

## 2. OpenCLAW

**What exists.** OpenCLAW has a first-class plugin registry, ClawHub, which is
the primary discovery surface for community plugins. There is no separate
"awesome-list" or docs pull request; the OpenCLAW docs explicitly do not keep a
static third-party plugin catalog. ClawHub itself is the catalog.

**How to submit.** Publish straight to ClawHub from the command line:

```
clawhub package publish dannyliv/agent-guard-openclaw --dry-run
clawhub package publish dannyliv/agent-guard-openclaw
```

ClawHub validates the submission (owner scope, package name, version, file
limits, source metadata). A new release stays hidden from normal install and
download surfaces until ClawHub finishes review and verification.

**Requirements.**

- The package must be published to ClawHub so users get correct install hints.
- A public GitHub repository for source review and issue tracking (this repo
  qualifies).
- Setup and usage documentation.
- Active maintenance: recent updates or responsive issue handling.
- `package.json` must carry OpenCLAW compatibility metadata —
  `openclaw.compat.pluginApi` and `openclaw.build.openclawVersion`.

**Current readiness — ready.**

- `openclaw-plugin/package.json` declares `name`, `version`, `license`
  (Apache-2.0), `author`, `homepage`, `repository`, the `openclaw` field with
  `extensions`, `compat.pluginApi`, and `build.openclawVersion`, plus
  `peerDependencies.openclaw`.
- `openclaw-plugin/openclaw.plugin.json` is a valid manifest with
  `activation.onStartup` and a `configSchema`.
- `openclaw-plugin/index.mjs` registers a real `before_tool_call` hook via the
  genuine `openclaw/plugin-sdk` `definePluginEntry` API.
- `openclaw-plugin/README.md` documents install, configuration, fail-open, and
  the maintainer/contact.
- `openclaw-plugin/test/plugin.test.mjs` exercises the real SDK registration.

**Open gaps.**

- The npm package `agent-guard-openclaw` must be published (the README's
  install line `openclaw plugins install agent-guard-openclaw` assumes it is
  live). The repo is publish-ready; the actual npm publish is a release step.
- Run `clawhub package publish` after the npm publish so ClawHub has the
  install hints.

---

## 3. OpenAI Codex

**What exists.** Codex has a plugin system: a plugin is a folder with a
`.codex-plugin/plugin.json` manifest, optionally bundling skills, MCP servers,
app integrations, and lifecycle hooks. Plugins are discovered through
marketplace catalogs — JSON files at `.agents/plugins/marketplace.json`
(repo-scoped) or `~/.agents/plugins/marketplace.json` (personal). Codex's CLI
has a plugin browser grouped by marketplace.

**How to submit.** There is no self-serve path to the official Codex Plugin
Directory today. The Codex documentation states plainly that "Adding plugins
to the official Plugin Directory is coming soon" and "Self-serve plugin
publishing and management are coming soon." Until that opens, the realistic
distribution path is:

- Ship a `.codex-plugin/plugin.json` plugin form in this repository so users
  can add it as a marketplace by pointing a `marketplace.json` at it.
- List it on the community catalog `RoggeOhta/awesome-codex-cli` (a curated
  GitHub list of Codex CLI tools, skills, subagents, and plugins) via a pull
  request — that is the de facto discovery surface while the official
  directory is unavailable.

**Requirements (for the eventual official directory and for the plugin form).**

- A `.codex-plugin/plugin.json` manifest with `name`, `version`,
  `description`, and pointers to bundled components (`skills`, hooks).
- A README with install and usage.
- A license.

**Current readiness — partial gap.** The Codex integration today is the
`agent-guard-codex-install` console script: it writes `~/.codex/hooks.json`
PreToolUse and PostToolUse entries plus the hook script. That is a valid and
fully-tested Codex lifecycle-hook integration (`test_e2e_codex_hook.py` runs
the real installer and hook script with the live classifier), but it is
**not** a Codex *plugin* in the new `.codex-plugin/plugin.json` sense, so it
cannot be listed in a Codex marketplace as-is.

**Open gaps.**

- Build a `.codex-plugin/plugin.json` plugin form that bundles the existing
  hook (a hooks-only plugin) so Agent Guard is installable via a Codex
  marketplace, not only via the one-line installer. This is new work, scoped
  separately.
- Once the official Codex Plugin Directory opens self-serve submission, submit
  through it.
- In the interim, open a pull request to `RoggeOhta/awesome-codex-cli` adding
  Agent Guard under the security/hooks category.

---

## 4. Hermes Agent (Nous Research)

**What exists.** The Hermes Agent framework discovers plugins from three
sources: `~/.hermes/plugins/` (user), `.hermes/plugins/` (project), and pip
entry points. There is no centralized Hermes plugin registry or marketplace,
and the Hermes docs describe no curated awesome-list or formal submission
process. Distribution is via PyPI (entry points) and Git repositories
(`hermes plugins install user/repo`).

**How to submit / distribute.** Be honest about the absence of a registry:

- Publish the package to PyPI. Once installed, Hermes discovers the plugin
  through the `hermes_agent.plugins` entry-point group; the user runs
  `hermes plugins enable agent-guard` to activate it.
- Promote the plugin through Hermes community channels (the
  `NousResearch/hermes-agent` GitHub repository discussions and the Nous
  Research Discord), since there is no marketplace to list in.

**Requirements.**

- A pip-installable package declaring a `register` callable under the
  `[project.entry-points."hermes_agent.plugins"]` group.
- Setup and usage documentation.

**Current readiness — ready.**

- `pyproject.toml` declares
  `[project.entry-points."hermes_agent.plugins"]` with
  `agent-guard = "agent_guard_plugins.integrations.hermes_plugin"`, the exact
  group name Hermes Agent scans.
- `agent_guard_plugins.integrations.hermes_plugin` exposes a `register(ctx)`
  function that registers `pre_tool_call` and `transform_tool_result` hooks;
  `test_e2e_hermes_plugin.py` loads it through the genuine hermes-agent
  `PluginManager`.
- `agent-guard-hermes-install` also writes a directory-plugin form into
  `~/.hermes/plugins/` for users who do not install via pip.
- The main README documents the Hermes integration, install, and usage.

**Open gaps.**

- The package must be published to PyPI so the entry point is discoverable
  without a local checkout (the repo is publish-ready; the actual PyPI publish
  is a release step, intentionally out of scope here).
- No registry exists to list in — community promotion is the realistic path.

---

## Cross-cutting release checklist

These are the release-time actions, separate from the documentation work that
is already merged:

1. Publish `agent-guard-plugins` to PyPI (covers Hermes discovery and the
   Python screening engine every platform depends on).
2. Publish `agent-guard-openclaw` to npm, then `clawhub package publish`.
3. Submit the Claude Code plugin through the Anthropic directory submission
   form.
4. Build a `.codex-plugin/plugin.json` plugin form for Codex, then submit to
   the Codex directory when self-serve opens; in the interim, PR
   `awesome-codex-cli`.

All four integrations already pass their real-runtime end-to-end tests against
the live platform artifacts, so the engineering surface is verified; the
remaining items are publishing and submission steps.
