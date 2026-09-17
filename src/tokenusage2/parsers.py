# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pure record parsers: one JSONL line (or database row) in, one event out.

Every parser cheaply rejects lines by substring before paying for
``json.loads``, because rollout files are dominated by large content records.
Codex writes the record type within the first ~100 bytes of every line, so only
that head is searched — never the multi-megabyte content that follows.
"""

import json
import math
import statistics
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Protocol

from tokenusage2 import keys
from tokenusage2.model import Account, Event, QuotaWindow, Tool, Usage

CODEX_WINDOWS = {300: "5h", 10080: "week"}
#: Codex's record type sits at byte ~60-92 of a line; 256 leaves ample margin.
CODEX_HEAD = 256


class Parser(Protocol):
    ctx: dict
    errors: int
    quotas: list[QuotaWindow]

    def feed(self, line: bytes) -> Event | None: ...


def count(value: object) -> int:
    """A non-negative integer token count, tolerating junk."""
    if type(value) is int:  # the common case, and bool is excluded by the exact type
        return value if value > 0 else 0
    return max(0, int(value)) if type(value) is float and math.isfinite(value) else 0


def parse_ts(value: object) -> float | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.timestamp()


def claude_route(request_id: str) -> str:
    """Anthropic's API stamps every response with a ``req_…`` request id; local
    Anthropic-compatible servers (Ollama, proxies) do not."""
    return "anthropic" if request_id.startswith("req_") else ""


def cache_write_1h(usage: Mapping[str, object]) -> int:
    """The 1-hour-TTL share of a Claude cache write, never more than the write."""
    split = usage.get("cache_creation")
    if not isinstance(split, dict):
        return 0
    return min(
        count(split.get("ephemeral_1h_input_tokens")),
        count(usage.get("cache_creation_input_tokens")),
    )


def _loads(line: bytes | str) -> dict | None:
    try:
        data = json.loads(line)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


class ClaudeParser:
    """Claude Code transcript lines (``projects/**/*.jsonl``)."""

    def __init__(self, account: str) -> None:
        self.account = account
        self.ctx: dict = {}
        self.errors = 0
        self.quotas: list[QuotaWindow] = []

    def feed(self, line: bytes) -> Event | None:
        if b'"usage"' not in line:
            return None
        obj = _loads(line)
        if obj is None:
            self.errors += 1
            return None
        message = obj.get("message")
        if obj.get("type") != "assistant" or not isinstance(message, dict):
            return None
        usage = message.get("usage")
        model = str(message.get("model") or "unknown")
        ident = message.get("id") or obj.get("uuid")
        ts = parse_ts(obj.get("timestamp"))
        if not isinstance(usage, dict) or model == "<synthetic>" or not ident or ts is None:
            return None
        details = usage.get("output_tokens_details")
        tokens = Usage(
            input=count(usage.get("input_tokens")),
            cache_read=count(usage.get("cache_read_input_tokens")),
            cache_write=count(usage.get("cache_creation_input_tokens")),
            cache_write_1h=cache_write_1h(usage),
            output=count(usage.get("output_tokens")),
            reasoning=count(details.get("thinking_tokens")) if isinstance(details, dict) else 0,
        )
        if tokens.total == 0:
            return None
        request_id = str(obj.get("requestId") or "")
        return Event(
            key=keys.claude_key(ident, request_id),
            ts=ts,
            tool=Tool.CLAUDE,
            account=self.account,
            model=model,
            route=claude_route(request_id),
            project=str(obj.get("cwd") or ""),
            session=str(obj.get("sessionId") or ""),
            usage=tokens,
        )


def codex_usage(data: Mapping[str, object]) -> Usage:
    """Codex reports ``input_tokens`` including the cached part; split it."""
    total_input = count(data.get("input_tokens"))
    cached = min(count(data.get("cached_input_tokens")), total_input)
    written = min(count(data.get("cache_write_input_tokens")), total_input - cached)
    return Usage(
        input=total_input - cached - written,
        cache_read=cached,
        cache_write=written,
        output=count(data.get("output_tokens")),
        reasoning=count(data.get("reasoning_output_tokens")),
    )


def thread_from_filename(path: Path) -> str:
    stem = path.stem
    return stem[-36:] if len(stem) >= 36 else stem


class CodexParser:
    """Codex rollout lines (``sessions/**/rollout-*.jsonl``).

    ``token_count`` events repeat the same cumulative total whenever only the
    rate limits refresh, so the pair (thread, cumulative total) identifies one
    usage increment. Compaction restarts the cumulative total, so every
    increment after the n-th restart gets ``:r<n>`` appended to its key — it
    could otherwise repeat an earlier total and be dropped as that increment.
    ``ctx`` carries thread, model, cwd, provider and the restart count across
    incremental reads of the same file.
    """

    def __init__(self, account: str, ctx: Mapping[str, object], fallback_thread: str) -> None:
        self.account = account
        self.ctx: dict = dict(ctx)
        self.ctx.setdefault("thread", fallback_thread)
        self.errors = 0
        self._limits: dict | None = None
        self._limits_ts = 0.0

    def feed(self, line: bytes) -> Event | None:
        head = line[:CODEX_HEAD]
        if b'"token_count"' in head:
            return self._token_count(line)
        if b'"session_meta"' in head or b'"turn_context"' in head:
            self._context(line)
        return None

    def _context(self, line: bytes) -> None:
        obj = _loads(line)
        if obj is None:
            self.errors += 1
            return
        payload = obj.get("payload")
        if not isinstance(payload, dict):
            return
        if obj.get("type") == "session_meta" and not self.ctx.get("meta"):
            self.ctx["meta"] = True
            if payload.get("id"):
                self.ctx["thread"] = str(payload["id"])
            self.ctx["cwd"] = str(payload.get("cwd") or "")
            self.ctx["provider"] = str(payload.get("model_provider") or "openai")
        elif obj.get("type") == "turn_context" and payload.get("model"):
            self.ctx["model"] = str(payload["model"])

    def _rate_limits(self, limits: object, ts: float) -> None:
        # Only the newest account-level limits matter; build windows once, at the end.
        if isinstance(limits, dict) and limits.get("limit_id") in {None, "codex"}:
            self._limits, self._limits_ts = limits, ts

    @property
    def quotas(self) -> list[QuotaWindow]:
        """The newest account-level rate-limit windows seen in this read."""
        limits = self._limits
        if limits is None:
            return []
        plan = str(limits["plan_type"]) if limits.get("plan_type") else None
        windows = []
        for slot in ("primary", "secondary"):
            window = limits.get(slot)
            if not isinstance(window, dict):
                continue
            used = window.get("used_percent")
            if isinstance(used, bool) or not isinstance(used, int | float):
                continue
            minutes = count(window.get("window_minutes"))
            resets = window.get("resets_at")
            windows.append(
                QuotaWindow(
                    account=self.account,
                    window=CODEX_WINDOWS.get(minutes, f"{minutes}m"),
                    used_percent=float(used),
                    resets_at=float(resets) if isinstance(resets, int | float) else None,
                    observed_at=self._limits_ts,
                    source="codex rollout",
                    plan=plan,
                )
            )
        return windows

    def _token_count(self, line: bytes) -> Event | None:
        obj = _loads(line)
        if obj is None:
            self.errors += 1
            return None
        payload = obj.get("payload")
        ts = parse_ts(obj.get("timestamp"))
        if obj.get("type") != "event_msg" or not isinstance(payload, dict) or ts is None:
            return None
        if payload.get("type") != "token_count":
            return None
        self._rate_limits(payload.get("rate_limits"), ts)
        info = payload.get("info")
        if not isinstance(info, dict):
            return None
        total = info.get("total_token_usage")
        last = info.get("last_token_usage")
        if not isinstance(total, dict) or not isinstance(last, dict):
            return None
        cumulative = count(total.get("total_tokens"))
        tokens = codex_usage(last)
        if cumulative == 0 or tokens.total == 0:
            return None
        # Restarts are found on the increments themselves, as the schema-7 upgrade
        # finds them in the archive, so both give an increment the same key.
        if cumulative < self.ctx.get("cumulative", 0):
            self.ctx["resets"] = self.ctx.get("resets", 0) + 1
        self.ctx["cumulative"] = cumulative
        thread = str(self.ctx["thread"])
        resets = self.ctx.get("resets", 0)
        return Event(
            key=keys.codex_key(thread, cumulative, resets),
            ts=ts,
            tool=Tool.CODEX,
            account=self.account,
            model=str(self.ctx.get("model") or "unknown"),
            route=str(self.ctx.get("provider") or "openai"),
            project=str(self.ctx.get("cwd") or ""),
            session=thread,
            usage=tokens,
        )


def make_parser(account: Account, ctx: Mapping[str, object], path: Path) -> Parser:
    if account.tool is Tool.CODEX:
        return CodexParser(account.id, ctx, thread_from_filename(path))
    return ClaudeParser(account.id)


def parse_opencode_message(account: str, row_id: str, data: str | bytes) -> Event | None:
    """One row of OpenCode's ``message`` table."""
    obj = _loads(data)
    if obj is None or obj.get("role") != "assistant":
        return None
    tokens = obj.get("tokens")
    times = obj.get("time")
    if not isinstance(tokens, dict) or not isinstance(times, dict):
        return None
    created = times.get("created")
    if isinstance(created, bool) or not isinstance(created, int | float):
        return None
    cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
    fresh = count(tokens.get("input"))
    output = count(tokens.get("output"))
    reasoning = count(tokens.get("reasoning"))
    read, write = count(cache.get("read")), count(cache.get("write"))
    # OpenCode keeps reasoning apart from output unless its own total says otherwise.
    if tokens.get("total") != fresh + output + read + write:
        output += reasoning
    usage = Usage(
        input=fresh, cache_read=read, cache_write=write, output=output, reasoning=reasoning
    )
    if usage.total == 0:
        return None
    path = obj.get("path") if isinstance(obj.get("path"), dict) else {}
    return Event(
        key=keys.opencode_key(account, row_id),
        ts=created / 1000.0,
        tool=Tool.OPENCODE,
        account=account,
        model=str(obj.get("modelID") or "unknown"),
        route=str(obj.get("providerID") or "unknown"),
        project=str(path.get("cwd") or ""),
        session=str(obj.get("sessionID") or ""),
        usage=usage,
    )


