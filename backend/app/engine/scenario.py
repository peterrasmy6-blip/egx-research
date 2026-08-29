"""
Historical investment scenarios: "what would have happened if I invested X?"

Two shapes are supported:
  * lump sum      - one purchase on one date
  * monthly plan  - a fixed amount invested every month (cost averaging)

Both use only prices that existed on or before the simulated date, so no
future information leaks into a past decision.

A deliberate local choice: results are reported in BOTH nominal and real
(inflation-adjusted) terms. Egyptian inflation has run high enough that a
large nominal gain can still be a loss in purchasing power, and hiding that
would mislead the user about whether they actually got richer.
"""
from __future__ import annotations

from datetime import date, timedelta

from .analytics import (
    price_on_or_after, price_on_or_before, latest_price, price_series,
    dividends_between, daily_returns, annualised_volatility, cagr,
    max_drawdown,
)

# Round-trip cost of an EGX equity trade (commission + exchange/clearing fees).
# Applied on entry only for a hold scenario, since nothing has been sold.
DEFAULT_COST_RATE = 0.00175

# Assumption, not data. Shown to the user and adjustable.
DEFAULT_INFLATION_ANNUAL = 0.20

# A requested date may fall on a weekend or public holiday, so we roll forward
# to the next trading day. Beyond this many days we refuse instead, rather than
# answering for a date the user never asked about.
MAX_ENTRY_ROLL_DAYS = 14


class InsufficientData(Exception):
    """Raised when a scenario cannot be computed honestly."""


def _months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def lump_sum(db, security, amount: float, start: date,
             end: date | None = None,
             cost_rate: float = DEFAULT_COST_RATE,
             inflation_annual: float = DEFAULT_INFLATION_ANNUAL,
             reinvest_dividends: bool = False) -> dict:
    """
    Invest `amount` EGP in one security on `start`, hold until `end`.

    Dividends are counted as cash received unless `reinvest_dividends` is set,
    in which case each payment buys more shares at that day's price.
    """
    if amount <= 0:
        raise InsufficientData("Investment amount must be greater than zero.")

    entry = price_on_or_after(db, security.id, start)
    if entry is None:
        raise InsufficientData(
            "No trading data for %s on or after %s. The earliest price we hold "
            "is later than the date you chose." % (security.ticker, start))

    # Rolling a weekend or holiday forward is fine. Rolling forward by years is
    # not: it would answer a question the user did not ask, and the honest
    # answer is that our history does not reach that far back.
    if (entry.d - start).days > MAX_ENTRY_ROLL_DAYS:
        raise InsufficientData(
            "Our price history for %s only begins on %s, so we cannot say what "
            "would have happened if you invested on %s. Try a date on or after %s."
            % (security.ticker, entry.d.isoformat(), start.isoformat(),
               entry.d.isoformat()))

    end = end or date.today()
    exit_px = price_on_or_before(db, security.id, end) or latest_price(db, security.id)
    if exit_px is None or exit_px.d <= entry.d:
        raise InsufficientData("Not enough price history between those dates.")

    # --- entry ---
    costs = amount * cost_rate
    invested_net = amount - costs
    shares = invested_net / entry.close

    # --- dividends over the holding period ---
    divs = dividends_between(db, security.id, entry.d, exit_px.d)
    dividend_cash = 0.0
    dividend_events = []
    running_shares = shares

    for dv in divs:
        payment = running_shares * dv.amount_per_share
        reinvested_shares = 0.0
        if reinvest_dividends:
            px = price_on_or_after(db, security.id, dv.ex_date)
            if px and px.close > 0:
                reinvested_shares = payment / px.close
                running_shares += reinvested_shares
            else:
                dividend_cash += payment      # could not reinvest; hold as cash
        else:
            dividend_cash += payment
        dividend_events.append({
            "date": dv.ex_date.isoformat(),
            "per_share": dv.amount_per_share,
            "payment": round(payment, 2),
            "reinvested_shares": round(reinvested_shares, 4),
        })

    # --- exit ---
    market_value = running_shares * exit_px.close
    final_value = market_value + dividend_cash
    profit = final_value - amount
    total_return = profit / amount

    price_only_return = exit_px.close / entry.close - 1.0
    years = (exit_px.d - entry.d).days / 365.25

    # --- risk over the actual holding window ---
    series = price_series(db, security.id, entry.d, exit_px.d)
    closes = [p.close for p in series]
    adj = [p.adj_close for p in series]
    dd = max_drawdown(closes)
    vol = annualised_volatility(daily_returns(adj))

    # --- purchasing power ---
    inflation_factor = (1.0 + inflation_annual) ** years if years > 0 else 1.0
    real_value = final_value / inflation_factor
    real_return = real_value / amount - 1.0

    return {
        "type": "lump_sum",
        "ticker": security.ticker,
        "name": security.name_en,
        "currency": security.currency,
        "requested_date": start.isoformat(),
        "entry_date": entry.d.isoformat(),
        "entry_date_adjusted": entry.d != start,
        "exit_date": exit_px.d.isoformat(),
        "years_held": round(years, 2),

        "amount_invested": round(amount, 2),
        "transaction_costs": round(costs, 2),
        "entry_price": round(entry.close, 4),
        "exit_price": round(exit_px.close, 4),
        "shares_bought": round(shares, 4),
        "shares_final": round(running_shares, 4),

        "market_value": round(market_value, 2),
        "dividends_received": round(dividend_cash, 2),
        "dividends_reinvested": reinvest_dividends,
        "dividend_events": dividend_events,
        "final_value": round(final_value, 2),
        "profit": round(profit, 2),

        "total_return_pct": round(total_return * 100, 2),
        "price_only_return_pct": round(price_only_return * 100, 2),
        "cagr_pct": (round(cagr(amount, final_value, years) * 100, 2)
                     if cagr(amount, final_value, years) is not None else None),

        "volatility_pct": round(vol * 100, 2) if vol else None,
        "max_drawdown_pct": round(dd["max_drawdown"] * 100, 2) if dd else None,

        "inflation_assumption_pct": round(inflation_annual * 100, 2),
        "real_value": round(real_value, 2),
        "real_return_pct": round(real_return * 100, 2),
        "beat_inflation": real_return > 0,

        "assumptions": [
            "Bought at the closing price on %s." % entry.d.isoformat(),
            "Transaction cost of %.3f%% applied on purchase."
            % (cost_rate * 100),
            "Dividends %s." % ("reinvested at the closing price on the ex-date"
                               if reinvest_dividends
                               else "held as cash, not reinvested"),
            "No tax has been applied.",
            "Inflation assumed at %.1f%% per year to show purchasing power. "
            "This is an assumption, not measured data."
            % (inflation_annual * 100),
        ],
    }


