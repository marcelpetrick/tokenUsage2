Base: public `v0.13.30` @ `fae6abc`  Scope: full 0.13.31 release candidate

## Findings

No unresolved HIGH, MEDIUM or LOW code or architecture finding remains.

The formal `origin/master...HEAD` branch review covered the rate-label fix and
its provider-state regression matrix. It found no Code or Architecture defect:
both displayed throughput values carry their own `/min` unit in wide and
70-column layouts, while the shared `5m avg` suffix states the sampling window.

The full Markdown audit found and repaired eight documentation/release gaps:

1. The latest-audit link pointed here while this report still described 0.13.29.
2. The already-tagged 0.13.30 version would have suppressed a new release.
3. The plan still described one burn rate rather than total and fresh rates.
4. The plan still described one combined provider-health indicator.
5. The LinkedIn fact sheet used the same stale singular-rate/status wording.
6. The README heading hierarchy skipped levels around the media tour.
7. The README did not show that each header number independently carries `/min`.
8. Generated history/version documentation needed regeneration for 0.13.31.

All eight are fixed. Every local Markdown link resolves, headings advance one
level at a time, code fences are balanced, and Markdown whitespace is clean.

The October compatibility pass found and repaired six concrete gaps:

1. Current Claude Opus 5.5 and GPT-6-family requests could be unpriced or use
   stale standard rates; OpenAI cache writes and the >272K tier were omitted.
2. Codex attributed an entire resumed session to its initial working directory
   even though current `turn_context` records carry a per-turn `cwd`.
3. Codex reconciliation ignored the current `sqlite_home` configuration and
   selected `state_9.sqlite` after `state_10.sqlite` lexicographically.
4. `--interval nan`, `--interval inf` and non-positive output dimensions passed
   argument validation and could freeze scanning or fail later in rendering.
5. Every snapshot walked the complete event archive to correct `last_ts` for a
   rare future timestamp, adding avoidable work to the hot display path.
6. The dashboard could not distinguish a local ingestion problem from a Claude
   or Codex service incident.

All six are covered by focused regressions. Pricing remains deliberately a
standard-rate estimate: fast/batch tiers, geography uplifts and non-token tool
charges are not silently guessed. Unpriced models and retained unsplit totals
continue to be marked incomplete instead of appearing free.

The documentation follow-up found three stale statements and repaired them:
the top-level privacy summary described an unqualified offline application,
the README still quoted the older 1.5 GB performance corpus, and the LinkedIn
fact sheet omitted session grouping and provider health. CLI syntax,
configuration examples, architecture, token semantics and local links now
match the implemented 0.13.31 behavior.

## Architecture and performance

The architecture remains appropriate for the workload: append-aware parsers
feed an idempotent SQLite archive and an incremental in-memory index; snapshots
aggregate only display windows while lifetime totals are maintained separately.
No rewrite or new runtime dependency is warranted.

Provider health is isolated behind an opt-in monitor. It contacts only fixed
official HTTPS endpoints, sends no credentials or usage data, caps response
size, validates the response schema, applies strict timeouts and performs every
request on a daemon thread so provider latency cannot freeze the dashboard.
Independent Claude and OpenAI bubbles map fully operational to green, partial
issues and maintenance to yellow, complete tracked-component outages to red,
and unknown/checking states to grey; synthetic responses cover every mapping.

Project-history measurement is also isolated from the application. A
standard-library generator reads immutable Git objects without checking out
commits, excludes its own outputs from the count, produces a deterministic SVG
and current-count table, and runs in `--check` mode in the shared quality gate.

The main corpus contains 1,987 logs (about 3.0 GiB). Repeated runs observed
5.6–23.3 s cold indexes depending on host load, 0.48–0.82 s warm starts,
10–39 ms unchanged rescans, 61–144 ms day/week/month snapshots and 2–4 ms
terminal renders. The remaining start-up cost is bounded by loading the archive
and rebuilding the in-memory index; steady-state polling is already cheap.

## Token-accounting coverage

- Claude assistant usage records count fresh input, output, cache reads and both
  cache-write TTL classes; duplicate streaming copies remain deduplicated by
  request identity.
- Codex `token_count` increments count input, cached input, output and reasoning
  without double-counting the newer parallel record stream. Local totals match
  Codex's own thread database.
- OpenCode input/output/reasoning and cache read/write fields remain covered.
- Local/custom models stay free only when a local route proves that fact;
  unknown remote prices remain visibly unpriced.
- The trailing five-minute window retains every token component. Its total rate
  includes cache, while its fresh rate is uncached input plus output; each is
  divided by five and rendered with its own `/min` unit.

## Verification

- All 12 mandatory local pipeline stages pass: 370 tests with 99.15% branch
  coverage, Ruff lint/format, ShellCheck, smoke rendering, sdist/wheel builds,
  generated-history verification, a clean-wheel render and the installed
  0.13.31 version check.
- The real archive holds 109,907 normalized events. Every event routed through
  Anthropic or OpenAI resolves to a published standard rate, including 109
  OpenAI requests in the >272K prompt tier.
- `--doctor --redact` scans 2,071 files without parse errors and reconciles both
  Codex accounts against `threads.tokens_used` at the displayed ±0.0%.

## Verdict

The 0.13.31 release candidate preserves the existing accounting semantics while
making both live rates unambiguous and the provider-state behavior exhaustively
testable. Code, architecture, user, release and supporting documentation are
synchronized; no review finding remains open.
