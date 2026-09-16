<!--
SPDX-FileCopyrightText: 2026 Marcel Petrick

SPDX-License-Identifier: GPL-3.0-or-later
-->

# tokenUsage2 — plan

A live, read-only terminal dashboard (in the spirit of btop, abtop and
AgentWhileTrue) that shows how many tokens every local coding agent burns,
per tool, per account and per backend, as daily, weekly and monthly views.

## 1. What [`tokenUsage`](https://github.com/marcelpetrick/codingWithGPT/tree/master/tokenUsage) does today (review)

`tokenUsage` is a one-shot report pipeline:

1. `run-token-overview.sh` downloads the third-party *Token Use* binary
   (latest release, checksum file from the same release), runs its
   `doctor`/`overview`, and times each stage.
2. `render-overview.py` turns Token Use's overview JSON into a static HTML bar
   chart per tool.
3. `render-yearly.py` queries Token Use's private `archive.db` (`calls` table)
   and renders a 12-month HTML/CSV/JSON report.
4. `render-linkedin.py` renders a poster from Claude's `stats-cache.json` and
   Codex's `state_5.sqlite` `threads.tokens_used`.

Findings that shape tokenUsage2:

| # | Finding | Consequence for tokenUsage2 |
|---|---------|-----------------------------|
| 1 | Only `~/.claude` and `~/.codex` are read; a second `CODEX_HOME` (a company account) is invisible. | Auto-discover every home: `$HOME` scan by content markers, `CLAUDE_CONFIG_DIR`/`CODEX_HOME` from the environment **and** from shell rc files, plus a config file. Nothing machine-specific is hardcoded. |
| 2 | Claude records routed to Ollama or proxies are counted as "Claude" without distinction. | Classify the backend per request: `requestId` `req_…` means the Anthropic API; model → host mapping is recovered from `ANTHROPIC_BASE_URL` launchers in shell rc files. |
| 3 | `render-yearly.py` depends on the internal schema of a third-party binary that is downloaded as "latest" (the checksum comes from the same release, so it detects corruption, not tampering). | Zero runtime dependencies; parse the tools' own files directly. |
| 4 | `render-linkedin.py` hardcodes `unavailable=(5, 6)` and the "May–June" wording — correct for the 2026 snapshot only. | Retained-but-unsplit history is detected from the data and drawn hatched. |
| 5 | `render-overview.py` crashes on an empty `by_tool` (`max()` of nothing) and divides by zero when every total is 0. | Every renderer is tested with empty data. |
| 6 | Codex usage is attributed to the month the *thread started*. | Attribute every request to its own timestamp. |
| 7 | Snapshot only: Claude deletes transcripts after its cleanup period, so history is lost between runs. | Keep an own SQLite archive that is appended incrementally; history survives transcript cleanup. |
| 8 | No tests, no CI. | pytest + coverage gate, ruff, GitHub Actions, one `localPipeline.sh` for local and CI. |

## 2. Data sources (verified on a real machine)

| Tool | Where | Record | Dedup rule |
|------|-------|--------|------------|
| Claude Code | `<home>/projects/**/*.jsonl` | `type=assistant`, `message.usage` | The same message is written once per content block and streaming copies carry `output_tokens: 0`: key `(message.id, requestId)`, keep the **largest** copy. |
| Claude Code | `<home>/stats-cache.json` | `dailyModelTokens` | Only for days before the first surviving transcript; split unknown → drawn hatched. |
| Claude Code | statusline snapshots (`*rate-limit*.json`, `$XDG_STATE_HOME/*/quota/claude.json`) | 5h / 7d `used_percentage` | Newest `updated_at` wins. |
| Codex CLI | `<home>/sessions/**/rollout-*.jsonl`, `archived_sessions/` | `event_msg/token_count` with `info` | Rate-limit refreshes repeat the same cumulative total: key `(thread, cumulative total)`, value `last_token_usage`. The newer `token_usage_record` stream is ignored — its cumulative totals do not line up with `token_count`, and `token_count` matches Codex's own `threads.tokens_used`. |
| Codex CLI | same events | `rate_limits.primary/secondary` | Per account, newest observation wins. |
| Codex CLI | `<home>/auth.json` | `id_token` JWT claims | e-mail + plan only; tokens are never stored or shown. |
| OpenCode | `$XDG_DATA_HOME/opencode/opencode.db` | `message.data.tokens` | message id. |

Token semantics are normalised to *fresh input / cache read / cache write /
output (reasoning is a subset of output)*. Codex's `input_tokens` includes the
cached part and is split accordingly.

## 3. Ideas — what the dashboard can show

Implemented in v0.1 (✓) and backlog (·):

- ✓ Header: clock, live burn rate (tokens/min over 5 min), today / week /
  month / all-time totals.
- ✓ Accounts panel: one row per discovered account — tool, label, identity
  (e-mail, redactable), plan, today/week/month, 24 h sparkline, last activity,
  **live quota bars** (5 h and weekly) with reset countdown.
