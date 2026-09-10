# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess
from pathlib import Path

from conftest import BERLIN, NOW
from tokenusage2.aggregate import build_snapshot
from tokenusage2.alerts import Alert, AlertTracker, evaluate, notify, typical_rate
from tokenusage2.config import AlertSettings
from tokenusage2.model import Account, Event, QuotaWindow, Tool, Usage

ACCOUNT = Account("a", Tool.CODEX, Path("/a"), "codex")


def ev(ts: float, total: int, *, unsplit: bool = False) -> Event:
    usage = Usage(unsplit=total) if unsplit else Usage(input=total)
    return Event(f"k{ts}", ts, Tool.CODEX, "a", "m", "openai", "/p", "s", usage)


def test_typical_rate_is_the_median_active_minute() -> None:
    events = [
        ev(NOW - 8 * 86400, 10**9),  # older than a week
        ev(NOW - 3600, 100),
        ev(NOW - 1800, 100),
        ev(NOW - 1790, 200),  # same minute as the one before
        ev(NOW - 900, 1000),
        ev(NOW - 800, 10**9, unsplit=True),  # retained totals are not requests
        ev(NOW - 60, 10**9),  # the current burst does not define "typical"
    ]
    assert typical_rate(events, NOW) == 300.0
    assert typical_rate([], NOW) == 0.0


def snapshot_with(events: list[Event], quotas: list[QuotaWindow]):
    return build_snapshot(events, [ACCOUNT], quotas, now=NOW, tz=BERLIN)


def test_quota_alerts_fire_per_window_and_skip_rolled_windows() -> None:
    quotas = [
        QuotaWindow("a", "5h", 95.0, NOW + 60, NOW, "x"),
        QuotaWindow("a", "week", 40.0, NOW + 60, NOW, "x"),
        QuotaWindow("a", "7d", 99.0, NOW - 60, NOW - 120, "x"),
    ]
    alerts = evaluate(snapshot_with([], quotas), AlertSettings(), 0.0)
    assert alerts == [Alert(f"quota:a:5h:{int(NOW + 60)}", "codex 5h quota at 95%")]
    open_window = [QuotaWindow("a", "5h", 91.0, None, NOW, "x")]
    assert evaluate(snapshot_with([], open_window), AlertSettings(), 0.0)[0].key.endswith("open")


def test_burn_alert_needs_factor_and_floor() -> None:
    burst = snapshot_with([ev(NOW - 60, 5_000_000)], [])  # 1M tokens/min over 5 minutes
    settings = AlertSettings(burn_factor=5, burn_floor=250_000)
    [alert] = evaluate(burst, settings, typical=100_000.0)
    assert alert.key == f"burn:{int(NOW // 900)}"
    assert alert.text == "burn rate 1.0M tok/min, 10x the typical 100k"
    assert evaluate(burst, settings, typical=300_000.0) == []
    assert evaluate(burst, AlertSettings(burn_floor=2_000_000), typical=0.0) == []
    assert evaluate(burst, settings, typical=0.0)[0].text == "burn rate 1.0M tok/min"


def test_tracker_fires_each_alert_once() -> None:
    tracker = AlertTracker()
    first, second = Alert("a", "x"), Alert("b", "y")
    assert tracker.update([first]) == [first]
    assert tracker.update([first, second]) == [second]
    assert tracker.update([first, second]) == []


def test_notify_only_when_enabled_and_available() -> None:
    calls: list[list[str]] = []

    def runner(argv: list[str], **options: object) -> None:
        calls.append(argv)

    alert = Alert("k", "codex 5h quota at 95%")
    enabled = AlertSettings(notify=True)
    assert notify(alert, enabled, runner, lambda _: "/usr/bin/notify-send")
    assert calls == [["notify-send", "--app-name=tokenUsage2", "tokenUsage2", alert.text]]
    assert not notify(alert, AlertSettings(), runner, lambda _: "/usr/bin/notify-send")
    assert not notify(alert, enabled, runner, lambda _: None)

    def broken(argv: list[str], **options: object) -> None:
        raise subprocess.TimeoutExpired(argv, 5)

    assert not notify(alert, enabled, broken, lambda _: "/usr/bin/notify-send")
    assert len(calls) == 1
