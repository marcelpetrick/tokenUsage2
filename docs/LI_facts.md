# tokenUsage2: LinkedIn fact finding

- **What it is:** tokenUsage2 is a live, btop-style terminal dashboard for understanding how much Claude Code, Codex CLI and OpenCode are being used across local accounts and backends.
- **Core technology:** It is written for Python 3.14 and deliberately uses only the Python standard library at runtime, including ANSI terminal control, `sqlite3`, JSON parsing and process inspection through `/proc`.
- **Privacy model:** The application is read-only, runs locally and offline, and does not need API keys or send transcript data to a remote service.
- **Automatic discovery:** It finds tool homes from configuration, environment variables, running processes, shell startup files, default locations and a bounded home-directory scan, then resolves duplicate paths to one account.
- **Data ingestion:** Claude Code JSONL transcripts and stats caches, Codex rollout JSONL files and OpenCode's SQLite database are incrementally ingested instead of being reread in full on every refresh.
- **Correct accounting:** Tool-specific records are normalized into fresh input, cache reads, cache writes and output; stable event keys prevent copied homes, streaming updates and repeated cumulative counters from double-counting usage.
- **Durable history:** A local SQLite archive preserves usage after source tools clean up old transcripts, while file offsets and checkpoints make warm refreshes incremental.
- **Ways to explore:** The TUI switches among daily, weekly and monthly periods; total, fresh, output and estimated-cost metrics; and groupings by account, tool, backend, model or project.
- **Operational context:** Alongside historical bars, tokenUsage2 shows live request activity, quota windows, burn rate, cache efficiency, per-project or per-session breakdowns and a weekday-by-hour heatmap.
- **Engineering and demo quality:** The repository has a 95% branch-coverage gate, linting, formatting, ShellCheck, package and clean-wheel smoke tests; its public screenshots and animations are rendered by the real dashboard from deterministic synthetic data with fictional, redacted identities.
