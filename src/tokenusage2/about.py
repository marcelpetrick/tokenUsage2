# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""The About overlay: who made tokenUsage2, its licence, dependencies and home page.

The text comes from the installed package metadata, so the author, project
URLs and pinned development tools stay in one place: ``pyproject.toml``.
"""

import platform
import re
import textwrap
from collections.abc import Sequence
from functools import cache
from importlib import metadata
from importlib.metadata import PackageMetadata

from tokenusage2.version import __version__

PROJECT_URL = "https://github.com/marcelpetrick/tokenUsage2"
AUTHOR = "Marcel Petrick"
LICENSE = "GPL-3.0-or-later"
# The overlay must stay readable on the smallest supported terminal (70
# columns): its box, borders and padding leave 62 columns for text.
WIDTH = 62
LABEL = 10  # fits the issues URL on one line


def _field(label: str, text: str) -> list[str]:
    """``text`` wrapped under a fixed-width label, never wider than ``WIDTH``."""
    return textwrap.wrap(
        text,
        WIDTH,
        initial_indent=label.ljust(LABEL),
        subsequent_indent=" " * LABEL,
        break_on_hyphens=False,
        break_long_words=False,  # a URL must stay whole to be usable
    )


def _author(meta: PackageMetadata) -> str:
    """The author's name only: an About box needs no e-mail address."""
    for field in ("Author", "Author-email"):
        value = meta.get(field)
        if value:
            names = [re.sub(r"\s*<[^>]*>", "", part).strip() for part in value.split(",")]
            return ", ".join(name for name in names if name) or AUTHOR
    return AUTHOR


def _urls(meta: PackageMetadata) -> dict[str, str]:
    urls = {}
    for entry in meta.get_all("Project-URL") or ():
        label, _, url = entry.partition(",")
        if url.strip():
            urls[label.strip().casefold()] = url.strip()
    return urls


def _dev_tools(meta: PackageMetadata) -> list[str]:
    tools = []
    for requirement in meta.get_all("Requires-Dist") or ():
        spec, _, marker = requirement.partition(";")
        if re.search(r"""extra\s*==\s*["']dev["']""", marker):
            tools.append(spec.strip())
    return tools


def about_lines(meta: PackageMetadata | None, python: str) -> list[str]:
    """The overlay text; ``meta`` is None when tokenUsage2 runs uninstalled."""
    author = _author(meta) if meta is not None else AUTHOR
    urls = _urls(meta) if meta is not None else {}
    licence = (meta.get("License-Expression") if meta is not None else None) or LICENSE
    tools = _dev_tools(meta) if meta is not None else []
    project = urls.get("source", PROJECT_URL)
    issues = urls.get("issues", f"{project}/issues")
    tool_list = ", ".join(tools) if tools else "see pyproject.toml"
    return [
        f"tokenUsage2 {__version__}",
        *textwrap.wrap("Local usage observability for Claude Code, Codex CLI and OpenCode.", WIDTH),
        "",
        *_field("Author", author),
        *_field("Project", project),
        *_field("Issues", issues),
        "",
        *_field("Licence", f"{licence} (GNU GPL v3 or later)"),
        *_field("", "Free software: you may share and change it under that licence."),
        *_field("", "It comes with ABSOLUTELY NO WARRANTY."),
        "",
        *_field("Runtime", f"Python {python}, standard library only; no third-party packages."),
        *_field("Dev tools", tool_list),
        "",
        *textwrap.wrap(
            "Agent files are read-only inputs. Prompts, responses and credentials are never "
            "stored or shown. Costs are standard-rate estimates, not invoices.",
            WIDTH,
        ),
    ]


def installed_metadata() -> PackageMetadata | None:
    try:
        return metadata.metadata("tokenusage2")
    except metadata.PackageNotFoundError:
        return None


@cache
def installed_about_lines() -> Sequence[str]:
    """The overlay text for this installation; metadata is read once per process."""
    return tuple(about_lines(installed_metadata(), platform.python_version()))
