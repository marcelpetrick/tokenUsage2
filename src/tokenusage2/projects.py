# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Display-time project attribution without changing archived working directories."""

import re
import tempfile
from collections.abc import Iterable
from pathlib import Path, PurePath

_CLAUDE_TEMP = re.compile(r"claude-\d+")


def project_name(path: str) -> str:
    """The conservative basename fallback for a raw working directory."""
    if not path:
        return "(unknown)"
    if path.startswith("("):
        return path
    return PurePath(path).name or path


def _encoded(path: Path) -> str:
    return "-" + path.as_posix().lstrip("/").replace("/", "-")


def _scratch_key(path: Path) -> str | None:
    """Claude's encoded source path in a `.../scratchpad/...` working directory."""
    parts = path.parts
    for index, part in enumerate(parts):
        if (
            _CLAUDE_TEMP.fullmatch(part)
            and len(parts) > index + 3
            and parts[index + 3] == "scratchpad"
        ):
            return parts[index + 1]
    return None


def _display_parts(path: Path) -> tuple[str, ...]:
    """Path components that are useful in a concise, portable label."""
    return tuple(part for part in path.parts if part != path.anchor)


def _unique_path_labels(paths: Iterable[Path]) -> dict[Path, str]:
    """Return the shortest distinguishing suffix for every canonical path."""
    unique = set(paths)
    depths = dict.fromkeys(unique, 1)
    while True:
        labels = {
            path: "/".join(_display_parts(path)[-depths[path] :]) or str(path) for path in unique
        }
        collisions: dict[str, list[Path]] = {}
        for path, label in labels.items():
            collisions.setdefault(label, []).append(path)
        duplicated = [group for group in collisions.values() if len(group) > 1]
        if not duplicated:
            return labels
        changed = False
        for group in duplicated:
            for path in group:
                limit = len(_display_parts(path))
                if depths[path] < limit:
                    depths[path] += 1
                    changed = True
        if not changed:
            return {path: str(path) for path in unique}


class ProjectResolver:
    """Turn raw request CWDs into stable, human project labels.

    Known paths let a Claude-created Codex scratchpad recover the source path
    encoded in its directory name. Git markers collapse nested CWDs to a
    worktree root. Both operations are cached for the lifetime of the event
    generation that created this resolver.
    """

    def __init__(self, paths: Iterable[str], temporary: Path | None = None) -> None:
        self.temporary = (temporary or Path(tempfile.gettempdir())).resolve()
        raw_paths = set(paths)
        candidates: dict[str, set[Path]] = {}
        for raw in raw_paths:
            if not raw or raw.startswith("("):
                continue
            path = Path(raw)
            if not path.is_absolute() or _scratch_key(path) is not None:
                continue
            for candidate in (path, *path.parents):
                if candidate == candidate.parent:
                    continue
                candidates.setdefault(_encoded(candidate), set()).add(candidate)
        self._encoded = candidates
        self._labels: dict[str, str] = {}
        targets = {target for raw in raw_paths if (target := self._canonical_path(raw)) is not None}
        self._path_labels = _unique_path_labels(targets)

    @staticmethod
    def _git_root(path: Path) -> Path | None:
        if not path.is_absolute():
            return None
        for candidate in (path, *path.parents):
            if (candidate / ".git").exists():
                return candidate
        return None

    def _scratch_source(self, path: Path) -> Path | None:
        key = _scratch_key(path)
        choices = self._encoded.get(key, set()) if key is not None else set()
        if not choices:
            return None
        roots = {root for choice in choices if (root := self._git_root(choice)) is not None}
        if len(roots) == 1:
            return roots.pop()
        existing = {choice for choice in choices if choice.exists()}
        return next(iter(existing)) if len(existing) == 1 else None

    def _canonical_path(self, raw: str) -> Path | None:
        if not raw or raw.startswith("("):
            return None
        path = Path(raw)
        source = self._scratch_source(path)
        return self._git_root(source or path)

    def label(self, raw: str) -> str:
        cached = self._labels.get(raw)
        if cached is not None:
            return cached
        if not raw or raw.startswith("("):
            label = project_name(raw)
        else:
            path = Path(raw)
            source = self._scratch_source(path)
            root = self._git_root(source or path)
            if root is not None:
                label = self._path_labels.get(root, root.name or str(root))
            elif path.is_absolute() and path.is_relative_to(self.temporary):
                label = "(temporary)"
            else:
                label = project_name(str(source or path))
        self._labels[raw] = label
        return label
