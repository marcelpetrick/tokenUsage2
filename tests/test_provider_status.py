# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from urllib.request import Request

from tokenusage2.provider_status import (
    Health,
    ProviderStatus,
    ProviderStatusMonitor,
    StatusEndpoint,
    fetch_status,
    parse_summary,
    status_badge,
    status_lines,
    status_problem,
)

ENDPOINT = StatusEndpoint("Codex", "https://status.example/summary.json", ("Codex API", "CLI"))


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def read(self, amount: int = -1) -> bytes:
        return self.data[:amount]


def summary(*components: tuple[str, str]) -> dict:
    return {"components": [{"name": name, "status": status} for name, status in components]}


def test_summary_tracks_only_relevant_components_and_the_worst_state() -> None:
    result = parse_summary(
        ENDPOINT,
        summary(
            ("Responses", "major_outage"),
            ("Codex API", "operational"),
            ("CLI", "partial_outage"),
        ),
        12.0,
    )
    assert result == ProviderStatus(
        "Codex",
        Health.DEGRADED,
        "CLI: degraded",
        12.0,
        "https://status.example/summary.json",
    )
    partial = parse_summary(ENDPOINT, summary(("CLI", "operational")), 1)
    assert (partial.health, partial.detail) == (Health.UNKNOWN, "not listed: Codex API")


def test_summary_rejects_invalid_or_missing_components() -> None:
    assert parse_summary(ENDPOINT, [], 1).detail == "invalid response"
    missing = parse_summary(ENDPOINT, summary(("Other", "operational")), 1)
    assert (missing.health, missing.detail) == (
        Health.UNKNOWN,
        "required components not listed",
    )
    assert parse_summary(ENDPOINT, summary(("CLI", "new_state")), 1).health is Health.UNKNOWN


def test_fetch_status_is_bounded_and_turns_failures_into_unknown() -> None:
    seen: list[tuple[str, float, str]] = []

    def opener(request: Request, timeout: float) -> FakeResponse:
        seen.append((request.full_url, timeout, request.headers["User-agent"]))
        return FakeResponse(
            json.dumps(summary(("Codex API", "operational"), ("CLI", "operational"))).encode()
        )

    result = fetch_status(ENDPOINT, 1.5, opener=opener, clock=lambda: 10.0)
    assert result.health is Health.OPERATIONAL
    assert seen == [(ENDPOINT.url, 1.5, "tokenUsage2/provider-status")]

    def broken(request: Request, timeout: float) -> FakeResponse:
        raise OSError("offline")

    failed = fetch_status(ENDPOINT, 1, opener=broken, clock=lambda: 11.0)
    assert (failed.health, failed.detail, failed.checked_at) == (Health.UNKNOWN, "offline", 11.0)

    def unsafe_error(request: Request, timeout: float) -> FakeResponse:
        raise OSError("offline\x1b[31m\nnow")

    assert fetch_status(ENDPOINT, 1, opener=unsafe_error).detail == "offline [31m now"


def test_monitor_is_opt_in_cached_and_refreshes_off_thread() -> None:
    disabled = ProviderStatusMonitor(False, endpoints=(ENDPOINT,))
    assert disabled.wait() == ()

    moment = [100.0]
    calls: list[float] = []

    def fetcher(endpoint: StatusEndpoint, timeout: float) -> ProviderStatus:
        calls.append(timeout)
        return ProviderStatus(endpoint.provider, Health.OPERATIONAL, "ok", moment[0], endpoint.url)

    monitor = ProviderStatusMonitor(
        True,
        refresh_seconds=30,
        timeout_seconds=1.25,
        endpoints=(ENDPOINT,),
        fetcher=fetcher,
        clock=lambda: moment[0],
    )
    assert monitor.statuses()[0].detail in {"checking…", "ok"}
    assert monitor.wait(1)[0].detail == "ok"
    assert calls == [1.25]
    assert monitor.wait(1)[0].detail == "ok"
    assert calls == [1.25]
    moment[0] += 31
    assert monitor.wait(1)[0].checked_at == 131.0
    assert calls == [1.25, 1.25]

    def crash(endpoint: StatusEndpoint, timeout: float) -> ProviderStatus:
        raise RuntimeError("unexpected failure")

    failed = ProviderStatusMonitor(True, endpoints=(ENDPOINT,), fetcher=crash)
    result = failed.wait(1)[0]
    assert (result.health, result.detail) == (Health.UNKNOWN, "unexpected failure")


def test_badges_problems_and_report_lines() -> None:
    good = ProviderStatus("Claude", Health.OPERATIONAL, "ok", 9.0, "https://status")
    bad = ProviderStatus("Codex", Health.OUTAGE, "CLI: outage", 8.0, "https://status")
    unknown = ProviderStatus("Codex", Health.UNKNOWN, "offline", 7.0, "https://status")
    pending = ProviderStatus("Claude", Health.UNKNOWN, "checking…", None, "https://status")
    assert status_badge(()) == ""
    assert status_badge((good,)) == "● APIs operational"
    assert status_badge((bad, good)) == "▲ Codex outage"
    assert status_badge((unknown,)) == "◇ Codex unknown"
    assert status_badge((pending,)) == "◇ APIs checking"
    assert status_problem((good,)) == ""
    assert status_problem((bad,)) == "Codex outage: CLI: outage"
    assert "checked 2s ago" in status_lines((good,), 11)[0]
    assert "checks disabled" in status_lines((), 11)[0]
