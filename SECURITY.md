# Security Policy

## Reporting a vulnerability

Open a [GitHub Security Advisory](https://github.com/dannyliv/agent-guard-plugins/security/advisories/new), not a public issue. This lets us coordinate a fix before details are public.

Contact: [@dannyliv](https://github.com/dannyliv) on GitHub.

## Scope

agent-guard-plugins is a client library. The three surfaces most likely to carry a real security issue:

**Model supply chain.** The classifier weights come from HuggingFace (`dannyliv/agent-guard-modernbert-base`). A compromised or substituted model would cause guards to silently pass injections. Pin the model commit SHA with `AGENT_GUARD_MODEL=dannyliv/agent-guard-modernbert-base@<sha>` if you need supply-chain guarantees.

**Dashboard XSS.** The Flask dashboard renders logged input text. If user-supplied text reaches the dashboard and autoescape is off, a script tag in logged text executes in the browser. The dashboard is fixed to run autoescape and binds to `127.0.0.1` by default. Do not expose it on a public network.

**Streaming inputs left unguarded.** `guard()` classifies a complete string. If your agent streams tokens and you pass partial chunks, the classifier sees incomplete context and may miss an injection. This is a documented limitation, not a bug. Call `guard()` on the full assembled prompt before passing it to your model.

## Out of scope

- Jailbreaks that defeat the classifier at threshold 0.4 (tune the threshold or file a model-card issue on HuggingFace)
- Vulnerabilities in upstream dependencies (torch, transformers, peft, flask): report directly to those projects
