"""
The EGX investment universe.

Candidate tickers below are the EGX30 / EGX70 / EGX100 membership plus other
actively traded EGX names. Nothing here is trusted blindly: `verify_universe`
checks every candidate against the live data source and only admits the ones
that return real price history. Names and sectors that the upstream source
leaves blank are filled from `SECTOR_MAP`, which is curated because Yahoo does
not classify Egyptian listings.
"""
from __future__ import annotations

# (EGX ticker, Yahoo symbol, English name, sector)
CANDIDATES: list[tuple[str, str, str, str]] = [
    # --- Banks & financial services ---
    ("COMI", "COMI.CA", "Commercial International Bank (CIB)", "Banks"),
    ("HRHO", "HRHO.CA", "EFG Holding", "Financial Services"),
    ("CIEB", "CIEB.CA", "Credit Agricole Egypt", "Banks"),
    ("ADIB", "ADIB.CA", "Abu Dhabi Islamic Bank - Egypt", "Banks"),
    ("SAUD", "SAUD.CA", "Al Baraka Bank Egypt", "Banks"),
    ("EXPA", "EXPA.CA", "Export Development Bank of Egypt", "Banks"),
    ("FAIT", "FAIT.CA", "Faisal Islamic Bank of Egypt", "Banks"),
    ("HDBK", "HDBK.CA", "Housing & Development Bank", "Banks"),
    ("QNBA", "QNBA.CA", "QNB Alahli", "Banks"),
    ("CANA", "CANA.CA", "Suez Canal Bank", "Banks"),
    ("EFIH", "EFIH.CA", "e-finance for Digital & Financial Investments", "Financial Services"),
    ("BINV", "BINV.CA", "B Investments Holding", "Financial Services"),
    ("AMER", "AMER.CA", "Amer Group Holding", "Real Estate"),

    # --- Real estate & construction ---
    ("TMGH", "TMGH.CA", "Talaat Moustafa Group Holding", "Real Estate"),
    ("EMFD", "EMFD.CA", "Emaar Misr for Development", "Real Estate"),
    ("PHDC", "PHDC.CA", "Palm Hills Developments", "Real Estate"),
    ("MNHD", "MNHD.CA", "Madinet Nasr for Housing & Development", "Real Estate"),
    ("HELI", "HELI.CA", "Heliopolis Housing & Development", "Real Estate"),
    ("OCDI", "OCDI.CA", "SODIC (Six of October Development)", "Real Estate"),
    ("ORHD", "ORHD.CA", "Orascom Development Egypt", "Real Estate"),
    ("ARCC", "ARCC.CA", "Arabian Cement Company", "Construction Materials"),
    ("ORAS", "ORAS.CA", "Orascom Construction", "Construction & Engineering"),

    # --- Industrials & materials ---
    ("SWDY", "SWDY.CA", "El Sewedy Electric", "Industrials"),
    ("ABUK", "ABUK.CA", "Abu Qir Fertilizers", "Chemicals"),
    ("MFPC", "MFPC.CA", "Misr Fertilizers Production (MOPCO)", "Chemicals"),
    ("SKPC", "SKPC.CA", "Sidi Kerir Petrochemicals", "Chemicals"),
    ("EGAL", "EGAL.CA", "Egypt Aluminium", "Metals & Mining"),
    ("ESRS", "ESRS.CA", "Ezz Steel", "Metals & Mining"),
    ("IRON", "IRON.CA", "Egyptian Iron & Steel", "Metals & Mining"),
    ("KZPC", "KZPC.CA", "Kafr El Zayat Pesticides", "Chemicals"),
    ("PRMH", "PRMH.CA", "Prime Holding", "Financial Services"),

    # --- Consumer & healthcare ---
    ("JUFO", "JUFO.CA", "Juhayna Food Industries", "Food & Beverage"),
    ("EAST", "EAST.CA", "Eastern Company", "Tobacco"),
    ("EFID", "EFID.CA", "Edita Food Industries", "Food & Beverage"),
    ("CCAP", "CCAP.CA", "Citadel Capital (Qalaa Holdings)", "Diversified Holdings"),
    ("ISPH", "ISPH.CA", "Ibnsina Pharma", "Healthcare"),
    ("CLHO", "CLHO.CA", "Cleopatra Hospitals Group", "Healthcare"),
    ("RMDA", "RMDA.CA", "Tenth of Ramadan Pharmaceuticals (Rameda)", "Healthcare"),
    ("OLFI", "OLFI.CA", "Obour Land for Food Industries", "Food & Beverage"),
    ("DOMT", "DOMT.CA", "Arabian Food Industries (Domty)", "Food & Beverage"),
    ("SPMD", "SPMD.CA", "Speed Medical", "Healthcare"),

    # --- Technology, telecom & services ---
    ("FWRY", "FWRY.CA", "Fawry for Banking Technology", "Technology"),
    ("ETEL", "ETEL.CA", "Telecom Egypt", "Telecommunications"),
    ("MTIE", "MTIE.CA", "MM Group for Industry & International Trade", "Consumer Discretionary"),
    ("ATQA", "ATQA.CA", "Ateka Holding", "Diversified Holdings"),
    ("GBCO", "GBCO.CA", "GB Corp (GB Auto)", "Consumer Discretionary"),
    ("AUTO", "AUTO.CA", "GB Auto", "Consumer Discretionary"),
    ("EKHO", "EKHO.CA", "Egypt Kuwait Holding", "Diversified Holdings"),
    ("EKHOA", "EKHOA.CA", "Egypt Kuwait Holding (EGP)", "Diversified Holdings"),
    ("ORWE", "ORWE.CA", "Oriental Weavers", "Consumer Discretionary"),
    ("SUGR", "SUGR.CA", "Delta Sugar", "Food & Beverage"),
    ("ELEC", "ELEC.CA", "Electro Cable Egypt", "Industrials"),
    ("AIVC", "AIVC.CA", "Aluminium Industry & Vehicles (Alco)", "Industrials"),
]

# Indices tracked as first-class securities so they can be benchmarked against.
INDEX_CANDIDATES: list[tuple[str, str, str]] = [
    ("EGX30", "^CASE30", "EGX 30 Price Return Index"),
]

SECTOR_MAP = {t: s for t, _, _, s in CANDIDATES}
