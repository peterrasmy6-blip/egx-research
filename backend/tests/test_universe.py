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


print("\n--- an older database is brought up to date ---")

# The deploy pipeline keeps its database in a cache between runs, so it can be
# far older than the code. A run failed with "no such column:
# securities.sources_listing" because a column added later was never applied to
# that cached copy. This proves the migration closes the gap.
import os
import shutil
import sqlite3
import tempfile

from sqlalchemy import create_engine, select as sa_select
from sqlalchemy.orm import sessionmaker

from app.models import Base, ensure_schema

LATER_COLUMNS = ["sources_listing", "listing_confirmed", "price_integrity",
                 "price_safe_from", "fetch_failures", "last_fetch_ok",
                 "data_note"]

src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "data", "egx.db")
if not os.path.exists(src):
    check("older-database migration (needs data/egx.db)", False, "no database")
else:
    tmp = os.path.join(tempfile.gettempdir(), "egx_schema_check.db")
    if os.path.exists(tmp):
        os.remove(tmp)
    shutil.copy(src, tmp)

    raw = sqlite3.connect(tmp)
    dropped = []
    for col in LATER_COLUMNS:
        try:
            raw.execute("ALTER TABLE securities DROP COLUMN %s" % col)
            dropped.append(col)
        except Exception:
            pass                       # an older SQLite cannot drop; skip it
    raw.commit()
    before = {r[1] for r in raw.execute("PRAGMA table_info(securities)")}
    raw.close()

    check("the fixture really is missing the later columns",
          bool(dropped) and not (set(dropped) & before),
          str(sorted(before))[:60])

    eng = create_engine("sqlite:///" + tmp)
    Base.metadata.create_all(eng)      # as init_db does: creates tables only
    added = ensure_schema(eng, verbose=False)
    check("the migration adds every missing column",
          set(dropped) <= {a.split(".", 1)[1] for a in added},
          "added=%s" % added)

    # The exact query that brought the pipeline down.
    Sess = sessionmaker(bind=eng)
    sess = Sess()
    try:
        row = sess.scalar(sa_select(Security).where(Security.ticker == "COMI"))
        check("selecting a company no longer raises OperationalError",
              row is not None and row.ticker == "COMI")
    except Exception as e:
        check("selecting a company no longer raises OperationalError",
              False, type(e).__name__ + ": " + str(e)[:70])
    sess.close()

    # A second run must not try to add the same columns again.
    again = ensure_schema(eng, verbose=False)
    check("the migration is safe to run repeatedly", again == [], str(again))

    eng.dispose()
    os.remove(tmp)


print("\n" + "=" * 54)
print("  %d passed, %d failed" % (PASS, FAIL))
print("=" * 54)
sys.exit(1 if FAIL else 0)
