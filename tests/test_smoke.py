"""Lightweight smoke tests — no network calls. Run with `pytest`."""
from __future__ import annotations
from datetime import date

from defence_db.ticker_map import derive_yahoo_symbol
from defence_db.adapters.base import MarketSnapshot


def test_yahoo_symbol_override():
    assert derive_yahoo_symbol("HNAL", "HAL") == "HAL.NS"
    assert derive_yahoo_symbol("BHE", "BEL") == "BEL.NS"


def test_yahoo_symbol_default_to_exchange():
    assert derive_yahoo_symbol("RANDOMBB", "MYCO") == "MYCO.NS"


def test_yahoo_symbol_unlisted_returns_none():
    assert derive_yahoo_symbol("SMPP", None) is None
    assert derive_yahoo_symbol(None, None) is None


def test_marketsnapshot_dict_roundtrip():
    s = MarketSnapshot(symbol="HAL.NS", as_of_date=date(2026, 6, 22), px_inr=4500.0)
    d = s.to_dict()
    assert d["symbol"] == "HAL.NS"
    assert d["px_inr"] == 4500.0
