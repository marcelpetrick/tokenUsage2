# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""How record keys and archive meta keys are spelled — in one place.

Parsers build record keys; ingestion, the store and the sources report read them
back. Archive migrations keep the historical spellings they convert from.
"""

from datetime import date

BACKFILL_PREFIX = "claude-daily:"
#: Prefixes of record keys that continue with the account id.
ACCOUNT_KEY_PREFIXES = ("opencode:", BACKFILL_PREFIX)


def claude_key(message_id: object, request_id: str) -> str:
    """No account: a copied home must not count a message twice."""
    return f"claude:{message_id}:{request_id}"


def codex_key(thread: str, cumulative: int, restarts: int = 0) -> str:
    """No account, as for Claude; increments after the n-th compaction restart end in ``:r<n>``."""
    return f"codex:{thread}:{cumulative}" + (f":r{restarts}" if restarts else "")


def codex_restarts(key: str) -> int:
    """How many compaction restarts preceded a Codex increment; 0 for any other key."""
    tail = key.rpartition(":")[2]
    return int(tail[1:]) if tail[:1] == "r" and tail[1:].isdigit() else 0


def opencode_key(account: str, row_id: str) -> str:
    return f"opencode:{account}:{row_id}"


def backfill_prefix(account: str) -> str:
    """The prefix of every retained daily total of ``account``."""
    return f"{BACKFILL_PREFIX}{account}:"


def backfill_key(account: str, day: date, model: str) -> str:
    return f"{backfill_prefix(account)}{day.isoformat()}:{model}"


def stats_cache_mark(account: str) -> str:
    """Meta key of the stats-cache signature the retained totals were derived from."""
    return f"statscache:{account}"


def stats_cache_scale_key(account: str) -> str:
    """Meta key of the measured stats-cache scale (see ``format_scale``)."""
    return f"statscache-scale:{account}"


def opencode_watermark(account: str) -> str:
    """Meta key of the newest OpenCode ``time_updated`` already read."""
    return f"opencode-watermark:{account}"


def account_meta_keys(account: str) -> tuple[str, str, str]:
    """Every meta key that belongs to one account."""
    return stats_cache_mark(account), stats_cache_scale_key(account), opencode_watermark(account)


def format_scale(scale: float, days: int) -> str:
    return f"{scale:.6f}:{days}"


def parse_scale(value: str | None) -> tuple[float, int] | None:
    """``(scale, days)`` from ``format_scale``; None when absent or malformed."""
    scale, _, days = (value or "").partition(":")
    try:
        return float(scale), int(days)
    except ValueError:
        return None
