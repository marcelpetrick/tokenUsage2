# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import fcntl
import itertools
import os
import select
import struct
import termios
import time
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from conftest import BERLIN, NOW
from tokenusage2.aggregate import GroupBy, Metric, Period
from tokenusage2.config import AlertSettings
from tokenusage2.demo import DemoSource
from tokenusage2.ingest import ScanReport
from tokenusage2.render import View
from tokenusage2.store import StoreBusyError
from tokenusage2.tui import (
    Controller,
    Terminal,
    _terminate,
    bucket_count,
    decode_keys,
    export_view,
    run,
    take_snapshot,
)


def test_decode_keys() -> None:
    assert decode_keys("\x1b[Dq") == ["left", "q"]
    assert decode_keys("\x1b") == ["esc"]
    assert decode_keys("\x1b[99zq") == ["q"]
    assert decode_keys("\x1b[5~\x1bOP") == ["pgup", "f1"]


def test_controller_maps_every_key() -> None:
    view = View()
    control = Controller(view)
    assert control.handle("q", []) == "quit"
    assert control.handle("r", []) == "rescan"
    assert control.handle("e", []) == "export"
    control.handle("w", [])
    assert view.period is Period.WEEK
    control.handle("left", [])
    control.handle("[", [])
    assert view.cursor == 2
    control.handle("right", [])
    assert view.cursor == 1
    control.handle("2", [])
    assert view.cursor == 1
    control.handle("m", [])
    assert (view.period, view.cursor) == (Period.MONTH, 0)
    control.handle("pgup", [], page=5)
    assert view.cursor == 5
    control.handle("pgdn", [], page=10)
    assert view.cursor == 0
    control.handle("home", [])
    assert view.cursor == 10**6
    control.handle("end", [])
    assert view.cursor == 0
    control.handle("g", [])
    control.handle("b", [])
    control.handle("v", [])
    assert (view.group, view.detail, view.metric) == (GroupBy.TOOL, GroupBy.PROJECT, Metric.FRESH)
    control.handle("a", ["x", "y"])
    assert view.account == "x"
    control.handle("a", ["x", "y"])
    control.handle("a", ["x", "y"])
    assert view.account is None
    for key in "htxp":
        control.handle(key, [])
    assert (view.heatmap, view.theme, view.redact, view.paused) == (True, "midnight", True, True)
    control.handle("+", [])
    assert view.interval == 5.0
    for _ in range(4):
        control.handle("-", [])
    assert view.interval == 0.5
    for _ in range(9):
        control.handle("+", [])
    assert view.interval == 30.0
    control.handle("?", [])
    assert view.help
    control.handle("s", [])
    assert view.sources
    assert not view.help
    control.handle("esc", [])
    assert not view.sources
    assert control.handle("unknown", []) is None


class FakeScreen:
    def __init__(self, batches: Sequence[object]) -> None:
        self.batches = list(batches)
        self.frames: list[list[str]] = []
        self.current = (140, 42)
        self.bells = 0

    def size(self) -> tuple[int, int]:
        return self.current

    def draw(self, lines: Sequence[str]) -> None:
        self.frames.append(list(lines))

    def bell(self) -> None:
        self.bells += 1

    def read_keys(self, timeout: float) -> list[str]:
        if not self.batches:
            return ["q"]
        batch = self.batches.pop(0)
        if batch == "resize":
            self.current = (100, 30)
            return []
        return list(batch)  # type: ignore[call-overload]


def test_run_loop_draws_reacts_and_quits() -> None:
    ticks = itertools.count()

    def clock() -> float:
        return NOW + next(ticks) * 0.7

    source = DemoSource(BERLIN, clock=clock, days=20)
    view = View(theme="plain")
    screen = FakeScreen([["w"], ["left"], [], "resize", ["?"], ["esc"], ["s"], ["r"], ["p"], []])
    assert run(source, view, BERLIN, screen=screen, clock=clock) == 0
    texts = ["\n".join(lines) for lines in screen.frames]
    assert any("discovering agent homes" in text for text in texts)
    assert any("indexing 1 / 1 files" in text for text in texts)
    assert any("Tokens per week" in text for text in texts)
    assert any("rescan now" in text for text in texts)
    assert any("demo mode" in text for text in texts)
    assert any("PAUSED" in text for text in texts)
    assert {len(line) for line in screen.frames[-1]} == {100}
    assert view.cursor == 1


def test_manual_rediscovery_redraws_changed_account_metadata() -> None:
    source = DemoSource(BERLIN, clock=lambda: NOW, days=5)
    accounts = [source.accounts()]
    original = accounts[0][0]
    source.accounts = lambda: accounts[0]  # type: ignore[method-assign]

    def rediscover() -> None:
        accounts[0] = [
            replace(account, label="renamed") if account.id == original.id else account
            for account in accounts[0]
        ]

    source.rediscover = rediscover  # type: ignore[method-assign]
    screen = FakeScreen([["r"], []])

    assert (
        run(source, View(theme="plain", paused=True), BERLIN, screen=screen, clock=lambda: NOW) == 0
    )
    assert any("renamed" in "\n".join(frame) for frame in screen.frames)


def test_take_snapshot_clamps_the_cursor_to_the_data() -> None:
    source = DemoSource(BERLIN, clock=lambda: NOW, days=20)
    view = View(cursor=10**6)
    take_snapshot(source, view, now=NOW, tz=BERLIN, count=10)
    assert 15 <= view.cursor <= 20


