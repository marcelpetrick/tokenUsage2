# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Durable interactive view preferences, separate from hand-written config."""

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tokenusage2.aggregate import GroupBy, Metric, Period
from tokenusage2.render import THEMES, View


@dataclass(frozen=True, slots=True)
class Preferences:
    """The view choices worth restoring; navigation and transient UI stay ephemeral."""

    period: Period = Period.DAY
    group: GroupBy = GroupBy.ACCOUNT
    metric: Metric = Metric.TOTAL
    detail: GroupBy = GroupBy.MODEL
    theme: str = "default"
    redact: bool = False
    heatmap: bool = False
    interval: float = 2.0
    account: str | None = None

    @classmethod
    def from_view(cls, view: View) -> Preferences:
        return cls(
            period=view.period,
            group=view.group,
            metric=view.metric,
            detail=view.detail,
            theme=view.theme,
            redact=view.redact,
            heatmap=view.heatmap,
            interval=view.interval,
            account=view.account,
        )

    def apply(self, view: View) -> None:
        for name, value in asdict(self).items():
            setattr(view, name, value)


def default_preferences_path(home: Path, env: Mapping[str, str]) -> Path:
    base = Path(env.get("XDG_STATE_HOME") or home / ".local" / "state")
    return base / "tokenusage2" / "view.json"


def _enum(value: object, enum: type[Period] | type[GroupBy] | type[Metric], fallback: Any) -> Any:
    try:
        return enum(value)
    except TypeError, ValueError:
        return fallback


def load_preferences(path: Path) -> Preferences:
    """Load every valid field independently; corrupt or future fields are harmless."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError, UnicodeError, json.JSONDecodeError:
        return Preferences()
    if not isinstance(raw, dict):
        return Preferences()
    defaults = Preferences()
    theme = raw.get("theme")
    interval = raw.get("interval")
    account = raw.get("account")
    return Preferences(
        period=_enum(raw.get("period"), Period, defaults.period),
        group=_enum(raw.get("group"), GroupBy, defaults.group),
        metric=_enum(raw.get("metric"), Metric, defaults.metric),
        detail=_enum(raw.get("detail"), GroupBy, defaults.detail),
        theme=theme if isinstance(theme, str) and theme in THEMES else defaults.theme,
        redact=raw.get("redact") if isinstance(raw.get("redact"), bool) else defaults.redact,
        heatmap=(raw.get("heatmap") if isinstance(raw.get("heatmap"), bool) else defaults.heatmap),
        interval=(
            float(interval)
            if isinstance(interval, int | float)
            and not isinstance(interval, bool)
            and interval in {0.5, 1.0, 2.0, 5.0, 10.0, 30.0}
            else defaults.interval
        ),
        account=account if isinstance(account, str) and account else None,
    )


def save_preferences(path: Path, preferences: Preferences) -> None:
    """Atomically replace the private state file."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    data = {"version": 1, **asdict(preferences)}
    try:
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def reset_preferences(path: Path) -> None:
    path.unlink(missing_ok=True)
