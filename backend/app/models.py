"""
Database schema for the EGX investment intelligence platform.

Design rule (non-negotiable): every stored financial fact carries its
source, the time it was captured, its currency and its reporting period.
Nothing is stored as a bare number. This is what makes the platform
auditable rather than merely plausible.
"""
from datetime import datetime, date
from sqlalchemy import (
    String, Float, Integer, Date, DateTime, ForeignKey, Text, Boolean,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Security(Base):
    """One tradeable instrument. Today: EGX equities and indices."""
    __tablename__ = "securities"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Canonical short EGX ticker, e.g. "COMI"
    ticker: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    # The symbol we use to fetch data upstream, e.g. "COMI.CA"
    yahoo_symbol: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name_en: Mapped[str] = mapped_column(String(255))
    name_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(24), nullable=True)

    asset_type: Mapped[str] = mapped_column(String(24), default="equity")  # equity|index|fund
    sector: Mapped[str | None] = mapped_column(String(80), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="EGP")

    shares_outstanding: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Lifecycle. A company is never deleted when its data is poor -- it stays
    # listed with an honest note, because absence from the list would imply it
    # does not exist on the exchange.
    listing_status: Mapped[str] = mapped_column(String(20), default="listed")

    # full | partial | price_only | none -- drives the "Data quality" badge.
    data_quality: Mapped[str] = mapped_column(String(20), default="unknown")
    data_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_statements: Mapped[bool] = mapped_column(Boolean, default=False)
    price_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    price_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    first_seen: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Price-series integrity. "discontinuous" means the history contains an
    # unadjusted corporate action, so returns spanning it would be fabricated.
    # How many consecutive times the source has returned nothing for this
    # security. Used to stop burning retry time on tickers that are listed but
    # simply not carried by the data source.
    # How many independent rosters list this security, and whether that is
    # enough to call the listing confirmed. Two rosters disagree by ~90
    # tickers, and a name appearing in only one of them -- with no price data
    # anywhere -- is not something to present as a current listing.
    sources_listing: Mapped[int] = mapped_column(Integer, default=0)
    listing_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    fetch_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_fetch_ok: Mapped[date | None] = mapped_column(Date, nullable=True)

    price_integrity: Mapped[str] = mapped_column(String(20), default="unknown")
    price_safe_from: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Provenance
    source: Mapped[str] = mapped_column(String(40), default="yahoo")
    source_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    last_refreshed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    prices: Mapped[list["Price"]] = relationship(back_populates="security", cascade="all, delete-orphan")
    dividends: Mapped[list["Dividend"]] = relationship(back_populates="security", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Security {self.ticker} {self.name_en[:30]}>"


class Price(Base):
    """
    Daily OHLCV. We store BOTH raw close and split/dividend-adjusted close.

    Why both: `close` is what the screen showed on that day (used for display
    and for share-count maths at purchase time), while `adj_close` is what
    total-return calculations must use. Conflating them is one of the most
    common sources of wrong backtest numbers.
    """
    __tablename__ = "prices"
    __table_args__ = (
        UniqueConstraint("security_id", "d", name="uq_price_security_date"),
        Index("ix_price_sec_date", "security_id", "d"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)
    d: Mapped[date] = mapped_column(Date, index=True)

    open: Mapped[float | None] = mapped_column(Float, nullable=True)
    high: Mapped[float | None] = mapped_column(Float, nullable=True)
    low: Mapped[float | None] = mapped_column(Float, nullable=True)
    close: Mapped[float] = mapped_column(Float)
    adj_close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)

    currency: Mapped[str] = mapped_column(String(8), default="EGP")
    source: Mapped[str] = mapped_column(String(40), default="yahoo")

    security: Mapped[Security] = relationship(back_populates="prices")


class Dividend(Base):
    """Cash dividend per share, on its ex-date."""
    __tablename__ = "dividends"
    __table_args__ = (UniqueConstraint("security_id", "ex_date", name="uq_div_security_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)
    ex_date: Mapped[date] = mapped_column(Date, index=True)
    amount_per_share: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="EGP")
    source: Mapped[str] = mapped_column(String(40), default="yahoo")

    security: Mapped[Security] = relationship(back_populates="dividends")


class FinancialFact(Base):
    """
    One line item from one financial statement for one reporting period.

    Stored long/narrow (one row per item) rather than wide, because the set of
    line items differs by industry -- a bank's income statement and a
    manufacturer's do not share a fixed column set.
    """
    __tablename__ = "financial_facts"
    __table_args__ = (
        UniqueConstraint("security_id", "statement", "period_end", "frequency", "item",
                         name="uq_fact"),
        Index("ix_fact_lookup", "security_id", "item", "frequency", "period_end"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"), index=True)

    statement: Mapped[str] = mapped_column(String(20))      # income|balance|cashflow
    frequency: Mapped[str] = mapped_column(String(10))      # annual|quarterly
    period_end: Mapped[date] = mapped_column(Date, index=True)
    item: Mapped[str] = mapped_column(String(120))          # e.g. "Total Revenue"
    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    currency: Mapped[str] = mapped_column(String(8), default="EGP")
    source: Mapped[str] = mapped_column(String(40), default="yahoo")
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IngestRun(Base):
    """
    Audit log of every data-collection attempt.

    If the website ever shows a stale or missing number, this table explains why.
    """
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(60))
    target: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20))          # ok|partial|failed
    rows_written: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FundProfile(Base):
    """
    Fund-specific facts, kept separate from Security so equity columns are not
    polluted with fields that only apply to funds.

    Funds carry a NAV rather than a market price, and the free source publishes
    only the *current* NAV with a few trailing returns -- no NAV history. That
    is why funds have a profile page but cannot be backtested: the tools that
    need a price series genuinely have nothing to work with, and the platform
    says so rather than producing an empty chart.
    """
    __tablename__ = "fund_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"),
                                             unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)

    nav: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_1y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    since_inception_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fund_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    risk: Mapped[str | None] = mapped_column(String(40), nullable=True)

    has_nav_history: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(40), default="egxbot")
    source_url: Mapped[str | None] = mapped_column(String(400), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SecurityMetrics(Base):
    """
    Cached metric snapshot for one security.

    Recomputed by `engine.metrics.refresh_metrics` after each data load.
    `computed_at` is surfaced in the UI so a cached figure is never mistaken
    for a live one.
    """
    __tablename__ = "security_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    security_id: Mapped[int] = mapped_column(ForeignKey("securities.id"),
                                             unique=True, index=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    as_of: Mapped[date | None] = mapped_column(Date, nullable=True)

    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    day_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    enterprise_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares: Mapped[float | None] = mapped_column(Float, nullable=True)

    ret_1w: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_1m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_3m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_6m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_1y: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_3y: Mapped[float | None] = mapped_column(Float, nullable=True)
    ret_5y: Mapped[float | None] = mapped_column(Float, nullable=True)

    volatility_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_52w: Mapped[float | None] = mapped_column(Float, nullable=True)
    low_52w: Mapped[float | None] = mapped_column(Float, nullable=True)
    pct_from_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    history_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_start: Mapped[date | None] = mapped_column(Date, nullable=True)

    dividend_ttm: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_growth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    pb: Mapped[float | None] = mapped_column(Float, nullable=True)
    ps: Mapped[float | None] = mapped_column(Float, nullable=True)
    ev_ebitda: Mapped[float | None] = mapped_column(Float, nullable=True)
    eps: Mapped[float | None] = mapped_column(Float, nullable=True)
    book_value_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)

    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    net_income: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_debt: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)

    net_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    operating_margin_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    roe_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    roa_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    roic_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_growth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue_cagr_3y_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    earnings_growth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # True when the share price and the financial statements appear to be in
    # different units or currencies, so per-share figures cannot be trusted.
    units_suspect: Mapped[bool] = mapped_column(Boolean, default=False)

    statement_periods: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latest_period: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Valuation summary, filled by the valuation engine.
    fair_value_base: Mapped[float | None] = mapped_column(Float, nullable=True)
    fair_value_bear: Mapped[float | None] = mapped_column(Float, nullable=True)
    fair_value_bull: Mapped[float | None] = mapped_column(Float, nullable=True)
    upside_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    valuation_class: Mapped[str | None] = mapped_column(String(40), nullable=True)
    valuation_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)


def init_db() -> None:
    from .db import engine
    Base.metadata.create_all(engine)
