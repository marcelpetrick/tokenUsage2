# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""SQLite archive of normalised events.

The archive makes restarts instant (files are tailed from their last offset)
and keeps history after Claude Code deletes old transcripts. Duplicate records
are merged by key, keeping the copy with the larger total: Claude writes
streaming copies of a message before the final one.
"""

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from tokenusage2.model import Account, Event, QuotaWindow, Tool, Usage
from tokenusage2.parsers import BACKFILL_PREFIX

SCHEMA_VERSION = 7
_TOOLS = {tool.value: tool for tool in Tool}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS files(
    path TEXT PRIMARY KEY, account TEXT NOT NULL, inode INTEGER NOT NULL,
    size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, offset INTEGER NOT NULL,
    ctx TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
    key TEXT PRIMARY KEY, ts REAL NOT NULL, tool TEXT NOT NULL, account TEXT NOT NULL,
    model TEXT NOT NULL, route TEXT NOT NULL, project TEXT NOT NULL, session TEXT NOT NULL,
    input INTEGER NOT NULL, cache_read INTEGER NOT NULL, cache_write INTEGER NOT NULL,
    output INTEGER NOT NULL, reasoning INTEGER NOT NULL, unsplit INTEGER NOT NULL,
    cache_write_1h INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS events_account_ts ON events(account, ts);
CREATE TABLE IF NOT EXISTS quotas(
    account TEXT NOT NULL, window TEXT NOT NULL, used_percent REAL NOT NULL,
    resets_at REAL, observed_at REAL NOT NULL, source TEXT NOT NULL, plan TEXT,
    PRIMARY KEY(account, window));
CREATE TABLE IF NOT EXISTS accounts(
    id TEXT PRIMARY KEY, tool TEXT NOT NULL, label TEXT NOT NULL, home TEXT NOT NULL,
    identity TEXT, plan TEXT, last_seen REAL NOT NULL);
CREATE TABLE IF NOT EXISTS copies(
    account TEXT NOT NULL, key TEXT NOT NULL, owner TEXT NOT NULL,
    PRIMARY KEY(account, key)) WITHOUT ROWID;
"""
_TOTAL = "{t}.input + {t}.cache_read + {t}.cache_write + {t}.output + {t}.unsplit"
_UPSERT = f"""
INSERT INTO events(key, ts, tool, account, model, route, project, session,
                   input, cache_read, cache_write, output, reasoning, unsplit, cache_write_1h)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(key) DO UPDATE SET
    tool = excluded.tool, account = excluded.account,
    ts = excluded.ts, model = excluded.model, route = excluded.route,
    project = excluded.project, session = excluded.session,
    input = excluded.input, cache_read = excluded.cache_read,
    cache_write = excluded.cache_write, output = excluded.output,
    reasoning = excluded.reasoning, unsplit = excluded.unsplit,
    cache_write_1h = excluded.cache_write_1h
WHERE {_TOTAL.format(t="excluded")} > {_TOTAL.format(t="events")}
   OR ({_TOTAL.format(t="excluded")} = {_TOTAL.format(t="events")}
       AND excluded.cache_write_1h > events.cache_write_1h)
"""


class StoreError(RuntimeError):
    """The archive exists but cannot be used by this version."""


_OWN_CLAUDE_PREFIX = "substr(key, 1, length(account) + 8) = 'claude:' || account || ':'"


def _claude_keys_without_account(conn: sqlite3.Connection) -> None:
    """Schema 1 → 2: Claude keys drop the account, so a copied home collapses.

    Where two homes held the same message, the first renamed row wins and the
    other, which could not take the shared key, is removed.
    """
    conn.execute(
        "UPDATE OR IGNORE events SET key = 'claude:' || substr(key, length(account) + 9) "
        f"WHERE tool = 'claude' AND {_OWN_CLAUDE_PREFIX}"
    )
    conn.execute(f"DELETE FROM events WHERE tool = 'claude' AND {_OWN_CLAUDE_PREFIX}")