def stats_cache_days(data: Mapping[str, object]) -> Iterator[tuple[date, dict]]:
    """``(date, tokensByModel)`` of every well-formed ``dailyModelTokens`` entry."""
    days = data.get("dailyModelTokens")
    for day in days if isinstance(days, list) else []:
        if not isinstance(day, dict) or not isinstance(day.get("tokensByModel"), dict):
            continue
        try:
            yield date.fromisoformat(str(day.get("date"))), day["tokensByModel"]
        except ValueError:
            continue


def stats_cache_scale(data: Mapping[str, object], requests: Iterable[Event]) -> tuple[float, int]:
    """Tokens the requests really used per token the stats cache counts, and on how many days.

    Claude Code's stats cache adds up every transcript line, and a response is
    written once per content block, so its daily totals run about twice the
    requests behind them. The ratio is measured on the days the cache shares
    with ``requests`` (deduplicated transcript records): after the first
    request's day, which cleanup may have cut, and before the day the cache was
    last computed, which may be partial. Cleanup removes whole transcripts, so
    the first days after that can still be cut; days whose ratio is below half
    the median day's are left out. It is never above 1, and ``(1.0, 0)`` when
    nothing overlaps.
    """
    used: dict[tuple[date, str], int] = {}
    for request in requests:
        day = datetime.fromtimestamp(request.ts, UTC).date()
        used[day, request.model] = used.get((day, request.model), 0) + request.usage.total
    if not used:
        return 1.0, 0
    first = min(day for day, _ in used)
    try:
        computed: date | None = date.fromisoformat(str(data.get("lastComputedDate")))
    except ValueError:
        computed = None
    per_day: dict[date, list[int]] = {}  # day -> [cached, measured]
    for when, models in stats_cache_days(data):
        if when <= first or (computed is not None and when >= computed):
            continue
        for model, tokens in models.items():
            if (when, str(model)) in used and count(tokens):
                sums = per_day.setdefault(when, [0, 0])
                sums[0] += count(tokens)
                sums[1] += used[when, str(model)]
    if not per_day:
        return 1.0, 0
    median = statistics.median(measured / cached for cached, measured in per_day.values())
    whole = [
        (cached, measured)
        for cached, measured in per_day.values()
        if measured / cached >= median / 2
    ]
    cached = sum(cached for cached, _ in whole)
    measured = sum(measured for _, measured in whole)
    return min(1.0, measured / cached), len(whole)


