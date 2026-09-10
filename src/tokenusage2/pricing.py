# SPDX-FileCopyrightText: 2026 Marcel Petrick
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""API-equivalent cost: what the tokens would cost at list prices.

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

    def cost(self, tokens: Tokens) -> float:
        five_minute = tokens.cache_write - tokens.cache_write_1h
        return (
            tokens.input * self.input
            + tokens.output * self.output
            + tokens.cache_read * self.cache_read
            + five_minute * self.cache_write
            + tokens.cache_write_1h * self.cache_write_1h
        ) / 1_000_000


FREE = Rates(0.0, 0.0, 0.0, 0.0, 0.0)


def anthropic(input_price: float, output_price: float, cache_read: float | None = None) -> Rates:
    """Anthropic's cache pricing: reads 0.1x input, writes 1.25x (5 min) or 2x (1 h)."""
    read = input_price * 0.1 if cache_read is None else cache_read
    return Rates(input_price, output_price, read, input_price * 1.25, input_price * 2)


#: Anthropic list prices per model glob, USD per 1M tokens (as of 2026-06-24).
#: The first matching glob wins, so more specific names come first.
ANTHROPIC_PRICES: tuple[tuple[str, Rates], ...] = (
    ("claude-fable-5-1*", anthropic(10, 50, cache_read=0.25)),
    ("claude-fable-5*", anthropic(10, 50)),
    ("claude-opus-5*", anthropic(5, 25)),
    ("claude-opus-4-8*", anthropic(5, 25)),
    ("claude-opus-4-7*", anthropic(5, 25)),
    ("claude-opus-4-6*", anthropic(5, 25)),
    ("claude-sonnet-5*", anthropic(2, 10)),
    ("claude-sonnet-4-6*", anthropic(3, 15)),
    ("claude-haiku-4-5*", anthropic(1, 5)),
)


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
        if tool is Tool.CLAUDE:
            return FREE
        return None
