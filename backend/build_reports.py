"""
Generate the evidence reports: EGX coverage and data-source inventory.

These are produced FROM the database, not written by hand, so they cannot drift
away from what the platform actually holds.
"""
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select, func
from app.db import SessionLocal
from app.models import Security, Price, Dividend, FinancialFact, SecurityMetrics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_coverage_report() -> str:
    db = SessionLocal()

    total = db.scalar(select(func.count(Security.id)))
    listed = db.scalar(select(func.count(Security.id))
                       .where(Security.listing_status == "listed"))
    delisted = total - listed

    with_px = db.scalar(select(func.count(func.distinct(Price.security_id))))
    with_fa = db.scalar(select(func.count(func.distinct(FinancialFact.security_id))))
    with_dv = db.scalar(select(func.count(func.distinct(Dividend.security_id))))

    n_px = db.scalar(select(func.count(Price.id)))
    n_fa = db.scalar(select(func.count(FinancialFact.id)))
    n_dv = db.scalar(select(func.count(Dividend.id)))
    newest = db.scalar(select(func.max(Price.d)))
    oldest = db.scalar(select(func.min(Price.d)))

    quality = dict(db.execute(select(Security.data_quality, func.count(Security.id))
                              .group_by(Security.data_quality)).all())

    with_val = db.scalar(select(func.count(SecurityMetrics.id))
                         .where(SecurityMetrics.fair_value_base.isnot(None))) or 0

    sectors = db.execute(
        select(Security.sector, func.count(Security.id))
        .where(Security.listing_status == "listed")
        .group_by(Security.sector).order_by(func.count(Security.id).desc())).all()

    # Companies with gaps, and why.
    gaps = db.scalars(
        select(Security)
        .where(Security.data_quality.in_(["none", "price_only", "partial"]))
        .order_by(Security.data_quality, Security.ticker)).all()

    L = []
    A = L.append
    A("# EGX Coverage Report")
    A("")
    A("Generated automatically from the database on "
      f"**{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}**.")
    A("This file is written by `backend/build_reports.py`, not by hand, so it "
      "always reflects what the platform actually holds.")
    A("")
    A("## Headline numbers")
    A("")
    A("| | |")
    A("|---|---|")
    A(f"| Securities discovered on EGX | **{total}** |")
    A(f"| Currently listed | {listed} |")
    A(f"| Delisted / renamed (kept for history) | {delisted} |")
    A(f"| With price history | **{with_px}** ({with_px/total*100:.0f}% of discovered) |")
    A(f"| With financial statements | **{with_fa}** ({with_fa/total*100:.0f}%) |")
    A(f"| With dividend records | {with_dv} |")
    A(f"| With a computable fair-value estimate | {with_val} |")
    A("")
    A("| Data volume | Rows |")
    A("|---|---|")
    A(f"| Daily price records | {n_px:,} |")
    A(f"| Financial statement figures | {n_fa:,} |")
    A(f"| Dividend payments | {n_dv:,} |")
    A("")
    A(f"Price history spans **{oldest} to {newest}**.")
    A("")

    A("## Data quality breakdown")
    A("")
    A("| Status | Companies | Meaning |")
    A("|---|---|---|")
    meanings = {
        "full": "Prices and financial statements both available.",
        "partial": "Some information unavailable from free sources.",
        "price_only": "Prices available, but no financial statements found.",
        "none": "No price history available from free sources.",
        "unknown": "Not yet assessed.",
    }
    for k in ("full", "partial", "price_only", "none", "unknown"):
        if quality.get(k):
            A(f"| {k} | {quality[k]} | {meanings[k]} |")
    A("")

    A("## Sector distribution")
    A("")
    A("| Sector | Companies |")
    A("|---|---|")
    for s, n in sectors:
        A(f"| {s or '_Unclassified_'} | {n} |")
    A("")
    A("Sector labels for the most liquid ~50 names are hand-checked. The rest are "
      "assigned by keyword matching on the company name, because no free source "
      "classifies EGX listings reliably. Unclassified is left blank rather than guessed.")
    A("")

    A("## Companies with incomplete data")
    A("")
    A("These companies remain in the database and remain searchable. The platform "
      "shows what it has and states plainly what is missing. **No figure is ever "
      "invented to fill a gap.**")
    A("")
    if gaps:
        A("| Ticker | Company | Status | Reason |")
        A("|---|---|---|---|")
        for s in gaps:
            note = (s.data_note or "").replace("|", "/")[:120]
            A(f"| {s.ticker} | {s.name_en[:44]} | {s.data_quality} | {note} |")
    else:
        A("_None — every discovered company has both prices and statements._")
    A("")

    # Data-integrity findings
    flagged = db.scalars(
        select(Security).where(Security.price_integrity == "discontinuous")
        .order_by(Security.ticker)).all()
    units = db.execute(
        select(Security.ticker, Security.name_en)
        .join(SecurityMetrics, SecurityMetrics.security_id == Security.id)
        .where(SecurityMetrics.units_suspect == True)  # noqa: E712
        .order_by(Security.ticker)).all()

    A("## Data-integrity findings")
    A("")
    A("Two classes of fault were found in the upstream data and are corrected "
      "here rather than published. Both were discovered because the figures "
      "they produced were arithmetically impossible.")
    A("")
    A("### 1. Unadjusted corporate actions — %d securities" % len(flagged))
    A("")
    A("A share split or consolidation that the source did not apply to earlier "
      "prices creates an overnight jump. The Egyptian Exchange limits daily "
      "moves to roughly 10-20%, so a larger one-day change cannot be trading. "
      "One company appeared as the year's best performer at **+805%** purely "
      "because a 6-for-1 consolidation was never applied backwards.")
    A("")
    A("Returns measured across such a break are **suppressed**, not estimated. "
      "Genuine extreme moves are preserved: a company that rose through weeks "
      "of consecutive limit-up days keeps its real return.")
    A("")
    if flagged:
        A("| Ticker | Company | Continuous from |")
        A("|---|---|---|")
        for s in flagged:
            A("| %s | %s | %s |" % (s.ticker, s.name_en[:40],
                                    s.price_safe_from or "-"))
        A("")
    A("### 2. Currency / unit mismatches — %d securities" % len(units))
    A("")
    A("Several EGX companies have a second share class quoted in US dollars "
      "while filing accounts in Egyptian pounds. Dividing one by the other "
      "produced a P/E of 0.15 and an apparent undervaluation of **2,934%**.")
    A("")
    A("Detected by comparing price with book value per share: every sound "
      "company here sits between roughly 0.7 and 6 times book, so a price below "
      "a tenth of book alongside a P/E under 1 indicates the two figures are "
      "not in the same money. Per-share measures and fair values are then "
      "withheld.")
    A("")
    if units:
        A("| Ticker | Company |")
        A("|---|---|")
        for t, n in units:
            A("| %s | %s |" % (t, n[:44]))
        A("")

    A("## Known limitations")
    A("")
    A("1. **EGX index history is unavailable free.** Yahoo serves the current EGX30 "
      "level but refuses historical ranges for `^CASE30`. No free alternative with "
      "usable history was found. Index history is therefore **not shown** rather "
      "than reconstructed from an incomplete constituent list, which would be a "
      "fabricated series.")
    A("2. **Egyptian investment funds are not covered.** Fund NAV history for EGX-"
      "listed funds is not published by any free source located. Funds are absent "
      "rather than partially faked.")
    A("3. **One primary price source.** Cross-source validation (comparing two "
      "independent providers) is not yet possible, because only one free source "
      "carries full EGX history. Company names and the listed roster ARE "
      "cross-checked against a second source.")
    A("4. **Arabic company names are not populated.** No free source located "
      "provides them in machine-readable form. Search works on English name, "
      "ticker and sector.")
    A("5. **Inflation is an assumption, not measured data.** Real-return figures "
      "use a user-adjustable rate defaulting to 20%/yr, and say so wherever shown.")
    A("")

    A("## Sources used")
    A("")
    A("| Source | Provides | Role |")
    A("|---|---|---|")
    A("| Yahoo Finance (`yfinance`) | Prices, dividends, income statement, balance "
      "sheet, cash flow | Primary data source |")
    A("| stockanalysis.com EGX listing | EGX short ticker codes and company names | "
      "Universe discovery |")
    A("| Yahoo lookup (ISIN prefix `EGS`) | Roster cross-check, ISIN codes | "
      "Independent verification |")
    A("")
    A("See `DATA_SOURCES.md` for the full assessment of each source.")

    db.close()
    return "\n".join(L)


if __name__ == "__main__":
    report = build_coverage_report()
    out = os.path.join(ROOT, "EGX_COVERAGE_REPORT.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(report)
    print("wrote", out)
    print(report[:1400])
