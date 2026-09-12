# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The sources report: what was found, where, how, and whether it adds up."""

import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from datetime import datetime, tzinfo
from pathlib import Path

from tokenusage2.config import Config
from tokenusage2.discover import Discovery, display_path
from tokenusage2.ingest import Ingestor
from tokenusage2.model import Account, Event, Tool
from tokenusage2.procscan import AgentProcess
from tokenusage2.render import compact, duration


def codex_thread_totals(account: Account) -> dict[str, int]:
    """Codex's own ``threads.tokens_used`` per thread id (empty when unreadable)."""
    databases = sorted(account.home.glob("state_*.sqlite"))
    if not databases:
        return {}
    try:
        uri = f"{databases[-1].resolve().as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=1.0)) as connection:
            rows = connection.execute("SELECT id, tokens_used FROM threads").fetchall()
    except sqlite3.Error:
        return {}
    return {str(thread): int(used or 0) for thread, used in rows}


def restart_of(key: str) -> int:
    """How many compaction restarts preceded a Codex increment (see the parser)."""
    tail = key.rpartition(":")[2]
    return int(tail[1:]) if tail[:1] == "r" and tail[1:].isdigit() else 0


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def reconcile_codex(account: Account, events: Sequence[Event]) -> str | None:
    """Parsed increments against Codex's own count, on the threads both know.

    Codex's ``tokens_used`` restarts with a thread's cumulative total at
    compaction, so increments before a thread's last restart are left out of
    the comparison and reported on their own.
    """
    used = codex_thread_totals(account)
    mine = [event for event in events if event.account == account.id and event.session in used]
    total = sum(used[thread] for thread in {event.session for event in mine})
    if not total:
        return None
    last: dict[str, int] = {}
    for event in mine:
        last[event.session] = max(last.get(event.session, 0), restart_of(event.key))
    parsed = earlier = 0
    for event in mine:
        if restart_of(event.key) < last[event.session]:
            earlier += event.usage.total
        else:
            parsed += event.usage.total
    summary = (
        f"parsed {compact(parsed)} vs Codex threads.tokens_used {compact(total)} "
        f"({(parsed - total) / total:+.1%})"
    )
    if earlier:
        restarted = _plural(sum(1 for count in last.values() if count), "thread")
        summary += f"; {compact(earlier)} more before compaction restarted the count in {restarted}"
    return summary


def reconcile_claude(account: Account, events: Sequence[Event], scale: str | None) -> str | None:
    """Where Claude's tokens come from, and how the stats cache was scaled.

    The stats cache counts every transcript line, so it cannot check the
    transcripts; what it contributes is shown with the measured scale instead.
    """
    mine = [event for event in events if event.account == account.id]
    if not mine:
        return None
    transcripts = sum(event.usage.total for event in mine if not event.usage.unsplit)
    retained = sum(event.usage.unsplit for event in mine)
    summary = f"{compact(transcripts)} from transcripts + {compact(retained)} retained daily totals"
    value, _, days = (scale or "").partition(":")
    if days.isdigit() and int(days):
        summary += (
            f" (stats-cache counts every transcript line: scaled by {float(value):.2f}, "
            f"measured on {_plural(int(days), 'day')})"
        )
    elif scale:
        summary += " (stats-cache not scaled: no whole day shared with transcripts)"
    return summary


def reconcile(account: Account, events: Sequence[Event], scale: str | None = None) -> str | None:
    if account.tool is Tool.CODEX:
        return reconcile_codex(account, events)
    if account.tool is Tool.CLAUDE:
        return reconcile_claude(account, events, scale)
    return None


def _day(ts: float | None, tz: tzinfo) -> str:
    return datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d") if ts else "—"


def doctor_lines(
    discovery: Discovery,
    ingestor: Ingestor,
    processes: Sequence[AgentProcess],
    running: Mapping[str, int],
    config: Config,
    archive: Path | None,
    home: Path,
    tz: tzinfo,
    now: float,
) -> list[str]:
    events = ingestor.index.events()
    counts = ingestor.store.event_counts()
    files: dict[str, int] = {}
    for state in ingestor.files():
        files[state.account] = files.get(state.account, 0) + 1
    lines = [
        f"archive    {display_path(archive, home) if archive else 'in memory (--no-archive)'}",
        f"config     {display_path(config.source, home) if config.source else 'none (optional)'}",
        f"rc files   {', '.join(path.name for path in discovery.rc_files) or 'none'}",
        f"processes  {len(processes)} running agent processes",
        "",
        "ACCOUNTS",
    ]
    for account in discovery.accounts:
        count, first, last = counts.get(account.id, (0, None, None))
        lines.append(
            f"  {account.tool:<8} {account.label:<16} {display_path(account.home, home)}"
            f"  [found via {account.origin}]"
        )
        who = " · ".join(filter(None, (account.identity, account.plan))) or "identity unknown"
        lines.append(f"           {who} · {running.get(account.id, 0)} running")
        stored = (
            "database" if account.tool is Tool.OPENCODE else f"{files.get(account.id, 0)} files"
        )
        lines.append(
            f"           {stored} · {count:,} events · {_day(first, tz)} → {_day(last, tz)}"
        )
        for (owner, window), quota in sorted(ingestor.quotas.items()):
            if owner == account.id:
                lines.append(
                    f"           quota {window}: {quota.used_percent:.0f}% · observed "
                    f"{duration(now - quota.observed_at)} ago via {quota.source}"
                )
        summary = reconcile(
            account, events, ingestor.store.get_meta(f"statscache-scale:{account.id}")
        )
        if summary:
            lines.append(f"           {summary}")
        labels = {known.id: known.label for known in discovery.accounts}
        for other, count in sorted(ingestor.duplicates.get(account.id, {}).items()):
            lines.append(
                f"           {count:,} records already counted under {labels.get(other, other)}"
            )
        mirror = ingestor.mirror_of(account.id)
        if mirror is not None:
            lines.append(
                f"           treated as a copy of {labels.get(mirror, mirror)}: "
                "its retained daily totals are skipped"
            )
    discovered = {account.id for account in discovery.accounts}
    archived = [
        account for account in ingestor.store.load_accounts() if account.id not in discovered
    ]
    if archived:
        lines += ["", "ARCHIVED (no longer on disk, history kept)"]
        for account in archived:
            count = counts.get(account.id, (0, None, None))[0]
            lines.append(f"  {account.tool:<8} {account.label:<16} {count:,} events")
    lines += ["", "BACKENDS (models routed away from Anthropic)"]
    for hint in discovery.hints:
        models = ", ".join(hint.models) or "(no model pinned)"
        lines.append(f"  {hint.launcher:<18} {hint.label:<26} {models}  [{hint.source}]")
    if not discovery.hints:
        lines.append("  none found in shell rc files or running processes")
    if discovery.notes:
        lines += ["", "NOTES"] + [f"  {note}" for note in discovery.notes]
    report = ingestor.last_report
    lines += [
        "",
        f"LAST SCAN  {report.files_seen} files seen · {report.files_read} read · "
        f"{report.bytes_read / 2**20:,.1f} MiB · {report.events_changed:,} events changed · "
        f"{report.errors} unparsable lines · {report.seconds * 1000:.0f} ms",
    ]
    lines += [f"  problem: {problem}" for problem in report.problems[:10]]
    return lines
