# LinkedIn content ideas — tokenUsage2 v0.14.1

Current story angles for tokenUsage2 after the v0.14.1 pricing and accounting
audit. Figures below were measured locally on 6 November 2026 and must remain
dated rather than presented as universal Claude Code behavior.

## Lead story: one response should count once

### Hook

> Claude Code showed 38.5 billion tokens. Request-level accounting found 20.1
> billion over the same overlapping history. The other 18.4 billion tokens were
> repeated usage records—not additional agent work.

### What happened

Claude Code's local `stats-cache.json` adds the usage object attached to every
assistant transcript line. A single response is commonly written once per
content block, with the same `message.id`, `requestId` and token usage repeated.
Adding lines therefore counts many requests two or more times.

tokenUsage2 identifies one request by `(message.id, requestId)` and keeps its
largest complete copy. Across 44 complete shared days for `claude-dmo`, the
deduplicated total was 52.2% of the native cache total. A separate audit proved
that every currently surviving Claude source key was present in the tokenUsage2
archive, so the smaller result was not caused by dropped records.

This is the precise advantage to communicate: **tokenUsage2 provides more
faithful request-level usage accounting than Claude Code's local stats-cache
aggregation because it understands and removes repeated transcript copies.**

### Why it matters

- A doubled token baseline distorts model, project and time-period comparisons.
- Applying list prices to repeated copies can nearly double a cost estimate.
- Cache-reuse analysis becomes misleading when repeated response records are
  mistaken for additional requests.
- A durable, deduplicated archive remains useful after Claude Code cleans up the
  source transcripts.

### Claim boundary

- Compare tokenUsage2 with Claude Code's **local stats-cache aggregation**, not
  with Anthropic invoices or server-side billing.
- The 38.5B and 20.1B figures describe one measured account and overlapping
  history on 6 November 2026; other accounts can have different duplication
  ratios.
- Claude quota percentages are server-side subscription windows, not raw token
  totals, and should not be compared with either figure.
- tokenUsage2 cost remains a published-standard-rate estimate, not an invoice.

## Codex contrast: accuracy versus completeness

Do not reuse the Claude overcounting claim for Codex. On the directly
comparable post-compaction sequence, Codex's native `threads.tokens_used`
counter and tokenUsage2 already agree:

- `codex-dmo`: exact match at 1,612,052,469 tokens.
- `codex`: a 353,400-token difference across 5.726B native tokens, or 0.00617%.

tokenUsage2's Codex advantage is completeness and granularity rather than
correcting a materially inaccurate native total. It deduplicates repeated
cumulative updates, attributes each increment to its request time, separates
fresh/cache/output/reasoning components and combines several accounts. It also
retained 68,253,638 earlier tokens that Codex's current thread counter no longer
includes because compaction restarted the cumulative sequence.

Use this public formulation:

> Claude's local stats cache materially overcounts repeated transcript records.
> Codex's current native counter is accurate, while tokenUsage2 preserves the
> more complete, granular history across compaction and multiple accounts.

## Ready-to-post draft

```text
Claude Code showed me 38.5 billion tokens.

When I reconstructed the same overlapping history request by request, I found 20.1 billion.

Nothing was missing. The difference was duplication.

Claude Code's local stats cache adds the usage attached to every assistant transcript line. One response can be written once per content block, with the same message ID, request ID and token usage repeated. Summing the lines can therefore count one request multiple times.

tokenUsage2 deduplicates on `(message.id, requestId)` and keeps the largest complete copy. Across 44 complete shared days, the request-level total was 52.2% of the native cache figure—and every surviving Claude source record was present in the archive.

That is one reason I built tokenUsage2: coding-agent observability needs to understand each tool's storage semantics, not merely add every number it finds.

The result is a more faithful view across Claude Code, Codex CLI and OpenCode: total versus fresh traffic, cache reuse, models, projects, sessions and standard-rate cost estimates, locally and without retaining prompt bodies.

The qualification matters: this compares local usage accounting, not Anthropic billing, and the measured ratio belongs to this account and date.

How much of your AI-usage dashboard is source-aware—and how much is just a sum?

https://github.com/marcelpetrick/tokenUsage2

#AIObservability #ClaudeCode #DeveloperTools #AgenticEngineering #FinOps
```

## Short version

```text
One Claude response should count once.

Claude Code's local stats cache showed 38.5B tokens for one account. Request-level deduplication found 20.1B over the same overlapping history: 52.2% of the native figure.

The cause was repeated usage attached to multiple transcript lines—not missing work. tokenUsage2 groups those copies by message and request ID, keeps the complete record and verifies that every surviving source request reached its archive.

That makes tokenUsage2 more accurate for request-level usage accounting than simply summing Claude Code's local stats cache.

Measured example, not a billing comparison.

https://github.com/marcelpetrick/tokenUsage2

#AIObservability #ClaudeCode #DeveloperTools #AgenticEngineering #FinOps
```

## Visual concept

Use a two-column card generated from synthetic data:

- Left: `Claude stats cache · 38.5B line-counted tokens`.
- Right: `tokenUsage2 · 20.1B deduplicated request tokens`.
- Center rule: `same message.id + requestId → one request`.
- Footer: `Measured 2026-11-06 · local stats, not an invoice`.

Do not publish account identities, raw transcript paths or prompt content. Label
the graphic as an observed case rather than a universal 48% saving.

## Follow-up angles

1. Show one fictional response repeated across two content-block lines and how
   the stable request key collapses it.
2. Explain why quota percentage, token count and standard-rate cost are three
   different measurements.
3. Compare Claude transcript duplication with Codex cumulative counters and
   compaction restarts. Claude needs request deduplication; Codex needs
   cumulative-update deduplication and explicit restart tracking. Every source
   needs its own accounting rule.
4. Demonstrate why “just parse the JSONL and sum the tokens” is insufficient for
   an agent-observability product.
