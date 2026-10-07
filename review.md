Base: `origin/master` @ `75976ce`  Scope: full current working tree and repository state

## Findings

No unresolved HIGH, MEDIUM or LOW code or architecture finding remains.

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

## Architecture and performance

The architecture remains appropriate for the workload: append-aware parsers
feed an idempotent SQLite archive and an incremental in-memory index; snapshots
aggregate only display windows while lifetime totals are maintained separately.
No rewrite or new runtime dependency is warranted.

Provider health is isolated behind an opt-in monitor. It contacts only fixed
official HTTPS endpoints, sends no credentials or usage data, caps response
size, validates the response schema, applies strict timeouts and performs every
request on a daemon thread so provider latency cannot freeze the dashboard.

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

## Verification

- All 11 mandatory local pipeline stages pass: 354 tests with 99.15% branch
  coverage, Ruff lint/format, ShellCheck, smoke rendering, sdist/wheel builds,
  a clean-wheel render and the installed 0.13.27 version check.
- The real archive holds 104,332 normalized events. Every event routed through
  Anthropic or OpenAI resolves to a published standard rate, including 109
  OpenAI requests in the >272K prompt tier.
- `--doctor --redact` scans 1,987 files without parse errors and reconciles both
  Codex accounts against `threads.tokens_used` at the displayed ±0.0%.

## Verdict

The repaired working tree fits Claude Code 2.1.292 and Codex CLI 0.160.1. It is
releaseable; no review finding remains open.
