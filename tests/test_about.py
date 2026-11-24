# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

from email.message import Message
from importlib import metadata

import pytest

from tokenusage2 import about
from tokenusage2.version import __version__


def package(**fields: str | list[str]) -> Message:
    meta = Message()
    for name, value in fields.items():
        for item in value if isinstance(value, list) else [value]:
            meta[name.replace("_", "-")] = item
    return meta


def test_about_text_comes_from_the_package_metadata() -> None:
    meta = package(
        Author_email="Ada Example <ada@example.test>, Bo Example <bo@example.test>",
        License_Expression="GPL-3.0-or-later",
        Project_URL=["Source, https://example.test/repo", "Issues, https://example.test/bugs"],
        Requires_Dist=['pytest==9.2.0; extra == "dev"', "tomli>=2; python_version < '3.11'"],
    )
    text = "\n".join(about.about_lines(meta, "3.14.0"))
    assert f"tokenUsage2 {__version__}" in text
    assert "Prepared by   Ada Example, Bo Example" in text
    assert "@" not in text  # no e-mail addresses in the overlay
    assert "Project page  https://example.test/repo" in text
    assert "Issues        https://example.test/bugs" in text
    assert "GPL-3.0-or-later (GNU General Public License v3 or later)" in text
    assert "ABSOLUTELY NO WARRANTY" in text
    assert "Python 3.14.0, standard library only" in text
    assert "Dev tools     pytest==9.2.0" in text
    assert "tomli" not in text  # only the development extra is listed


def test_about_text_falls_back_when_metadata_is_missing_or_sparse() -> None:
    for meta in (None, package(Author="", Project_URL="Source,")):
        text = "\n".join(about.about_lines(meta, "3.14.1"))
        assert f"Prepared by   {about.AUTHOR}" in text
        assert f"Project page  {about.PROJECT_URL}" in text
        assert f"Issues        {about.PROJECT_URL}/issues" in text
        assert f"Licence       {about.LICENSE}" in text
        assert "Dev tools     see pyproject.toml" in text
    assert "Prepared by   Cy" in "\n".join(about.about_lines(package(Author="Cy"), "3.14"))


def test_installed_metadata_handles_an_uninstalled_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(name: str) -> None:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(about.metadata, "metadata", missing)
    assert about.installed_metadata() is None


def test_installed_about_lines_describe_this_installation() -> None:
    lines = about.installed_about_lines()
    assert lines[0] == f"tokenUsage2 {__version__}"
    assert any("GPL-3.0-or-later" in line for line in lines)
    assert any(about.PROJECT_URL in line for line in lines)
