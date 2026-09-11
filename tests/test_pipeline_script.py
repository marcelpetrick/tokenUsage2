# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""localPipeline.sh is the one entry point for setup, checks and builds; keep it sound."""

import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "localPipeline.sh"


def pipeline(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args], capture_output=True, text=True, timeout=30, check=False
    )


def test_the_script_is_valid_bash() -> None:
    assert subprocess.run(["bash", "-n", str(SCRIPT)], check=False).returncode == 0


def test_help_lists_every_stage() -> None:
    result = pipeline("--help")
    assert result.returncode == 0
    for stage in (
        "Interpreter",
        "Virtualenv",
        "Dependencies",
        "Ruff lint",
        "Ruff format",
        "ShellCheck",
        "Tests",
        "Smoke run",
        "Build",
        "Wheel check",
        "Binary",
        "Launch",
        ".venv/bin/tokenusage2",
    ):
        assert stage in result.stdout


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--bogus"], "unknown option: --bogus"),
        (["--report-dir"], "--report-dir needs a path"),
    ],
)
def test_bad_arguments_are_rejected(args: list[str], message: str) -> None:
    result = pipeline(*args)
    assert result.returncode == 2
    assert message in result.stderr


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is not installed")
def test_shellcheck_is_clean() -> None:
    result = subprocess.run(
        ["shellcheck", str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout
