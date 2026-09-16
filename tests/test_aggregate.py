# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import itertools
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from conftest import BERLIN
from tokenusage2.aggregate import (
    GroupBy,
    Lifetime,
    Metric,
    Period,
    Snapshot,
    Tally,
    build_snapshot,
    labels,
    lifetimes_of,
    period_start,
    periods_back,
    shift,
    usage_value,
)
from tokenusage2.model import Account, Event, QuotaWindow, Tool, Usage
from tokenusage2.pricing import Pricer
from tokenusage2.projects import project_name

ACCOUNTS = [
    Account("a", Tool.CLAUDE, Path("/a"), "alpha"),
    Account("b", Tool.CODEX, Path("/b"), "beta"),
]
TODAY = date(2026, 9, 10)
NOW = datetime.combine(TODAY, time(15), tzinfo=BERLIN).timestamp()
_keys = itertools.count()


def at(days_ago: int = 0, hour: int = 10, minute: int = 0) -> float:
    day = TODAY - timedelta(days=days_ago)
    return datetime.combine(day, time(hour, minute), tzinfo=BERLIN).timestamp()


def ev(
    ts: float,
    account: str = "a",
    *,
    model: str = "m1",
    backend: str = "anthropic",
    usage: Usage | None = None,
) -> Event:
    tool = Tool.CLAUDE if account == "a" else Tool.CODEX
    return Event(
        f"e{next(_keys)}",
        ts,
        tool,
        account,
        model,
        backend,
        "/w/alpha",
        "s",
        usage or Usage(input=100),
    )


def snap(events: list[Event], quotas: list[QuotaWindow] | None = None, **options) -> Snapshot:
    return build_snapshot(
        sorted(events, key=lambda e: e.ts), ACCOUNTS, quotas or [], now=NOW, tz=BERLIN, **options
    )


def test_period_arithmetic() -> None:
    assert period_start(Period.WEEK, TODAY) == date(2026, 9, 7)
    assert period_start(Period.MONTH, TODAY) == date(2026, 9, 1)
    assert shift(Period.MONTH, date(2026, 11, 1), 3) == date(2027, 2, 1)
    assert shift(Period.MONTH, date(2026, 1, 1), -1) == date(2025, 12, 1)
    assert shift(Period.WEEK, date(2026, 9, 7), -1) == date(2026, 8, 31)
    assert periods_back(Period.DAY, date(2026, 9, 1), TODAY) == 9
    assert periods_back(Period.WEEK, date(2026, 9, 1), TODAY) == 1
    assert periods_back(Period.MONTH, date(2025, 12, 31), TODAY) == 9


def test_labels() -> None:
    assert labels(Period.DAY, TODAY) == ("10", "Thu 10 Sep 2026")
    assert labels(Period.WEEK, date(2026, 9, 7))[0] == "W37"
    assert labels(Period.MONTH, date(2026, 9, 1)) == ("Sep", "September 2026")


def test_the_dst_change_day_is_exactly_one_bucket() -> None:
    now = datetime(2026, 10, 26, 12, tzinfo=BERLIN).timestamp()
    snapshot = build_snapshot([], [], [], now=now, tz=BERLIN, count=3)
    assert [b.end_ts - b.start_ts for b in snapshot.buckets] == [86400, 90000, 86400]


def test_totals_buckets_and_group_order() -> None:
    events = [ev(at(0, 9)), ev(at(0, 10), "b", usage=Usage(input=300)), ev(at(1)), ev(at(40))]
    snapshot = snap(events, count=7)
    assert [
        snapshot.today.total,
        snapshot.week.total,
        snapshot.month.total,
        snapshot.all.total,
    ] == [400, 500, 500, 600]
    assert len(snapshot.buckets) == 7
    assert snapshot.selected == 6
    assert snapshot.buckets[-1].total.total == 400
    assert snapshot.groups == ["beta", "alpha"]
    rows = {row.id: row for row in snapshot.accounts}
    assert rows["a"].today.total == 100
    assert rows["b"].today.total == 300
    assert rows["a"].all.calls == 3
    assert (snapshot.first_ts, snapshot.last_ts) == (at(40), at(0, 10))


def test_cursor_scrolls_the_window_only_past_its_edge() -> None:
    inside = snap([ev(at(10))], count=5, cursor=2)
    assert inside.selected == 2
    assert inside.buckets[-1].start == TODAY
    beyond = snap([ev(at(10))], count=5, cursor=10)
    assert beyond.selected == 0
    assert beyond.buckets[0].start == date(2026, 8, 31)
    assert beyond.breakdown[0].tally.total == 100


