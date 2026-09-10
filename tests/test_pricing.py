# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from tokenusage2.model import Tool, Usage
from tokenusage2.pricing import ANTHROPIC_PRICES, FREE, Pricer, Rates, anthropic


def test_anthropic_cache_multipliers() -> None:
    assert anthropic(5, 25) == Rates(5, 25, 0.5, 6.25, 10)
    assert anthropic(10, 50, cache_read=0.25).cache_read == 0.25


def test_cost_prices_every_part_of_the_split() -> None:
    usage = Usage(input=10, cache_read=1000, cache_write=100, cache_write_1h=40, output=50)
    # 10*5 + 1000*0.5 + 60*6.25 + 40*10 + 50*25 = 50 + 500 + 375 + 400 + 1250
    assert anthropic(5, 25).cost(usage) == pytest.approx(2575 / 1_000_000)
    assert FREE.cost(usage) == 0.0


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-opus-5", anthropic(5, 25)),
        ("claude-sonnet-5", anthropic(2, 10)),
        ("claude-sonnet-4-6", anthropic(3, 15)),
        ("claude-haiku-4-5-20251001", anthropic(1, 5)),
        ("claude-fable-5-1", anthropic(10, 50, cache_read=0.25)),
        ("claude-fable-5", anthropic(10, 50)),
        ("claude-unknown-9", None),
    ],
)
def test_anthropic_list_prices(model: str, expected: Rates | None) -> None:
    assert Pricer().rates(Tool.CLAUDE, model, "anthropic") == expected


def test_resolution_order() -> None:
    custom = Rates(1, 2, 0, 0, 0)
    pricer = Pricer([("gpt-5*", custom), ("claude-opus-5", FREE)])
    assert pricer.rates(Tool.CODEX, "gpt-5.6-sol", "openai") is custom
    assert pricer.rates(Tool.CLAUDE, "claude-opus-5", "anthropic") is FREE
    assert pricer.rates(Tool.CLAUDE, "north-mini:q4", "") is FREE
    assert pricer.rates(Tool.CODEX, "gpt-6-astra", "openai") is None
    assert pricer.rates(Tool.OPENCODE, "claude-sonnet-5", "anthropic") == anthropic(2, 10)
    assert pricer.rates(Tool.OPENCODE, "qwen", "ollama-local") is None
    assert pricer.rates(Tool.CODEX, "gpt-6-astra", "openai") is None


def test_specific_globs_come_first() -> None:
    patterns = [pattern for pattern, _ in ANTHROPIC_PRICES]
    assert patterns.index("claude-fable-5-1*") < patterns.index("claude-fable-5*")
