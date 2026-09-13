# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Incremental ingestion: tail append-only logs into the archive and memory.

A file is skipped while its inode, size and mtime are unchanged. When it grows,
only the new complete lines are read; when it is replaced or truncated it is
re-read from the start. Keys make every re-read idempotent.
"""

import json
import os
import sqlite3
import time
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, datetime, tzinfo
from datetime import time as clock_time
from pathlib import Path

from tokenusage2.aggregate import Lifetime, Tally, lifetimes_of
from tokenusage2.discover import Discovery, display_path
from tokenusage2.model import Account, Event, QuotaWindow, Tool
from tokenusage2.parsers import (
    BACKFILL_PREFIX,
    make_parser,
    parse_claude_quota,
    parse_opencode_message,
    parse_stats_cache,
    stats_cache_scale,
)
from tokenusage2.store import FileState, Store

type Progress = Callable[[int, int], None]

#: Files read per write transaction, so another tokenusage2 never waits long.
COMMIT_EVERY = 64


class EventIndex:
    """In-memory events by key, applying the archive's keep-the-larger rule.

    Per-account lifetime totals, the first transcript timestamp and the record
    count are maintained on every change, so neither a frame nor a scan has to
    walk the whole history. Removing the first or newest record of an account
    marks it stale; that one account is recomputed when next read.
    """

    def __init__(self, events: Iterable[Event] = (), *, ordered: bool = False) -> None:
        loaded = list(events)
        self._by_key: dict[str, Event] = {event.key: event for event in loaded}
        # The archive hands over rows already sorted by time; no need to sort again.
        unique = len(loaded) == len(self._by_key)
        self._sorted: list[Event] | None = loaded if ordered and unique else None
        self.generation = 0
        self._lifetimes = lifetimes_of(self._by_key.values())
        self._first: dict[str, float] = {}
        self._records: dict[str, int] = {}
        self._stale: set[str] = set()
        for event in self._by_key.values():
            self._note(event)

    def __len__(self) -> int:
        return len(self._by_key)

    def get(self, key: str) -> Event | None:
        return self._by_key.get(key)

    def _note(self, event: Event) -> None:
        if event.key.startswith(BACKFILL_PREFIX):
            return
        account = event.account
        self._records[account] = self._records.get(account, 0) + 1
        first = self._first.get(account)
        if first is None or event.ts < first:
            self._first[account] = event.ts

    def _add(self, event: Event) -> None:
        lifetime = self._lifetimes.get(event.account)
        if lifetime is None:
            lifetime = self._lifetimes[event.account] = Lifetime()
        lifetime.tally.add(event.usage)
        per_model = lifetime.models.get((event.tool, event.model, event.route))
        if per_model is None:
            per_model = lifetime.models[event.tool, event.model, event.route] = Tally()
        per_model.add(event.usage)
        if not event.usage.unsplit and (lifetime.last_ts is None or event.ts > lifetime.last_ts):
            lifetime.last_ts = event.ts
        self._note(event)

    def _remove(self, event: Event) -> None:
        account = event.account
        lifetime = self._lifetimes[account]
        lifetime.tally.remove(event.usage)
        per_model = lifetime.models[event.tool, event.model, event.route]
        per_model.remove(event.usage)
        if not per_model.calls and not per_model.total:
            del lifetime.models[event.tool, event.model, event.route]
        if event.ts in (lifetime.last_ts, self._first.get(account)):
            self._stale.add(account)
        if not event.key.startswith(BACKFILL_PREFIX):
            self._records[account] -= 1

    def _refresh(self, account: str) -> None:
        if account not in self._stale:
            return
        self._stale.discard(account)
        mine = [event for event in self._by_key.values() if event.account == account]
        fresh = lifetimes_of(mine).get(account, Lifetime())
        self._lifetimes.setdefault(account, Lifetime()).last_ts = fresh.last_ts
        transcripts = [e.ts for e in mine if not e.key.startswith(BACKFILL_PREFIX)]
        if transcripts:
            self._first[account] = min(transcripts)
        else:
            self._first.pop(account, None)

    def upsert(self, event: Event) -> bool:
        old = self._by_key.get(event.key)
        # The larger copy wins; on a tie, the copy that knows its cache TTL split.
        if old is not None and (event.usage.total, event.usage.cache_write_1h) <= (
            old.usage.total,
            old.usage.cache_write_1h,
        ):
            return False
        return self._put(old, event)

    def replace(self, event: Event) -> bool:
        """Store ``event`` under its key even when it is smaller; False if nothing changes."""
        old = self._by_key.get(event.key)
        return old != event and self._put(old, event)

    def _put(self, old: Event | None, event: Event) -> bool:
        if old is not None:
            self._remove(old)
        self._by_key[event.key] = event
        self._add(event)
        self._sorted = None
        self.generation += 1
        return True

    def discard(self, prefix: str, min_ts: float) -> int:
        doomed = [
            key
            for key, event in self._by_key.items()
            if key.startswith(prefix) and event.ts >= min_ts
        ]
        for key in doomed:
            self._remove(self._by_key.pop(key))
        if doomed:
            self._sorted = None
            self.generation += 1
        return len(doomed)

    def events(self) -> list[Event]:
        if self._sorted is None:
            self._sorted = sorted(self._by_key.values(), key=lambda event: event.ts)
        return self._sorted

    def lifetimes(self) -> dict[str, Lifetime]:
        for account in list(self._stale):
            self._refresh(account)
        return self._lifetimes

    def earliest(self, account: str) -> float | None:
        """First transcript record of ``account`` (retained daily totals excluded)."""
        self._refresh(account)
        return self._first.get(account)

    def count(self, account: str) -> int:
        """Transcript records of ``account`` (retained daily totals excluded)."""
        return self._records.get(account, 0)


@dataclass(slots=True)
class ScanReport:
    files_seen: int = 0
    files_read: int = 0
    bytes_read: int = 0
    events_changed: int = 0
    quota_updates: int = 0
    errors: int = 0
    seconds: float = 0.0
    problems: list[str] = field(default_factory=list)
    #: Set when a newer tokenusage2 owns the archive; the scan then wrote nothing.
    outdated: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.events_changed or self.quota_updates)


def walk_jsonl(root: Path | str, prefix: str = "") -> Iterator[str]:
    """``.jsonl`` files below ``root`` as plain strings (no Path objects per scan)."""
    stack = [str(root)]
    while stack:
        try:
            entries = os.scandir(stack.pop())
        except OSError:
            continue
        with entries:
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    stack.append(entry.path)
                elif entry.name.endswith(".jsonl") and entry.name.startswith(prefix):
                    yield entry.path


class Ingestor:
    def __init__(
        self,
        store: Store,
        discovery: Discovery,
        tz: tzinfo,
        home: Path,
        env: Mapping[str, str],
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.store = store
        self.tz = tz
        self.home = home
        self.env = env
        self.clock = clock
        self._merge_spellings(discovery.accounts)
        self.index = EventIndex(store.load_events(), ordered=True)
        self.quotas = {(q.account, q.window): q for q in store.load_quotas()}
        self._files = store.load_file_states()
        self.last_report = ScanReport()
        #: Records one home already held for another, ``{account: {other: count}}``,
        #: counted once per record key however often a file is read again.
        self.duplicates = store.copy_counts()
        self._copies_changed = False
        self.discovery = discovery
        self.set_discovery(discovery)

    def _merge_spellings(self, accounts: Iterable[Account]) -> None:
        """Fold every archived id of a home into the id it is discovered under now.

        Before 0.11 an account was named after whichever spelling of its home
        was found first, so a symlinked home could collect several ids.
        """
        self.store.begin()
        if self.store.newer_schema():  # a newer build owns the archive: write nothing
            self.store.rollback()
            return
        current = {(account.tool, account.home.resolve()): account.id for account in accounts}
        for stored in self.store.load_accounts():
            new = current.get((stored.tool, stored.home.resolve()))
            if new is not None and new != stored.id:
                self.store.rename_account(stored.id, new)
        self.store.commit()

    def set_discovery(self, discovery: Discovery) -> None:
        self.store.begin()
        self.discovery = discovery
        if self.store.newer_schema():  # a newer build owns the archive: write nothing
            self.store.rollback()
            return
        self.store.upsert_accounts(discovery.accounts, self.clock())
        self.store.commit()

    def files(self) -> list[FileState]:
        return list(self._files.values())

    def files_for(self, account: Account) -> list[str]:
        if account.tool is Tool.CLAUDE:
            return list(walk_jsonl(account.home / "projects"))
        if account.tool is Tool.CODEX:
            return [
                path
                for root in ("sessions", "archived_sessions")
                for path in walk_jsonl(account.home / root, "rollout-")
            ]
        return []

    def scan(self, progress: Progress | None = None) -> ScanReport:
        started = time.perf_counter()
        report = ScanReport()
        jobs = [
            (account, path)
            for account in self.discovery.accounts
            for path in self.files_for(account)
        ]
        if not self._lock(report):  # before anything in memory changes
            return self._finish(report, started)
        for number, (account, path) in enumerate(jobs, 1):
            self._ingest_file(account, path, report)
            if progress is not None and (number % 16 == 0 or number == len(jobs)):
                progress(number, len(jobs))
            if number % COMMIT_EVERY == 0:
                self.store.commit()
                if not self._lock(report):
                    return self._finish(report, started)
        if self._copies_changed:  # the retained totals below ask mirror_of
            self.duplicates = self.store.copy_counts()
            self._copies_changed = False
        for account in self.discovery.accounts:
            if account.tool is Tool.OPENCODE:
                self._ingest_opencode(account, report)
            elif account.tool is Tool.CLAUDE:
                self._backfill(account, report)
                self._claude_quotas(account, report)
        self.store.commit()
        return self._finish(report, started)

    def _lock(self, report: ScanReport) -> bool:
        """Take the write lock; False, with nothing written, when a newer build owns the archive.

        A busy archive raises ``StoreBusyError`` instead, also before anything changes.
        """
        self.store.begin()
        outdated = self.store.newer_schema()
        if outdated:
            self.store.rollback()
            report.outdated = outdated
            report.problems.append(outdated)
        return not outdated

    def _finish(self, report: ScanReport, started: float) -> ScanReport:
        report.seconds = time.perf_counter() - started
        self.last_report = report
        return report

    def _apply(self, events: Iterable[Event]) -> int:
        accepted: list[Event] = []
        #: ``(account, key)`` → the owner of the record that account holds a copy
        #: of, or None once the account owns it; in order, so the last change wins.
        copies: dict[tuple[str, str], str | None] = {}
        for event in events:
            previous = self.index.get(event.key)
            other = previous.account if previous is not None else event.account
            if self.index.upsert(event):
                accepted.append(event)
                if other != event.account:  # the larger copy is here now
                    copies[other, event.key] = event.account
                    copies[event.account, event.key] = None
            elif other != event.account:
                copies[event.account, event.key] = other
        if accepted:
            self.store.upsert_events(accepted)
        if copies:
            self.store.drop_copies(held for held, owner in copies.items() if owner is None)
            self.store.add_copies(
                (account, key, owner) for (account, key), owner in copies.items() if owner
            )
            self._copies_changed = True
        return len(accepted)

    def mirror_of(self, account: str) -> str | None:
        """The home ``account`` merely copies: most of its records are counted there."""
        copies = self.duplicates.get(account)
        if not copies:
            return None
        other, count = max(copies.items(), key=lambda item: item[1])
        return other if count > self.index.count(account) else None

    def _apply_quotas(self, quotas: Iterable[QuotaWindow]) -> int:
        changed = []
        for quota in quotas:
            old = self.quotas.get((quota.account, quota.window))
            if old is None or quota.observed_at > old.observed_at:
                self.quotas[quota.account, quota.window] = quota
                changed.append(quota)
        if changed:
            self.store.upsert_quotas(changed)
        return len(changed)

    def _ingest_file(self, account: Account, key: str, report: ScanReport) -> None:
        try:
            stat = os.stat(key)  # noqa: PTH116 - no Path object per file per scan
        except OSError:
            return
        report.files_seen += 1
        state = self._files.get(key)
        if (
            state is not None
            and state.inode == stat.st_ino
            and state.size == stat.st_size
            and state.mtime_ns == stat.st_mtime_ns
        ):
            return
        resume = (
            state is not None
            and state.inode == stat.st_ino
            and stat.st_size >= state.offset
            and state.account == account.id
        )
        start = state.offset if resume and state is not None else 0
        ctx = state.ctx if resume and state is not None else {}
        path = Path(key)
        parser = make_parser(account, ctx, path)
        events: list[Event] = []
        offset = start
        try:
            with path.open("rb") as handle:
                handle.seek(start)
                feed = parser.feed
                for line in handle:
                    if not line.endswith(b"\n"):
                        break
                    offset += len(line)
                    event = feed(line)
                    if event is not None:
                        events.append(event)
        except OSError as error:
            report.problems.append(f"{display_path(path, self.home)}: {error.strerror}")
            return
        report.files_read += 1
        report.bytes_read += offset - start
        report.errors += parser.errors
        report.events_changed += self._apply(events)
        report.quota_updates += self._apply_quotas(parser.quotas)
        state = FileState(
            key, account.id, stat.st_ino, stat.st_size, stat.st_mtime_ns, offset, parser.ctx
        )
        self._files[key] = state
        self.store.save_file_state(state)

    def _ingest_opencode(self, account: Account, report: ScanReport) -> None:
        mark = f"opencode-watermark:{account.id}"
        since = int(self.store.get_meta(mark) or 0)
        try:
            uri = f"{account.home.resolve().as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=1.0)) as connection:
                rows = connection.execute(
                    "SELECT id, time_updated, data FROM message WHERE time_updated >= ? "
                    "ORDER BY time_updated",
                    (since,),
                ).fetchall()
        except sqlite3.Error as error:
            report.problems.append(f"{display_path(account.home, self.home)}: {error}")
            return
        report.files_seen += 1
        if not rows:
            return
        report.files_read += 1
        events = [
            event
            for row in rows
            if (event := parse_opencode_message(account.id, str(row[0]), row[2]))
        ]
        report.events_changed += self._apply(events)
        self.store.set_meta(mark, str(max(int(row[1]) for row in rows)))

    def _backfill(self, account: Account, report: ScanReport) -> None:
        """Claude's retained daily totals for days no surviving transcript covers."""
        path = account.home / "stats-cache.json"
        try:
            stat = path.stat()
        except OSError:
            return
        first = self.index.earliest(account.id)
        # The cache's dates are UTC days: the first transcript's UTC day may be cut.
        before = datetime.fromtimestamp(first, UTC).date() if first is not None else None
        mirror = self.mirror_of(account.id)
        # The version prefix re-derives totals archived by an older rule once.
        signature = f"v4:{stat.st_size}:{stat.st_mtime_ns}:{before}:{mirror}"
        mark = f"statscache:{account.id}"
        if self.store.get_meta(mark) == signature:
            return
        if mirror is not None:
            # A copy of another home: its retained totals are already counted there.
            prefix = f"{BACKFILL_PREFIX}{account.id}:"
            self.index.discard(prefix, float("-inf"))
            self.store.delete_events(prefix, float("-inf"))
            self.store.delete_meta(f"statscache-scale:{account.id}")
            self.store.set_meta(mark, signature)
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            report.problems.append(f"{display_path(path, self.home)}: {error}")
            return
        prefix = f"{BACKFILL_PREFIX}{account.id}:"
        if before is not None:
            cutoff = datetime.combine(before, clock_time(0), tzinfo=UTC).timestamp()
            self.index.discard(prefix, cutoff)
            self.store.delete_events(prefix, cutoff)
        data = data if isinstance(data, dict) else {}
        requests = [
            event
            for event in self.index.events()
            if event.account == account.id and not event.key.startswith(BACKFILL_PREFIX)
        ]
        scale, days = stats_cache_scale(data, requests)
        # Replaced, not merged by size: a smaller scale must be able to lower a total.
        changed = [
            event
            for event in parse_stats_cache(account.id, data, before, scale)
            if self.index.replace(event)
        ]
        self.store.replace_events(changed)
        report.events_changed += len(changed)
        self.store.set_meta(f"statscache-scale:{account.id}", f"{scale:.6f}:{days}")
        self.store.set_meta(mark, signature)

    def quota_files(self, account: Account) -> list[Path]:
        """Statusline snapshots: the account's own, plus unbound ones for the main home."""
        files = sorted(account.home.glob("*rate-limit*.json"))
        claude_homes = [a.home for a in self.discovery.accounts if a.tool is Tool.CLAUDE]
        if account.home == self.home / ".claude" or len(claude_homes) == 1:
            state_home = Path(self.env.get("XDG_STATE_HOME") or self.home / ".local" / "state")
            files += sorted(state_home.glob("*/quota/claude.json"))
        return files

    def _claude_quotas(self, account: Account, report: ScanReport) -> None:
        quotas: list[QuotaWindow] = []
        for path in self.quota_files(account):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                modified = path.stat().st_mtime
            except OSError, ValueError:
                continue
            if isinstance(data, dict) and data.get("source", "claude") == "claude":
                quotas += parse_claude_quota(
                    account.id, data, modified, display_path(path, self.home)
                )
        report.quota_updates += self._apply_quotas(quotas)