- ✓ Timeline: stacked bars for the last N days / ISO weeks / months, coloured
  by account, tool, backend, model or project; a cursor selects a bucket and scrolls
  back through history.
- ✓ Breakdown of the selected bucket by model, project, session, backend,
  account or tool: calls, fresh input, cache read, cache write, output, total,
  cost and share bar.
- ✓ Live feed: the newest requests with model, project and token split;
  just-arrived rows are highlighted.
- ✓ Heatmap: hour-of-day × weekday over the last four weeks.
- ✓ Metrics: raw total (incl. cache), fresh (input+output), output and
  standard-rate cost estimate.
- ✓ Sources overlay / `--doctor`: discovered homes, how each was found, file
  and event counts, archive path, backend hints, quota freshness, and
  reconciliation against Codex `threads.tokens_used` and Claude `stats-cache`.
- ✓ `--once` (one frame to stdout), `--json` (machine-readable snapshot),
  `--demo` (synthetic data for screenshots and tests).
- ✓ Standard-rate cost estimate with built-in provider rates and editable
  overrides (0.5.0, expanded in 0.13.0).
- ✓ Cache efficiency trend: cache-read share per bucket (0.6.0).
- ✓ Threshold notifications: quota ≥ 90 %, unusual burn rate (0.7.0).
- ✓ Per-session drill-down (0.8.0).
- ✓ CSV export of the current view (0.9.0).
- ✓ A GitHub release per version, with a README badge (0.10.0).
- · Aider / Gemini CLI / other agents as further parsers.

## 4. Architecture

```
discover.py  → Account list + backend hints (env, $HOME scan, rc files, config.toml)
procscan.py  → running agents, their homes/backends and per-account process counts
parsers.py   → pure line/row → Event functions per tool
store.py     → SQLite archive (files, events, quotas, accounts), upsert-with-max
ingest.py    → incremental tail of append-only JSONL, OpenCode watermark, backfill
projects.py  → display-time Git roots, Claude scratchpads and temporary labels
pricing.py   → provider-gated standard rates plus configured overrides
aggregate.py → buckets (DST-safe local midnights), tallies, account summaries
render.py    → cell canvas → ANSI/plain frame, themes, panels, overlays
tui.py       → alternate screen, cbreak keys, resize, refresh loop
cli.py       → TUI, --once, --json, --csv, --doctor and --demo
```

Python 3.14, standard library only (`sqlite3`, `tomllib`, `zoneinfo`,
`termios`). Rendering is plain ANSI text like AgentWhileTrue, so frames are
testable as strings.

## 5. Delivery

1. Plan (this file).
2. Package skeleton, discovery, parsers, archive + ingestion, aggregation,
   renderer, TUI + CLI — one commit each, each with tests.
3. `localPipeline.sh` (ruff, format, pytest with a coverage gate, smoke run,
   wheel build) and a GitHub Actions workflow running the same script.
4. README with badges and a screenshot rendered from `--demo`.

## 6. Backlog plan (0.4 → 0.9)

The open ideas from §3, in delivery order — one commit and one version each:

| Version | Item | Approach |
|---------|------|----------|
| 0.4.0 | Cache-write TTL split | Claude Code writes most of its cache at the 1-hour TTL (2× the input price) and the rest at 5 minutes (1.25×) — measured 106M vs 3.6M tokens for Opus 5, 15.5M vs 5.2M for Sonnet 5. Record the 1-hour share per request (archive schema 4; Claude transcripts are re-read once) so costs can be exact. |
| 0.5.0 | Standard-rate cost estimate | A price table per model glob in USD per 1M tokens (input, output, cache read, cache write 5 m / 1 h). It began with Anthropic defaults; 0.13.0 added provider-gated OpenAI Work/Codex rates. Requests answered by a local backend cost nothing unless config supplies an override. Metric `cost` (`v`) and the breakdown cost column use per-model lifetime sums. Retained daily totals stay unpriced — their split is unknown. |
| 0.6.0 | Cache-efficiency trend | A row under the timeline bars: the cache-read share of prompt tokens per bucket. |
| 0.7.0 | Alerts | Quota ≥ 90 % (configurable) and a burn rate far above the typical active-minute rate of the last seven days — shown in the status line, optionally through `notify-send` and the terminal bell; each alert fires once per quota window or burn episode. |
| 0.8.0 | Session drill-down | `session` as a breakdown dimension: project · session id with first and last request. |
| 0.9.0 | CSV export | `--csv` (timeline rows to stdout) and `e` in the dashboard (timeline and breakdown files under `$XDG_DATA_HOME/tokenusage2/exports`). |
| 0.10.0 | Releases | A GitHub Actions workflow on every push to `master`: when `version.py` names a version without a `v<version>` tag, it runs the pipeline, builds sdist and wheel, and creates the tag and a GitHub release whose notes are that version's `CHANGELOG.md` section. A release badge in the README shows the newest one. |
| 0.10.1 | Hand-over | `codingWithGPT/tokenUsage2/`, where the project started, keeps only a README that points here and says that all further work happens in this repository; its CI workflow goes with the code. |
| — | Aider / Gemini CLI | Deferred: no Gemini CLI data exists on the development machine and the only Aider history holds no token lines (a local model), so no parser could be verified against real records. |

