# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import stat
from pathlib import Path

import pytest

from tokenusage2.aggregate import GroupBy, Metric, Period
from tokenusage2.cli import _initial_view, build_parser
from tokenusage2.preferences import (
    Preferences,
    default_preferences_path,
    load_preferences,
    reset_preferences,
    save_preferences,
)
from tokenusage2.render import View


def test_preferences_round_trip_privately_and_reset(tmp_path: Path) -> None:
    path = tmp_path / "state" / "tokenusage2" / "view.json"
    chosen = Preferences(
        period=Period.WEEK,
        group=GroupBy.MODEL,
        metric=Metric.COST,
        detail=GroupBy.PROJECT,
        theme="midnight",
        palette=12345,
        redact=True,
        heatmap=True,
        interval=5.0,
        account="account-id",
    )
    save_preferences(path, chosen)
    assert load_preferences(path) == chosen
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert json.loads(path.read_text())["version"] == 1

    reset_preferences(path)
    assert not path.exists()
    assert load_preferences(path) == Preferences()


def test_invalid_fields_fall_back_independently(tmp_path: Path) -> None:
    path = tmp_path / "view.json"
    path.write_text(
        json.dumps(
            {
                "period": "nonsense",
                "group": "model",
                "metric": 7,
                "detail": "project",
                "theme": "missing",
                "redact": "yes",
                "heatmap": True,
                "interval": 3,
                "account": "",
                "future": "ignored",
            }
        )
    )
    assert load_preferences(path) == Preferences(
        group=GroupBy.MODEL,
        detail=GroupBy.PROJECT,
        heatmap=True,
    )
    path.write_text("not json")
    assert load_preferences(path) == Preferences()


def test_default_preferences_path_honours_xdg_state_home() -> None:
    assert default_preferences_path(Path("/home/me"), {}) == Path(
        "/home/me/.local/state/tokenusage2/view.json"
    )
    assert default_preferences_path(Path("/home/me"), {"XDG_STATE_HOME": "/state"}) == Path(
        "/state/tokenusage2/view.json"
    )


def test_restart_restores_saved_choices_and_flags_override_them(tmp_path: Path) -> None:
    path = tmp_path / "view.json"
    save_preferences(
        path,
        Preferences(
            period=Period.WEEK,
            group=GroupBy.BACKEND,
            metric=Metric.COST,
            detail=GroupBy.SESSION,
            theme="amber",
            palette=12345,
            redact=True,
            heatmap=True,
            interval=10.0,
            account="saved-account",
        ),
    )
    restored, factory, wanted = _initial_view(
        build_parser().parse_args([]), {}, path, interactive=True
    )
    assert Preferences.from_view(restored) == load_preferences(path)
    assert factory == View()
    assert wanted == "saved-account"

    no_color, factory, _ = _initial_view(
        build_parser().parse_args([]), {"NO_COLOR": "1"}, path, interactive=True
    )
    assert (no_color.theme, factory.theme) == ("plain", "plain")

    overridden, _, wanted = _initial_view(
        build_parser().parse_args(
            [
                "--period",
                "month",
                "--group",
                "tool",
                "--metric",
                "output",
                "--breakdown",
                "account",
                "--theme",
                "plain",
                "--no-redact",
                "--interval",
                "1",
                "--account",
                "cli-account",
            ]
        ),
        {},
        path,
        interactive=True,
    )
    assert Preferences.from_view(overridden) == Preferences(
        period=Period.MONTH,
        group=GroupBy.TOOL,
        metric=Metric.OUTPUT,
        detail=GroupBy.ACCOUNT,
        theme="plain",
        palette=12345,
        redact=False,
        heatmap=True,
        interval=1.0,
        account="cli-account",
    )
    assert overridden.palette == 12345
    assert wanted == "cli-account"


def test_noninteractive_modes_keep_stable_factory_defaults(tmp_path: Path) -> None:
    path = tmp_path / "view.json"
    save_preferences(path, Preferences(period=Period.MONTH, redact=True, theme="amber"))
    view, _, wanted = _initial_view(
        build_parser().parse_args(["--json"]), {}, path, interactive=False
    )
    assert Preferences.from_view(view) == Preferences()
    assert wanted is None


@pytest.mark.parametrize("palette", [-1, 2**32, True, 1.5, "2", None, [], {}])
def test_invalid_saved_palettes_use_original_colours(tmp_path: Path, palette: object) -> None:
    path = tmp_path / "view.json"
    path.write_text(json.dumps({"palette": palette, "theme": "amber"}))
    assert load_preferences(path) == Preferences(theme="amber")
