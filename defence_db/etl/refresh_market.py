"""Refresh live market data for every company with a known Yahoo symbol.

Run via `python -m defence_db.etl.refresh_market` (or scripts/refresh.py for CLI).
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Callable
from sqlalchemy import select, and_

from ..db import init_db, session_scope
from ..models import Company, PriceSnapshot, RefreshRun
from ..adapters import YFinanceSource, MarketDataSource

logger = logging.getLogger(__name__)

ProgressFn = Callable[[int, int, str], None]


def refresh_all(
    source: MarketDataSource | None = None,
    on_progress: ProgressFn | None = None,
) -> RefreshRun:
    init_db()
    src = source or YFinanceSource()

    with session_scope() as session:
        run = RefreshRun(source=src.name, started_at=datetime.utcnow())
        session.add(run)
        session.flush()

        companies = session.execute(
            select(Company).where(Company.yahoo_symbol.is_not(None))
        ).scalars().all()
        run.companies_attempted = len(companies)
        total = len(companies)
        logger.info("refreshing %d companies via %s", total, src.name)

        ok = 0
        for i, co in enumerate(companies, start=1):
            if on_progress:
                try:
                    on_progress(i, total, co.name)
                except Exception:
                    pass
            snap = src.fetch(co.yahoo_symbol)
            if snap is None:
                continue
            existing = session.execute(
                select(PriceSnapshot).where(and_(
                    PriceSnapshot.company_id == co.id,
                    PriceSnapshot.as_of_date == snap.as_of_date,
                ))
            ).scalar_one_or_none()
            data = dict(
                company_id=co.id, as_of_date=snap.as_of_date,
                px_inr=snap.px_inr, px_usd=snap.px_usd, currency=snap.currency,
                mkt_cap_inr_mn=snap.mkt_cap_inr_mn, mkt_cap_usd_mn=snap.mkt_cap_usd_mn,
                ev_inr_mn=snap.ev_inr_mn, ev_usd_mn=snap.ev_usd_mn,
                pe_ttm=snap.pe_ttm, pe_fwd=snap.pe_fwd,
                ev_ebitda_ttm=snap.ev_ebitda_ttm, ev_ebitda_fwd=snap.ev_ebitda_fwd,
                px_to_book=snap.px_to_book, px_to_tbv=snap.px_to_tbv,
                roe=snap.roe, roce=snap.roce, roic=snap.roic,
                net_debt_inr_mn=snap.net_debt_inr_mn, net_debt_usd_mn=snap.net_debt_usd_mn,
                net_debt_to_ebitda=snap.net_debt_to_ebitda,
                shares_out_mn=snap.shares_out_mn, free_float_pct=snap.free_float_pct,
                vol_5d_mn=snap.vol_5d_mn, vol_10d_mn=snap.vol_10d_mn, vol_30d_mn=snap.vol_30d_mn,
                source=src.name, raw=snap.raw, fetched_at=datetime.utcnow(),
            )
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
            else:
                session.add(PriceSnapshot(**data))
            ok += 1
        run.companies_succeeded = ok
        run.finished_at = datetime.utcnow()
        logger.info("refresh complete: %d/%d", ok, total)
        return run


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    r = refresh_all()
    print(f"refresh: {r.companies_succeeded}/{r.companies_attempted} via {r.source}")
