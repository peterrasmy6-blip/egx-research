"""
Re-apply the sector classifier to companies already in the database.

Why this exists
---------------
Sectors used to be written only when a company was first inserted, and never
revisited. So every correction to the classifier reached new listings only, and
the companies that were already wrong stayed wrong -- which is how a third of
the exchange ended up filed under Financial Services because their registered
names contain the word "investment".

The loader now lets the classifier own the field, so on a full refresh this
happens by itself. This script does the same thing without a network round
trip, for an existing database that would otherwise have to wait for one.

It is deliberately idempotent and reports what it changed rather than doing it
silently, because a sector is not cosmetic: it decides which companies a
reader is invited to compare with which.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Security
from app.ingest.discovery import (CURATED_SECTORS, classify_sector_strong,
                                  classify_sector_weak)


def reclassify(db, *, apply: bool = True, verbose: bool = True) -> dict:
    rows = db.scalars(select(Security).where(
        Security.asset_type == "equity")).all()

    changes, cleared = [], []
    for sec in rows:
        # Without a network call there is no african-markets hint here, and
        # the label already stored may well have come from one. So an existing
        # sector outranks the weak name-reading and is never cleared: this
        # script corrects mistakes, it does not throw away evidence it cannot
        # see.
        want = (CURATED_SECTORS.get(sec.ticker)
                or classify_sector_strong(sec.name_en)
                or sec.sector
                or classify_sector_weak(sec.name_en))
        if want == sec.sector:
            continue
        (cleared if want is None else changes).append(
            (sec.ticker, sec.name_en, sec.sector, want))
        if apply:
            sec.sector = want

    if apply:
        db.commit()

    if verbose:
        for ticker, name, was, now in changes:
            print("  %-7s %-44s %s -> %s" % (ticker, name[:44], was, now))
        for ticker, name, was, _ in cleared:
            print("  %-7s %-44s %s -> unclassified" % (ticker, name[:44], was))
        print("\n  %d reclassified, %d unclassified, %d unchanged"
              % (len(changes), len(cleared),
                 len(rows) - len(changes) - len(cleared)))

    return {"reclassified": len(changes), "cleared": len(cleared),
            "unchanged": len(rows) - len(changes) - len(cleared)}


if __name__ == "__main__":
    db = SessionLocal()
    try:
        reclassify(db, apply="--dry-run" not in sys.argv)
    finally:
        db.close()
