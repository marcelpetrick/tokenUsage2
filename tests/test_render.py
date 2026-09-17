# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import re
from pathlib import Path

import pytest

from conftest import BERLIN, NOW
from tokenusage2.aggregate import GroupBy, Metric, Period, QuotaView, build_snapshot
from tokenusage2.demo import DemoSource
from tokenusage2.model import Account, Event, Tool, Usage
from tokenusage2.pricing import Rates
from tokenusage2.render import (
    THEME_NAMES,
    Column,
    View,
    amount,
    clean,
    clip,
    compact,
    cost_text,
    duration,
    fit_columns,
    layout,
    mask,
    money,
    quota_cell,
    render,
    render_message,
    sparkline,
    stack_cells,
    tally_amount,
    token_text,
)
from tokenusage2.tui import bucket_count, take_snapshot
from tokenusage2.version import __version__

ANSI = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture(scope="module")
def demo() -> DemoSource:
    return DemoSource(BERLIN, clock=lambda: NOW, days=40)


def frame(demo: DemoSource, view: View, width: int = 160, height: int = 48, **options) -> list[str]:
    count = bucket_count(view, width, height, len(demo.accounts()))
    snapshot = take_snapshot(demo, view, now=NOW, tz=BERLIN, count=count)
    return render(snapshot, view, width, height, tz=BERLIN, **options)


def visible(lines: list[str]) -> list[str]:
    return [ANSI.sub("", line) for line in lines]


@pytest.mark.parametrize("theme", THEME_NAMES)
@pytest.mark.parametrize(
    ("width", "height"), [(70, 16), (100, 30), (119, 40), (160, 48), (240, 70)]
)
def test_every_line_is_exactly_the_terminal_width(
    demo: DemoSource, theme: str, width: int, height: int
) -> None:
    lines = visible(frame(demo, View(theme=theme), width, height))
    assert len(lines) == height
    assert {len(line) for line in lines} == {width}


def test_plain_frame_shows_every_panel(demo: DemoSource) -> None:
    text = "\n".join(frame(demo, View(theme="plain"), mode="DEMO", status="status!"))
    assert "\x1b" not in text
    for needle in (
        f"◆ tokenUsage2 {__version__}  DEMO",
        "DEMO",
        "Accounts",
        "Tokens per day",
        "Live feed",
        "you@example.com",
        "codex-work",
        "5h quota",
        "claude-opus-5",
        "status!",
        "cache hit",
    ):
        assert needle in text


def test_retained_history_is_drawn_hatched() -> None:
    source = DemoSource(BERLIN, clock=lambda: NOW, days=90)
    text = "\n".join(frame(source, View(theme="plain", period=Period.MONTH)))
    assert "▒ retained daily total (split unknown)" in text
    assert "▒" in text.split("Tokens per month")[1]


def test_retained_history_is_marked_where_the_metric_cannot_show_it() -> None:
    accounts = [Account("a", Tool.CLAUDE, Path("/a"), "alpha")]
    retained = Event(
        "claude-daily:a:2026-09-09:m",
        NOW - 86400,
        Tool.CLAUDE,
        "a",
        "m",
        "",
        "",
        "",
        Usage(unsplit=500),
    )
    view = View(theme="plain", metric=Metric.FRESH)

    def timeline(events: list[Event]) -> str:
        snapshot = build_snapshot(
            events, accounts, [], now=NOW, tz=BERLIN, metric=Metric.FRESH, count=7
        )
        text = "\n".join(visible(render(snapshot, view, 160, 48, tz=BERLIN)))
        return text.split("Tokens per day")[1]

    marked, empty = timeline([retained]), timeline([])
    assert marked.count("░") > empty.count("░")
    assert "░ retained daily total (only in the total view)" in marked
    assert "no usage in this range" not in marked
    assert "no usage in this range" in empty


def test_colour_themes_emit_styles(demo: DemoSource) -> None:
    assert "\x1b[0;" in frame(demo, View(theme="default"))[0]
    assert "48;5;234" in "".join(frame(demo, View(theme="midnight")))


def test_redaction_masks_identities(demo: DemoSource) -> None:
    text = "\n".join(frame(demo, View(theme="plain", redact=True)))
    assert "you@example.com" not in text
    assert "y…@e….com" in text


def test_tiny_terminals_get_a_message(demo: DemoSource) -> None:
    lines = frame(demo, View(theme="plain"), 50, 10)
    assert len(lines) == 10
    assert {len(line) for line in lines} == {50}
    assert any("terminal too small" in line for line in lines)


def test_overlays(demo: DemoSource) -> None:
    help_text = "\n".join(frame(demo, View(theme="plain", help=True)))
    assert "rescan now" in help_text
    sources = "\n".join(frame(demo, View(theme="plain", sources=True), sources=["hello sources"]))
    assert "hello sources" in sources


