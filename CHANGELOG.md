<!--
SPDX-FileCopyrightText: 2026 Marcel Petrick

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Changelog

All notable changes to tokenUsage2. Versions follow semantic versioning; the
archive schema version is noted whenever it changes, because an older build
refuses a newer archive.

## 0.11.3

Archive schema 6 — migrated in place; Codex rollouts are read again once.

### Fixed

- A copied Codex home (`cp -r ~/.codex ~/.codex-backup`, found by the `$HOME`
  scan) no longer counts its usage a second time. Codex record keys carried
  the account, so the same increment was a new record in every home that held
  it; they are now `(thread, cumulative total)` alone, as Claude's keys have
  no account. Copies are recorded like Claude's and shown by `--doctor`; the
  upgrade collapses increments archived under several homes.

## 0.11.2

### Fixed

- Claude's retained daily totals are no longer about twice too large. Claude
  Code's `stats-cache.json` adds up every transcript line, and a response is
  written once per content block, so the days before the first transcript
  counted most requests two or more times. The totals are now scaled by the
  ratio of deduplicated requests to cached tokens, measured on the whole days
  the cache shares with transcripts; the scale is re-measured whenever the
  cache changes, and already archived totals are corrected on the first start.

## 0.11.1

### Build

- The pinned development tools move to ruff 0.16.7 and build 1.6.1.

## 0.11.0

### Fixed

- A home reached through several spellings — a symlink, a path in a running
  agent's environment — is one account. Its id is now where the directory
  really lives, and its name comes from its steadiest spelling (config, rc
  files, default locations and the scan before the environment and running
  processes). Both used to follow whichever spelling was found first, so a
  symlinked home changed id whenever an agent started or stopped: its history
  split across two accounts, its files were read again, and its Codex records
  were counted under both ids.
- On the first start, the ids an archive holds for such a home are merged into
  its current id; Codex, OpenCode and retained-total keys are rewritten and
  records held twice are dropped.

### Changed

- Accounts found only through the environment or a running process are listed
  after the others.

## 0.10.9

### Fixed

- When the larger copy of a Claude record turns up in another home, the
  archive now moves the record to that home too. It kept the old account, so
  the record counted for one home until the next start and for the other one
  after it.

## 0.10.8

Archive schema 5 — migrated in place; Claude transcripts are read again once.

### Fixed

- Records a home shares with another are counted once per record key. The
  count grew with every re-read of a copied file (a new inode from rsync, a
  schema upgrade), so a home with records of its own was soon taken for a mere
  copy and its retained daily totals were dropped. The counts now live in the
  archive's `copies` table; the upgrade rebuilds them, and totals dropped by a
  wrong copy verdict come back.
- When the larger copy of a record turns up in another home, the bookkeeping
  follows it: the home that held the record now holds the copy.

## 0.10.7

### Fixed

- A `TZ` the system accepts no longer stops the dashboard. `TZ=:/etc/localtime`
  (common under systemd and in containers) used to exit with "unknown time
  zone"; it is now read as the zone file it names. A POSIX rule such as
  `CET-1CEST,M3.5.0,M10.5.0/3` falls back to the system zone, as an unset `TZ`
  does. Only `--tz` must still name an IANA zone.

## 0.10.6

### Build

- `localPipeline.sh` goes from a fresh clone to a verified, runnable
  `.venv/bin/tokenusage2`. It finds Python 3.14, creates `.venv` and installs
  the pinned development tools (uv when present, pip otherwise). It runs ruff
  lint and format, ShellCheck, the tests with the coverage gate and a demo
  frame. It builds sdist and wheel, installs the wheel into a clean venv and
  runs it, and checks the installed command's version. Every stage is timed;
  a summary table and a PASS/FAIL verdict close the run.
- New options `--verbose` and `--report-dir PATH`. An unknown option is
  rejected with exit status 2.
- CI and the release workflow no longer install the tools themselves; they run
  the same script. CI adds the pipeline summary to the job summary and uploads
  the stage logs.

## 0.10.5

### Documentation

- The release workflow states what it does with a push that carries several
  version bumps: it releases the newest version; the older ones stay untagged.

## 0.10.4

### Fixed

- The export confirmation never showed while an alert was active, because the
  alert replaces the footer status. A fresh notice now takes the footer for its
  ten seconds.

## 0.10.3

### Fixed

- Two exports within the same second overwrote each other; the second pair
  now gets a `-2` suffix.

