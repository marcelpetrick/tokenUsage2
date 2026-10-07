# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Standard-rate estimate: what the tokens would cost at published token rates.

An estimate, not an invoice — a subscription bills differently, and a local
backend costs electricity rather than tokens. Prices are resolved when
displaying, so a changed price table re-prices the whole history.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Protocol

from tokenusage2.model import Tool


class Tokens(Protocol):
    """Anything with a token split: a request's ``Usage`` or an aggregated ``Tally``."""

    input: int
    cache_read: int
    cache_write: int
    cache_write_1h: int
    output: int


@dataclass(frozen=True, slots=True)
class Rates:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float
    cache_write_1h: float
    long_context_threshold: int | None = None
    long_input_multiplier: float = 1.0
    long_output_multiplier: float = 1.0

    def cost(self, tokens: Tokens, *, long_context: bool | None = None) -> float:
        prompt = tokens.input + tokens.cache_read + tokens.cache_write
        if long_context is None:
            long_context = (
                self.long_context_threshold is not None and prompt > self.long_context_threshold
            )
        input_multiplier = self.long_input_multiplier if long_context else 1.0
        output_multiplier = self.long_output_multiplier if long_context else 1.0
        five_minute = tokens.cache_write - tokens.cache_write_1h
        return (
            tokens.input * self.input * input_multiplier
            + tokens.output * self.output * output_multiplier
            + tokens.cache_read * self.cache_read * input_multiplier
            + five_minute * self.cache_write * input_multiplier
            + tokens.cache_write_1h * self.cache_write_1h * input_multiplier
        ) / 1_000_000


FREE = Rates(0.0, 0.0, 0.0, 0.0, 0.0)


def anthropic(input_price: float, output_price: float, cache_read: float | None = None) -> Rates:
    """Anthropic's cache pricing: reads 0.1x input, writes 1.25x (5 min) or 2x (1 h)."""
    read = input_price * 0.1 if cache_read is None else cache_read
    return Rates(input_price, output_price, read, input_price * 1.25, input_price * 2)


def openai(
    input_price: float,
    cache_read: float,
    output_price: float,
    *,
    cache_write: float = 0.0,
    long_context: bool = False,
) -> Rates:
    """OpenAI standard rates, optionally including cache writes and the >272K tier."""
    return Rates(
        input_price,
        output_price,
        cache_read,
        cache_write,
        cache_write,
        272_000 if long_context else None,
        2.0 if long_context else 1.0,
        1.5 if long_context else 1.0,
    )


#: Anthropic list prices per model glob, USD per 1M tokens (as of 2026-10-07).
#: The first matching glob wins, so more specific names come first.
ANTHROPIC_PRICES: tuple[tuple[str, Rates], ...] = (
    ("claude-fable-5-1*", anthropic(10, 50, cache_read=0.25)),
    ("claude-fable-5*", anthropic(10, 50)),
    ("claude-mythos-5-1*", anthropic(10, 50, cache_read=0.25)),
    ("claude-mythos-5*", anthropic(10, 50)),
    ("claude-opus-5-5*", anthropic(4, 20, cache_read=0.2)),
    ("claude-opus-5*", anthropic(5, 25)),
    ("claude-opus-4-8*", anthropic(5, 25)),
    ("claude-opus-4-7*", anthropic(5, 25)),
    ("claude-opus-4-6*", anthropic(5, 25)),
    ("claude-sonnet-5*", anthropic(2, 10)),
    ("claude-sonnet-4-6*", anthropic(3, 15)),
    ("claude-haiku-4-5*", anthropic(1, 5)),
)

#: OpenAI standard rates per model glob, USD per 1M tokens (as of 2026-10-07).
#: Source: https://developers.openai.com/api/docs/pricing
#: More specific names precede their families. Models without a final price,
#: such as GPT-5.3-Codex-Spark, are deliberately absent and blocked below.
OPENAI_PRICES: tuple[tuple[str, Rates], ...] = (
    ("gpt-6-astra*", openai(10, 1, 50, cache_write=12.5, long_context=True)),
    ("gpt-6.1-sol*", openai(2, 0.1, 10, cache_write=2.5, long_context=True)),
    ("gpt-6-sol*", openai(2, 0.2, 10, cache_write=2.5, long_context=True)),
    ("gpt-6-luna*", openai(0.1, 0.01, 0.5, cache_write=0.125, long_context=True)),
    ("gpt-5.6-sol*", openai(4, 0.4, 20, cache_write=5, long_context=True)),
    ("gpt-5.6-terra*", openai(2, 0.2, 12, cache_write=2.5, long_context=True)),
    ("gpt-5.6-luna*", openai(0.2, 0.02, 1.2, cache_write=0.25, long_context=True)),
    ("gpt-rosalind-research*", openai(5, 0.5, 25)),
    ("gpt-5.5*", openai(5, 0.5, 30, long_context=True)),
    ("daybreak-blue*", openai(4, 0.4, 20)),
    ("daybreak-red*", openai(12.5, 1.25, 75)),
    ("gpt-5.4-mini*", openai(0.75, 0.075, 4.5)),
    ("gpt-5.4*", openai(2.5, 0.25, 15, long_context=True)),
    ("gpt-5.3-codex*", openai(1.75, 0.175, 14)),
    ("gpt-5.3*", openai(1.75, 0.175, 14)),
    ("gpt-5.2*", openai(1.75, 0.175, 14)),
)
OPENAI_UNPRICED = ("gpt-5.5-pro*", "gpt-5.3-codex-spark*")


def _match(model: str, table: Sequence[tuple[str, Rates]]) -> Rates | None:
    return next((rates for pattern, rates in table if fnmatchcase(model, pattern)), None)


class Pricer:
    """Rates for a request, from what its log says about the model and the route.

    Configured prices win. A request Anthropic's API answered uses the list
    price of its model; a Claude Code request a local backend answered costs
    nothing. Everything else stays unpriced until the config names it.
    """

    def __init__(self, configured: Sequence[tuple[str, Rates]] = ()) -> None:
        self.configured = tuple(configured)
        self._rates: dict[tuple[Tool, str, str], Rates | None] = {}

    def rates(self, tool: Tool, model: str, route: str) -> Rates | None:
        key = (tool, model, route)
        if key not in self._rates:
            self._rates[key] = self._resolve(tool, model, route)
        return self._rates[key]

    def _resolve(self, tool: Tool, model: str, route: str) -> Rates | None:
        configured = _match(model, self.configured)
        if configured is not None:
            return configured
        if route == "anthropic":
            return _match(model, ANTHROPIC_PRICES)
        if route == "openai":
            if any(fnmatchcase(model, pattern) for pattern in OPENAI_UNPRICED):
                return None
            return _match(model, OPENAI_PRICES)
        if tool is Tool.CLAUDE:
            return FREE
        return None
