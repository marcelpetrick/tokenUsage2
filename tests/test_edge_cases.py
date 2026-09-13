# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Error paths and edge cases the feature tests do not reach."""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import UTC
from pathlib import Path

import pytest

from conftest import BERLIN, NOW, FakeHome, codex_tokens
from tokenusage2.aggregate import GroupBy, build_snapshot, group_key
from tokenusage2.cli import default_archive, main
from tokenusage2.config import Config
from tokenusage2.demo import DemoSource
from tokenusage2.discover import _read, _sanitize_url, codex_identity, discover
from tokenusage2.doctor import codex_thread_totals
from tokenusage2.ingest import EventIndex, Ingestor, ScanReport
from tokenusage2.model import Account, Event, Tool, Usage
from tokenusage2.parsers import CodexParser, parse_opencode_message
from tokenusage2.procscan import AgentProcess, process_home
from tokenusage2.render import (
    Canvas,
    Rect,
    View,
    draw_breakdown,
    draw_header,
    draw_heatmap,
    draw_timeline,
)
from tokenusage2.store import SCHEMA_VERSION, Store
from tokenusage2.tui import data_span


@pytest.fixture
def ingestor(home: FakeHome) -> Iterator[Ingestor]:
    store = Store(None)
    yield Ingestor(
        store, discover(home.root, home.env, Config()), BERLIN, home.root, home.env, lambda: NOW
    )
    store.close()


# --- ingestion --------------------------------------------------------------------------


def test_a_file_that_vanishes_before_it_is_read_is_skipped(
    ingestor: Ingestor, tmp_path: Path
) -> None:
    report = ScanReport()
    claude = next(account for account in ingestor.discovery.accounts if account.tool is Tool.CLAUDE)
    ingestor._ingest_file(claude, str(tmp_path / "gone.jsonl"), report)
    assert (report.files_seen, report.problems) == (0, [])


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads files without read permission")
def test_an_unreadable_transcript_is_reported_and_skipped(
    home: FakeHome, ingestor: Ingestor
) -> None:
    transcript = home.root / ".claude" / "projects" / "-work-alpha" / "s1.jsonl"
    transcript.chmod(0)
    try:
        report = ingestor.scan()
    finally:
        transcript.chmod(0o600)
    assert "~/.claude/projects/-work-alpha/s1.jsonl: Permission denied" in report.problems
    assert not any(
        event.tool is Tool.CLAUDE and not event.usage.unsplit for event in ingestor.index.events()
    )


def test_a_scan_without_new_rows_or_a_stats_cache_still_reports_its_progress(
    home: FakeHome, ingestor: Ingestor
) -> None:
    with closing(sqlite3.connect(home.opencode_db)) as connection, connection:
        connection.execute("DELETE FROM message")
    (home.root / ".claude" / "stats-cache.json").unlink()
    progress: list[tuple[int, int]] = []
    ingestor.scan(lambda done, total: progress.append((done, total)))
    assert progress == [(3, 3)]  # one Claude transcript and two Codex rollouts
    assert not any(e.usage.unsplit or e.tool is Tool.OPENCODE for e in ingestor.index.events())


def test_the_index_forgets_an_account_whose_only_request_is_gone() -> None:
    only = Event("claude:m:", 5.0, Tool.CLAUDE, "c", "m", "", "", "", Usage(input=1))
    index = EventIndex([only])
    assert index.discard("claude:", 0.0) == 1
    assert index.lifetimes()["c"].last_ts is None
    assert index.earliest("c") is None


def test_the_restart_migration_leaves_keys_without_a_cumulative_total_alone(
    tmp_path: Path,
) -> None:
    path = tmp_path / "v6.sqlite"
    with closing(Store(path)) as store:
        odd = Event(
            "codex:t:unknown", 1.0, Tool.CODEX, "codex:x", "m", "openai", "", "t", Usage(input=1)
        )
        store.upsert_events([odd])
        store.set_meta("schema", "6")
        store.commit()
    with closing(Store(path)) as store:
        assert [event.key for event in store.load_events()] == ["codex:t:unknown"]
        assert store.get_meta("schema") == str(SCHEMA_VERSION)


# --- parsers ----------------------------------------------------------------------------