def test_bucket_count_follows_width_and_history() -> None:
    view = View()
    assert bucket_count(view, 160, 48, 4) == 75
    assert bucket_count(view, 160, 48, 4, span=3) == 14
    assert bucket_count(view, 160, 48, 4, span=30) == 30
    assert bucket_count(View(period=Period.MONTH), 160, 48, 4, span=200) == 36


def test_terminal_session_restores_the_tty() -> None:
    master, slave = os.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    before = termios.tcgetattr(slave)
    with open(slave, closefd=False) as stdin, open(slave, "w", closefd=False) as stdout:
        with Terminal(stdin, stdout) as terminal:
            assert terminal.size() == (80, 24)
            terminal.draw(["ab", "cd"])
            terminal.bell()
            os.write(master, b"\x1b[Dq")
            assert terminal.read_keys(1.0) == ["left", "q"]
            assert terminal.read_keys(0.0) == []
        assert termios.tcgetattr(slave) == before
    # A pty hands output over in chunks: read until the teardown arrives.
    output, deadline = b"", time.monotonic() + 2.0
    while b"\x1b[?1049l" not in output and time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.1)
        if ready:
            output += os.read(master, 65536)
    assert b"\x1b[?1049h" in output
    assert b"\x1b[?1049l" in output
    os.close(master)
    os.close(slave)


def test_sigterm_handler_exits_cleanly() -> None:
    with pytest.raises(SystemExit) as stop:
        _terminate(15, None)
    assert stop.value.code == 143


def test_run_loop_raises_each_alert_once(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = itertools.count()

    def clock() -> float:
        return NOW + next(ticks) * 0.7

    source = DemoSource(BERLIN, clock=clock, days=20)
    monkeypatch.setattr(
        source, "alert_settings", lambda: AlertSettings(quota_percent=80, bell=True)
    )
    screen = FakeScreen([[], [], ["v"], []])
    assert run(source, View(theme="plain"), BERLIN, screen=screen, clock=clock) == 0
    assert screen.bells == 1  # codex 5h at 81 % — once, not on every frame
    assert any("▲ codex 5h quota at 81%" in "\n".join(lines) for lines in screen.frames)


def test_e_exports_the_view_as_csv(tmp_path: Path) -> None:
    ticks = itertools.count()

    def clock() -> float:
        return NOW + next(ticks) * 0.7

    source = DemoSource(BERLIN, clock=clock, days=20)
    screen = FakeScreen([["e"], []])
    assert (
        run(source, View(theme="plain"), BERLIN, screen=screen, clock=clock, export_dir=tmp_path)
        == 0
    )
    files = sorted(path.name.split("-")[0] for path in tmp_path.iterdir())
    assert files == ["breakdown", "timeline"]
    assert any("exported timeline-" in "\n".join(lines) for lines in screen.frames)


def test_export_view_reports_problems(tmp_path: Path) -> None:
    source = DemoSource(BERLIN, clock=lambda: NOW, days=5)
    view = View()
    assert export_view(source, view, BERLIN, now=NOW, count=5, directory=None).startswith(
        "export needs"
    )
    blocker = tmp_path / "file"
    blocker.write_text("")
    message = export_view(source, view, BERLIN, now=NOW, count=5, directory=blocker / "x")
    assert message.startswith("export failed")


def test_export_notice_wins_over_an_active_alert(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ticks = itertools.count()

    def clock() -> float:
        return NOW + next(ticks) * 0.7

    source = DemoSource(BERLIN, clock=clock, days=20)
    monkeypatch.setattr(source, "alert_settings", lambda: AlertSettings(quota_percent=80))
    screen = FakeScreen([["e"], []])
    assert (
        run(source, View(theme="plain"), BERLIN, screen=screen, clock=clock, export_dir=tmp_path)
        == 0
    )
    frames = ["\n".join(lines) for lines in screen.frames]
    assert any("▲ codex 5h quota" in frame for frame in frames)
    assert any("exported timeline-" in frame for frame in frames)


def test_a_busy_archive_does_not_stop_the_dashboard() -> None:
    source = DemoSource(BERLIN, clock=lambda: NOW, days=5)
    scans = itertools.count()
    scan = source.scan

    def flaky(progress: object = None) -> object:
        if next(scans) < 2:  # the start-up scan and the first refresh find the archive busy
            raise StoreBusyError("archive x is busy")
        return scan()

    def rediscover() -> None:
        raise StoreBusyError("archive x is busy")

    source.scan = flaky  # type: ignore[method-assign]
    ticks = itertools.count(NOW, 1.0)
    screen = FakeScreen([[], [], ["r"], []])
    source.rediscover = rediscover  # type: ignore[method-assign]
    assert (
        run(
            source,
            View(theme="plain", interval=0.5),
            BERLIN,
            screen=screen,
            clock=lambda: next(ticks),
        )
        == 0
    )
    texts = ["\n".join(frame) for frame in screen.frames]
    assert any("archive busy: another tokenusage2 is writing to it" in text for text in texts)
    assert "archive busy" not in texts[-1]


def test_the_dashboard_says_when_a_newer_build_owns_the_archive() -> None:
    source = DemoSource(BERLIN, clock=lambda: NOW, days=5)
    outdated = "archive schema 8 was written by tokenusage2 9.0.0; restart"
    source.scan = lambda progress=None: ScanReport(outdated=outdated)  # type: ignore[method-assign]
    screen = FakeScreen([[]])
    assert run(source, View(theme="plain"), BERLIN, screen=screen, clock=lambda: NOW) == 0
    assert outdated in "\n".join(screen.frames[-1])
