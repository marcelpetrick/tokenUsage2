# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Opt-in, non-blocking health checks against the providers' public status APIs."""

import json
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from urllib.request import Request, urlopen

MAX_RESPONSE = 1_000_000


class Health(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProviderStatus:
    provider: str
    health: Health
    detail: str
    checked_at: float | None
    url: str


@dataclass(frozen=True, slots=True)
class StatusEndpoint:
    provider: str
    url: str
    components: tuple[str, ...]


ENDPOINTS = (
    StatusEndpoint(
        "Claude",
        "https://status.claude.com/api/v2/components.json",
        ("Claude API (api.anthropic.com)", "Claude Code"),
    ),
    StatusEndpoint(
        "Codex",
        "https://status.openai.com/api/v2/components.json",
        ("Codex API", "CLI"),
    ),
)

_HEALTH = {
    "operational": Health.OPERATIONAL,
    "degraded_performance": Health.DEGRADED,
    "partial_outage": Health.DEGRADED,
    "major_outage": Health.OUTAGE,
    "under_maintenance": Health.MAINTENANCE,
}
_SEVERITY = {
    Health.UNKNOWN: -1,
    Health.OPERATIONAL: 0,
    Health.MAINTENANCE: 1,
    Health.DEGRADED: 2,
    Health.OUTAGE: 3,
}


class Response(Protocol):
    def __enter__(self) -> Response: ...
    def __exit__(self, *args: object) -> None: ...
    def read(self, amount: int = -1) -> bytes: ...


type Opener = Callable[[Request, float], Response]


def _open(request: Request, timeout: float) -> Response:
    return urlopen(request, timeout=timeout)


def _safe_detail(value: object) -> str:
    """Keep network errors concise and safe for direct terminal rendering."""
    cleaned = "".join(character if character.isprintable() else " " for character in str(value))
    return " ".join(cleaned.split())[:240]


def parse_summary(endpoint: StatusEndpoint, data: object, checked_at: float) -> ProviderStatus:
    """Extract only the provider components tokenUsage2 actually depends on."""
    if not isinstance(data, Mapping) or not isinstance(data.get("components"), list):
        return ProviderStatus(
            endpoint.provider, Health.UNKNOWN, "invalid response", checked_at, endpoint.url
        )
    wanted = {name.casefold(): name for name in endpoint.components}
    found: dict[str, tuple[str, Health]] = {}
    for component in data["components"]:
        if not isinstance(component, Mapping):
            continue
        name = component.get("name")
        raw = component.get("status")
        key = name.casefold() if isinstance(name, str) else ""
        if key in wanted and isinstance(raw, str):
            found[key] = (wanted[key], _HEALTH.get(raw, Health.UNKNOWN))
    if not found:
        return ProviderStatus(
            endpoint.provider,
            Health.UNKNOWN,
            "required components not listed",
            checked_at,
            endpoint.url,
        )
    missing = [name for name in endpoint.components if name.casefold() not in found]
    states = [state for _, state in found.values()]
    problems = [state for state in states if state not in {Health.OPERATIONAL, Health.UNKNOWN}]
    if problems:
        health = max(problems, key=_SEVERITY.__getitem__)
    elif missing or Health.UNKNOWN in states:
        health = Health.UNKNOWN
    else:
        health = Health.OPERATIONAL
    affected = [
        f"{name}: {state}" for name, state in found.values() if state is not Health.OPERATIONAL
    ]
    if missing:
        affected.append(f"not listed: {', '.join(missing)}")
    detail = ", ".join(affected) if affected else "all tracked components operational"
    return ProviderStatus(endpoint.provider, health, detail, checked_at, endpoint.url)


def fetch_status(
    endpoint: StatusEndpoint,
    timeout: float,
    *,
    opener: Opener = _open,
    clock: Callable[[], float] = time.time,
) -> ProviderStatus:
    """Fetch one bounded Statuspage summary without credentials or user data."""
    checked_at = clock()
    request = Request(endpoint.url, headers={"User-Agent": "tokenUsage2/provider-status"})
    try:
        with opener(request, timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("response too large")
        return parse_summary(endpoint, json.loads(raw), checked_at)
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        detail = _safe_detail(error) or type(error).__name__
        return ProviderStatus(endpoint.provider, Health.UNKNOWN, detail, checked_at, endpoint.url)


class ProviderStatusMonitor:
    """Refresh provider health on a daemon thread; callers only read cached state."""

    def __init__(
        self,
        enabled: bool,
        *,
        refresh_seconds: float = 300.0,
        timeout_seconds: float = 2.0,
        endpoints: Sequence[StatusEndpoint] = ENDPOINTS,
        fetcher: Callable[[StatusEndpoint, float], ProviderStatus] = fetch_status,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.enabled = enabled
        self.refresh_seconds = refresh_seconds
        self.timeout_seconds = timeout_seconds
        self.endpoints = tuple(endpoints)
        self.fetcher = fetcher
        self.clock = clock
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: float | None = None
        self._statuses = tuple(
            ProviderStatus(endpoint.provider, Health.UNKNOWN, "checking…", None, endpoint.url)
            for endpoint in self.endpoints
        )
        if not enabled:
            self._statuses = ()
            self._done.set()

    def poll(self) -> None:
        """Start a refresh when stale; never wait for the network."""
        if not self.enabled:
            return
        now = self.clock()
        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
            fresh = self._started_at is not None and now - self._started_at < self.refresh_seconds
            if running or fresh:
                return
            self._started_at = now
            self._done.clear()
            self._thread = threading.Thread(
                target=self._refresh,
                name="tokenusage2-provider-status",
                daemon=True,
            )
            self._thread.start()

    def _refresh(self) -> None:
        statuses = []
        for endpoint in self.endpoints:
            try:
                status = self.fetcher(endpoint, self.timeout_seconds)
            except Exception as error:  # the daemon boundary must always wake waiters
                detail = _safe_detail(error) or type(error).__name__
                status = ProviderStatus(
                    endpoint.provider, Health.UNKNOWN, detail, self.clock(), endpoint.url
                )
            statuses.append(status)
        with self._lock:
            self._statuses = tuple(statuses)
            # Publish an idle state before waking waiters. Otherwise a waiter
            # can observe the completed Event while this thread is still alive
            # and incorrectly suppress a refresh that is already due.
            self._thread = None
        self._done.set()

    def statuses(self) -> tuple[ProviderStatus, ...]:
        self.poll()
        with self._lock:
            return self._statuses

    def wait(self, timeout: float | None = None) -> tuple[ProviderStatus, ...]:
        """Wait for the current opt-in refresh, used by one-shot output modes."""
        self.poll()
        self._done.wait(timeout)
        with self._lock:
            return self._statuses


def status_badge(statuses: Sequence[ProviderStatus]) -> str:
    """Compact header text; disabled checks consume no space."""
    if not statuses:
        return ""
    pending = [status for status in statuses if status.checked_at is None]
    problems = [
        status for status in statuses if status.health not in {Health.OPERATIONAL, Health.UNKNOWN}
    ]
    unknown = [status for status in statuses if status.health is Health.UNKNOWN]
    if problems:
        worst = max(problems, key=lambda status: _SEVERITY[status.health])
        return f"▲ {worst.provider} {worst.health}"
    if pending:
        return "◇ APIs checking"
    if unknown:
        names = "/".join(status.provider for status in unknown)
        return f"◇ {names} unknown"
    return "● APIs operational"


def status_problem(statuses: Sequence[ProviderStatus]) -> str:
    problems = [
        status for status in statuses if status.health not in {Health.OPERATIONAL, Health.UNKNOWN}
    ]
    if not problems:
        return ""
    worst = max(problems, key=lambda status: _SEVERITY[status.health])
    return f"{worst.provider} {worst.health}: {worst.detail}"


def status_lines(statuses: Sequence[ProviderStatus], now: float) -> list[str]:
    if not statuses:
        return ["provider checks disabled (enable [provider_status] or --provider-status)"]
    lines = []
    for status in statuses:
        age = (
            "checking"
            if status.checked_at is None
            else f"checked {max(0, now - status.checked_at):.0f}s ago"
        )
        lines.append(
            f"  {status.provider:<8} {status.health:<11} {status.detail} · {age} · {status.url}"
        )
    return lines