def test_breakdowns_and_groupings() -> None:
    events = [
        ev(at(0, 9), model="big"),
        ev(at(0, 10), model="big"),
        ev(at(0, 11), model="small", backend="ollama@gpu", usage=Usage(output=50)),
    ]
    by_model = snap(events, detail=GroupBy.MODEL)
    assert [(r.name, r.extra, r.tally.calls) for r in by_model.breakdown] == [
        ("big", "anthropic", 2),
        ("small", "ollama@gpu", 1),
    ]
    by_project = snap(events, detail=GroupBy.PROJECT, metric=Metric.OUTPUT)
    assert [row.name for row in by_project.breakdown] == ["alpha"]
    assert snap(events, group=GroupBy.BACKEND).groups == ["anthropic", "ollama@gpu"]
    assert snap(events, group=GroupBy.TOOL).groups == ["claude"]
    relabelled = snap(events, group=GroupBy.BACKEND, backend=lambda e: f"via {e.route}")
    assert relabelled.groups == ["via anthropic", "via ollama@gpu"]
    assert snap(events, group=GroupBy.PROJECT).groups == ["alpha"]


def test_project_resolver_is_used_for_projects_sessions_and_recent_events() -> None:
    event = ev(at(0))
    event.project = "/work/repo/src"
    resolved = snap(
        [event],
        group=GroupBy.PROJECT,
        detail=GroupBy.SESSION,
        project=lambda _path: "repo",
    )
    assert resolved.groups == ["repo"]
    assert resolved.breakdown[0].name == "repo · s"
    assert resolved.project_labels == {"/work/repo/src": "repo"}


def test_supplied_lifetimes_replace_the_full_recount() -> None:
    events = [ev(at(40)), ev(at(0)), ev(at(0), "b")]
    recounted = snap(events)
    supplied = snap(events, lifetimes=lifetimes_of(events))
    assert (supplied.all, supplied.accounts) == (recounted.all, recounted.accounts)
    marker = snap(events, lifetimes={"a": Lifetime(Tally(calls=1, input=999), at(5))})
    assert marker.all.total == 999
    row = next(r for r in marker.accounts if r.id == "a")
    assert (row.all.total, row.last_ts) == (999, at(5))
    assert snap(events, lifetimes={}, account_filter="a").all.total == 0


def test_account_filter() -> None:
    snapshot = snap([ev(at(0)), ev(at(0), "b")], account_filter="b")
    assert [row.id for row in snapshot.accounts] == ["b"]
    assert snapshot.today.total == 100


def test_rate_hourly_running_and_last_request() -> None:
    snapshot = snap([ev(NOW - 60, usage=Usage(input=500)), ev(NOW - 2 * 3600)], running={"a": 2})
    row = next(r for r in snapshot.accounts if r.id == "a")
    assert row.running == 2
    assert row.rate == snapshot.rate == 100.0
    assert (row.hourly[23], row.hourly[21]) == (500, 100)
    assert row.last_ts == NOW - 60


def test_quota_windows_roll_over_and_sort() -> None:
    quotas = [
        QuotaWindow("a", "week", 50, NOW + 10, NOW, "x"),
        QuotaWindow("a", "5h", 90, NOW - 10, NOW - 100, "x"),
        QuotaWindow("gone", "5h", 1, None, NOW, "x"),
    ]
    row = next(r for r in snap([], quotas).accounts if r.id == "a")
    assert [(q.window, q.used, q.rolled) for q in row.quotas] == [
        ("5h", 0.0, True),
        ("week", 50, False),
    ]


def test_heatmap_by_weekday_and_hour() -> None:
    snapshot = snap([ev(at(0, 14, 30)), ev(at(7, 14, 5)), ev(at(40, 14))])
    assert snapshot.heatmap[3][14] == 200
    assert sum(map(sum, snapshot.heatmap)) == 200


def test_heatmap_uses_the_wall_clock_hour_on_dst_days() -> None:
    def cell(moment: datetime) -> tuple[int, int]:
        ts = moment.timestamp()
        snapshot = build_snapshot([ev(ts)], ACCOUNTS, [], now=ts + 3600, tz=BERLIN)
        ((row, hour),) = [
            (row, hour)
            for row, cells in enumerate(snapshot.heatmap)
            for hour, value in enumerate(cells)
            if value
        ]
        return row, hour

    sunday = 6
    assert cell(datetime(2026, 3, 29, 10, 30, tzinfo=BERLIN)) == (sunday, 10)  # 23-hour day
    assert cell(datetime(2026, 10, 25, 10, 30, tzinfo=BERLIN)) == (sunday, 10)  # 25-hour day
    assert cell(datetime(2026, 10, 25, 2, 30, fold=1, tzinfo=BERLIN)) == (sunday, 2)  # repeated
    assert cell(datetime(2026, 10, 25, 23, 59, tzinfo=BERLIN)) == (sunday, 23)