def test_heatmap_replaces_the_feed(demo: DemoSource) -> None:
    text = "\n".join(frame(demo, View(theme="plain", heatmap=True)))
    assert "Activity" in text
    assert "Thu" in text
    assert "Live feed" not in text


def test_every_combination_renders(demo: DemoSource) -> None:
    for period in Period:
        for group in GroupBy:
            for metric in Metric:
                view = View(theme="plain", period=period, group=group, metric=metric, detail=group)
                lines = frame(demo, view, 130, 40)
                assert {len(line) for line in lines} == {130}
    week = "\n".join(frame(demo, View(theme="plain", period=Period.WEEK)))
    assert "Tokens per week" in week


def test_empty_data_renders_placeholders() -> None:
    snapshot = build_snapshot([], [], [], now=NOW, tz=BERLIN)
    text = "\n".join(render(snapshot, View(theme="plain"), 130, 40, tz=BERLIN))
    for needle in (
        "no accounts found",
        "no usage in this range",
        "no usage in this bucket",
        "waiting for the first request",
    ):
        assert needle in text


def test_many_accounts_are_summarised() -> None:
    accounts = [Account(f"x{i}", Tool.CLAUDE, Path("/x"), f"acct{i}") for i in range(20)]
    snapshot = build_snapshot([], accounts, [], now=NOW, tz=BERLIN)
    text = "\n".join(render(snapshot, View(theme="plain"), 130, 30, tz=BERLIN))
    assert "more — press a to filter" in text


def test_layout() -> None:
    assert layout(160, 48, 3).right is not None
    narrow = layout(100, 40, 3)
    assert narrow.right is None
    assert narrow.left is not None
    short = layout(100, 20, 3)
    assert short.timeline is not None
    assert short.left is None
    assert layout(100, 12, 3).timeline is None
    assert layout(100, 12, 3).capacity == 1


def test_text_helpers() -> None:
    assert [compact(v) for v in (0, 999, 999.6, 12_345, 99_950, 1_234_567, 2.5e9, 3e13)] == [
        "0",
        "999",
        "1.0k",
        "12.3k",
        "100k",
        "1.2M",
        "2.5B",
        "30.0T",
    ]
    assert [duration(s) for s in (-5, 5, 125, 3900, 90000, 115 * 86400)] == [
        "0s",
        "5s",
        "2m",
        "1h05m",
        "1d01h",
        "115d",
    ]
    assert [token_text(v) for v in (0, 512, 872, 999, 999.6, 12_345)] == [
        "0tok",
        "512tok",
        "872tok",
        "999tok",
        "1.0k",
        "12.3k",
    ]
    assert mask("you@example.com") == "y…@e….com"
    assert mask("x@localhost") == "x…@localhost"
    assert mask("API key") == "API key"
    assert mask(None) == ""
    assert clean("a\tb") == "a b"
    assert clean("漢字") == "??"
    assert clean("é") == "e"
    assert clip("hello", 3) == "he…"
    assert clip("x", 0) == ""
    assert sparkline([0, 1, 8], 3) == " ▁█"
    assert sparkline([0, 0], 2) == "  "
    assert sparkline([1, 2], 0) == ""


def test_token_tables_name_fresh_input_and_unit_small_counts() -> None:
    event = Event(
        "e",
        NOW,
        Tool.CLAUDE,
        "a",
        "claude-opus-5",
        "anthropic",
        "/work/project",
        "s",
        Usage(input=512, cache_read=12_345, output=872),
    )
    account = Account("a", Tool.CLAUDE, Path("/a"), "claude")
    snapshot = build_snapshot([event], [account], [], now=NOW, tz=BERLIN, count=1)
    text = "\n".join(visible(render(snapshot, View(theme="plain"), 160, 48, tz=BERLIN)))
    assert "fresh" in text
    assert "512tok" in text
    assert "872tok" in text
    assert "12.3k" in text


def test_stack_cells() -> None:
    assert stack_cells([], 1.0, 4) == []
    assert stack_cells([(8, "s0", False)], 1.0, 4) == [("█", "s0")]
    assert stack_cells([(4, "s0", False)], 1.0, 4) == [("▄", "s0")]
    assert stack_cells([(0.1, "s0", False)], 1.0, 4) == [("▁", "s0")]
    assert stack_cells([(8, "s0", False), (8, "s1", True)], 1.0, 4) == [("█", "s0"), ("▒", "s1")]
    assert stack_cells([(4, "s1", True)], 1.0, 4) == [("░", "s1")]


