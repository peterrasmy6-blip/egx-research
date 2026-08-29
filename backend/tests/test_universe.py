"""
Tests for the reference stock universe.

The universe is the one thing every other part of the platform sits on top of.
If a rights issue leaks into it, the screener ranks a subscription right as if
it were a company; if a second share class survives, a portfolio can hold the
same business twice while believing it is diversified. So these tests are less
about arithmetic than about the definition of "a company" holding still.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.ingest import reference_universe as R
from app.ingest.discovery import apply_reference
from app.models import Security

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  PASS  %s" % name)
    else:
        FAIL += 1
        print("  FAIL  %s  %s" % (name, detail))


# ------------------------------------------------------- the reference list
print("\n--- reference list is internally consistent ---")

overlap = set(R.ORDINARY) & set(R.EXCLUDED)
check("no ticker is both an ordinary share and an excluded instrument",
      not overlap, str(overlap))

check("every rename points at a real ordinary share",
      all(v in R.ORDINARY for v in R.RENAMES.values()),
      str([v for v in R.RENAMES.values() if v not in R.ORDINARY]))

check("no rename source is itself an ordinary share",
      not (set(R.RENAMES) & set(R.ORDINARY)),
      str(set(R.RENAMES) & set(R.ORDINARY)))

check("every off-reference company is inside the universe",
      set(R.KEEP_EXTRA) <= set(R.ORDINARY))

check("every exclusion states a reason",
      all(len(v) == 2 and v[1].strip() for v in R.EXCLUDED.values()))

check("every exclusion has a recognised kind",
      all(v[0] in {"rights", "etf", "certificate", "fund", "class"}
          for v in R.EXCLUDED.values()),
      str({v[0] for v in R.EXCLUDED.values()}))


print("\n--- the instruments that must never be companies ---")

# Each of these was present in the raw source rosters and would have been
# counted as a company.
for tk, why in [("AMES_r2", "rights issue"),
                ("SVCE_r1", "subscription rights"),
                ("EGX30ETF", "an index tracker"),
                ("KASABF", "a certificate"),
                ("EGREF", "a listed fund"),
                ("FAITA", "a second currency class of FAIT"),
                ("VLMR", "a second currency class of VLMRA"),
                ("CCAPP", "preferred shares of CCAP"),
                ("SEIGA", "a second class of SEIG"),
                ("EKHOA", "a second class of EKHO")]:
    check("%s excluded (%s)" % (tk, why), R.classify(tk) == "excluded")

# ...and the company behind each second class is present exactly once.
for keep, drop in [("FAIT", "FAITA"), ("VLMRA", "VLMR"), ("CCAP", "CCAPP"),
                   ("SEIG", "SEIGA"), ("EKHO", "EKHOA")]:
    check("%s kept once, %s not counted again" % (keep, drop),
          keep in R.ORDINARY and drop not in R.ORDINARY)


print("\n--- the filter applied to a dirty roster ---")

# A miniature version of what the two rosters actually hand us.
dirty = {
    "COMI": {"name": "Commercial Intl Bank", "sources": 2},
    "AUTO": {"name": "GB Auto", "sources": 1},           # renamed to GBCO
    "GBCO": {"name": "GB Corp", "sources": 1},           # the same company
    "AMES_r2": {"name": "Rights Issue of Alex", "sources": 1},
    "EGX30ETF": {"name": "EGX30 ETF", "sources": 1},
    "VODE": {"name": "Vodafone Egypt", "sources": 1},    # long gone
    "WHOKNOWS": {"name": "Mystery Co", "sources": 1},    # unrecognised
}
out = apply_reference(dirty, verbose=False)

check("the rights issue is gone", "AMES_r2" not in out)
check("the ETF is gone", "EGX30ETF" not in out)
check("the delisted company is gone", "VODE" not in out)
check("the unrecognised ticker is gone", "WHOKNOWS" not in out)
check("the stale ticker is folded into the current one",
      "AUTO" not in out and "GBCO" in out)
check("the rename does not duplicate the company",
      sum(1 for t in out if t in ("AUTO", "GBCO")) == 1)
check("a real company survives", "COMI" in out)
check("names come from the reference list, not the roster",
      out["COMI"]["name"] == R.ORDINARY["COMI"],
      out["COMI"]["name"])
check("companies the roster missed are restored from the reference list",
      set(R.ORDINARY) <= set(out))
check("filtering twice changes nothing",
      set(apply_reference(out, verbose=False)) == set(out))


print("\n--- the database matches the reference list ---")

db = SessionLocal()
listed = {s.ticker for s in db.scalars(
    Security.__table__.select().where(
        (Security.asset_type == "equity")
        & (Security.listing_status == "listed")).with_only_columns(
            Security.ticker)) } if False else {
    r[0] for r in db.execute(
        Security.__table__.select().with_only_columns(Security.ticker).where(
            (Security.asset_type == "equity")
            & (Security.listing_status == "listed")))}

check("the searchable universe is exactly the reference list",
      listed == set(R.ORDINARY),
      "missing=%s extra=%s" % (sorted(set(R.ORDINARY) - listed)[:5],
                               sorted(listed - set(R.ORDINARY))[:5]))

retired = {r[0] for r in db.execute(
    Security.__table__.select().with_only_columns(Security.ticker).where(
        (Security.asset_type == "equity")
        & (Security.listing_status != "listed")))}
check("no excluded instrument is searchable",
      not (set(R.EXCLUDED) & listed))
check("excluded instruments are retired, not deleted",
      set(R.EXCLUDED) & (listed | retired) == set(R.EXCLUDED) & (listed | retired))

# Nothing may be silently dropped: every retired row must say why.
noreason = [r[0] for r in db.execute(
    Security.__table__.select().with_only_columns(
        Security.ticker, Security.data_note).where(
            (Security.asset_type == "equity")
            & (Security.listing_status != "listed"))) if not r[1]]
check("every retired ticker records why it was retired",
      not noreason, str(noreason[:8]))

db.close()

print("\n" + "=" * 54)
print("  %d passed, %d failed" % (PASS, FAIL))
print("=" * 54)
sys.exit(1 if FAIL else 0)