def test_codex_parser_skips_malformed_context_limits_and_totals() -> None:
    parser = CodexParser("acct", {}, "t")
    assert parser.feed(b'{"type": "session_meta", "payload": 3}\n') is None
    limits = codex_tokens("2026-09-10T10:00:00Z", None, primary=5.0)
    limits["payload"]["rate_limits"]["primary"] = "not a window"
    limits["payload"]["rate_limits"]["secondary"]["used_percent"] = True
    assert parser.feed((json.dumps(limits) + "\n").encode()) is None
    assert parser.quotas == []
    broken = codex_tokens("2026-09-10T10:00:01Z", 10, inp=10)
    broken["payload"]["info"]["total_token_usage"] = 3
    assert parser.feed((json.dumps(broken) + "\n").encode()) is None
    assert parser.errors == 0


def test_an_opencode_message_without_a_usable_creation_time_is_skipped() -> None:
    data = {"role": "assistant", "tokens": {"input": 1}, "time": {"created": True}}
    assert parse_opencode_message("acct", "row", json.dumps(data)) is None


# --- sources report, discovery, processes ---------------------------------------------


def test_an_unreadable_codex_state_database_gives_no_thread_totals(tmp_path: Path) -> None:
    (tmp_path / "state_5.sqlite").write_bytes(b"not a database" * 100)
    assert codex_thread_totals(Account("codex:x", Tool.CODEX, tmp_path, "x")) == {}


def test_the_sources_report_says_when_no_backend_launcher_exists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / ".claude" / "projects").mkdir(parents=True)
    code = main(
        ["--doctor", "--no-archive", "--tz", "UTC"],
        env={"HOME": str(tmp_path)},
        proc=tmp_path / "proc",
        clock=lambda: NOW,
    )
    assert code == 0
    assert "none found in shell rc files or running processes" in capsys.readouterr().out


def test_discovery_helpers_tolerate_bad_ports_unreadable_files_and_bare_logins(
    tmp_path: Path,
) -> None:
    assert _sanitize_url("http://user:secret@host:99999/v1") == "http://host/v1"
    assert _read(tmp_path) == ""  # a directory cannot be read as text
    (tmp_path / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}))
    assert codex_identity(tmp_path) == (None, None)


def test_an_opencode_process_has_no_home_variable() -> None:
    assert process_home(AgentProcess(1, Tool.OPENCODE), Path("/h"), {}) is None


# --- command line, loop, aggregation -----------------------------------------------------


def test_the_default_archive_follows_xdg_data_home() -> None:
    assert default_archive(Path("/h"), {}) == Path("/h/.local/share/tokenusage2/archive.sqlite")
    data_home = {"XDG_DATA_HOME": "/data"}
    assert default_archive(Path("/h"), data_home) == Path("/data/tokenusage2/archive.sqlite")


def test_no_history_spans_no_buckets() -> None:
    source = DemoSource(BERLIN, clock=lambda: NOW, days=1)
    source._events = []
    assert data_span(source, View(), NOW, BERLIN) is None


def test_group_key_groups_a_single_event() -> None:
    event = Event(
        "k", NOW, Tool.CLAUDE, "a", "claude-opus-5", "anthropic", "/w/p", "s", Usage(input=1)
    )
    assert group_key(event, GroupBy.MODEL, {}) == "claude-opus-5"


# --- rendering -----------------------------------------------------------------------------


def test_the_canvas_clips_writes_outside_it_and_skips_boxes_too_small_to_draw() -> None:
    canvas = Canvas(5, 1)
    assert canvas.put(0, 3, "hidden") == 6  # below the canvas: nothing is drawn
    assert canvas.put(0, 0, "abcdef", limit=3) == 3
    canvas.box(Rect(0, 0, 1, 1), "title")
    assert canvas.lines({}) == ["abc  "]


def test_panels_cope_with_too_little_room_and_no_data() -> None:
    snapshot = build_snapshot([], [], [], now=NOW, tz=BERLIN)
    canvas = Canvas(120, 14)
    draw_timeline(canvas, Rect(0, 0, 120, 4), snapshot, View())  # no room for a chart
    draw_breakdown(canvas, Rect(0, 0, 120, 6), replace(snapshot, buckets=[]), View())
    draw_heatmap(canvas, Rect(0, 0, 60, 4), snapshot)  # fewer rows than weekdays
    draw_heatmap(canvas, Rect(60, 0, 60, 14), snapshot)
    assert "no activity in the last four weeks" in "\n".join(canvas.lines({}))
    header = Canvas(200, 1)
    draw_header(header, 200, snapshot, View(), "LIVE", UTC, "alpha")
    assert "[alpha]" in header.lines({})[0]
