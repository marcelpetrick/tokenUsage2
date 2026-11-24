# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "quality_gates", ROOT / "scripts" / "quality_gates.py"
)
assert _spec is not None
assert _spec.loader is not None
gates = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gates)


def cobertura(tmp_path: Path, lines: str, branches: str) -> Path:
    path = tmp_path / "coverage.xml"
    path.write_text(f'<coverage line-rate="{lines}" branch-rate="{branches}"></coverage>')
    return path


def stats(tmp_path: Path, **values: object) -> Path:
    path = tmp_path / "mutmut-cicd-stats.json"
    path.write_text(json.dumps(values))
    return path


def test_coverage_requires_lines_and_branches_separately(tmp_path: Path) -> None:
    assert gates.check_coverage(cobertura(tmp_path, "0.995", "0.99"), 99) == (
        "lines 99.50%, branches 99.00% (bar 99% each)"
    )
    # A high line rate must not hide a low branch rate, as a combined total would.
    with pytest.raises(gates.GateError, match=r"branches 98\.00%"):
        gates.check_coverage(cobertura(tmp_path, "1.0", "0.98"), 99)
    with pytest.raises(gates.GateError, match=r"lines 98\.90%"):
        gates.check_coverage(cobertura(tmp_path, "0.989", "1.0"), 99)


@pytest.mark.parametrize("content", ["<coverage/>", "not xml", '<coverage line-rate="x"/>'])
def test_unreadable_coverage_reports_fail(tmp_path: Path, content: str) -> None:
    path = tmp_path / "coverage.xml"
    path.write_text(content)
    with pytest.raises(gates.GateError, match="unreadable coverage report"):
        gates.check_coverage(path, 99)
    with pytest.raises(gates.GateError, match="unreadable"):
        gates.check_coverage(tmp_path / "missing.xml", 99)


def test_mutation_score_counts_timeouts_as_killed_and_excludes_skipped(tmp_path: Path) -> None:
    path = stats(tmp_path, killed=55, timeout=5, survived=40, total=110, skipped=10)
    assert gates.mutation_score(path) == (60.0, 60, 100)
    assert gates.check_mutation(path, 60) == "mutation score 60.00% (60/100 killed, bar 60%)"
    with pytest.raises(gates.GateError, match="below the bar"):
        gates.check_mutation(path, 60.5)


@pytest.mark.parametrize(
    "values",
    [{"killed": 1}, {"killed": "x", "total": 2}, {"killed": 0, "total": 3, "skipped": 3}],
)
def test_unusable_mutation_statistics_fail(tmp_path: Path, values: dict) -> None:
    with pytest.raises(gates.GateError):
        gates.mutation_score(stats(tmp_path, **values))
    with pytest.raises(gates.GateError, match="unreadable"):
        gates.mutation_score(tmp_path / "missing.json")


def test_cli_exit_status_and_messages(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    good = cobertura(tmp_path, "1.0", "1.0")
    assert gates.main(["coverage", str(good), "--bar", "99"]) == 0
    assert "lines 100.00%" in capsys.readouterr().out
    low = stats(tmp_path, killed=1, total=4)
    assert gates.main(["mutation", str(low), "--bar", "60"]) == 1
    assert "below the bar" in capsys.readouterr().err
