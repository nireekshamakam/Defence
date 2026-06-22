"""Streamlit dashboard — browse the live defence DB.

Run:
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import select

# allow running with `streamlit run app/streamlit_app.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from defence_db.db import init_db, SessionLocal  # noqa: E402
from defence_db.models import Company, PriceSnapshot, FinancialSnapshot, RefreshRun  # noqa: E402
from defence_db.etl.seed_from_excel import seed  # noqa: E402
from defence_db.etl.refresh_market import refresh_all  # noqa: E402

st.set_page_config(page_title="Defence & Aerospace Live DB", layout="wide")
init_db()

# Auto-seed on first run (e.g. fresh Streamlit Cloud deploy) so the dashboard
# is never empty out of the box.
with SessionLocal() as _s:
    from sqlalchemy import func, select as _sel
    if _s.execute(_sel(func.count(Company.id))).scalar() == 0:
        with st.spinner("First-run setup: seeding companies from source Excel..."):
            seed()


@st.cache_data(ttl=300)
def load_overview() -> pd.DataFrame:
    with SessionLocal() as s:
        companies = s.execute(select(Company)).scalars().all()
        rows = []
        for c in companies:
            latest = (
                s.execute(
                    select(PriceSnapshot)
                    .where(PriceSnapshot.company_id == c.id)
                    .order_by(PriceSnapshot.as_of_date.desc())
                    .limit(1)
                ).scalar_one_or_none()
            )
            rows.append({
                "Company": c.name,
                "BB": c.bb_ticker,
                "Yahoo": c.yahoo_symbol,
                "Value Chain": c.value_chain,
                "Sub-Segment": c.sub_segment,
                "Type": c.type_size,
                "Status": c.listing_status,
                "Mkt Cap (USD mn)": latest.mkt_cap_usd_mn if latest else None,
                "Price (INR)": latest.px_inr if latest else None,
                "P/E (TTM)": latest.pe_ttm if latest else None,
                "P/E (Fwd)": latest.pe_fwd if latest else None,
                "EV/EBITDA": latest.ev_ebitda_ttm if latest else None,
                "ROE": latest.roe if latest else None,
                "Net Debt/EBITDA": latest.net_debt_to_ebitda if latest else None,
                "As Of": latest.as_of_date if latest else None,
            })
        return pd.DataFrame(rows)


@st.cache_data(ttl=300)
def load_financials_for(company_name: str) -> pd.DataFrame:
    with SessionLocal() as s:
        co = s.execute(select(Company).where(Company.name == company_name)).scalar_one_or_none()
        if not co:
            return pd.DataFrame()
        rows = s.execute(
            select(FinancialSnapshot).where(FinancialSnapshot.company_id == co.id)
            .order_by(FinancialSnapshot.fiscal_year, FinancialSnapshot.period_type)
        ).scalars().all()
        return pd.DataFrame([{
            "FY": r.fiscal_year, "Type": r.period_type,
            "Revenue (INR mn)": r.revenue_inr_mn,
            "ROE": r.roe, "ROCE": r.roce,
            "PAT margin": r.pat_margin_pct,
            "FCFF Yield (EV)": r.fcff_yield_on_ev,
            "WC days": r.working_capital_days,
            "Source": r.source,
        } for r in rows])


@st.cache_data(ttl=300)
def load_price_history(company_name: str) -> pd.DataFrame:
    with SessionLocal() as s:
        co = s.execute(select(Company).where(Company.name == company_name)).scalar_one_or_none()
        if not co:
            return pd.DataFrame()
        rows = s.execute(
            select(PriceSnapshot).where(PriceSnapshot.company_id == co.id)
            .order_by(PriceSnapshot.as_of_date)
        ).scalars().all()
        return pd.DataFrame([{
            "Date": r.as_of_date, "Price (INR)": r.px_inr,
            "Mkt Cap (USD mn)": r.mkt_cap_usd_mn,
            "P/E (TTM)": r.pe_ttm, "EV/EBITDA": r.ev_ebitda_ttm,
        } for r in rows])


# ---------- UI ----------
st.title("Defence & Aerospace — Live Database")

overview = load_overview()
if overview.empty:
    st.warning("Database is empty. Run `python scripts/bootstrap.py` to seed, then `python scripts/refresh.py`.")
    st.stop()

with st.sidebar:
    st.header("Live data")
    with SessionLocal() as _ls:
        last = _ls.execute(
            select(RefreshRun).order_by(RefreshRun.id.desc()).limit(1)
        ).scalar_one_or_none()
    if last and last.finished_at:
        st.caption(
            f"Last refresh: {last.finished_at.strftime('%Y-%m-%d %H:%M UTC')}  \n"
            f"{last.companies_succeeded}/{last.companies_attempted} OK via {last.source}"
        )
    else:
        st.caption("No refresh recorded yet — click below to pull live data.")

    if st.button("🔄 Refresh live data now", type="primary", use_container_width=True):
        progress = st.progress(0.0, text="Starting...")
        status_box = st.empty()

        def _on_progress(i: int, total: int, name: str) -> None:
            progress.progress(i / max(total, 1), text=f"{i}/{total} — {name[:40]}")

        try:
            run = refresh_all(on_progress=_on_progress)
            progress.empty()
            status_box.success(
                f"✅ Refreshed {run.companies_succeeded}/{run.companies_attempted} companies. "
                "Reloading dashboard..."
            )
            load_overview.clear()
            load_financials_for.clear()
            load_price_history.clear()
            st.rerun()
        except Exception as e:
            progress.empty()
            status_box.error(f"Refresh failed: {e}")

    st.divider()
    st.header("Filters")
    chains = ["(All)"] + sorted([c for c in overview["Value Chain"].dropna().unique()])
    sizes = ["(All)"] + sorted([c for c in overview["Type"].dropna().unique()])
    statuses = ["(All)"] + sorted([c for c in overview["Status"].dropna().unique()])
    chain = st.selectbox("Value Chain", chains)
    size = st.selectbox("Size", sizes)
    status = st.selectbox("Status", statuses)

    mc_series = overview["Mkt Cap (USD mn)"].dropna()
    mc_ceiling = int(mc_series.max()) if not mc_series.empty else 100000
    if mc_ceiling <= 0:
        mc_ceiling = 100000
    mc_min, mc_max = st.slider(
        "Mkt Cap (USD mn)", 0, mc_ceiling, (0, mc_ceiling),
    )

has_live_data = overview["Mkt Cap (USD mn)"].notna().any()
if not has_live_data:
    st.info(
        "📡 No live market data yet. Click **🔄 Refresh live data now** in the sidebar "
        "to pull prices, P/E, market cap, etc. from Yahoo Finance "
        "(takes ~2–3 minutes for all 78 listed companies)."
    )

filt = overview.copy()
if chain != "(All)":
    filt = filt[filt["Value Chain"] == chain]
if size != "(All)":
    filt = filt[filt["Type"] == size]
if status != "(All)":
    filt = filt[filt["Status"] == status]
filt = filt[
    (filt["Mkt Cap (USD mn)"].fillna(0) >= mc_min)
    & (filt["Mkt Cap (USD mn)"].fillna(0) <= mc_max)
]

def _fmt(v, spec=".1f"):
    return format(v, spec) if pd.notna(v) else "—"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Companies", len(filt))
c2.metric("Total Mkt Cap (USD mn)", _fmt(filt['Mkt Cap (USD mn)'].sum(skipna=True), ",.0f") if filt['Mkt Cap (USD mn)'].notna().any() else "—")
c3.metric("Median P/E (TTM)", _fmt(filt['P/E (TTM)'].median()))
c4.metric("Median EV/EBITDA", _fmt(filt['EV/EBITDA'].median()))

tab1, tab2, tab3 = st.tabs(["Overview", "Company detail", "Valuation scatter"])

with tab1:
    st.dataframe(filt, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered view (CSV)",
        filt.to_csv(index=False).encode(),
        file_name="defence_filtered.csv",
        mime="text/csv",
    )

with tab2:
    pick = st.selectbox("Company", filt["Company"].tolist() if not filt.empty else overview["Company"].tolist())
    if pick:
        st.subheader(pick)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Financial history (DB)**")
            st.dataframe(load_financials_for(pick), use_container_width=True, hide_index=True)
        with c2:
            st.markdown("**Price snapshots**")
            hist = load_price_history(pick)
            st.dataframe(hist, use_container_width=True, hide_index=True)
            if not hist.empty and hist["Price (INR)"].notna().any():
                st.line_chart(hist.set_index("Date")["Price (INR)"])

with tab3:
    import plotly.express as px
    sc = filt.dropna(subset=["P/E (TTM)", "ROE"])
    if not sc.empty:
        fig = px.scatter(
            sc, x="P/E (TTM)", y="ROE", size="Mkt Cap (USD mn)", color="Value Chain",
            hover_name="Company", title="Valuation vs profitability",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Not enough data with both P/E and ROE yet — run a refresh.")
