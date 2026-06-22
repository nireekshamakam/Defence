from __future__ import annotations
import logging
import math
from datetime import date

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import MarketSnapshot
from ..config import INR_PER_USD_FALLBACK

logger = logging.getLogger(__name__)


def _f(x) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


class YFinanceSource:
    """Free Yahoo Finance adapter. Good for NSE-listed Indian defence cos.

    Limitations to be aware of:
      - Yahoo's `info` dict is rate-limited and occasionally returns stale values.
      - Forward P/E and EV/EBITDA are sometimes missing for thinly-traded names.
      - ROE/ROCE are TTM only; treat them as approximations of Bloomberg figures.
    """

    name = "yfinance"

    def __init__(self, inr_per_usd: float | None = None):
        self.inr_per_usd = inr_per_usd or INR_PER_USD_FALLBACK

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
    )
    def _fetch_info(self, symbol: str) -> dict:
        import yfinance as yf
        tkr = yf.Ticker(symbol)
        info = tkr.info or {}
        if not info:
            raise RuntimeError(f"empty info for {symbol}")
        return info

    def fetch(self, symbol: str) -> MarketSnapshot | None:
        try:
            info = self._fetch_info(symbol)
        except Exception as e:
            logger.warning("yfinance fetch failed for %s: %s", symbol, e)
            return None

        currency = info.get("currency") or "INR"
        px = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
        mc = _f(info.get("marketCap"))           # in reporting currency, full units
        ev = _f(info.get("enterpriseValue"))
        shares = _f(info.get("sharesOutstanding"))
        float_shares = _f(info.get("floatShares"))
        debt = _f(info.get("totalDebt"))
        cash = _f(info.get("totalCash"))
        net_debt = (debt or 0) - (cash or 0) if debt is not None or cash is not None else None

        # Yahoo returns INR for .NS tickers — convert to USD using fallback rate if needed.
        if currency.upper() == "INR":
            px_inr, px_usd = px, (px / self.inr_per_usd if px else None)
            mc_inr_mn = mc / 1e6 if mc else None
            mc_usd_mn = mc / 1e6 / self.inr_per_usd if mc else None
            ev_inr_mn = ev / 1e6 if ev else None
            ev_usd_mn = ev / 1e6 / self.inr_per_usd if ev else None
            nd_inr_mn = net_debt / 1e6 if net_debt is not None else None
            nd_usd_mn = net_debt / 1e6 / self.inr_per_usd if net_debt is not None else None
        else:
            px_usd, px_inr = px, (px * self.inr_per_usd if px else None)
            mc_usd_mn = mc / 1e6 if mc else None
            mc_inr_mn = mc / 1e6 * self.inr_per_usd if mc else None
            ev_usd_mn = ev / 1e6 if ev else None
            ev_inr_mn = ev / 1e6 * self.inr_per_usd if ev else None
            nd_usd_mn = net_debt / 1e6 if net_debt is not None else None
            nd_inr_mn = net_debt / 1e6 * self.inr_per_usd if net_debt is not None else None

        ebitda = _f(info.get("ebitda"))
        nd_to_ebitda = None
        if net_debt is not None and ebitda and ebitda != 0:
            nd_to_ebitda = net_debt / ebitda

        return MarketSnapshot(
            symbol=symbol,
            as_of_date=date.today(),
            px_inr=px_inr,
            px_usd=px_usd,
            currency=currency,
            mkt_cap_inr_mn=mc_inr_mn,
            mkt_cap_usd_mn=mc_usd_mn,
            ev_inr_mn=ev_inr_mn,
            ev_usd_mn=ev_usd_mn,
            pe_ttm=_f(info.get("trailingPE")),
            pe_fwd=_f(info.get("forwardPE")),
            ev_ebitda_ttm=_f(info.get("enterpriseToEbitda")),
            px_to_book=_f(info.get("priceToBook")),
            roe=_f(info.get("returnOnEquity")),
            roce=None,  # not directly available
            roic=None,
            net_debt_inr_mn=nd_inr_mn,
            net_debt_usd_mn=nd_usd_mn,
            net_debt_to_ebitda=_f(nd_to_ebitda),
            shares_out_mn=(shares / 1e6) if shares else None,
            free_float_pct=(float_shares / shares) if (shares and float_shares) else None,
            vol_5d_mn=None,
            vol_10d_mn=(_f(info.get("averageVolume10days")) or 0) / 1e6 or None,
            vol_30d_mn=(_f(info.get("averageVolume")) or 0) / 1e6 or None,
            raw={k: info.get(k) for k in (
                "shortName", "longName", "exchange", "currency", "currentPrice",
                "marketCap", "enterpriseValue", "trailingPE", "forwardPE",
                "enterpriseToEbitda", "priceToBook", "returnOnEquity",
                "totalDebt", "totalCash", "ebitda", "sharesOutstanding",
                "floatShares", "averageVolume", "averageVolume10days",
            )},
        )