## 7. Data-correctness repair plan (September 2026)

Status legend: ☐ pending · ◐ in progress · ☑ verified and committed.

The 0.12.7 dashboard was reproduced against the real archive on 2026-09-16.
The selected day's project breakdown proved three separate issues:

- Claude rows showed bare small values such as `512` and `872` under `input`.
  These are correct fresh-token counts—Anthropic reports cached prompt tokens in
  separate fields—but the absent unit and the generic heading make them look
  truncated next to values such as `662k`.
- Codex records for `gpt-5.6-sol` via `openai` were wholly unpriced, leaving
  `26,406,455` tokens for `DividendenDackel` and `690,684` for
  `gitAnimationImrprovement` with a `—` cost. The resolver only contains
  built-in Anthropic rates.
- Project grouping uses the basename of the raw request working directory.
  That produced `src` for a nested directory, `cat` for a Claude-created Codex
  scratchpad, and `tmp` for unattributed temporary work.

| Version | Status | Work | Acceptance evidence |
|---------|--------|------|---------------------|
| 0.12.8 | ☑ | Record this execution plan and the real-data baseline before changing behaviour. | Plan, version and changelog are committed together. |
| 0.12.9 | ☑ | Make token-table semantics explicit: label fresh input accurately and append an exact `tok` unit below the compact `k` threshold. | 43 rendering tests pass; helper coverage proves `512tok`, `872tok` and threshold behaviour; real `--once` shows `532tok` and `872tok` under `fresh`, with all 160 columns intact. |
| 0.13.0 | ☑ | Add provider-gated OpenAI standard token rates for the priced Codex/Work models, while preserving config overrides and leaving local, unknown and research-preview models unpriced. | 80 focused tests pass; every OpenAI model in the real archive resolves to a rate; `DividendenDackel` now shows `$14.256092` and `gitAnimationImrprovement` `$0.593018`, both with zero unpriced tokens. |
| 0.13.1 | ☑ | Resolve project labels to Git worktree roots, map recognized Claude scratchpads back to their source project, and label other temporary paths `(temporary)`. | 81 focused tests pass; real totals are preserved while `src`, `frontend` and `cat` merge into `x-clone-starter`, `gitAnimationImrprovement` resolves to its `codingWithGPT` worktree, and bare `tmp` becomes `(temporary)`. |
| 0.13.2 | ☑ | Review all changes, update user documentation, run focused tests and the full local pipeline, reproduce against the real archive, and prepare the release. | Risk review has zero findings; all 11 pipeline stages pass with 301 tests and 99.41% coverage; the clean-wheel and real-archive assertions pass; release workflow run 35149420481 published `v0.13.2` with both artifacts. |

Implementation rules for this repair:

1. Each row above is one atomic commit and carries its own version/changelog
   entry, matching the repository's release contract.
2. Update this table in the corresponding implementation commit with the exact
   evidence obtained; do not mark work complete based only on inspection.
3. Built-in prices apply only when the recorded route is `openai`. User
   `[prices]` entries keep precedence. Extra fees that cannot be derived from
   local token logs (for example fast mode or regional processing) are stated
   as exclusions rather than guessed.
4. Project canonicalisation is display-time only: preserve raw working
   directories in the archive, perform no destructive migration, and fall back
   safely when a historical path no longer exists.

## 8. Post-release dependency and source review

| Version | Status | Work | Acceptance evidence |
|---------|--------|------|---------------------|
| 0.13.3 | ☑ | Run the `updateDependencies` audit, update stale exact pins, and run the complete repository gate. | PyPI reports only Ruff stale (`0.16.7` → `0.16.8`); all 11 pipeline stages pass with 301 tests, 99.41% coverage and a verified 0.13.3 wheel. |
| 0.13.4 | ☑ | Run `reviewBranch`, store its report in `review.md`, then fix every HIGH or MEDIUM finding in separate atomic, versioned commits and re-review. | The formal `origin/master...HEAD` review reports zero Code or Architecture findings; no HIGH or MEDIUM fix commit is required. |
| 0.13.5 | ☑ | Audit and update all Markdown and other repository documentation against the current behavior, commands, versions and release process. | README CLI/config/privacy/release text, architecture and feature plan, changelog, review link, screenshot generator and synthetic dashboard image are synchronized with 0.13 behavior. |
| 0.13.6 | ☐ | Run the final source/documentation review and complete pipeline, then push and verify the public release and artifacts. | Pending the documentation audit. |
