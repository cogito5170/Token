"""List-price costing (CALCULATED) in nano-USD and the models / prices seed.

Prices are data (model_prices rows), never code constants used at costing time; SEED only fills an empty table.
Unit: price is micro-USD per Mtok, so  tokens * price / 1e6 micro-USD  =  tokens * price / 1000 nano-USD  (exact
integer when price is a multiple of 1000, as every seeded price is).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

PRICE_FIELDS = ("input", "output", "cache_read", "cache_write_5m", "cache_write_1h")


@dataclass(frozen=True)
class Price:
    model_id: str
    version: int
    effective_from: date
    input: int
    output: int
    cache_read: int
    cache_write_5m: int
    cache_write_1h: int
    source_note: str = ""


@dataclass(frozen=True)
class ModelRow:
    id: str
    provider: str
    family: str
    tier: int
    min_cache_tokens: int | None = None
    display_name: str = ""


def _final_task(model_id: str, input_usd: int, output_usd: int) -> Price:
    i, o = input_usd * 1_000_000, output_usd * 1_000_000
    return Price(model_id, 1, date(2025, 1, 1), i, o, i // 10, i * 5 // 4, i * 2,
                 "FINAL_TASK table: cache write x1.25 (1h x2), cache read x0.1")


# FINAL_TASK table (fixtures/final_task/SUMMARY.md): Haiku $1/$5, Sonnet $2/$10 per Mtok.
SEED_MODELS = (
    ModelRow("claude-haiku-4-5-20251001", "anthropic", "claude", 1, None, "Claude Haiku 4.5"),
    ModelRow("claude-sonnet-5-5", "anthropic", "claude", 2, None, "Claude Sonnet 5.5"),
)
SEED_PRICES = (
    _final_task("claude-haiku-4-5-20251001", 1, 5),
    _final_task("claude-sonnet-5-5", 2, 10),
)


def pick_price(prices: list[Price], day: date) -> Price | None:
    """Newest version effective on `day`; before every version, the oldest one."""
    if not prices:
        return None
    ok = [p for p in prices if p.effective_from <= day]
    return max(ok, key=lambda p: p.version) if ok else min(prices, key=lambda p: p.version)


def cost_nano(price: Price, input_tokens, cache_read, cache_write_5m, cache_write_1h, output_tokens) -> int | None:
    """Nano-USD list cost, or None (unknown, never 0) when input or output tokens are unknown.
    Unknown cache counts contribute nothing: the cache columns are optional in most sources."""
    if input_tokens is None or output_tokens is None:
        return None
    total = (input_tokens * price.input + output_tokens * price.output
             + (cache_read or 0) * price.cache_read
             + (cache_write_5m or 0) * price.cache_write_5m
             + (cache_write_1h or 0) * price.cache_write_1h)
    return total // 1000


def nano_to_micro(nano: int) -> int:
    """The single rounding step (half up), done on aggregates only."""
    return (nano + 500) // 1000