## 0.10.2

### Fixed

- `--json` and `--csv` exported only as many buckets as a 160-column
  timeline fits — the terminal-size fallback when piped — which was 75 of 154
  days on a real archive. Exports now cover the whole history; `--once` still
  sizes its frame to the terminal.

## 0.10.1

### Documentation

- The hand-over: `codingWithGPT/tokenUsage2/` keeps only a README pointing to
  this repository, where all further work happens (`PLAN.md` §6; the README
  names where the project came from).

## 0.10.0

### Added

- Automatic GitHub releases: a workflow on every push to `master` releases a
  version that has no tag yet — it runs the pipeline, builds sdist and wheel,
  and creates the tag `v<version>` and a release whose notes are that version's
  section of this changelog (`scripts/release_notes.py`). A test guards that
  the current version always has a section. The README shows the latest
  release and the workflow's status as badges.

## 0.9.0

### Added

- CSV export. `--csv` prints the timeline — one row per bucket and group with
  the full token split, cost and unpriced tokens — and `e` in the dashboard
  writes the timeline and the selected bucket's breakdown as timestamped files
  to `$XDG_DATA_HOME/tokenusage2/exports`; the footer names them.

## 0.8.0

### Added

- Session drill-down: `b` cycles the breakdown through `session` too — one row
  per agent session in the selected bucket (project · short session id) with
  the time of its first and last request. `--breakdown session` and
  `--group session` work on the command line.

## 0.7.0

### Added

- Alerts: a 5 h or weekly quota at or above 90 %, and a burn rate above five
  times the typical active minute of the last seven days (never below 250k
  tokens/min). The active alert replaces the status in the footer; new alerts
  can also raise a `notify-send` desktop notification and the terminal bell.
  Each fires once per quota window or fifteen-minute burn episode. Configure
  with `[alerts]`; `--json` lists the active alerts.

## 0.6.0

### Added

- Cache-efficiency trend: a row under the timeline's dates shows each bucket's
  cache-hit share (cache reads over all prompt tokens) as a height glyph,
  green from 80 %, yellow from 50 %, red below. `--json` buckets carry
  `cache_share`.

## 0.5.0

### Added

- API-equivalent cost. A new `cost` metric (`v`) shows dollars in the header,
  the accounts table and the timeline; the breakdown gets a cost column. Claude
  requests Anthropic's API answered use Anthropic's list prices per model
  (as of 2026-06-24: Opus 5 $5/$25, Sonnet 5 $2/$10, Haiku 4.5 $1/$5 per 1M
  input/output tokens; cache reads 0.1x, writes 1.25x for 5 minutes and 2x for
  1 hour); requests a local backend answered cost nothing; other models are
  priced through `[prices."<model glob>"]` in the config. All-time cost comes
  from per-model lifetime sums, `--json` is always priced, and unpriced tokens
  are counted (`unpriced`) instead of being treated as free.

## 0.4.0

Archive schema 4 — migrated in place; Claude transcripts are read again once.

### Added

- Every request records the part of its cache write made with the 1-hour TTL
  (`cache_write_1h`), which Anthropic prices at 2x input instead of 1.25x.
  Claude Code writes most of its cache that way (measured 106M 1-hour vs 3.6M
  5-minute tokens for Opus 5), so cost estimates need the split. A re-read copy
  that knows the split replaces an archived copy of the same total without it.

## 0.3.11

### Documentation

- The README shows a screenshot of the dashboard running live in Konsole
  instead of the rendered demo frame.

## 0.3.10

### Documentation

- `PLAN.md` §6: automatic GitHub releases per version, with a release badge.

## 0.3.9

### Documentation

- `PLAN.md` §6: the delivery plan for the backlog — cache-write TTL split, cost
  estimates, cache-efficiency trend, alerts, session drill-down, CSV export —
  and why the Aider / Gemini CLI parsers are deferred.

## 0.3.8

### Changed

- Moved from `marcelpetrick/codingWithGPT` (`tokenUsage2/`) into this
  repository. Every commit was cherry-picked with its author, date and message
  and carries its own version here: 0.0.1–0.0.9 are the development steps
  before the first complete release 0.1.0. Links, badges, the CI workflow (no
  sub-directory filter or working directory any more) and a top-level `LICENSE`
  are adapted to the standalone layout.

## 0.3.7

### Documentation

