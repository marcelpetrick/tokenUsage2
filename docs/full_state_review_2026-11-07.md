# Full-state review — 7 November 2026

Baseline: `eb01b40`. Scope: repository source, architecture, tests, release
workflow and maintained documentation. Findings are ordered by impact and
refer to the baseline; fewer than twenty are listed because speculative issues
are excluded.

## Confirmed findings

1. **HIGH — Code — `src/tokenusage2/ingest.py:340`.** Independent dashboards
   sharing one SQLite archive could retain divergent stale event caches after
   another writer committed. The repair reloads state under the write lock when
   SQLite reports external changes; two-connection regressions cover it.
2. **HIGH — Code — `src/tokenusage2/parsers.py:311`.** An extreme finite
   OpenCode timestamp could be persisted and crash date rendering. Source
   timestamps are now checked against the representable datetime range; existing
   invalid archive records produce an actionable error without being deleted.
3. **MEDIUM — Code — `src/tokenusage2/aggregate.py:157`.** All-time cost used
   only a 272K threshold, underpricing Haiku 5.5 requests above 100K. Lifetime
   sums now preserve the built-in pricing boundaries.
4. **MEDIUM — Code — `src/tokenusage2/aggregate.py:543`.** Future-dated events
   entered all-time totals despite the documented snapshot boundary. They are
   now excluded until their timestamp while remaining in the archive.
5. **MEDIUM — Code — `src/tokenusage2/pricing.py:198`.** Unknown Claude routes
   were treated as free, hiding potentially billable proxy usage. Only explicit
   local routes are zero-priced; unknown routes stay unpriced.
6. **MEDIUM — Code — `src/tokenusage2/parsers.py:220`.** A list or object in a
   Codex quota identifier caused `TypeError` and dropped valid usage. Invalid
   identifiers are now ignored without dropping the increment.
7. **MEDIUM — Code — `src/tokenusage2/parsers.py:37`.** Oversized token counts
   exceeded SQLite's signed integer range and aborted ingestion. Unsupported
   counts are now rejected and covered by boundary tests.
8. **MEDIUM — Code — `src/tokenusage2/aggregate.py:501`.** Model breakdowns
   merged different backends under the first backend label. Rows now distinguish
   the model/backend pair.
9. **MEDIUM — Code — `src/tokenusage2/aggregate.py:375`.** Session IDs sharing
   their first eight characters were merged. Colliding visible IDs now receive
   distinct labels without scanning the entire archive every frame.
10. **MEDIUM — Architecture — `.github/workflows/release.yml:52`.** An existing
    tag could be mistaken for a complete release after an interrupted publish.
    The workflow checks assets and can recover missing artifacts from the tag.
11. **MEDIUM — Documentation — `docs/LI_content_ideas_0141.md:11`.** The
    38.5B/20.1B comparison used 46 overlapping dates, while the 0.522 scale used
    44 filtered dates; the entire difference was not proven to be duplication.
    The brief and fact sheet now disclose the distinct scopes and limitations.
12. **LOW — Code — `src/tokenusage2/config.py:203`.** Invalid UTF-8 config
    produced a traceback. It now becomes an actionable configuration error.

## Next steps

Focused regressions cover the repaired paths. Run the full shared pipeline,
verify generated history and monitor CI before considering the repair complete.
