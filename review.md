Base: origin/master @ 1609bd8   Head: 8694e15
Scope: full current source state, with `origin/master...HEAD` risk diff
Files changed: 18   +399 / -35 lines

## Findings

No HIGH or MEDIUM Code or Architecture findings remain.

The six reproduced release-blocking defects are covered at their failure
boundaries and pass on the current source:

1. Same-inode truncate-and-regrow replacement: `ingest.py` verifies a sampled
   consumed-prefix checkpoint before resuming, with ordinary appends remaining
   constant-I/O.
2. Non-finite token counts: `parsers.py` rejects NaN and both infinities before
   integer conversion.
3. Incomplete prices: `render.py` shows wholly unknown estimates as `—`, mixed
   estimates as the known lower bound `≥$…`, and marks unpriced cost buckets.
4. Duplicate project basenames: `projects.py` assigns the shortest unique path
   suffix to colliding Git roots while preserving concise unique labels.
5. Rediscovery: `live.py` advances the source generation and `tui.py` keys its
   snapshot memo on full account metadata and archived state.
6. Future records: `aggregate.py` applies one inclusive-`now` boundary to the
   active bucket, breakdown, current totals, activity, heatmap and feed.

### LOW — one physical path cannot currently serve two tool account types

`src/tokenusage2/discover.py:446` keeps one global `seen` set across the Claude,
Codex and OpenCode loops. An explicitly configured directory containing valid
data for two tools is assigned only to the first tool. This requires an unusual
shared-home layout and predates this branch; normal per-tool homes are not
affected.

### LOW — non-finite configured prices are accepted

`src/tokenusage2/config.py:127` rejects negative prices but TOML `inf` and `nan`
pass the numeric check and can propagate a non-finite estimate to output. This
only affects an explicitly malformed optional price override and predates this
branch.

### LOW — a corrupt SQLite archive can escape as a raw database error

`src/tokenusage2/store.py:246` and the initialization block below it normalize
busy and schema errors, but not general `sqlite3.DatabaseError`; the CLI catches
`StoreError`, so a corrupt archive may produce a traceback instead of a concise
rebuild instruction. This is a recoverability/diagnostic issue, not silent data
corruption, and predates this branch.

### LOW — project resolution repeats ancestor filesystem probes on rebuild

`src/tokenusage2/projects.py:84` builds scratch candidates and then resolves
every raw path separately, repeating `.git` probes for shared ancestors. The
work is bounded to one rebuild per event generation and is small for the
observed archive, but a synthetic archive with many unique deep paths could
make a frame slower.

## Verification

- Ruff lint and formatting: clean.
- All 11 local release-pipeline stages pass: 307 tests, 99.38% branch
  coverage, smoke render, sdist/wheel build, clean-wheel render and binary
  version check for 0.13.14.
- Focused regressions cover all six repaired failure modes.
- Real archive: 55,629 events loaded; all seven observed OpenAI-routed models
  resolve to rates; no `src`, `frontend`, `cat` or `tmp` project label remains;
  current project rows have no unpriced tokens.

## Verdict

The current source is releaseable. Findings 1–6 from the full-state review are
fixed, and there are no remaining HIGH or MEDIUM findings. The four LOW items
above are non-blocking follow-up work outside the requested repair set.
