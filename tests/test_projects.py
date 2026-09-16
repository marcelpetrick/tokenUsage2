# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from tokenusage2.projects import ProjectResolver, project_name


def encode(path: Path) -> str:
    return "-" + path.as_posix().lstrip("/").replace("/", "-")


def test_project_name_is_the_conservative_fallback() -> None:
    assert project_name("") == "(unknown)"
    assert project_name("/a/b/") == "b"
    assert project_name("(retained daily total)") == "(retained daily total)"
    assert project_name("/") == "/"


def test_nested_and_deleted_paths_resolve_to_the_git_root(tmp_path: Path) -> None:
    root = tmp_path / "work" / "real-project"
    (root / ".git").mkdir(parents=True)
    nested = root / "deleted" / "nested"
    resolver = ProjectResolver([str(nested)])
    assert resolver.label(str(root)) == "real-project"
    assert resolver.label(str(nested)) == "real-project"


def test_claude_scratchpad_resolves_through_its_encoded_source(tmp_path: Path) -> None:
    root = tmp_path / "repos" / "source-with-hyphens"
    (root / ".git").mkdir(parents=True)
    nested = root / "src" / "frontend"
    scratch = (
        Path("/tmp")
        / "claude-1000"
        / encode(nested)
        / "00000000-0000-0000-0000-000000000000"
        / "scratchpad"
        / "cat"
    )
    resolver = ProjectResolver([str(nested), str(scratch)])
    assert resolver.label(str(scratch)) == "source-with-hyphens"


def test_temporary_unknown_and_retained_paths_have_honest_labels(tmp_path: Path) -> None:
    resolver = ProjectResolver([], temporary=tmp_path)
    assert resolver.label(str(tmp_path / "scratch" / "cat")) == "(temporary)"
    assert resolver.label("relative/project") == "project"
    assert resolver.label("") == "(unknown)"
    assert resolver.label("(retained daily total)") == "(retained daily total)"
