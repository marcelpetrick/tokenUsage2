<!--
SPDX-FileCopyrightText: 2026 Marcel Petrick

SPDX-License-Identifier: GPL-3.0-or-later
-->

# tokenUsage2 architecture

This document describes tokenUsage2 in the [C4 model](https://c4model.com/)
style: system context, containers, components and two runtime flows. The
diagrams use Mermaid, which GitHub renders directly. The module list in
[`PLAN.md`](../PLAN.md#4-architecture) stays the short reference; this page
explains how the parts fit together.

## Design constraints

- Python 3.14 and the standard library are the whole runtime; there are no
  third-party runtime dependencies.
- Agent-tool directories are read-only inputs. tokenUsage2 writes only its own
  SQLite archive, exports and private view preferences.
- Prompt and response bodies, credentials and authentication tokens are never
  stored or shown. Parsers keep usage metadata only.
- Archived events are append-preserving. Labels, project names and prices are
  resolved at display time, so a presentation change never rewrites history.
- Rendering produces plain strings on a cell canvas, so every frame can be
  tested without a terminal.

## Level 1: system context

```mermaid
C4Context
    title System context: tokenUsage2

    Person(dev, "Developer", "Runs coding agents and watches their usage")
    System(tu2, "tokenUsage2", "Local terminal dashboard for token usage, quotas and estimated cost")

    System_Ext(claude, "Claude Code", "Transcripts, stats cache, statusline quota snapshots")
    System_Ext(codex, "Codex CLI", "Rollout JSONL with token counts and rate limits; state SQLite")
    System_Ext(opencode, "OpenCode", "Message database")
    System_Ext(procfs, "Linux /proc", "Running agent processes and their environment")
    System_Ext(status, "Provider status pages", "Official public Statuspage summaries (opt-in)")

    Rel(dev, tu2, "Views dashboard, exports JSON/CSV", "terminal")
    Rel(tu2, claude, "Reads", "files, read-only")
    Rel(tu2, codex, "Reads", "files, read-only")
    Rel(tu2, opencode, "Reads", "SQLite, read-only")
    Rel(tu2, procfs, "Scans", "read-only")
    Rel(tu2, status, "Polls when enabled", "HTTPS, bounded")
```

The only network access is the opt-in provider-status poll, which sends no
credentials or user data. Status badges summarize public components; they do
not prove that an authenticated API path works.

## Level 2: containers

```mermaid
C4Container
    title Containers: tokenUsage2

    Person(dev, "Developer")

    System_Boundary(tu2, "tokenUsage2") {
        Container(cli, "CLI and live TUI", "Python 3.14, stdlib", "Dashboard, --once, --json, --csv, --doctor, --demo")
        ContainerDb(archive, "Archive", "SQLite", "Normalized events, file offsets, quota windows, account metadata")
        Container(prefs, "View preferences", "JSON in XDG state", "Private, atomically written view state")
        Container(config, "Configuration", "TOML in XDG config", "Optional homes, labels, prices, alerts, status polling")
    }

    System_Ext(sources, "Agent homes", "Claude Code, Codex CLI, OpenCode")
    System_Ext(status, "Provider status pages")

    Rel(dev, cli, "Uses", "keys, terminal")
    Rel(cli, archive, "Reads and writes", "sqlite3")
    Rel(cli, prefs, "Reads and writes")
    Rel(cli, config, "Reads")
    Rel(cli, sources, "Tails incrementally", "read-only")
    Rel(cli, status, "Polls in a background thread", "HTTPS")
```

Several dashboards may share one archive. Each writer takes the write lock,
detects commits by other connections, and refreshes its cached events, file
offsets, quotas and account metadata before applying further updates.

## Level 3: components

Arrows point from a module to the modules it imports. `model.py` (plain data
types) and `keys.py` (record-key spelling) are shared by most modules and are
omitted for readability.

```mermaid
flowchart LR
    subgraph entry["Entry and interaction"]
        cli["cli.py<br/>argument parsing, output modes"]
        tui["tui.py<br/>terminal loop, keys, resize"]
        prefs["preferences.py<br/>private view state"]
        export["export.py<br/>CSV rows"]
    end

    subgraph sources["Data sources"]
        live["live.py<br/>machine source"]
        demo["demo.py<br/>synthetic source"]
        discover["discover.py<br/>account homes, identities"]
        procscan["procscan.py<br/>/proc scan"]
        doctor["doctor.py<br/>sources report, reconciliation"]
    end

    subgraph ingestion["Ingestion and storage"]
        ingest["ingest.py<br/>incremental tailing, index"]
        parsers["parsers.py<br/>pure line → event"]
        store["store.py<br/>SQLite archive"]
    end

    subgraph view["Aggregation and presentation"]
        aggregate["aggregate.py<br/>buckets, tallies, quota views"]
        alerts["alerts.py<br/>quota and burn alerts"]
        render["render.py<br/>canvas, themes, panels"]
        pricing["pricing.py<br/>standard-rate estimate"]
        projects["projects.py<br/>display-time project names"]
        pstatus["provider_status.py<br/>opt-in status checks"]
    end

    config["config.py<br/>optional TOML"]

    cli --> tui & live & demo & export & prefs & config & pstatus
    tui --> aggregate & alerts & render & export & prefs
    live --> discover & procscan & ingest & doctor & pricing & projects & pstatus
    demo --> aggregate & ingest & pricing & render
    discover --> procscan & config
    doctor --> discover & ingest & render
    ingest --> parsers & store & discover
    aggregate --> pricing & projects
    alerts --> aggregate & config
    render --> aggregate & pstatus
    config --> pricing
```

Responsibilities follow one rule: input-side modules (parsers, ingest, store)
never format anything, and output-side modules (aggregate, render) do no I/O.
`aggregate.py` turns the sorted event list into one immutable `Snapshot` per
frame; `render.py` draws that snapshot onto a cell canvas and emits ANSI or
plain text.

## Runtime flow: one refresh

```mermaid
sequenceDiagram
    participant T as tui.py
    participant L as live.py
    participant I as ingest.py
    participant P as parsers.py
    participant S as store.py (SQLite)
    participant A as aggregate.py
    participant R as render.py

    T->>L: scan()
    L->>I: scan(progress)
    I->>S: begin write, detect other connections' commits
    S-->>I: external changes (events, offsets, quotas)
    loop each changed source file
        I->>P: feed(new lines from the stored offset)
        P-->>I: Event | quota window
    end
    I->>S: upsert events and newer quotas, commit
    I-->>L: ScanReport
    T->>A: build_snapshot(events, accounts, quotas, now)
    A-->>T: Snapshot
    T->>R: render(snapshot, view)
    R-->>T: frame text
```

A file is skipped while its inode, size and modification time are unchanged.
Growing files are read from their last offset; replaced or truncated files
are read again from the start. Record keys make every re-read idempotent.

## Runtime flow: quota windows

```mermaid
sequenceDiagram
    participant C as Codex rollout / Claude snapshot
    participant P as parsers.py
    participant I as ingest.py
    participant A as aggregate.quota_view
    participant R as render.quota_cell

    C->>P: rate-limit record (used %, window, resets_at)
    P->>I: QuotaWindow(observed_at)
    I->>I: keep only a newer observation per account and window
    A->>A: resets_at passed?
    alt window still open
        A-->>R: used %, countdown
        R-->>R: bar, percentage (dimmed when older than 1 h)
    else window rolled after the last observation
        A-->>R: used unknown (None)
        R-->>R: "?% reset" until a newer observation
    end
```

A provider reset time alone does not prove how much of the new window is
already spent, so the dashboard never infers `0%`. In the case that prompted
this rule, Codex logged 80% weekly use and then only window-less `premium`
limit records while it refused work after the reported reset time.

## Quality gates

`localPipeline.sh` is the single local, CI and release gate. It requires line
coverage and branch coverage of at least 99% each, Ruff lint and format checks,
ShellCheck, the generated-history check, a demo smoke frame and a clean-wheel
install. Mutation testing with mutmut measures how many injected source faults
the tests detect; see the [README](../README.md#development) for the bar and
how to run it.
