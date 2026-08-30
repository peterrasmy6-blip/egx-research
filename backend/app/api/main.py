"""
Web API for the EGX research platform.

The API validates input, calls the deterministic engine, and returns results
together with the provenance and freshness information a reader needs in order
to judge how much weight to put on them.

Positioning: this service provides research, analysis, historical simulation
and education. It does not provide personalised investment advice, and no
endpoint returns a buy/sell instruction for an individual.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_

from ..db import get_session
from ..models import (Security, Price, Dividend, IngestRun, SecurityMetrics,
                      FinancialFact)
from ..engine import (analytics, fundamentals, scenario, valuation,
                      portfolio, forecast, screener as screener_mod, metrics,
                      composite)
from ..engine.forecast_portfolio_run import (forecast_portfolio,
                                             ForecastError as PFError)
from .education import GLOSSARY, LESSONS, QUESTIONNAIRE, score_questionnaire

WEB_DIR = Path(__file__).resolve().parents[1] / "web"

DISCLAIMER = (
    "This platform provides financial information, research, educational "
    "content, historical analysis, scenario analysis and analytical tools. It "
    "does not provide personalised investment advice, portfolio management, or "
    "guarantees of investment returns. Historical performance and model-based "
    "scenarios do not guarantee future results. Users are responsible for their "
    "own investment decisions."
)

app = FastAPI(
    title="EGX Research",
    description="Free research, analysis and education for the Egyptian Exchange. "
                "Not investment advice.",
    version="0.3.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _require(db, ticker: str) -> Security:
    s = analytics.get_security(db, ticker)
    if s is None:
        raise HTTPException(404, "We do not hold data for '%s'." % ticker)
    return s


def _metrics(db, sec) -> SecurityMetrics | None:
    return db.scalar(select(SecurityMetrics)
                     .where(SecurityMetrics.security_id == sec.id))


def _quality_label(q: str | None) -> dict:
    return {
        "full": {"label": "High", "detail":
                 "Prices and financial statements are both available."},
        "partial": {"label": "Partial", "detail":
                    "Some information is unavailable from reliable free sources."},
        "price_only": {"label": "Prices only", "detail":
                       "No financial statements were found, so profitability and "
                       "valuation measures cannot be calculated."},
        "none": {"label": "Unavailable", "detail":
                 "No price history is available from our free sources."},
    }.get(q or "unknown",
          {"label": "Unknown", "detail": "Data coverage has not been assessed yet."})


# --------------------------------------------------------------------------
# Universe & search
# --------------------------------------------------------------------------
@app.get("/api/securities")
def list_securities(include_delisted: bool = False, db=Depends(get_session)):
    q = select(Security, SecurityMetrics).outerjoin(
        SecurityMetrics, SecurityMetrics.security_id == Security.id)
    if not include_delisted:
        q = q.where(Security.listing_status == "listed")
    rows = db.execute(q.order_by(Security.ticker)).all()
    return [{
        "ticker": s.ticker, "name": s.name_en, "sector": s.sector,
        "asset_type": s.asset_type, "listing_status": s.listing_status,
        "data_quality": s.data_quality,
        "market_cap": (m.market_cap if m else None) or s.market_cap,
        "price": m.price if m else None,
        "day_change_pct": m.day_change_pct if m else None,
        "ret_1y": m.ret_1y if m else None,
        "currency": s.currency,
    } for s, m in rows]


@app.get("/api/search")
def search(q: str = Query(..., min_length=1), db=Depends(get_session)):
    """Find a company by ticker, English name, Arabic name, or sector."""
    term = "%%%s%%" % q.strip().lower()
    rows = db.execute(
        select(Security, SecurityMetrics)
        .outerjoin(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(or_(func.lower(Security.ticker).like(term),
                   func.lower(Security.name_en).like(term),
                   func.lower(func.coalesce(Security.name_ar, "")).like(term),
                   func.lower(func.coalesce(Security.sector, "")).like(term)))
        .order_by(Security.listing_status,
                  SecurityMetrics.market_cap.desc().nullslast())
        .limit(25)).all()
    return [{"ticker": s.ticker, "name": s.name_en, "sector": s.sector,
             "data_quality": s.data_quality,
             "listing_status": s.listing_status,
             "price": m.price if m else None} for s, m in rows]


@app.get("/api/sectors")
def sectors(db=Depends(get_session)):
    rows = db.execute(
        select(Security.sector, func.count(Security.id))
        .where(Security.listing_status == "listed", Security.sector.isnot(None))
        .group_by(Security.sector).order_by(func.count(Security.id).desc())).all()
    return [{"sector": s, "count": n} for s, n in rows]


# --------------------------------------------------------------------------
# Company research
# --------------------------------------------------------------------------
@app.get("/api/security/{ticker}")
def security_detail(ticker: str, db=Depends(get_session)):
    sec = _require(db, ticker)
    m = _metrics(db, sec)
    last = analytics.latest_price(db, sec.id)

    fund = fundamentals.summary(db, sec.id)
    stale_days = (date.today() - last.d).days if last else None

    return {
        "ticker": sec.ticker,
        "name": sec.name_en,
        "name_ar": sec.name_ar,
        "isin": sec.isin,
        "sector": sec.sector,
        "industry": sec.industry,
        "asset_type": sec.asset_type,
        "listing_status": sec.listing_status,
        "currency": sec.currency,

        "price": m.price if m else (last.close if last else None),
        "price_date": last.d.isoformat() if last else None,
        "day_change_pct": m.day_change_pct if m else None,
        "market_cap": (m.market_cap if m else None) or sec.market_cap,
        "shares_outstanding": (m.shares if m else None) or sec.shares_outstanding,
        "high_52w": m.high_52w if m else None,
        "low_52w": m.low_52w if m else None,

        "performance": {
            "1W": m.ret_1w if m else None, "1M": m.ret_1m if m else None,
            "3M": m.ret_3m if m else None, "6M": m.ret_6m if m else None,
            "1Y": m.ret_1y if m else None, "3Y": m.ret_3y if m else None,
            "5Y": m.ret_5y if m else None,
        } if m else {},
        "risk": {
            "volatility_pct": m.volatility_pct if m else None,
            "max_drawdown_pct": m.max_drawdown_pct if m else None,
        } if m else {},
        "valuation": {
            "pe": m.pe, "pb": m.pb, "ps": m.ps, "ev_ebitda": m.ev_ebitda,
            "eps": m.eps, "book_value_per_share": m.book_value_per_share,
            "dividend_yield_pct": m.dividend_yield_pct,
            "dividend_ttm": m.dividend_ttm,
        } if m else {},
        "quality": {
            "roe_pct": m.roe_pct, "roa_pct": m.roa_pct, "roic_pct": m.roic_pct,
            "net_margin_pct": m.net_margin_pct,
            "operating_margin_pct": m.operating_margin_pct,
            "debt_to_equity": m.debt_to_equity,
            "revenue_growth_pct": m.revenue_growth_pct,
            "revenue_cagr_3y_pct": m.revenue_cagr_3y_pct,
            "earnings_growth_pct": m.earnings_growth_pct,
        } if m else {},

        "data_quality": {
            "status": sec.data_quality,
            **_quality_label(sec.data_quality),
            "note": sec.data_note,
            "fundamentals_available": fund.get("available", False),
            "fundamentals_coverage_pct": fund.get("coverage_pct"),
            "latest_statement": fund.get("latest_period"),
            "statement_periods": fund.get("periods_available"),
            "missing": fund.get("missing_concepts", []),
            "price_history_from": sec.price_start.isoformat() if sec.price_start else None,
            "price_history_days": m.history_days if m else None,
            "market_data_age_days": stale_days,
            "is_stale": bool(stale_days is not None and stale_days > 5),
            "source": sec.source,
            "source_url": sec.source_url,
            "metrics_computed_at": m.computed_at.isoformat() if m and m.computed_at else None,
            "price_integrity": sec.price_integrity,
            "units_suspect": bool(m.units_suspect) if m else False,
            "price_safe_from": (sec.price_safe_from.isoformat()
                                if sec.price_safe_from else None),
        },
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/security/{ticker}/prices")
def security_prices(ticker: str, range: str = "5y", db=Depends(get_session)):
    sec = _require(db, ticker)
    days = {"1m": 30, "3m": 91, "6m": 182, "1y": 365, "3y": 1095,
            "5y": 1826, "10y": 3652, "max": 100000}.get(range.lower(), 1826)
    last = analytics.latest_price(db, sec.id)
    if last is None:
        return {"ticker": sec.ticker, "points": [], "available": False}
    series = analytics.price_series(db, sec.id, last.d - timedelta(days=days))
    return {"ticker": sec.ticker, "currency": sec.currency, "range": range,
            "available": True,
            "points": [{"d": p.d.isoformat(), "c": round(p.close, 4),
                        "a": round(p.adj_close, 4)} for p in series]}


@app.get("/api/security/{ticker}/fundamentals")
def security_fundamentals(ticker: str, frequency: str = "annual",
                          db=Depends(get_session)):
    sec = _require(db, ticker)
    if frequency not in ("annual", "quarterly"):
        raise HTTPException(400, "frequency must be 'annual' or 'quarterly'")
    hist = fundamentals.statement_history(db, sec.id, frequency)
    if not hist:
        return {"ticker": sec.ticker, "available": False,
                "reason": "No %s financial statements are available for this "
                          "company from free sources." % frequency}
    return {"ticker": sec.ticker, "currency": sec.currency,
            "frequency": frequency, "available": True, "history": hist,
            "source": sec.source}


@app.get("/api/security/{ticker}/dividends")
def security_dividends(ticker: str, db=Depends(get_session)):
    sec = _require(db, ticker)
    rows = db.scalars(select(Dividend).where(Dividend.security_id == sec.id)
                      .order_by(Dividend.ex_date.desc())).all()
    return {"ticker": sec.ticker, "currency": sec.currency,
            "count": len(rows),
            "dividends": [{"ex_date": d.ex_date.isoformat(),
                           "amount": d.amount_per_share} for d in rows]}


@app.get("/api/security/{ticker}/integrity")
def security_integrity(ticker: str, db=Depends(get_session)):
    """Detected breaks in the price series (unadjusted corporate actions)."""
    from ..engine import integrity
    sec = _require(db, ticker)
    return {"ticker": sec.ticker, **integrity.assess_security(db, sec)}


@app.get("/api/security/{ticker}/valuation")
def security_valuation(ticker: str, db=Depends(get_session)):
    """Model-estimated fair value range. Not a price target, not advice."""
    sec = _require(db, ticker)
    m = _metrics(db, sec)
    last = analytics.latest_price(db, sec.id)
    if last is None:
        return {"available": False,
                "reason": "No price is available for this security."}

    hist = fundamentals.statement_history(db, sec.id, "annual")
    meds = metrics.sector_medians(db)
    peer = meds.get(sec.sector or "", {})

    dps = m.dividend_ttm if m else None
    dgr = (m.dividend_growth_pct / 100.0) if (m and m.dividend_growth_pct) else None

    result = valuation.value_security(
        db, sec, last.close, hist, dps, dgr, peer)
    result["ticker"] = sec.ticker
    result["name"] = sec.name_en
    result["as_of"] = last.d.isoformat()
    return result


# --------------------------------------------------------------------------
# Market reference
# --------------------------------------------------------------------------
@app.get("/api/market/composite")
def market_composite(years: int = Query(default=7, ge=1, le=15),
                     db=Depends(get_session)):
    """
    A broad EGX reference series built from our own price data.

    Explicitly NOT the official EGX30 -- that history is not available from any
    free source. The response carries its own biases with it.
    """
    start = date.today() - timedelta(days=365 * years + 30)
    return composite.build_composite(db, start=start)


@app.get("/api/market/indices-note")
def indices_note():
    """Why official EGX index history is not shown."""
    return {
        "official_indices_available": False,
        "explanation": (
            "The Egyptian Exchange publishes EGX30, EGX70 and EGX100, but their "
            "historical values are not available from any free, machine-readable "
            "source we could find. Yahoo Finance returns the current EGX30 level "
            "but refuses historical ranges for it. The EGX website publishes "
            "index pages without a public data feed, and other providers either "
            "charge for the data or prohibit automated access in their terms."),
        "what_we_did_instead": (
            "We build our own equal-weighted composite from the prices we hold, "
            "and label it clearly as ours. We do not reconstruct a series and "
            "call it the EGX30 -- without the official historical constituents "
            "and weights, that would be a fabricated series wearing an official "
            "name."),
        "sources_checked": [
            "Yahoo Finance (^CASE30) - current level only, historical ranges refused",
            "stooq.com - no Egyptian index series served",
            "egx.com.eg - web pages only, no public data feed",
            "Paid providers (EODHD, Twelve Data, ICE) - excluded on cost",
        ],
    }


# --------------------------------------------------------------------------
# Scenarios
# --------------------------------------------------------------------------
class LumpSumRequest(BaseModel):
    ticker: str
    amount: float = Field(gt=0)
    start: date
    end: date | None = None
    reinvest_dividends: bool = False
    inflation_annual: float = Field(default=scenario.DEFAULT_INFLATION_ANNUAL, ge=0, le=1)


class MonthlyRequest(BaseModel):
    ticker: str
    monthly_amount: float = Field(ge=0)
    start: date
    end: date | None = None
    initial_amount: float = Field(default=0.0, ge=0)
    inflation_annual: float = Field(default=scenario.DEFAULT_INFLATION_ANNUAL, ge=0, le=1)


@app.post("/api/scenario/lumpsum")
def api_lumpsum(req: LumpSumRequest, db=Depends(get_session)):
    sec = _require(db, req.ticker)
    if req.start > date.today():
        raise HTTPException(400, "That date is in the future. This tool looks at "
                                 "what already happened.")
    try:
        return scenario.lump_sum(db, sec, req.amount, req.start, req.end,
                                 inflation_annual=req.inflation_annual,
                                 reinvest_dividends=req.reinvest_dividends)
    except scenario.InsufficientData as e:
        raise HTTPException(422, str(e))


@app.post("/api/scenario/monthly")
def api_monthly(req: MonthlyRequest, db=Depends(get_session)):
    sec = _require(db, req.ticker)
    if req.start > date.today():
        raise HTTPException(400, "That date is in the future.")
    try:
        return scenario.monthly_plan(db, sec, req.monthly_amount, req.start,
                                     req.end,
                                     inflation_annual=req.inflation_annual,
                                     initial_amount=req.initial_amount)
    except scenario.InsufficientData as e:
        raise HTTPException(422, str(e))


# --------------------------------------------------------------------------
# Backtesting & portfolio
# --------------------------------------------------------------------------
class Holding(BaseModel):
    ticker: str
    weight: float = Field(ge=0)


class BacktestRequest(BaseModel):
    holdings: list[Holding]
    start: date
    end: date | None = None
    initial: float = Field(default=100000.0, ge=0)
    monthly: float = Field(default=0.0, ge=0)
    rebalance: str = "none"
    reinvest_dividends: bool = True


@app.post("/api/backtest")
def api_backtest(req: BacktestRequest, db=Depends(get_session)):
    if req.rebalance not in ("none", "monthly", "quarterly", "annual"):
        raise HTTPException(400, "rebalance must be none, monthly, quarterly or annual")
    if req.start > date.today():
        raise HTTPException(400, "The start date is in the future.")
    try:
        return portfolio.backtest(
            db, [h.model_dump() for h in req.holdings], req.start, req.end,
            initial=req.initial, monthly=req.monthly, rebalance=req.rebalance,
            reinvest_dividends=req.reinvest_dividends)
    except portfolio.BacktestError as e:
        raise HTTPException(422, str(e))


class PositionIn(BaseModel):
    ticker: str
    value: float = Field(gt=0)


@app.post("/api/portfolio/analyse")
def api_portfolio(holdings: list[PositionIn], db=Depends(get_session)):
    if not holdings:
        raise HTTPException(400, "Add at least one holding.")
    try:
        return portfolio.analyse_composition(
            db, [h.model_dump() for h in holdings])
    except portfolio.BacktestError as e:
        raise HTTPException(422, str(e))


# --------------------------------------------------------------------------
# Forecasting
# --------------------------------------------------------------------------
class ProjectionRequest(BaseModel):
    initial: float = Field(default=0.0, ge=0)
    monthly: float = Field(default=0.0, ge=0)
    years: int = Field(default=10, ge=1, le=40)
    conservative_pct: float = Field(default=8.0, ge=-20, le=60)
    base_pct: float = Field(default=15.0, ge=-20, le=60)
    optimistic_pct: float = Field(default=22.0, ge=-20, le=60)
    inflation_pct: float = Field(default=20.0, ge=0, le=60)
    annual_increase_pct: float = Field(default=0.0, ge=0, le=50)


@app.post("/api/forecast/scenarios")
def api_projection(req: ProjectionRequest):
    try:
        return forecast.scenario_projection(
            req.initial, req.monthly, req.years,
            {"conservative": req.conservative_pct / 100,
             "base": req.base_pct / 100,
             "optimistic": req.optimistic_pct / 100},
            inflation=req.inflation_pct / 100,
            annual_increase=req.annual_increase_pct / 100)
    except forecast.ForecastError as e:
        raise HTTPException(422, str(e))


class MonteCarloRequest(BaseModel):
    initial: float = Field(default=100000.0, ge=0)
    monthly: float = Field(default=0.0, ge=0)
    years: int = Field(default=10, ge=1, le=40)
    simulations: int = Field(default=5000, ge=100, le=20000)
    ticker: str | None = None
    annual_return_pct: float | None = None
    annual_volatility_pct: float | None = None
    inflation_pct: float = Field(default=20.0, ge=0, le=60)
    target: float | None = None


@app.post("/api/forecast/montecarlo")
def api_montecarlo(req: MonteCarloRequest, db=Depends(get_session)):
    """
    Monte Carlo simulation.

    If a ticker is given, the historical return and volatility of that security
    are measured and offered as the starting assumptions. The user can override
    them; what they cannot do is get a simulation with no stated assumption.
    """
    r = req.annual_return_pct / 100 if req.annual_return_pct is not None else None
    v = req.annual_volatility_pct / 100 if req.annual_volatility_pct is not None else None
    basis = "assumptions you provided"
    warnings: list[str] = []
    historical_return = None

    if req.ticker:
        sec = _require(db, req.ticker)
        try:
            p = forecast.estimate_parameters(db, sec.id)
        except forecast.ForecastError as e:
            raise HTTPException(422, str(e))

        historical_return = p["annual_return_historical"]

        # Volatility is a reasonably stable thing to measure from history.
        if v is None:
            v = p["annual_volatility"]

        # Expected RETURN is not. Past average return is a notoriously poor
        # predictor of future return: a company that has just had a strong run
        # will project a spectacular future purely because it did well before.
        # Defaulting to it produced "0.0% chance of loss" for a bank over ten
        # years, which is plainly false. So the default is the market-implied
        # cost of equity -- Egyptian government yield plus an equity premium --
        # which is grounded in what investors currently require rather than in
        # what happened to work recently.
        market_expected = (valuation.DEFAULTS["risk_free_rate"]
                           + valuation.DEFAULTS["equity_risk_premium"])
        if r is None:
            r = market_expected
            basis = ("a market-based expected return of %.1f%% (Egyptian "
                     "government yield plus an equity risk premium), with "
                     "volatility of %.1f%% measured from %s's own history "
                     "between %s and %s"
                     % (r * 100, v * 100, sec.ticker,
                        p["period_start"], p["period_end"]))
            if historical_return > market_expected * 1.3:
                warnings.append(
                    "%s returned about %.0f%% a year over the past %s years. "
                    "That is far above what investors currently require, and "
                    "assuming it continues would produce a very flattering "
                    "projection. This simulation uses %.1f%% instead. You can "
                    "override it, but a past run is not a forecast."
                    % (sec.ticker, historical_return * 100,
                       p["years_of_history"], r * 100))
        else:
            basis = ("your chosen return of %.1f%%, with volatility of %.1f%% "
                     "measured from %s's history" % (r * 100, v * 100, sec.ticker))

    if r is None or v is None:
        raise HTTPException(
            422, "Provide an expected return and volatility, or choose a "
                 "company so volatility can be measured from its history.")

    try:
        out = forecast.monte_carlo(
            req.initial, req.monthly, req.years, r, v,
            simulations=req.simulations, inflation=req.inflation_pct / 100,
            target=req.target)
    except forecast.ForecastError as e:
        raise HTTPException(422, str(e))
    out["basis"] = basis
    out["ticker"] = req.ticker
    out["warnings"] = warnings
    out["historical_return_pct"] = (round(historical_return * 100, 1)
                                    if historical_return is not None else None)
    return out


class PortfolioForecastRequest(BaseModel):
    holdings: list[Holding]
    initial: float = Field(default=100000.0, ge=0)
    monthly: float = Field(default=0.0, ge=0)
    years: int = Field(default=3, ge=1, le=30)
    inflation_pct: float = Field(default=20.0, ge=0, le=60)
    simulations: int = Field(default=5000, ge=100, le=20000)


@app.post("/api/forecast/portfolio")
def api_portfolio_forecast(req: PortfolioForecastRequest, db=Depends(get_session)):
    """Model-based forecast for a portfolio the user builds today."""
    try:
        return forecast_portfolio(
            db, [h.model_dump() for h in req.holdings],
            initial=req.initial, years=req.years, monthly=req.monthly,
            inflation=req.inflation_pct / 100, simulations=req.simulations)
    except PFError as e:
        raise HTTPException(422, str(e))


@app.get("/api/security/{ticker}/risk-parameters")
def api_risk_params(ticker: str, db=Depends(get_session)):
    sec = _require(db, ticker)
    try:
        p = forecast.estimate_parameters(db, sec.id)
    except forecast.ForecastError as e:
        raise HTTPException(422, str(e))
    return {"ticker": sec.ticker, "name": sec.name_en,
            "annual_return_historical_pct": round(p["annual_return_historical"] * 100, 2),
            "annual_volatility_pct": round(p["annual_volatility"] * 100, 2),
            "years_of_history": p["years_of_history"],
            "period_start": p["period_start"], "period_end": p["period_end"],
            "note": "Measured from past prices. The past is not a forecast."}


# --------------------------------------------------------------------------
# Screener & comparison
# --------------------------------------------------------------------------
class Filter(BaseModel):
    field: str
    op: str = "gte"
    value: float


class ScreenRequest(BaseModel):
    filters: list[Filter] = []
    sectors: list[str] | None = None
    sort_by: str = "market_cap"
    descending: bool = True
    limit: int = Field(default=100, ge=1, le=300)


@app.get("/api/reference")
def reference():
    """Engine assumptions, so the methodology page reflects what actually ran."""
    from app.engine.valuation import DEFAULTS as VAL_DEFAULTS
    return {"valuation_defaults": VAL_DEFAULTS}


@app.get("/api/metrics")
def all_metrics():
    """Every metric row, keyed by ticker. The sector pages read this."""
    db = SessionLocal()
    try:
        return {
            sec.ticker: {"pe": m.pe, "pb": m.pb, "roe_pct": m.roe_pct,
                         "dividend_yield_pct": m.dividend_yield_pct,
                         "ret_1y": m.ret_1y}
            for sec, m in db.execute(
                select(Security, SecurityMetrics)
                .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
                .where(Security.listing_status == "listed")).all()
        }
    finally:
        db.close()


@app.get("/api/screener/fields")
def screener_fields():
    return {"fields": [{"field": k, "label": v[1], "unit": v[2]}
                       for k, v in screener_mod.FILTERABLE.items()],
            "withheld": [{"field": k, "reason": v}
                         for k, v in screener_mod.WITHHELD_FROM_SCREENER.items()]}


@app.post("/api/screener")
def api_screener(req: ScreenRequest, db=Depends(get_session)):
    return screener_mod.run_screen(
        db, [f.model_dump() for f in req.filters],
        sort_by=req.sort_by, descending=req.descending,
        sectors=req.sectors, limit=req.limit)


@app.get("/api/compare")
def api_compare(tickers: str = Query(..., description="Comma-separated tickers"),
                db=Depends(get_session)):
    ts = [t.strip() for t in tickers.split(",") if t.strip()]
    try:
        return screener_mod.compare(db, ts)
    except ValueError as e:
        raise HTTPException(422, str(e))


# --------------------------------------------------------------------------
# Education
# --------------------------------------------------------------------------
@app.get("/api/education/glossary")
def api_glossary():
    return {"terms": GLOSSARY}


@app.get("/api/education/lessons")
def api_lessons():
    return {"lessons": LESSONS}


@app.get("/api/education/questionnaire")
def api_questionnaire():
    return {"questions": QUESTIONNAIRE,
            "note": ("This questionnaire is educational. It describes how you "
                     "tend to think about risk. It does not produce a "
                     "personalised investment recommendation.")}


class QuestionnaireAnswers(BaseModel):
    answers: dict[str, int]


@app.post("/api/education/questionnaire")
def api_questionnaire_score(req: QuestionnaireAnswers):
    return score_questionnaire(req.answers)


# --------------------------------------------------------------------------
# Platform status
# --------------------------------------------------------------------------
@app.get("/api/status")
def status(db=Depends(get_session)):
    n_listed = db.scalar(select(func.count(Security.id))
                         .where(Security.listing_status == "listed"))
    n_px = db.scalar(select(func.count(Price.id)))
    n_dv = db.scalar(select(func.count(Dividend.id)))
    n_fa = db.scalar(select(func.count(FinancialFact.id)))
    newest = db.scalar(select(func.max(Price.d)))
    quality = dict(db.execute(
        select(Security.data_quality, func.count(Security.id))
        .group_by(Security.data_quality)).all())
    with_px = db.scalar(select(func.count(func.distinct(Price.security_id))))
    with_fa = db.scalar(select(func.count(func.distinct(FinancialFact.security_id))))
    recent = db.scalars(select(IngestRun).where(IngestRun.status == "failed")
                        .order_by(IngestRun.id.desc()).limit(5)).all()
    age = (date.today() - newest).days if newest else None
    return {
        "securities_listed": n_listed,
        "securities_with_prices": with_px,
        "securities_with_statements": with_fa,
        "price_rows": n_px, "dividend_rows": n_dv, "statement_facts": n_fa,
        "latest_market_date": newest.isoformat() if newest else None,
        "market_data_age_days": age,
        "is_stale": bool(age is not None and age > 5),
        "data_quality_breakdown": quality,
        "recent_failures": [{"job": r.job, "target": r.target,
                             "message": (r.message or "")[:160],
                             "at": r.started_at.isoformat()} for r in recent],
        "sources": ["Yahoo Finance (prices, dividends, financial statements)",
                    "stockanalysis.com (EGX listed-company index)"],
        "server_time": datetime.utcnow().isoformat(),
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/disclaimer")
def api_disclaimer():
    return {"disclaimer": DISCLAIMER,
            "positioning": ("Research, analysis, simulation and education "
                            "software. Not a licensed financial adviser; does "
                            "not manage money or give personalised advice.")}


# --------------------------------------------------------------------------
# Web app
# --------------------------------------------------------------------------
if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}
