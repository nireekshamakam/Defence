"""Export the live DB back to an Excel snapshot — preserves the user's familiar layout."""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from ..config import EXPORT_DIR
from ..db import session_scope
from ..models import Company, PriceSnapshot, FinancialSnapshot

logger = logging.getLogger(__name__)


def _companies_df(session) -> pd.DataFrame:
    rows = session.execute(select(Company)).scalars().all()
    return pd.DataFrame([dict(
        Company=c.name, BB=c.bb_ticker, Exch=c.exchange_ticker, Yahoo=c.yahoo_symbol,
        Status=c.listing_status, Incorp=c.incorporation_year, Legacy=c.legacy_years,
        Type=c.type_size, Location=c.location, SubSegment=c.sub_segment,
        ValueChain=c.value_chain, TAM_CAGR=c.tam_cagr_fy30,
        Promoter=c.promoter, PromOwn=c.promoter_ownership_pct,
        Barriers=c.barriers_to_entry, Switching=c.switching_costs, Stickiness=c.customer_stickiness,
    ) for c in rows])


def _latest_prices_df(session) -> pd.DataFrame:
    rows = session.execute(select(Company)).scalars().all()
    out = []
    for c in rows:
        snap = (
            session.execute(
                select(PriceSnapshot)
                .where(PriceSnapshot.company_id == c.id)
                .order_by(PriceSnapshot.as_of_date.desc())
                .limit(1)
            ).scalar_one_or_none()
        )
        if not snap:
            continue
        out.append(dict(
            Company=c.name, BB=c.bb_ticker, Yahoo=c.yahoo_symbol, AsOf=snap.as_of_date,
            PxINR=snap.px_inr, PxUSD=snap.px_usd,
            MktCapUSDmn=snap.mkt_cap_usd_mn, MktCapINRmn=snap.mkt_cap_inr_mn,
            EVUSDmn=snap.ev_usd_mn, EVINRmn=snap.ev_inr_mn,
            PE_TTM=snap.pe_ttm, PE_Fwd=snap.pe_fwd,
            EV_EBITDA_TTM=snap.ev_ebitda_ttm, EV_EBITDA_Fwd=snap.ev_ebitda_fwd,
            P_B=snap.px_to_book, ROE=snap.roe,
            NetDebtINRmn=snap.net_debt_inr_mn, NetDebt_EBITDA=snap.net_debt_to_ebitda,
            SharesOutMn=snap.shares_out_mn, FreeFloatPct=snap.free_float_pct,
            Source=snap.source,
        ))
    return pd.DataFrame(out)


def _financials_df(session) -> pd.DataFrame:
    rows = session.execute(select(FinancialSnapshot)).scalars().all()
    return pd.DataFrame([dict(
        company_id=r.company_id, FY=r.fiscal_year, Type=r.period_type,
        RevenueINRmn=r.revenue_inr_mn, EBITDAINRmn=r.ebitda_inr_mn,
        EPS=r.eps, NetIncomeINRmn=r.net_income_inr_mn,
        ROE=r.roe, ROCE=r.roce,
        PATMargin=r.pat_margin_pct, EBITDAMargin=r.ebitda_margin_pct,
        FCFFYieldEV=r.fcff_yield_on_ev, WCDays=r.working_capital_days,
        OrderBookINRmn=r.order_backlog_inr_mn,
        Source=r.source,
    ) for r in rows])


def export(out_path: Path | None = None) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = out_path or EXPORT_DIR / f"defence_live_{stamp}.xlsx"
    with session_scope() as session:
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            _companies_df(session).to_excel(writer, sheet_name="Companies", index=False)
            _latest_prices_df(session).to_excel(writer, sheet_name="Live_Market", index=False)
            _financials_df(session).to_excel(writer, sheet_name="Financials_History", index=False)
    logger.info("exported %s", path)
    return path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(export())