def _backend_becomes_route(conn: sqlite3.Connection) -> None:
    """Schema 2 → 3: store what the log says, not a display label.

    Labels are resolved when displaying, so config and launcher changes relabel
    history. Claude rows keep only whether Anthropic's API answered.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
    if "backend" in columns:
        conn.execute("ALTER TABLE events RENAME COLUMN backend TO route")
    conn.execute(
        "UPDATE events SET route = CASE WHEN route = 'anthropic' THEN 'anthropic' ELSE '' END "
        "WHERE tool = 'claude'"
    )


def _cache_write_ttl_split(conn: sqlite3.Connection) -> None:
    """Schema 3 → 4: record the 1-hour-TTL share of cache writes.

    Claude transcripts are read again once — their file offsets are forgotten —
    so archived requests pick up the split; the tie-break in the upsert lets
    the re-read copy replace the one without it.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
    if "cache_write_1h" not in columns:
        conn.execute("ALTER TABLE events ADD COLUMN cache_write_1h INTEGER NOT NULL DEFAULT 0")
    conn.execute("DELETE FROM files WHERE account LIKE 'claude:%'")


def _copies_by_distinct_key(conn: sqlite3.Connection) -> None:
    """Schema 4 → 5: count the records a home shares with another once per key.

    The old tallies grew with every re-read of a copied file, so they are
    dropped, and Claude transcripts are read again once to rebuild them.
    """
    conn.execute("DELETE FROM meta WHERE key = 'duplicates'")
    conn.execute("DELETE FROM files WHERE account LIKE 'claude:%'")


_OWN_CODEX_PREFIX = "substr(key, 1, length(account) + 7) = 'codex:' || account || ':'"


def _codex_keys_without_account(conn: sqlite3.Connection) -> None:
    """Schema 5 → 6: Codex keys drop the account, so a copied home collapses.

    Where two homes held the same increment, the first renamed row wins and the
    other is removed; Codex rollouts are read again once to record the copies.
    """
    conn.execute(
        "UPDATE OR IGNORE events SET key = 'codex:' || substr(key, length(account) + 8) "
        f"WHERE tool = 'codex' AND {_OWN_CODEX_PREFIX}"
    )
    conn.execute(f"DELETE FROM events WHERE tool = 'codex' AND {_OWN_CODEX_PREFIX}")
    conn.execute("DELETE FROM files WHERE account LIKE 'codex:%'")


def _codex_counter_restarts(conn: sqlite3.Connection) -> None:
    """Schema 6 → 7: increments after a compaction restart get their own keys.

    A thread's archived increments are replayed in time order; each drop of the
    cumulative total is a restart, and the increments after the n-th get
    ``:r<n>`` like the parser gives them. Codex rollouts are read again once,
    so every file's restart count is known when it is next read.
    """
    rows = conn.execute("SELECT key, session FROM events WHERE tool = 'codex' ORDER BY session, ts")
    previous: dict[str, int] = {}
    restarts: dict[str, int] = {}
    renames = []
    for key, session in rows.fetchall():
        tail = key.rpartition(":")[2]
        if not tail.isdigit():
            continue
        cumulative = int(tail)
        if cumulative < previous.get(session, 0):
            restarts[session] = restarts.get(session, 0) + 1
        previous[session] = cumulative
        if restarts.get(session):
            renames.append((f"{key}:r{restarts[session]}", key))
    conn.executemany("UPDATE OR IGNORE events SET key = ? WHERE key = ?", renames)
    conn.execute("DELETE FROM files WHERE account LIKE 'codex:%'")


#: ``MIGRATIONS[n]`` upgrades an archive from schema ``n`` to ``n + 1``.
MIGRATIONS = {
    1: _claude_keys_without_account,
    2: _backend_becomes_route,
    3: _cache_write_ttl_split,
    4: _copies_by_distinct_key,
    5: _codex_keys_without_account,
    6: _codex_counter_restarts,
}


@dataclass(slots=True)
class FileState:
    path: str
    account: str
    inode: int
    size: int
    mtime_ns: int
    offset: int
    ctx: dict