def parse_stats_cache(
    account: str,
    data: Mapping[str, object],
    before: date | None,
    scale: float = 1.0,
) -> list[Event]:
    """Claude's retained daily totals, only for UTC days before the first transcript's.

    The cache's dates are UTC days, so each total is placed at UTC noon. The
    split into input/cache/output is not retained, so the tokens are recorded
    as ``unsplit`` and drawn hatched. ``scale`` (see ``stats_cache_scale``)
    turns the cache's per-line count into requests.
    """
    events = []
    for when, models in stats_cache_days(data):
        if before is not None and when >= before:
            continue
        noon = datetime.combine(when, time(12), tzinfo=UTC).timestamp()
        for model, raw in models.items():
            tokens = round(count(raw) * scale)
            if tokens == 0:
                continue
            model = str(model)
            events.append(
                Event(
                    key=keys.backfill_key(account, when, model),
                    ts=noon,
                    tool=Tool.CLAUDE,
                    account=account,
                    model=model,
                    route="anthropic" if model.startswith("claude-") else "",
                    project="(retained daily total)",
                    session="",
                    usage=Usage(unsplit=tokens),
                )
            )
    return events


def parse_claude_quota(
    account: str, data: Mapping[str, object], fallback_ts: float, source: str
) -> list[QuotaWindow]:
    """A Claude Code statusline snapshot with ``five_hour``/``seven_day`` windows."""
    observed = data.get("updated_at")
    observed_at = float(observed) if isinstance(observed, int | float) else fallback_ts
    quotas = []
    for key, name in (("five_hour", "5h"), ("seven_day", "week")):
        window = data.get(key)
        if not isinstance(window, dict):
            continue
        used = window.get("used_percentage", window.get("used_percent"))
        if isinstance(used, bool) or not isinstance(used, int | float):
            continue
        resets = window.get("resets_at")
        quotas.append(
            QuotaWindow(
                account=account,
                window=name,
                used_percent=float(used),
                resets_at=float(resets) if isinstance(resets, int | float) and resets else None,
                observed_at=observed_at,
                source=source,
            )
        )
    return quotas
