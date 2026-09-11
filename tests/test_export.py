# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import csv
import io
from datetime import date, datetime, time
from pathlib import Path

from conftest import BERLIN
from tokenusage2.aggregate import GroupBy, build_snapshot
from tokenusage2.export import (
    BREAKDOWN_FIELDS,
    TIMELINE_FIELDS,
    breakdown_rows,
    export,
    timeline_rows,
    to_csv,
)
from tokenusage2.model import Account, Event, Tool, Usage
from tokenusage2.pricing import Pricer

NOW = datetime.combine(date(2026, 9, 10), time(15), tzinfo=BERLIN).timestamp()


def snapshot():
    events = [
        Event(
            "a",
            NOW - 3600,
            Tool.CLAUDE,
            "c",
            "claude-opus-5",
            "anthropic",
            "/w/p",
            "s",
            Usage(input=1_000_000, cache_write=10, cache_write_1h=10),
        ),
        Event("b", NOW - 86400, Tool.CODEX, "x", "gpt", "openai", "/w/q", "t", Usage(output=7)),
    ]
    accounts = [
        Account("c", Tool.CLAUDE, Path("/c"), "claude"),
        Account("x", Tool.CODEX, Path("/x"), "codex"),
    ]
    return build_snapshot(
        sorted(events, key=lambda event: event.ts),  # the contract: time order
        accounts,
        [],
        now=NOW,
        tz=BERLIN,
        count=3,
        priced=True,
        pricing=Pricer().rates,
        detail=GroupBy.ACCOUNT,
    )


def test_timeline_rows_carry_the_split_and_cost() -> None:
    rows = timeline_rows(snapshot())
    assert [(r["bucket_start"], r["group"], r["total"]) for r in rows] == [
        ("2026-09-09", "codex", 7),
        ("2026-09-10", "claude", 1_000_010),
    ]
    assert rows[1]["cost"] == 5.0001  # 1M input at $5 + 10 one-hour cache-write tokens at $10
    assert rows[0]["unpriced"] == 7


def test_breakdown_rows_and_csv_text() -> None:
    rows = breakdown_rows(snapshot())
    assert [(r["breakdown_by"], r["name"], r["extra"]) for r in rows] == [
        ("account", "claude", "claude")
    ]
    text = to_csv(rows, BREAKDOWN_FIELDS)
    parsed = list(csv.DictReader(io.StringIO(text)))
    assert list(parsed[0]) == list(BREAKDOWN_FIELDS)
    assert parsed[0]["cache_write_1h"] == "10"


def test_export_writes_both_files(tmp_path: Path) -> None:
    timeline, breakdown = export(snapshot(), tmp_path / "exports", "20260910-150000")
    assert timeline.name == "timeline-20260910-150000.csv"
    assert timeline.read_text().splitlines()[0] == ",".join(TIMELINE_FIELDS)
    assert breakdown.read_text().count("\n") == 2


def test_a_second_export_in_the_same_second_keeps_the_first(tmp_path: Path) -> None:
    first = export(snapshot(), tmp_path, "stamp")
    second = export(snapshot(), tmp_path, "stamp")
    assert [path.name for path in first] == ["timeline-stamp.csv", "breakdown-stamp.csv"]
    assert [path.name for path in second] == ["timeline-stamp-2.csv", "breakdown-stamp-2.csv"]
