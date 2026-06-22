"""One-time seed: read the source Excel and load companies + historical financials.

Run via `python -m defence_db.etl.seed_from_excel` — idempotent (uses name as key).
"""
from __future__ import annotations
import logging
from datetime import datetime
from pathlib import Path

import openpyxl
from sqlalchemy import select

from ..config import SOURCE_EXCEL
from ..db import init_db, session_scope
from ..models import Company, FinancialSnapshot, ManualInput
from ..ticker_map import derive_yahoo_symbol

logger = logging.getLogger(__name__)

SEGMENT_COLS = {
    33: "Aerospace Systems",
    34: "Land Systems",
    35: "Naval Systems",
    36: "Mechanical Systems",
    37: "Structural Systems",
    38: "Weapon Systems",
    39: "Munitions & Ordnance",
    40: "Other Stand-Alone Items",
    41: "Electrical Equipment & Components",
    42: "Electronic Equipment & Components",
    43: "Test Solutions & Engineering",
    44: "Raw Materials",
    45: "Precision Components",
}

# (column_index, fiscal_year, period_type, field) for financial back-data in CCA_Defense.
# These are revenue blocks; we capture EBITDA% / ROE / ROCE / margins similarly.
REVENUE_COLS = [(47, 2025, "A"), (48, 2024, "A"), (49, 2023, "A")]
REVENUE_EST_COLS = [(50, 2025, "E"), (51, 2024, "E"), (52, 2023, "E"), (53, 2022, "E")]
EV_EBITDA_COLS = [(54, 2025, "A"), (55, 2024, "A"), (56, 2023, "A"), (57, 2022, "A")]
ROE_COLS = [(58, 2025, "A"), (59, 2024, "A"), (60, 2023, "A"), (61, 2022, "A")]
ROCE_COLS = [(62, 2025, "A"), (63, 2024, "A"), (64, 2023, "A"), (65, 2022, "A")]
PAT_COLS = [(73, 2025, "A"), (74, 2024, "A"), (75, 2023, "A")]
FCFF_COLS = [(76, 2025, "A"), (77, 2024, "A"), (78, 2023, "A")]
WC_COLS = [(79, 2025, "A"), (80, 2024, "A"), (81, 2023, "A")]


def _bool(v):
    if v is None:
        return None
    if isinstance(v, str):
        return v.strip().upper() in {"Y", "YES", "TRUE", "1"}
    return bool(v)


def _str(v):
    return None if v is None else str(v).strip() or None


def _num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _upsert_company(session, row: tuple) -> Company:
    name = _str(row[2])
    if not name:
        raise ValueError("row missing company name")

    existing = session.execute(select(Company).where(Company.name == name)).scalar_one_or_none()
    seg_flags = {label: _bool(row[idx]) for idx, label in SEGMENT_COLS.items()}

    fields = dict(
        name=name,
        bb_ticker=_str(row[3]),
        exchange_ticker=_str(row[4]),
        incorporation_year=int(row[6]) if isinstance(row[6], (int, float)) else None,
        legacy_years=int(row[7]) if isinstance(row[7], (int, float)) else None,
        listing_status=_str(row[8]),
        sub_segment=_str(row[9]),
        tam_cagr_fy30=_num(row[10]),
        type_size=_str(row[23]),
        location=_str(row[24]),
        promoter=_str(row[25]),
        promoter_ownership_pct=_num(row[26]),
        other_shareholders=_str(row[27]),
        barriers_to_entry=_str(row[28]),
        switching_costs=_str(row[29]),
        customer_stickiness=_str(row[30]),
        insights_from_mgmt=_str(row[31]),
        comments=_str(row[32]),
        value_chain=_str(row[46]),
        segments={k: v for k, v in seg_flags.items() if v},
    )
    fields["yahoo_symbol"] = derive_yahoo_symbol(fields["bb_ticker"], fields["exchange_ticker"])

    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
        return existing
    co = Company(**fields)
    session.add(co)
    session.flush()
    return co


def _add_financials(session, company: Company, row: tuple) -> None:
    """Pull historical revenue / EV-EBITDA / ROE / ROCE etc. into FinancialSnapshot."""
    by_year: dict[tuple[int, str], dict] = {}

    def upsert(fy, ptype, **kwargs):
        d = by_year.setdefault((fy, ptype), {})
        d.update({k: v for k, v in kwargs.items() if v is not None})

    for idx, fy, ptype in REVENUE_COLS + REVENUE_EST_COLS:
        upsert(fy, ptype, revenue_inr_mn=_num(row[idx]))
    for idx, fy, ptype in EV_EBITDA_COLS:
        # this is actually EV/EBITDA multiple — we record it on the corresponding price snapshot,
        # but we'll also keep it on financials for historical comparisons.
        pass
    for idx, fy, ptype in ROE_COLS:
        upsert(fy, ptype, roe=_num(row[idx]))
    for idx, fy, ptype in ROCE_COLS:
        upsert(fy, ptype, roce=_num(row[idx]))
    for idx, fy, ptype in PAT_COLS:
        upsert(fy, ptype, pat_margin_pct=_num(row[idx]))
    for idx, fy, ptype in FCFF_COLS:
        upsert(fy, ptype, fcff_yield_on_ev=_num(row[idx]))
    for idx, fy, ptype in WC_COLS:
        upsert(fy, ptype, working_capital_days=_num(row[idx]))

    for (fy, ptype), data in by_year.items():
        if not data:
            continue
        # upsert by (company, fy, ptype, source)
        from sqlalchemy import and_
        existing = session.execute(
            select(FinancialSnapshot).where(and_(
                FinancialSnapshot.company_id == company.id,
                FinancialSnapshot.fiscal_year == fy,
                FinancialSnapshot.period_type == ptype,
                FinancialSnapshot.source == "excel_seed",
            ))
        ).scalar_one_or_none()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
        else:
            session.add(FinancialSnapshot(
                company_id=company.id, fiscal_year=fy, period_type=ptype,
                source="excel_seed", **data,
            ))


def seed(excel_path: Path | None = None) -> int:
    init_db()
    path = Path(excel_path) if excel_path else SOURCE_EXCEL
    if not path.exists():
        raise FileNotFoundError(f"source excel not found: {path}")

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["CCA_Defense"]

    n = 0
    with session_scope() as session:
        for row in ws.iter_rows(min_row=3, values_only=True):
            if row[1] is None or not isinstance(row[1], (int, float)) or row[2] is None:
                continue
            try:
                co = _upsert_company(session, row)
                _add_financials(session, co, row)
                n += 1
            except Exception as e:
                logger.error("seed failed for row %s: %s", row[2], e)
    logger.info("seeded %d companies from %s", n, path.name)
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(f"seeded {seed()} companies")