- README: a performance section with the measured before/after table for
  every stage, and corrected first-start (≈2 s) and restart (≈0.2 s) figures.

## 0.3.6

### Performance

- The idle rescan that runs every refresh 17.8 → 4.6 ms. `/proc` is scanned
  incrementally — each new pid is read once, vanished pids are forgotten, and
  the 30-second rediscovery does a full rescan — and transcript files are
  walked with `os.scandir` as plain strings instead of a `Path` object per file
  per scan. A fresh full scan still yields an identical event fingerprint.

## 0.3.5

### Performance

- Snapshots 32/41/43 → 20/24/24 ms (day/week/month) on 45k events. Each
  bucket walks its own time slice instead of a bisect per event, the grouping
  key is specialised once per snapshot (project basenames memoised), bucket
  totals are merged from their group tallies, the month/week/day totals
  accumulate per account and merge, and the heatmap is sliced by day.

## 0.3.4

### Performance

- Warm start 207 → 148 ms for 45k archived events: `Event` and `Usage` are
  plain slots dataclasses (the frozen constructor was 3.4x slower and nothing
  hashes them), the archive maps tool names with a dict instead of enum calls,
  and the index takes the archive's time-ordered rows without sorting again.

## 0.3.3

### Performance

- Cold indexing 3.1–4.1 s → 1.75 s for 1.5 GB of logs. Codex writes the record
  type within the first ~100 bytes of every line, so only a 256-byte head is
  searched instead of scanning every multi-megabyte line three times; the
  parser keeps only the newest account-level rate limits instead of building
  62k quota objects; `count()` has a fast path for plain integers. A fresh full
  scan of the real home produces an identical event fingerprint before and
  after.

## 0.3.2

### Fixed

- Every snapshot re-added the entire history to get the all-time totals, so
  the cost grew with an archive that never shrinks. The event index now keeps
  per-account lifetime totals, the first transcript timestamp and the record
  count current on every change; a snapshot only walks the current week or
  month. Measured on 45k events: snapshot 69 → 34 ms (day), 78 → 44 ms (week,
  month); idle rescan 21 → 18 ms because the backfill check is O(1) now.

## 0.3.1

### Added

- `scripts/profile_app.py` times every stage the dashboard runs against the
  real home directory — cold indexing, warm start, an idle rescan, a snapshot
  per period, rendering and the JSON export — first without instrumentation,
  then under cProfile. Baseline on 1.5 GB of logs (45k events): cold index
  4.1 s, warm start 207 ms, idle rescan 21 ms, snapshot 69–79 ms, render 1.9 ms.

## 0.3.0

Archive schema 3 — migrated in place on first start.

### Fixed

- Backend labels were decided once at ingest and stored, so a `[backends]`
  config change or a newly discovered launcher never relabelled history. The
  archive now stores only what the log says (`route`: whether Anthropic's API
  answered, the Codex `model_provider`, the OpenCode `providerID`), and labels
  are resolved when displaying, cached per model.

## 0.2.0

Archive schema 2 — schema-1 archives are migrated in place on first start.

### Fixed

- A copied Claude home (for example `~/.claude-backup`, which the `$HOME` scan
  finds) counted every message a second time, because message keys included
  the account. Keys are now `(message.id, requestId)` across all homes; the
  migration rewrites old keys and drops the duplicates.
- Duplicates are recorded per pair of homes. A home whose records are mostly
  counted elsewhere is treated as a copy, so its retained daily totals from
  `stats-cache.json` are skipped too. `--doctor` reports both.

## 0.1.2

### Fixed

- Helper processes were counted as running agent sessions: the same `codex`
  and `claude` binaries also run `codex app-server`, `codex mcp-server`,
  `claude mcp serve`, `login`, `doctor` and similar. The subcommand is now
  checked (skipping option values such as `-c key=value`).

## 0.1.1

### Fixed

- A request stamped exactly at a local midnight landed in the newest bucket
  instead of its own day, and in the wrong heatmap cell: the `+ 1e-9` nudge used
  for the bucket lookup vanishes in float precision at epoch magnitudes. Buckets
  are now found with `bisect_right`.

## 0.1.0

- First release: live btop-style dashboard for Claude Code, Codex CLI and
  OpenCode token usage across every auto-discovered local account, with daily,
  weekly and monthly views, a SQLite archive (schema 1), `--once`, `--json`,
  `--doctor` and `--demo`.
