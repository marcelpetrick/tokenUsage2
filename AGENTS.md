<!--
SPDX-FileCopyrightText: 2026 Marcel Petrick

SPDX-License-Identifier: GPL-3.0-or-later
-->

# Repository guidance for coding agents

This file applies to the entire tokenUsage2 repository. Keep changes small,
evidence-based and compatible with the local/CI/release pipeline.

## Product contract

tokenUsage2 is a local-first, btop-style terminal dashboard for Claude Code,
Codex CLI and OpenCode usage. It normalizes local usage metadata across
accounts, models, backends, projects and sessions while retaining history in
its own SQLite archive.

Preserve these invariants:

- Python 3.14 and the standard library are the complete runtime dependency
  surface. Development tools stay exactly pinned in `pyproject.toml`.
- Treat agent-tool directories as read-only. Write only tokenUsage2's archive,
  exports and private preference state.
- Never retain or display credentials, authentication tokens, prompt bodies or
  response bodies. Test and public demo identities must be fictional/redacted.
- Keep raw archived events append-preserving. Resolve labels and pricing at
  display time when possible; do not destructively migrate history for a
  presentation change.
- Total throughput includes cache; fresh throughput is fresh input plus output.
  Both header rates are trailing five-minute averages expressed per minute.
- `cache%` is cache reads divided by prompt tokens. It is a neutral reuse ratio,
  not a health, quality or efficiency score.
- Cost is a standard-rate estimate. Unknown hosted prices remain visibly
  unpriced; incomplete mixed totals remain marked as lower bounds. Recognized
  local routes may be zero-priced.
- Provider-status polling stays opt-in, bounded and outside the render path.
  Badges summarize official public status components; they do not prove a
  user's authenticated API path works.
- Interactive preferences may persist privately, but `Shift+R` must reset only
  view state and must never remove configuration, archives or source data.

## Working method

1. Read `PLAN.md`, the relevant README section and existing tests before
   changing behavior.
2. Preserve unrelated user changes and inspect the worktree before staging.
3. Add a focused regression for every behavior fix. Prefer pure parser,
   aggregation and string-rendering tests over timing-dependent integration
   tests.
4. Keep behavior changes, documentation-only work and generated-media updates
   in atomic commits. Stage explicit paths and review the staged diff.
5. A user-visible software change requires a version and changelog entry in the
   same commit. Documentation-only corrections do not require a release bump.
6. Never publish, tag or push unless the user explicitly requests it. The
   release workflow publishes a version on `master` only when its tag is absent.

## Validation

Run the narrowest relevant checks while iterating, then the proportional gate:

- Python: `.venv/bin/python -m pytest -q <relevant tests>` and
  `.venv/bin/python -m ruff check src tests scripts`.
- Markdown-only changes: `.venv/bin/pytest -q tests/test_docs.py` and
  `git diff --check`.
- Generated project history: `.venv/bin/python scripts/history_chart.py`; the
  committed SVG and count table must pass the script's `--check` mode.
- Product, packaging, dependency or release changes:
  `./localPipeline.sh --noRun`. This is the same mandatory gate used by CI and
  releases.

Do not weaken coverage, lint, formatting or generated-file checks to make a
change pass. If an external tool such as ShellCheck is unavailable, report the
pipeline's explicit skip rather than claiming that stage passed.

## Documentation and public media

- Keep `README.md`, `PLAN.md`, `CHANGELOG.md`, architecture notes and CLI help
  synchronized with current behavior.
- Every Markdown file needs one top-level heading, valid heading nesting,
  resolvable local links and no trailing whitespace; `tests/test_docs.py`
  enforces these rules.
- Public performance numbers are measured reference runs, not universal
  guarantees. State the corpus and date with the result.
- Regenerate GIF and MP4 tours with
  `.venv/bin/python scripts/record_gifs.py`; do not hand-edit generated media.
  The script must use the production renderer and deterministic synthetic data.
- Frame public messaging as usage observability. Do not claim prompt inspection,
  reasoning evaluation, task-success measurement, invoice accuracy or
  authenticated provider-API monitoring.

## Repository map

- `src/tokenusage2/`: product code.
- `tests/`: focused and regression coverage.
- `scripts/`: reproducible history, profiling, screenshots and media.
- `docs/`: architecture, generated history and factual/review material.
- `media/`: screenshots, tours and publication copy.
- `localPipeline.sh`: authoritative local/CI/release gate.