def _row(event: Event) -> tuple:
    u = event.usage
    return (
        event.key,
        event.ts,
        str(event.tool),
        event.account,
        event.model,
        event.route,
        event.project,
        event.session,
        u.input,
        u.cache_read,
        u.cache_write,
        u.output,
        u.reasoning,
        u.unsplit,
        u.cache_write_1h,
    )


#: Record keys that continue with the account id (see parsers).
_ACCOUNT_KEYS = ("opencode:", BACKFILL_PREFIX)


class Store:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.conn = sqlite3.connect(str(path) if path else ":memory:", timeout=5.0)
        if path is not None:
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        stored = self.get_meta("schema")
        if stored is not None:
            version = int(stored) if stored.isdigit() else -1
            while version < SCHEMA_VERSION and version in MIGRATIONS:
                MIGRATIONS[version](self.conn)
                version += 1
            if version != SCHEMA_VERSION:
                self.conn.close()
                raise StoreError(
                    f"archive schema {stored} is not supported (expected "
                    f"{SCHEMA_VERSION}); move {path} aside to rebuild it"
                )
        self.set_meta("schema", str(SCHEMA_VERSION))
        self.commit()

    def close(self) -> None:
        self.conn.close()

    def commit(self) -> None:
        self.conn.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def delete_meta(self, key: str) -> None:
        self.conn.execute("DELETE FROM meta WHERE key = ?", (key,))

    def load_file_states(self) -> dict[str, FileState]:
        rows = self.conn.execute(
            "SELECT path, account, inode, size, mtime_ns, offset, ctx FROM files"
        )
        return {row[0]: FileState(*row[:6], json.loads(row[6])) for row in rows}

    def save_file_state(self, state: FileState) -> None:
        self.conn.execute(
            "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(path) DO UPDATE SET "
            "account = excluded.account, inode = excluded.inode, size = excluded.size, "
            "mtime_ns = excluded.mtime_ns, offset = excluded.offset, ctx = excluded.ctx",
            (
                state.path,
                state.account,
                state.inode,
                state.size,
                state.mtime_ns,
                state.offset,
                json.dumps(state.ctx, sort_keys=True),
            ),
        )

    def upsert_events(self, events: Iterable[Event]) -> int:
        before = self.conn.total_changes
        self.conn.executemany(_UPSERT, (_row(event) for event in events))
        return self.conn.total_changes - before

    def replace_events(self, events: Iterable[Event]) -> None:
        """Write ``events`` over whatever their keys hold, larger or not."""
        self.conn.executemany(
            "INSERT OR REPLACE INTO events(key, ts, tool, account, model, route, project, session,"
            " input, cache_read, cache_write, output, reasoning, unsplit, cache_write_1h)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (_row(event) for event in events),
        )

    def delete_events(self, key_prefix: str, min_ts: float) -> int:
        escaped = key_prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        cursor = self.conn.execute(
            "DELETE FROM events WHERE key LIKE ? ESCAPE '\\' AND ts >= ?", (escaped + "%", min_ts)
        )
        return cursor.rowcount

    def add_copies(self, copies: Iterable[tuple[str, str, str]]) -> None:
        """Record ``(account, key, owner)``: ``account`` holds a record ``owner`` counts."""
        self.conn.executemany(
            "INSERT INTO copies VALUES (?, ?, ?) "
            "ON CONFLICT(account, key) DO UPDATE SET owner = excluded.owner",
            copies,
        )

    def drop_copies(self, held: Iterable[tuple[str, str]]) -> None:
        """Forget ``(account, key)`` copies whose account now owns the record."""
        self.conn.executemany("DELETE FROM copies WHERE account = ? AND key = ?", held)

    def copy_counts(self) -> dict[str, dict[str, int]]:
        """``{account: {owner: records}}``, one per distinct record key."""
        counts: dict[str, dict[str, int]] = {}
        rows = self.conn.execute(
            "SELECT account, owner, COUNT(*) FROM copies GROUP BY account, owner"
        )
        for account, owner, records in rows:
            counts.setdefault(account, {})[owner] = records
        return counts

    def rename_account(self, old: str, new: str) -> None:
        """Move everything recorded for account ``old`` to ``new``.

        OpenCode and retained-total keys embed the account and are rewritten;
        a record ``new`` already holds is dropped under ``old``, so a history
        split across both ids counts once.
        """
        conn = self.conn
        for prefix in _ACCOUNT_KEYS:
            before, after = f"{prefix}{old}:", f"{prefix}{new}:"
            conn.execute(
                "UPDATE OR IGNORE events SET key = ? || substr(key, ?) WHERE substr(key, 1, ?) = ?",
                (after, len(before) + 1, len(before), before),
            )
            conn.execute("DELETE FROM events WHERE substr(key, 1, ?) = ?", (len(before), before))
        conn.execute("UPDATE events SET account = ? WHERE account = ?", (new, old))
        conn.execute("UPDATE files SET account = ? WHERE account = ?", (new, old))
        for table in ("quotas", "copies"):
            conn.execute(f"UPDATE OR IGNORE {table} SET account = ? WHERE account = ?", (new, old))
            conn.execute(f"DELETE FROM {table} WHERE account = ?", (old,))
        conn.execute("UPDATE copies SET owner = ? WHERE owner = ?", (new, old))
        conn.execute("DELETE FROM copies WHERE account = owner")
        conn.execute("DELETE FROM accounts WHERE id = ?", (old,))
        conn.execute(
            "DELETE FROM meta WHERE key IN (?, ?, ?)",
            (f"statscache:{old}", f"statscache-scale:{old}", f"opencode-watermark:{old}"),
        )

    def load_events(self) -> list[Event]:
        rows = self.conn.execute(
            "SELECT key, ts, tool, account, model, route, project, session, input, "
            "cache_read, cache_write, output, reasoning, unsplit, cache_write_1h "
            "FROM events ORDER BY ts"
        )
        return [
            Event(r[0], r[1], _TOOLS[r[2]], r[3], r[4], r[5], r[6], r[7], Usage(*r[8:]))
            for r in rows
        ]

    def upsert_quotas(self, quotas: Iterable[QuotaWindow]) -> int:
        before = self.conn.total_changes
        self.conn.executemany(
            "INSERT INTO quotas VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(account, window) "
            "DO UPDATE SET used_percent = excluded.used_percent, resets_at = excluded.resets_at,"
            " observed_at = excluded.observed_at, source = excluded.source, plan = excluded.plan"
            " WHERE excluded.observed_at > quotas.observed_at",
            (
                (q.account, q.window, q.used_percent, q.resets_at, q.observed_at, q.source, q.plan)
                for q in quotas
            ),
        )
        return self.conn.total_changes - before

    def load_quotas(self) -> list[QuotaWindow]:
        rows = self.conn.execute(
            "SELECT account, window, used_percent, resets_at, observed_at,"
            " source, plan FROM quotas ORDER BY account, window"
        )
        return [QuotaWindow(*row) for row in rows]

    def upsert_accounts(self, accounts: Iterable[Account], now: float) -> None:
        self.conn.executemany(
            "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
            "label = excluded.label, home = excluded.home, identity = excluded.identity, "
            "plan = excluded.plan, last_seen = excluded.last_seen",
            ((a.id, str(a.tool), a.label, str(a.home), a.identity, a.plan, now) for a in accounts),
        )

    def load_accounts(self) -> list[Account]:
        rows = self.conn.execute(
            "SELECT id, tool, label, home, identity, plan FROM accounts ORDER BY id"
        )
        return [Account(r[0], Tool(r[1]), Path(r[3]), r[2], r[4], r[5], "archive") for r in rows]

    def event_counts(self) -> dict[str, tuple[int, float, float]]:
        rows = self.conn.execute(
            "SELECT account, COUNT(*), MIN(ts), MAX(ts) FROM events GROUP BY account"
        )
        return {row[0]: (row[1], row[2], row[3]) for row in rows}
