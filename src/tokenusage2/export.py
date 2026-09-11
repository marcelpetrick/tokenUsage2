# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""CSV export of the current view: the timeline rows and the selected bucket's breakdown."""

import csv
import io
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from tokenusage2.aggregate import Snapshot, Tally

TALLY_FIELDS = (
    "calls",
    "input",
    "cache_read",
    "cache_write",
    "cache_write_1h",
    "output",
    "reasoning",
    "unsplit",
    "total",
    "cost",
    "unpriced",
)
TIMELINE_FIELDS = ("period", "bucket_start", "bucket", "group_by", "group", *TALLY_FIELDS)
BREAKDOWN_FIELDS = ("bucket_start", "bucket", "breakdown_by", "name", "extra", *TALLY_FIELDS)


def tally_fields(tally: Tally) -> dict[str, object]:
    values: dict[str, object] = {name: getattr(tally, name) for name in TALLY_FIELDS[:-3]}
    values.update(total=tally.total, cost=round(tally.cost, 6), unpriced=tally.unpriced)
    return values


def timeline_rows(snapshot: Snapshot) -> list[dict[str, object]]:
    """One row per bucket and group, oldest bucket first."""
    return [
        {
            "period": str(snapshot.period),
            "bucket_start": bucket.start.isoformat(),
            "bucket": bucket.long,
            "group_by": str(snapshot.group),
            "group": name,
            **tally_fields(tally),
        }
        for bucket in snapshot.buckets
        for name, tally in sorted(bucket.groups.items())
    ]


def breakdown_rows(snapshot: Snapshot) -> list[dict[str, object]]:
    """The selected bucket broken down as on screen."""
    bucket = snapshot.selected_bucket
    return [
        {
            "bucket_start": bucket.start.isoformat() if bucket else "",
            "bucket": bucket.long if bucket else "",
            "breakdown_by": str(snapshot.detail),
            "name": row.name,
            "extra": row.extra,
            **tally_fields(row.tally),
        }
        for row in snapshot.breakdown
    ]


def to_csv(rows: Iterable[Mapping[str, object]], fields: Sequence[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def export(snapshot: Snapshot, directory: Path, stamp: str) -> tuple[Path, Path]:
    """Write ``timeline-<stamp>.csv`` and ``breakdown-<stamp>.csv`` into ``directory``."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    timeline = directory / f"timeline-{stamp}.csv"
    breakdown = directory / f"breakdown-{stamp}.csv"
    timeline.write_text(to_csv(timeline_rows(snapshot), TIMELINE_FIELDS), encoding="utf-8")
    breakdown.write_text(to_csv(breakdown_rows(snapshot), BREAKDOWN_FIELDS), encoding="utf-8")
    return timeline, breakdown
