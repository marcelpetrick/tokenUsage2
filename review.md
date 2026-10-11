# tokenUsage2 review — 0.13.35

Base: public `v0.13.34` at `c59a544`

Scope: regenerated product tours and every tracked Markdown document

## Findings

No runtime Code or Architecture defect is introduced by this documentation-only
release. The audit found six documentation and generated-media gaps; all are
resolved in the release candidate:

1. This report still described the `0.13.31` candidate and its obsolete test,
   corpus and version evidence while the README called it the latest audit.
2. README and PLAN performance figures described an older, smaller corpus.
3. PLAN named Claude Code 2.1.295 although 2.1.296 is installed, and did not
   identify the checked OpenCode version.
4. The three GIFs and four MP4s predated durable view preferences and the
   `Shift+R` footer/help text.
5. The LinkedIn fact sheet omitted durable preferences and factory reset.
6. The archived LinkedIn post lacked a document title and its dense prose made
   the historical context unnecessarily hard to scan.

The static live screenshot remains intentionally named for v0.13.33 and is now
captioned as such. Its redactions were visually checked; it is historical media,
not a claim that the older version is current.

## Markdown audit

All seven tracked Markdown documents were read against the current CLI, source,
release workflow and generated artifacts. The README synopsis matches
`tokenusage2 --help`; preference precedence, private XDG state, `Shift+R`, rate
units, cache-share semantics, provider-status colours, pricing limits and the
13-stage pipeline are described consistently.

Every local Markdown link resolves, heading levels are ordered, code fences are
balanced and whitespace is clean. All 21 unique external URLs returned HTTP 200
on 2026-10-11. A regression test now enforces local links, heading hierarchy,
balanced fences and trailing whitespace for root, `docs/` and `media/` Markdown.

Historical changelog and planning evidence remains historical rather than being
rewritten as current data. `media/LI_quickpost.md` is explicitly labeled as an
archived September 2026 post, and `docs/history/loc-current.md` remains generated
exclusively by `scripts/history_chart.py`.

## Current compatibility and performance evidence

- Claude Code 2.1.296, Codex CLI 0.162.0 and OpenCode 1.15.4 were present during
  this audit.
- The source corpus contained 2,135 logs totaling 3.18 GiB; the retained archive
  contained 113,430 events.
- The 2026-10-11 reference run measured a 21.7 s cold index, 1.85 s warm start,
  39 ms unchanged rescan, 204–275 ms snapshot builds and a 6.5 ms 160 × 48
  render. These are observations, not performance guarantees.

## Media verification

`scripts/record_gifs.py` rebuilt every tour from the real renderer and
deterministic synthetic data. The GIFs use a 720 × 900 logical canvas and contain
9 tour, 8 grouping and 9 exploration frames. Their matching H.264 MP4s are
13.2 s, 11.8 s and 13.6 s; the combined LinkedIn cut is 38.6 s. Visual inspection
confirmed readable layouts, fictional identities, active redaction and the
current version in the dashboard header.

## Verification

- The focused Markdown regression passes.
- Generated project-history files verify reproducibly.
- All 12 mandatory local pipeline stages pass with 384 tests and 99.00% branch
  coverage, Ruff lint/format, ShellCheck, smoke rendering, distribution builds,
  a clean-wheel render and the installed 0.13.35 version check. GitHub evidence
  is recorded in the release handoff after the push.

## Verdict

The documentation is current, concise and internally consistent, and every
repository-owned animation has been regenerated from the current dashboard.
No finding remains open for the `0.13.35` release.
