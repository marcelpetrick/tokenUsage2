# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Threshold alerts: a quota nearly used up, or a burn rate far above normal.

Each alert has a stable key, so it fires once per quota window or per
fifteen-minute burn episode instead of on every refresh.
"""

import shutil
import statistics
import subprocess
from bisect import bisect_left
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tokenusage2.aggregate import Snapshot
from tokenusage2.config import AlertSettings
from tokenusage2.model import Event
from tokenusage2.render import compact

BURN_EPISODE_SECONDS = 15 * 60


@dataclass(frozen=True, slots=True)
class Alert:
    key: str
    text: str


def _ts(event: Event) -> float:
    return event.ts


def typical_rate(events: Sequence[Event], now: float, days: int = 7) -> float:
    """Median tokens per active minute over the last ``days``, the last 5 minutes excluded."""
    start = bisect_left(events, now - days * 86400, key=_ts)
    end = bisect_left(events, now - 300, key=_ts)
    minutes: dict[int, int] = {}
    for position in range(start, end):
        event = events[position]
        if not event.usage.unsplit:
            minute = int(event.ts // 60)
            minutes[minute] = minutes.get(minute, 0) + event.usage.total
    return float(statistics.median(minutes.values())) if minutes else 0.0


def evaluate(snapshot: Snapshot, settings: AlertSettings, typical: float) -> list[Alert]:
    alerts = []
    for row in snapshot.accounts:
        for quota in row.quotas:
            if quota.rolled or quota.used < settings.quota_percent:
                continue
            window = int(quota.resets_at) if quota.resets_at else "open"
            alerts.append(
                Alert(
                    f"quota:{row.id}:{quota.window}:{window}",
                    f"{row.label} {quota.window} quota at {quota.used:.0f}%",
                )
            )
    threshold = max(settings.burn_floor, typical * settings.burn_factor)
    if snapshot.rate > threshold:
        text = f"burn rate {compact(snapshot.rate)} tok/min"
        if typical:
            text += f", {snapshot.rate / typical:.0f}x the typical {compact(typical)}"
        alerts.append(Alert(f"burn:{int(snapshot.now // BURN_EPISODE_SECONDS)}", text))
    return alerts


class AlertTracker:
    """Remembers which alerts fired; ``update`` returns only the new ones."""

    def __init__(self) -> None:
        self._fired: set[str] = set()

    def update(self, alerts: Sequence[Alert]) -> list[Alert]:
        new = [alert for alert in alerts if alert.key not in self._fired]
        self._fired.update(alert.key for alert in alerts)
        return new


def notify(
    alert: Alert,
    settings: AlertSettings,
    runner: Callable[..., object] = subprocess.run,
    which: Callable[[str], str | None] = shutil.which,
) -> bool:
    """A desktop notification through ``notify-send``, when enabled and available."""
    if not settings.notify or which("notify-send") is None:
        return False
    try:
        runner(
            ["notify-send", "--app-name=tokenUsage2", "tokenUsage2", alert.text],
            check=False,
            timeout=5,
            capture_output=True,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return True
