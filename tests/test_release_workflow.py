# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Exercise release-state detection without contacting GitHub."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from tokenusage2.version import __version__

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


def workflow_script(step: str) -> str:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {step}")
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    body = []
    for line in lines[run + 1 :]:
        if line and not line.startswith("          "):
            break
        body.append(line[10:] if line else "")
    return "\n".join(body)


@pytest.mark.parametrize(
    ("tagged", "status", "assets", "expected", "success"),
    [
        (False, 404, [], "missing", True),
        (True, 404, [], "missing", True),
        (True, 200, ["wheel", "source"], "complete", True),
        (True, 200, ["wheel"], "incomplete", True),
        (False, 200, ["wheel", "source"], None, False),
        (True, 403, [], None, False),
        (True, 200, ["pending"], None, False),
    ],
)
def test_release_detection(
    tmp_path: Path,
    tagged: bool,
    status: int,
    assets: list[str],
    expected: str | None,
    success: bool,
) -> None:
    names = {
        "wheel": f"tokenusage2-{__version__}-py3-none-any.whl",
        "source": f"tokenusage2-{__version__}.tar.gz",
        "pending": f"tokenusage2-{__version__}-py3-none-any.whl",
    }
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps(
            {
                "draft": False,
                "prerelease": False,
                "assets": [
                    {"name": names[a], "state": "new" if a == "pending" else "uploaded"}
                    for a in assets
                ],
            }
        ),
        encoding="utf-8",
    )
    git = tmp_path / "git"
    git.write_text(f"#!/bin/sh\nexit {0 if tagged else 1}\n", encoding="utf-8")
    git.chmod(0o755)
    curl = tmp_path / "curl"
    curl.write_text(
        '#!/bin/sh\nwhile [ "$1" != "--output" ]; do shift; done\n'
        'cp "$TEST_PAYLOAD" "$2"\nprintf "%s" "$TEST_STATUS"\n',
        encoding="utf-8",
    )
    curl.chmod(0o755)
    output = tmp_path / "output"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "TEST_PAYLOAD": str(payload),
        "TEST_STATUS": str(status),
        "GITHUB_OUTPUT": str(output),
        "RUNNER_TEMP": str(tmp_path),
        "GH_TOKEN": "test",
        "GITHUB_API_URL": "https://api.example.invalid",
        "GITHUB_REPOSITORY": "test/repo",
    }
    result = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", workflow_script("Inspect the tag and release assets")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert (result.returncode == 0) is success, result.stderr
    if expected is not None:
        assert f"state={expected}" in output.read_text(encoding="utf-8")


@pytest.mark.parametrize("present", ["wheel", "source"])
def test_recovery_uploads_only_missing_asset(tmp_path: Path, present: str) -> None:
    names = {
        "wheel": f"tokenusage2-{__version__}-py3-none-any.whl",
        "source": f"tokenusage2-{__version__}.tar.gz",
    }
    payload = tmp_path / "release.json"
    payload.write_text(json.dumps({"assets": [{"name": names[present]}]}), encoding="utf-8")
    gh = tmp_path / "gh"
    gh.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$TEST_CALLS"\n', encoding="utf-8")
    gh.chmod(0o755)
    calls = tmp_path / "calls"
    env = os.environ | {
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "RUNNER_TEMP": str(tmp_path),
        "TEST_CALLS": str(calls),
    }
    script = workflow_script("Upload only missing release assets").replace(
        "${{ steps.version.outputs.version }}", __version__
    )
    result = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    uploaded = calls.read_text(encoding="utf-8").splitlines()
    missing = "source" if present == "wheel" else "wheel"
    assert uploaded == [f"release upload v{__version__} dist/{names[missing]}"]