def monthly_plan(db, security, monthly_amount: float, start: date,
                 end: date | None = None,
                 cost_rate: float = DEFAULT_COST_RATE,
                 inflation_annual: float = DEFAULT_INFLATION_ANNUAL,
                 initial_amount: float = 0.0) -> dict:
    """Invest a fixed amount every month from `start` (cost averaging)."""
    if monthly_amount <= 0 and initial_amount <= 0:
        raise InsufficientData("Enter a monthly amount or a starting amount.")

    end = end or date.today()
    first = price_on_or_after(db, security.id, start)
    if first is None:
        raise InsufficientData(
            "No trading data for %s on or after %s." % (security.ticker, start))

    shares = 0.0
    contributed = 0.0
    costs_total = 0.0
    purchases = []

    if initial_amount > 0:
        c = initial_amount * cost_rate
        shares += (initial_amount - c) / first.close
        contributed += initial_amount
        costs_total += c
        purchases.append({"date": first.d.isoformat(), "amount": initial_amount,
                          "price": round(first.close, 4)})

    n_months = _months_between(start, end)
    for m in range(n_months + 1):
        y = start.year + (start.month - 1 + m) // 12
        mo = (start.month - 1 + m) % 12 + 1
        try:
            buy_date = date(y, mo, min(start.day, 28))
        except ValueError:
            continue
        if buy_date > end:
            break
        px = price_on_or_after(db, security.id, buy_date)
        if px is None or px.d > end:
            continue
        c = monthly_amount * cost_rate
        shares += (monthly_amount - c) / px.close
        contributed += monthly_amount
        costs_total += c
        purchases.append({"date": px.d.isoformat(), "amount": monthly_amount,
                          "price": round(px.close, 4)})

    if not purchases:
        raise InsufficientData("No purchase dates fell inside the available price history.")

    exit_px = price_on_or_before(db, security.id, end) or latest_price(db, security.id)
    divs = dividends_between(db, security.id, first.d, exit_px.d)
    # Dividend per payment depends on shares held at that time; recompute properly.
    dividend_cash = 0.0
    for dv in divs:
        held = sum(p["amount"] * (1 - cost_rate) / p["price"]
                   for p in purchases if p["date"] <= dv.ex_date.isoformat())
        dividend_cash += held * dv.amount_per_share

    market_value = shares * exit_px.close
    final_value = market_value + dividend_cash
    profit = final_value - contributed
    years = (exit_px.d - first.d).days / 365.25

    inflation_factor = (1.0 + inflation_annual) ** years if years > 0 else 1.0
    real_value = final_value / inflation_factor

    return {
        "type": "monthly_plan",
        "ticker": security.ticker,
        "name": security.name_en,
        "currency": security.currency,
        "start_date": first.d.isoformat(),
        "exit_date": exit_px.d.isoformat(),
        "years": round(years, 2),
        "n_purchases": len(purchases),
        "monthly_amount": monthly_amount,
        "initial_amount": initial_amount,
        "total_contributed": round(contributed, 2),
        "transaction_costs": round(costs_total, 2),
        "shares_final": round(shares, 4),
        "average_cost_per_share": round(
            (contributed - costs_total) / shares, 4) if shares else None,
        "exit_price": round(exit_px.close, 4),
        "market_value": round(market_value, 2),
        "dividends_received": round(dividend_cash, 2),
        "final_value": round(final_value, 2),
        "profit": round(profit, 2),
        "total_return_pct": round(profit / contributed * 100, 2) if contributed else None,
        "gain_from_contributions": round(contributed, 2),
        "gain_from_returns": round(profit, 2),
        "inflation_assumption_pct": round(inflation_annual * 100, 2),
        "real_value": round(real_value, 2),
        "purchases": purchases,
        "assumptions": [
            "Bought once a month on (or just after) day %d." % min(start.day, 28),
            "Transaction cost of %.3f%% applied on each purchase." % (cost_rate * 100),
            "Dividends held as cash, not reinvested.",
            "No tax applied.",
            "Because money was added over time, a single annual growth rate is "
            "not shown - each instalment was invested for a different length of time.",
        ],
    }
