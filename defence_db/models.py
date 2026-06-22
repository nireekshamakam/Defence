from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime, ForeignKey, Text,
    UniqueConstraint, Index, JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Company(Base):
    """Static descriptor for each defence/aerospace company."""
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    bb_ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    exchange_ticker: Mapped[str | None] = mapped_column(String(20), index=True)
    yahoo_symbol: Mapped[str | None] = mapped_column(String(20), index=True)
    listing_status: Mapped[str | None] = mapped_column(String(30))  # Listed / Unlisted

    incorporation_year: Mapped[int | None] = mapped_column(Integer)
    legacy_years: Mapped[int | None] = mapped_column(Integer)
    type_size: Mapped[str | None] = mapped_column(String(30))  # Large Cap / Mid Cap / Small Cap
    location: Mapped[str | None] = mapped_column(String(120))
    sub_segment: Mapped[str | None] = mapped_column(String(120))
    tam_cagr_fy30: Mapped[float | None] = mapped_column(Float)

    promoter: Mapped[str | None] = mapped_column(String(120))
    promoter_ownership_pct: Mapped[float | None] = mapped_column(Float)
    other_shareholders: Mapped[str | None] = mapped_column(Text)

    barriers_to_entry: Mapped[str | None] = mapped_column(String(20))
    switching_costs: Mapped[str | None] = mapped_column(String(20))
    customer_stickiness: Mapped[str | None] = mapped_column(String(20))

    value_chain: Mapped[str | None] = mapped_column(String(60))  # e.g. "Platforms", "Tier 1"
    segments: Mapped[dict | None] = mapped_column(JSON)  # {"Aerospace Systems": True, ...}

    insights_from_mgmt: Mapped[str | None] = mapped_column(Text)
    comments: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    prices: Mapped[list["PriceSnapshot"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    financials: Mapped[list["FinancialSnapshot"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    manual: Mapped[list["ManualInput"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Company {self.bb_ticker or self.name}>"


class PriceSnapshot(Base):
    """One row per (company, as_of_date) — live market data, refreshed daily."""
    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", "as_of_date", name="uq_price_company_date"),
        Index("ix_price_company_date", "company_id", "as_of_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    as_of_date: Mapped[date] = mapped_column(Date, index=True)

    px_inr: Mapped[float | None] = mapped_column(Float)
    px_usd: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(8), default="INR")

    mkt_cap_inr_mn: Mapped[float | None] = mapped_column(Float)
    mkt_cap_usd_mn: Mapped[float | None] = mapped_column(Float)
    ev_inr_mn: Mapped[float | None] = mapped_column(Float)
    ev_usd_mn: Mapped[float | None] = mapped_column(Float)

    pe_ttm: Mapped[float | None] = mapped_column(Float)
    pe_fwd: Mapped[float | None] = mapped_column(Float)
    ev_ebitda_ttm: Mapped[float | None] = mapped_column(Float)
    ev_ebitda_fwd: Mapped[float | None] = mapped_column(Float)
    px_to_book: Mapped[float | None] = mapped_column(Float)
    px_to_tbv: Mapped[float | None] = mapped_column(Float)

    roe: Mapped[float | None] = mapped_column(Float)
    roce: Mapped[float | None] = mapped_column(Float)
    roic: Mapped[float | None] = mapped_column(Float)

    net_debt_inr_mn: Mapped[float | None] = mapped_column(Float)
    net_debt_usd_mn: Mapped[float | None] = mapped_column(Float)
    net_debt_to_ebitda: Mapped[float | None] = mapped_column(Float)

    shares_out_mn: Mapped[float | None] = mapped_column(Float)
    free_float_pct: Mapped[float | None] = mapped_column(Float)

    vol_5d_mn: Mapped[float | None] = mapped_column(Float)
    vol_10d_mn: Mapped[float | None] = mapped_column(Float)
    vol_30d_mn: Mapped[float | None] = mapped_column(Float)

    source: Mapped[str] = mapped_column(String(40), default="yfinance")
    raw: Mapped[dict | None] = mapped_column(JSON)

    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    company: Mapped["Company"] = relationship(back_populates="prices")


class FinancialSnapshot(Base):
    """One row per (company, fiscal_year, period_type) — reported or estimated financials."""
    __tablename__ = "financial_snapshots"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", "period_type", "source", name="uq_fin_company_year_src"),
        Index("ix_fin_company_year", "company_id", "fiscal_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    fiscal_year: Mapped[int] = mapped_column(Integer, index=True)
    period_type: Mapped[str] = mapped_column(String(1), default="A")  # A=actual, E=estimate

    revenue_inr_mn: Mapped[float | None] = mapped_column(Float)
    ebitda_inr_mn: Mapped[float | None] = mapped_column(Float)
    net_income_inr_mn: Mapped[float | None] = mapped_column(Float)
    eps: Mapped[float | None] = mapped_column(Float)

    pat_margin_pct: Mapped[float | None] = mapped_column(Float)
    ebitda_margin_pct: Mapped[float | None] = mapped_column(Float)
    fcff_yield_on_ev: Mapped[float | None] = mapped_column(Float)
    working_capital_days: Mapped[float | None] = mapped_column(Float)
    debt_equity: Mapped[float | None] = mapped_column(Float)

    roe: Mapped[float | None] = mapped_column(Float)
    roce: Mapped[float | None] = mapped_column(Float)

    order_backlog_inr_mn: Mapped[float | None] = mapped_column(Float)
    deferred_rev_st_inr_mn: Mapped[float | None] = mapped_column(Float)
    deferred_rev_lt_inr_mn: Mapped[float | None] = mapped_column(Float)

    source: Mapped[str] = mapped_column(String(40), default="excel_seed")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="financials")


class ManualInput(Base):
    """Analyst overrides / management-input estimates that aren't market-fetchable."""
    __tablename__ = "manual_inputs"
    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", "field", name="uq_manual_field"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    field: Mapped[str] = mapped_column(String(80))
    value_num: Mapped[float | None] = mapped_column(Float)
    value_text: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company: Mapped["Company"] = relationship(back_populates="manual")


class RefreshRun(Base):
    """Log of every refresh execution — for auditing / monitoring."""
    __tablename__ = "refresh_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String(40))
    companies_attempted: Mapped[int] = mapped_column(Integer, default=0)
    companies_succeeded: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