def test_fit_columns_keeps_priorities_and_flexes() -> None:
    columns = [
        Column("a", 5, priority=0, flex=True),
        Column("b", 5, priority=2),
        Column("c", 5, priority=1),
    ]
    assert fit_columns(columns, 11) == [(0, 5), (2, 5)]
    assert fit_columns(columns, 20) == [(0, 8), (1, 5), (2, 5)]


def test_quota_cell_states() -> None:
    assert quota_cell(None, NOW) == [("—", "dim")]
    rolled = quota_cell(QuotaView("5h", 0.0, None, NOW, "x", True), NOW)
    assert "reset" in "".join(text for text, _ in rolled)
    high = quota_cell(QuotaView("5h", 92.0, NOW + 3900, NOW - 7200, "x", False), NOW)
    assert high[0][1] == "bad"
    assert high[2][1] == "dim"
    assert high[3][0].strip() == "1h05m"
    unknown_reset = quota_cell(QuotaView("5h", 50.0, None, NOW, "x", False), NOW)
    assert unknown_reset[0][1] == "ok"


def test_series_colours_are_stable() -> None:
    view = View()
    first = view.series("x")
    view.series("y")
    assert view.series("x") == first == "s0"


def test_render_message() -> None:
    lines = render_message(40, 5, ["title", "sub"], "plain")
    assert len(lines) == 5
    assert "title" in lines[1]
    assert "sub" in lines[2]


def test_money_amount_and_cost_text() -> None:
    from tokenusage2.aggregate import Tally

    assert [money(v) for v in (0, 0.004, 1.234, 123.4, 12_345)] == [
        "$0",
        "<$0.01",
        "$1.23",
        "$123",
        "$12.3k",
    ]
    assert amount(2.5, Metric.COST) == "$2.50"
    assert amount(2500, Metric.TOTAL) == "2.5k"
    assert cost_text(Tally(input=5, unpriced=5)) == "—"
    assert cost_text(Tally(input=5, cost=0.5)) == "$0.50"
    assert cost_text(Tally(input=10, cost=0.5, unpriced=5)) == "≥$0.50"
    assert tally_amount(Tally(input=5, unpriced=5), Metric.COST) == "—"


def test_cost_view_marks_partial_and_wholly_unpriced_estimates() -> None:
    account = Account("a", Tool.CODEX, Path("/a"), "alpha")
    known = Event(
        "known",
        NOW - 60,
        Tool.CODEX,
        "a",
        "known",
        "openai",
        "/work/shared",
        "s",
        Usage(input=1_000_000),
    )
    unknown = Event(
        "unknown",
        NOW - 30,
        Tool.CODEX,
        "a",
        "unknown",
        "openai",
        "/work/shared",
        "s",
        Usage(input=1_000_000),
    )

    def pricing(_tool: Tool, model: str, _route: str) -> Rates | None:
        return Rates(4, 20, 0.4, 0, 0) if model == "known" else None

    view = View(theme="plain", metric=Metric.COST, detail=GroupBy.PROJECT)
    partial = build_snapshot(
        [known, unknown],
        [account],
        [],
        now=NOW,
        tz=BERLIN,
        metric=Metric.COST,
        detail=GroupBy.PROJECT,
        pricing=pricing,
    )
    partial_text = "\n".join(render(partial, view, 160, 48, tz=BERLIN))
    unavailable = build_snapshot(
        [unknown],
        [account],
        [],
        now=NOW,
        tz=BERLIN,
        metric=Metric.COST,
        detail=GroupBy.PROJECT,
        pricing=pricing,
    )
    unavailable_text = "\n".join(render(unavailable, view, 160, 48, tz=BERLIN))

    assert "today ≥$4.00" in partial_text
    assert "≥$4.00" in partial_text
    assert "today —" in unavailable_text
    assert "unpriced usage (cost unknown)" in unavailable_text


def test_cost_view_shows_dollars(demo: DemoSource) -> None:
    text = "\n".join(frame(demo, View(theme="plain", metric=Metric.COST)))
    assert "standard-rate estimate" in text
    assert "today $" in text
    assert " cost" in text


def test_timeline_shows_the_cache_trend(demo: DemoSource) -> None:
    lines = frame(demo, View(theme="plain"))
    assert "cache-hit share" in "\n".join(lines)
    row = next(line for line in lines if line.startswith("│ cache "))
    assert "█" in row or "▇" in row
    short = "\n".join(frame(demo, View(theme="plain"), 100, 16))  # timeline too short
    assert "cache-hit share" not in short


def test_footer_shows_an_active_alert(demo: DemoSource) -> None:
    lines = frame(demo, View(theme="plain"), alert="codex 5h quota at 95%")
    assert lines[-1].rstrip().endswith("▲ codex 5h quota at 95%")
