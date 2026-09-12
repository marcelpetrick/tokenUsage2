# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import sqlite3
from contextlib import closing
from pathlib import Path

from tokenusage2.doctor import reconcile, restart_of
from tokenusage2.model import Account, Event, Tool, Usage


def increment(key: str, total: int, session: str = "t") -> Event:
    return Event(key, 1.0, Tool.CODEX, "codex:x", "m", "openai", "", session, Usage(input=total))


def test_codex_reconciliation_sets_increments_before_a_restart_apart(tmp_path: Path) -> None:
    with closing(sqlite3.connect(tmp_path / "state_5.sqlite")) as connection, connection:
        connection.execute("CREATE TABLE threads (id TEXT, tokens_used INTEGER)")
        connection.executemany("INSERT INTO threads VALUES (?, ?)", [("t", 150), ("idle", 0)])
    account = Account("codex:x", Tool.CODEX, tmp_path, "x")
    events = [
        increment("codex:t:1000", 1000),  # before compaction: Codex's count dropped it
        increment("codex:t:100:r1", 100),
        increment("codex:t:150:r1", 50),
        increment("codex:gone:5", 5, "gone"),  # a thread Codex no longer lists
    ]
    assert reconcile(account, events) == (
        "parsed 150 vs Codex threads.tokens_used 150 (+0.0%); "
        "1.0k more before compaction restarted the count in 1 thread"
    )
    assert reconcile(account, events[1:3]) == "parsed 150 vs Codex threads.tokens_used 150 (+0.0%)"
    assert reconcile(account, events[3:]) is None
    assert reconcile(Account("codex:y", Tool.CODEX, tmp_path / "none", "y"), events) is None


def test_restart_of_reads_the_parser_suffix() -> None:
    assert [restart_of(key) for key in ("codex:t:5:r12", "codex:t:5", "claude:m:req")] == [12, 0, 0]


def test_claude_reconciliation_shows_its_sources_and_the_stats_cache_scale() -> None:
    account = Account("claude:x", Tool.CLAUDE, Path("/x"), "x")
    events = [
        Event("claude:m:req", 1.0, Tool.CLAUDE, "claude:x", "m", "", "", "", Usage(input=1500)),
        Event(
            "claude-daily:claude:x:2026-09-01:m",
            1.0,
            Tool.CLAUDE,
            "claude:x",
            "m",
            "",
            "",
            "",
            Usage(unsplit=2500),
        ),
    ]
    sources = "1.5k from transcripts + 2.5k retained daily totals"
    assert reconcile(account, events, "0.509796:26") == (
        f"{sources} (stats-cache counts every transcript line: scaled by 0.51, measured on 26 days)"
    )
    assert reconcile(account, events, "0.5:1") == (
        f"{sources} (stats-cache counts every transcript line: scaled by 0.50, measured on 1 day)"
    )
    assert reconcile(account, events, "1.000000:0") == (
        f"{sources} (stats-cache not scaled: no whole day shared with transcripts)"
    )
    assert reconcile(account, events) == sources
    assert reconcile(account, []) is None
    assert reconcile(Account("opencode:x", Tool.OPENCODE, Path("/x"), "o"), events) is None
