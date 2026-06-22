from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Protocol, Any


@dataclass
class MarketSnapshot:
    """Normalized market-data payload — what every adapter returns."""
    symbol: str
    as_of_date: date
    px_inr: float | None = None
    px_usd: float | None = None
    currency: str | None = "INR"

    mkt_cap_inr_mn: float | None = None
    mkt_cap_usd_mn: float | None = None
    ev_inr_mn: float | None = None
    ev_usd_mn: float | None = None

    pe_ttm: float | None = None
    pe_fwd: float | None = None
    ev_ebitda_ttm: float | None = None
    ev_ebitda_fwd: float | None = None
    px_to_book: float | None = None
    px_to_tbv: float | None = None

    roe: float | None = None
    roce: float | None = None
    roic: float | None = None

    net_debt_inr_mn: float | None = None
    net_debt_usd_mn: float | None = None
    net_debt_to_ebitda: float | None = None

    shares_out_mn: float | None = None
    free_float_pct: float | None = None

    vol_5d_mn: float | None = None
    vol_10d_mn: float | None = None
    vol_30d_mn: float | None = None

    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MarketDataSource(Protocol):
    """Pluggable data source. Add new providers (Bloomberg, NSEPython, paid APIs) here."""

    name: str

    def fetch(self, symbol: str) -> MarketSnapshot | None: ...
