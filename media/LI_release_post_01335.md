# LinkedIn launch post — tokenUsage2 v0.13.35

Historical 0.13.35 material: video durations and test counts below describe that
release. The shared media files now show 0.14.0; see the
[current palette announcement](LI_release_post_0140.md) for updated copy.

Publish with the native 4:5 video `tokenUsage2-linkedin.mp4` on 11 October 2026.
The copy below is ready to paste; the alternatives provide different hooks
without changing the factual claims.

## Recommended post

```text
Coding agents became a stack before they became observable.

I use Claude Code, Codex CLI and OpenCode across multiple accounts, models and backends. Each tool exposes part of the picture. None gives me one operating view of what is active, what is consuming tokens, how much traffic is cache reuse, which project caused a spike, or whether a problem is local or provider-wide.

So today I am releasing tokenUsage2 v0.13.35: a local-first, btop-style observability dashboard for coding-agent usage.

It gives me:

• total and fresh five-minute token rates, both clearly shown per minute
• daily, weekly and monthly history
• breakdowns by account, tool, backend, model, project and session
• cache-reuse trends, live quota windows and a request feed
• standard-rate cost estimates that keep unknown prices visibly unknown
• separate Claude and OpenAI service-health indicators

The tool reads the agents' local usage metadata and keeps its own SQLite archive. It does not store prompts or responses, needs no API keys, makes no network requests by default and has no third-party runtime dependencies.

It is written for Python 3.14, licensed GPLv3+, and the release gate passes 384 tests with 99.00% branch coverage.

The video is not a mock-up: every frame comes from the real renderer using deterministic synthetic data and fictional, redacted identities.

GitHub and v0.13.35 release:
https://github.com/marcelpetrick/tokenUsage2

If you run more than one coding agent, which signal are you currently missing: cost, cache reuse, quotas, model mix, project attribution, or something else?

#AgenticEngineering #AIObservability #DeveloperTools #Python #OpenSource
```

## Why this framing fits

- “Coding agents became a stack before they became observable” names the
  category problem before introducing the project.
- “Usage observability” is accurate. The software does not judge agent output,
  inspect prompt meaning or track task success.
- The six bullets move from immediate live signals to historical investigation
  and operational diagnosis.
- Privacy and engineering evidence answer the likely objections after value is
  established, rather than leading with implementation details.
- The closing question gives practitioners several concrete ways to respond.
- The five hashtags target agent infrastructure, observability, developer tools,
  Python and open-source audiences without repeating every product name.

## Alternative hooks

Choose one of these only if it better matches the intended audience:

### Technical operator

```text
Three coding agents. Multiple accounts. Hosted and local models. One question:
what is actually consuming the tokens right now?
```

### Cost and cache

```text
A five-million-token rate can be real—and still say very little about how much
new work an agent is doing. Cache traffic changes the picture.
```

### Local-first

```text
I wanted coding-agent observability without sending my coding-agent telemetry to
another SaaS product.
```

### Builder story

```text
The moment I ran Claude Code, Codex CLI and OpenCode side by side, their separate
usage views stopped being enough.
```

## Shorter post variant

```text
Released today: tokenUsage2 v0.13.35.

It is a local-first, btop-style observability dashboard for Claude Code, Codex CLI and OpenCode across accounts and backends.

See total versus fresh token throughput, cache reuse, quotas, model/project/session breakdowns, standard-rate cost estimates, provider health and history that survives transcript cleanup—without storing prompts or responses.

Python 3.14. Zero third-party runtime dependencies. GPLv3+. 384 tests and 99.00% branch coverage.

The attached 38.6-second tour is rendered by the real application with synthetic, redacted data.

https://github.com/marcelpetrick/tokenUsage2

What would you want to observe across your coding agents?

#AgenticEngineering #AIObservability #DeveloperTools #Python #OpenSource
```

## First comment option

Use this only if you prefer the main post without installation details. Keep the
GitHub link in the main post so the release remains immediately actionable.

```text
Quick start on Linux with Python 3.14:

git clone https://github.com/marcelpetrick/tokenUsage2.git
cd tokenUsage2
./localPipeline.sh

The repository includes the source, reproducible demo, wheel/sdist release,
architecture notes and the complete accounting caveats.
```

## Hashtag alternatives by audience

Use one set, not all sets together.

- **Recommended release:** `#AgenticEngineering #AIObservability #DeveloperTools #Python #OpenSource`
- **Tool users:** `#ClaudeCode #Codex #OpenCode #TerminalUI #LocalFirst`
- **Platform/DevEx:** `#DeveloperExperience #PlatformEngineering #Observability #LocalFirst #OpenSource`
- **Cost/cache follow-up:** `#FinOps #AIInfrastructure #LLMOps #Caching #DeveloperTools`

The recommended set has the best overall fit for this release: category,
problem, builder audience, implementation ecosystem and distribution model.