def test_metrics_and_retained_totals() -> None:
    tally = Tally()
    tally.add(Usage(unsplit=100))
    tally.add(Usage(input=10, cache_read=30, cache_write=10, output=5))
    assert tally.calls == 1
    assert [tally.value(m) for m in Metric] == [155, 15, 5, 0.0]
    assert (tally.hatched(Metric.TOTAL), tally.hatched(Metric.FRESH)) == (100, 0)
    assert tally.cache_share == 30 / 50
    assert Tally().cache_share == 0.0
    snapshot = snap([ev(at(1), usage=Usage(unsplit=1000)), ev(at(0))])
    assert snapshot.has_hatched
    fresh = snap([ev(at(1), usage=Usage(unsplit=1000)), ev(at(0))], metric=Metric.FRESH)
    assert (fresh.has_retained, fresh.has_hatched) == (True, False)
    assert [event.usage.unsplit for event in snapshot.recent] == [0]
    assert next(r for r in snapshot.accounts if r.id == "a").last_ts == at(0)
    assert usage_value(Usage(output=3), Metric.OUTPUT) == 3
    assert usage_value(Usage(input=1, cache_read=9), Metric.FRESH) == 1


def test_project_name() -> None:
    assert project_name("") == "(unknown)"
    assert project_name("/a/b/") == "b"
    assert project_name("(retained daily total)") == "(retained daily total)"
    assert project_name("/") == "/"


def test_absurd_cursor_stays_in_date_range() -> None:
    snapshot = build_snapshot(
        [], [], [], now=NOW, tz=BERLIN, period=Period.MONTH, cursor=10**9, count=6
    )
    assert snapshot.selected == 0
    assert snapshot.buckets[0].start.year > 1500


def test_empty_snapshot() -> None:
    snapshot = build_snapshot([], [], [], now=NOW, tz=BERLIN)
    assert (snapshot.groups, snapshot.breakdown, snapshot.first_ts) == ([], [], None)
    assert len(snapshot.buckets) == 30
    assert not snapshot.has_hatched
    assert snapshot.selected_bucket is snapshot.buckets[-1]


def test_events_exactly_at_midnight_open_their_own_bucket() -> None:
    # A float epoch has no room for a 1e-9 nudge; the edge itself must bucket right.
    oldest = at(6, 0)
    snapshot = snap([ev(oldest), ev(at(1, 0))], count=7)
    assert snapshot.buckets[0].start_ts == oldest
    assert [bucket.total.calls for bucket in snapshot.buckets] == [1, 0, 0, 0, 0, 1, 0]
    assert snapshot.heatmap[period_start(Period.DAY, TODAY - timedelta(days=6)).weekday()][0] == (
        100
    )


def test_cost_view_prices_buckets_totals_and_lifetimes() -> None:
    events = [
        ev(at(0), model="claude-opus-5", usage=Usage(input=1_000_000)),
        ev(at(0, 11), model="north", backend="", usage=Usage(output=10)),
        ev(at(0), "b", model="gpt", backend="openai", usage=Usage(input=5)),
    ]
    rates = Pricer().rates
    cost = snap(events, metric=Metric.COST, pricing=rates)
    assert cost.buckets[-1].total.cost == pytest.approx(5.0)
    assert (cost.today.cost, cost.all.cost, cost.all.unpriced) == (
        pytest.approx(5.0),
        pytest.approx(5.0),
        5,
    )
    row = next(r for r in cost.accounts if r.id == "a")
    assert row.all.cost == pytest.approx(5.0)
    assert cost.groups == ["alpha"]
    tokens = snap(events, pricing=rates)
    assert tokens.buckets[-1].total.cost == 0.0
    assert {r.name: r.tally.cost for r in tokens.breakdown} == {
        "claude-opus-5": pytest.approx(5.0),
        "north": 0.0,
        "gpt": 0.0,
    }
    assert next(r for r in tokens.breakdown if r.name == "gpt").tally.unpriced == 5
    assert snap(events, pricing=rates, priced=True).all.cost == pytest.approx(5.0)
    assert snap(events, metric=Metric.COST).all.unpriced == sum(e.usage.total for e in events)


def test_breakdown_by_session_shows_first_and_last_request() -> None:
    def request(ts: float, session: str, project: str) -> Event:
        return Event(
            f"s{ts}", ts, Tool.CLAUDE, "a", "m", "anthropic", project, session, Usage(input=10)
        )

    events = [
        request(at(0, 9), "abcdef123456", "/w/alpha"),
        request(at(0, 11, 30), "abcdef123456", "/w/alpha"),
        request(at(0, 10), "zzz", "/w/beta"),
    ]
    snapshot = snap(events, detail=GroupBy.SESSION)
    assert [(r.name, r.extra, r.tally.calls) for r in snapshot.breakdown] == [
        ("alpha · abcdef12", "09:00 → 11:30", 2),
        ("beta · zzz", "10:00 → 10:00", 1),
    ]
    assert "alpha · abcdef12" in snap(events, group=GroupBy.SESSION).groups
    retained = [request(at(0, 8), "", "(retained daily total)")]
    assert snap(retained, detail=GroupBy.SESSION).breakdown[0].name.endswith(" · -")
