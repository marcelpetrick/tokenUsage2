# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
from pathlib import Path

import pytest

from tokenusage2.version import __version__

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "release_notes", ROOT / "scripts" / "release_notes.py"
)
assert _spec is not None
assert _spec.loader is not None
release_notes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## 1.2.0

### Added

- New thing.

## 1.1.0

- Old thing.
"""


def test_section_stops_at_the_next_version() -> None:
    assert release_notes.section(CHANGELOG, "1.2.0") == "### Added\n\n- New thing."
    assert release_notes.section(CHANGELOG, "1.1.0") == "- Old thing."
    assert release_notes.section(CHANGELOG, "9.9.9") is None
    assert release_notes.section("## 2.0.0\n\n## 1.0.0\n", "2.0.0") is None


def test_every_released_version_documents_itself() -> None:
    # The release workflow uses this section as the notes of the GitHub release.
    assert release_notes.current_version() == __version__
    assert release_notes.section((ROOT / "CHANGELOG.md").read_text(), __version__)


def test_main(capsys: pytest.CaptureFixture[str]) -> None:
    assert release_notes.main(["release_notes.py"]) == 0
    assert capsys.readouterr().out.strip()
    assert release_notes.main(["release_notes.py", "0.0.0-missing"]) == 1
    assert "no section" in capsys.readouterr().err
