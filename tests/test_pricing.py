# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from tokenusage2.model import Tool, Usage
from tokenusage2.pricing import (
    ANTHROPIC_PRICES,
    FREE,
    OPENAI_PRICES,
    Pricer,
    Rates,
    anthropic,
    openai,
)


def test_anthropic_cache_multipliers() -> None:
    assert anthropic(5, 25) == Rates(5, 25, 0.5, 6.25, 10)
    assert anthropic(10, 50, cache_read=0.25).cache_read == 0.25


def test_cost_prices_every_part_of_the_split() -> None:
    usage = Usage(input=10, cache_read=1000, cache_write=100, cache_write_1h=40, output=50)
    # 10*5 + 1000*0.5 + 60*6.25 + 40*10 + 50*25 = 50 + 500 + 375 + 400 + 1250
    assert anthropic(5, 25).cost(usage) == pytest.approx(2575 / 1_000_000)
    assert FREE.cost(usage) == 0.0


def test_openai_prices_cache_writes_and_long_context_when_the_model_does() -> None:
    usage = Usage(input=10, cache_read=1000, cache_write=100, output=50)
    # Older models without a published write rate retain the zero default.
    assert openai(4, 0.4, 20).cost(usage) == pytest.approx(1440 / 1_000_000)
    current = openai(2, 0.2, 10, cache_write=2.5, long_context=True)
    assert current.cost(usage) == pytest.approx((20 + 200 + 250 + 500) / 1_000_000)
    large = Usage(input=1000, cache_read=271_001, cache_write=0, output=100)
    assert current.cost(large) == pytest.approx((4000 + 108_400.4 + 1500) / 1_000_000)


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("claude-opus-5", anthropic(5, 25)),
        ("claude-opus-5-5", anthropic(4, 20, cache_read=0.2)),
        ("claude-sonnet-5", anthropic(2, 10)),
        ("claude-sonnet-4-6", anthropic(3, 15)),
        ("claude-haiku-4-5-20251001", anthropic(1, 5)),
        ("claude-fable-5-1", anthropic(10, 50, cache_read=0.25)),
        ("claude-fable-5", anthropic(10, 50)),
        ("claude-mythos-5-1", anthropic(10, 50, cache_read=0.25)),
        ("claude-unknown-9", None),
    ],
)
def test_anthropic_list_prices(model: str, expected: Rates | None) -> None:
    assert Pricer().rates(Tool.CLAUDE, model, "anthropic") == expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-6-astra", openai(10, 1, 50, cache_write=12.5, long_context=True)),
        ("gpt-6.1-sol", openai(2, 0.1, 10, cache_write=2.5, long_context=True)),
        ("gpt-6-sol", openai(2, 0.2, 10, cache_write=2.5, long_context=True)),
        ("gpt-6-luna", openai(0.1, 0.01, 0.5, cache_write=0.125, long_context=True)),
        ("gpt-5.6-sol", openai(4, 0.4, 20, cache_write=5, long_context=True)),
        ("gpt-5.6-terra", openai(2, 0.2, 12, cache_write=2.5, long_context=True)),
        ("gpt-5.6-luna", openai(0.2, 0.02, 1.2, cache_write=0.25, long_context=True)),
        ("gpt-rosalind-research", openai(5, 0.5, 25)),
        ("gpt-5.5-pro", None),
        ("gpt-5.5", openai(5, 0.5, 30, long_context=True)),
        ("daybreak-blue", openai(4, 0.4, 20)),
        ("daybreak-red", openai(12.5, 1.25, 75)),
        ("gpt-5.4-mini", openai(0.75, 0.075, 4.5)),
        ("gpt-5.4", openai(2.5, 0.25, 15, long_context=True)),
        ("gpt-5.3-codex", openai(1.75, 0.175, 14)),
        ("gpt-5.3", openai(1.75, 0.175, 14)),
        ("gpt-5.2", openai(1.75, 0.175, 14)),
        ("gpt-5.3-codex-spark", None),
        ("gpt-unknown", None),
    ],
)
def test_openai_standard_prices(model: str, expected: Rates | None) -> None:
    assert Pricer().rates(Tool.CODEX, model, "openai") == expected


def test_resolution_order() -> None:
    custom = Rates(1, 2, 0, 0, 0)
    pricer = Pricer([("gpt-5*", custom), ("claude-opus-5", FREE)])
    assert pricer.rates(Tool.CODEX, "gpt-5.6-sol", "openai") is custom
    assert pricer.rates(Tool.CLAUDE, "claude-opus-5", "anthropic") is FREE
    assert pricer.rates(Tool.CLAUDE, "north-mini:q4", "") is FREE
    assert pricer.rates(Tool.CODEX, "gpt-6-astra", "openai") == openai(
        10, 1, 50, cache_write=12.5, long_context=True
    )
    assert pricer.rates(Tool.OPENCODE, "claude-sonnet-5", "anthropic") == anthropic(2, 10)
    assert pricer.rates(Tool.OPENCODE, "qwen", "ollama-local") is None
    assert Pricer().rates(Tool.CODEX, "gpt-5.6-sol", "ollama-local") is None
    assert pricer.rates(Tool.CODEX, "gpt-5.6-sol", "ollama-local") is custom
    assert pricer.rates(Tool.CODEX, "gpt-5.3-codex-spark", "openai") is custom
    assert Pricer().rates(Tool.OPENCODE, "gpt-5.6-sol", "openai") == openai(
        4, 0.4, 20, cache_write=5, long_context=True
    )
    assert pricer.rates(Tool.OPENCODE, "gpt-5.6-sol", "openai") is custom


def test_specific_globs_come_first() -> None:
    anthropic_patterns = [pattern for pattern, _ in ANTHROPIC_PRICES]
    openai_patterns = [pattern for pattern, _ in OPENAI_PRICES]
    assert anthropic_patterns.index("claude-fable-5-1*") < anthropic_patterns.index(
        "claude-fable-5*"
    )
    assert openai_patterns.index("gpt-5.4-mini*") < openai_patterns.index("gpt-5.4*")
