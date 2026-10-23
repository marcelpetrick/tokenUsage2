# tokenUsage2 documentation review — 0.14.0

Review date: 23 October 2026. Scope: all repository Markdown, current CLI/help,
palette implementation and tests, release metadata and generated media/history.
This is a documentation audit, not a new full-source Code or Architecture review.

## Findings resolved

- Replace this report's obsolete 0.13.35 scope, 384-test count and 38.6-second
  video description with verified 0.14.0 evidence.
- Record completed publication in the plan, feature summary and documentation
  index, including `p`, `Space`, `t`, persistence and factory reset.
- Describe cache share as neutral reuse and qualify read-only operation as
  applying to agent-tool directories. tokenUsage2 writes its own state.
- Distinguish generated synthetic tours from the separately captioned historical
  live screenshot; retain dated performance and compatibility observations.
- Replace “usage evaluation” in the README comparison and label comparisons
  with other projects as original design context.
- Index current and archived publication material, preserve historical release
  claims and link current announcement copy from the September quick post.

## Public release verification

[v0.14.0](https://github.com/marcelpetrick/tokenUsage2/releases/tag/v0.14.0) is
public, stable and published on 23 October 2026. Its tag points to
`5693a8fcdd31cb25e5db4b46ade275c1e3273cc1`.

- [CI run 39929687832](https://github.com/marcelpetrick/tokenUsage2/actions/runs/39929687832): success.
- [Release run 39929687857](https://github.com/marcelpetrick/tokenUsage2/actions/runs/39929687857): success.
- Local release gate: 12 mandatory stages passed, 400 tests, 99.00% branch
  coverage, lint/format, ShellCheck, generated-history verification, demo render,
  package builds and a clean-wheel render/version check.
- Downloaded wheel and source archive were checked against GitHub's SHA-256
  digests; packaged version, palette implementation and dependency pins matched.
- Dependency audit updated setuptools 84.0.0 → 84.2.1 and Ruff 0.16.9 → 0.17.2.
  Pytest 9.1.1, pytest-cov 7.1.0 and build 1.6.1 were already current at release.

## Behavior checked against documentation

`p` explores reproducible permutations of the existing 20 category colours,
without changing accounting or category identity. The timeline, legend and
matching breakdown use the same mapping. Palette state is saved privately and
restored on interactive launch; missing or invalid saved values use palette zero.
`Space` pauses/resumes, `t` changes overall themes and plain stays uncoloured.
`Shift+R` resets view state without deleting configuration, sources or archives.

The README CLI synopsis matches `tokenusage2 --help`. There is no palette CLI
flag; non-interactive output does not load saved view preferences. Existing
regressions cover palette uniqueness/stability, persistence, invalid state,
reset, redraw while paused and plain-theme behavior.

## Media and historical evidence

All generated tours use the production renderer and deterministic synthetic,
redacted data. GIF frame counts are 12 / 8 / 9 for tour / groupings / exploration.
Their H.264 MP4s are 17.4 / 11.8 / 13.6 seconds at 720 × 900; the combined video
is 42.8 seconds. The palette frame was visually checked during release work.

The 11 October 2026 corpus and performance observations remain dated reference
runs, not new 0.14.0 benchmarks. Earlier changelog, plan and publication records
retain their original version-specific evidence. See the
[documentation index](docs/README.md) for current and archived material.

## Documentation validation

All three `tests/test_docs.py` checks pass; `git diff --check` is clean.
The suite checks heading order, balanced fences, local links and
trailing whitespace across root, `docs/` and `media/` Markdown. Generated history
is maintained only through `scripts/history_chart.py`; its current-count table
reflects the documentation head, which can be newer than the release tag.

External publishing advice in archived 0.13.35 material retains its original
review date; this audit does not revalidate LinkedIn policy or competitor features.
