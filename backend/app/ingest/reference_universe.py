"""
The reference stock universe.

Why this file exists
--------------------
The two free rosters the platform discovers from (stockanalysis.com and
african-markets.com) disagree badly. Together they yielded 318 "companies",
but roughly a fifth of those were ghosts: tickers that were renamed years ago
(GB Auto became GBCO, Orascom Investment Holding became OIH), companies that
left the exchange (Vodafone Egypt, Orange Egypt, Integrated Diagnostics), and
non-ordinary instruments (preferred shares, bearer shares). None of them trade;
none of them returned a single price bar from any source.

A retail broker's own instrument list is a far better statement of what an
Egyptian investor can actually buy today. This module encodes that list, taken
from the reference screenshots supplied for the project, and classifies every
entry in it.

What counts as a stock here
---------------------------
An *ordinary listed share* of a company. Deliberately excluded, because they
are not companies and would otherwise be counted twice:

  rights issues      a temporary tradable right to subscribe to new shares
                     (tickers ending _r1 / _r2 / _r3)
  ETFs               a basket tracking an index, not a business
  certificates       a wrapper over an underlying holding
  listed funds       a fund, covered on the funds side of the platform
  second classes     the same company quoted again in another currency, or as
                     preferred / bearer shares

Each exclusion records *why*, so the coverage report can explain itself rather
than presenting an unexplained smaller number.

Reconciling with what we already had
------------------------------------
Three rules, applied in this order:

  1. RENAMES    the roster's ticker is stale but the company is the same one.
                The row is renamed, keeping its price history.
  2. KEEP_EXTRA a company absent from the broker's list that nonetheless has
                real, recent price history. It is a genuine EGX share the
                broker simply does not offer, so it stays -- deleting a real
                traded company because one broker skips it would be wrong.
  3. everything else that is neither in the reference list nor has any price
     data is retired from the searchable universe.

Nothing is ever deleted from the database. Retired rows are marked so the
coverage report can count them and so a later listing can revive them.
"""
from __future__ import annotations

# --- Ordinary listed shares -------------------------------------------------
# 269 companies: the 262 ordinary shares on the reference broker list,
# plus the 7 in KEEP_EXTRA below. Ticker -> display name.
ORDINARY: dict[str, str] = {
    "AALR": "General Company for Land Reclamation",
    "ABUK": "Abu Qir Fertilizers and Chemicals",
    "ACAMD": "Arab Company for Asset Management",
    "ACAP": "A Capital",
    "ACGC": "Arab Cotton Ginning",
    "ACRO": "Acrow Misr",
    "ACTF": "ACT Financial",
    "ADCI": "Arab Pharmaceuticals",
    "ADIB": "Abu Dhabi Islamic Bank - Egypt",
    "ADPC": "The Arab Dairy Products",
    "ADRI": "Arab Development and Real Estate",
    "AFDI": "Al Ahly for Development and Investment",
    "AFMC": "Alexandria Flour Mills",
    "AIDC": "Arabia for Investment and Development",
    "AIFI": "Atlas for Investment and Food Industries",
    "AIHC": "Arabia Investments Holding",
    "AJWA": "AJWA for Food Industries",
    "ALCN": "Alexandria Container and Cargo Handling",
    "ALEX": "Alexandria Portland Cement",
    "ALUM": "Arab Aluminum",
    "AMER": "Amer Group",
    "AMES": "Alexandria New Medical Center",
    "AMIA": "Arab Moltaqa Investments",
    "AMII": "Arabian Metal Industries",
    "AMOC": "Alexandria Mineral Oils Company",
    "AMPI": "Novida for Investment and Technology",
    "APPC": "Advanced Pharmaceutical Packaging",
    "APSW": "Arab Polvara Spinning and Weaving",
    "ARAB": "ARAB Developers Holding",
    "ARCC": "Arabian Cement Company",
    "AREH": "Egyptian Real Estate Group",
    "ARVA": "Arab Valves Company",
    "ASCM": "Asec Company for Mining (ASCOM)",
    "ASPI": "Aspire Capital Holding for Financial Investments",
    "ATLC": "Al Tawfeek Leasing Company",
    "ATQA": "Misr National Steel - Ataqa",
    "AXPH": "Alexandria Pharmaceuticals",
    "BIDI": "El Badr Investment And Development",
    "BIGP": "Barbary Investment Group",
    "BINV": "B Investments Holding",
    "BIOC": "GlaxoSmithKline Egypt",
    "BONY": "Bonyan for Development and Trade",
    "BTFH": "Beltone Financial Holding",
    "CAED": "Cairo Educational Services",
    "CANA": "Suez Canal Bank",
    "CCAP": "Qalaa Holdings (Citadel Capital)",
    "CCRS": "Gulf Canadian Real Estate Investment",
    "CEFM": "Middle Egypt Flour Mills",
    "CERA": "The Arab Ceramic Company (Aracemco)",
    "CFGH": "Concrete Fashion Group For Commerce",
    "CICH": "CI Capital Holding",
    "CIEB": "Credit Agricole Egypt",
    "CIRA": "Cairo for Investing and Development",
    "CLHO": "Cleopatra Hospital Company",
    "CNFN": "Contact Financial Holding",
    "COMI": "Commercial International Bank (CIB)",
    "COPR": "Copper For Commercial Investment",
    "COSG": "Cairo Oils and Soap",
    "CPCI": "Cairo Pharmaceuticals",
    "CPME": "Catalyst Partners",
    "CRST": "Crestmark Contracting and Real Estate",
    "CSAG": "Canal Shipping Agencies",
    "DAPH": "Development and Engineering Industries",
    "DCCC": "Damietta Container and Cargo Handling",
    "DCRC": "Delta Construction and Rebuilding",
    "DEIN": "Delta Insurance",
    "DGTZ": "Digitize for Investment And Technology",
    "DIFC": "International Dry Ice Company",
    "DOMT": "Arabian Food Industries (Domty)",
    "DSCW": "Dice Sport and Casual Wear",
    "DTPP": "Delta for Printing and Packaging",
    "EALR": "El Arabia for Land Reclamation",
    "EASB": "Egyptian Arabian Themar Securities",
    "EAST": "Eastern Company",
    "EBSC": "Osool ESB Securities Brokerage",
    "ECAP": "El Ezz Porcelain (Gemma)",
    "EDBM": "Egyptian For Developing Building Materials",
    "EDFM": "East Delta Flour Mills",
    "EEII": "El Arabia Engineering Industries",
    "EFIC": "Egyptian Financial and Industrial",
    "EFID": "Edita Food Industries",
    "EFIH": "e-Finance for Digital and Financial Investments",
    "EGAL": "Egypt Aluminum",
    "EGAS": "Natural Gas and Mining Projects (Egypt Gas)",
    "EGBE": "Egyptian Gulf Bank",
    "EGCH": "Egyptian Chemical Industries (Kima)",
    "EGSA": "Egyptian Satellites (Nilesat)",
    "EGTS": "Egyptian for Tourism Resorts",
    "EHDR": "Egyptians Housing Development",
    "EITP": "Egyptian International Tourism Projects",
    "EIUD": "Egyptians For Investment and Urban Development",
    "EKHO": "Egypt Kuwait Holding",
    "ELEC": "Electro Cable Egypt",
    "ELKA": "El Kahera Housing",
    "ELNA": "El Nasr for Manufacturing Agricultural Crops",
    "ELSH": "El Shams Housing and Urbanization",
    "ELWA": "El Wadi Company for Touristic Investment",
    "EMFD": "Emaar Misr",
    "ENGC": "Engineering Industries (Icon)",
    "EOSB": "El Orouba Securities Brokerage",
    "EPCO": "Egyptian Chemical Industries",
    "EPPK": "Egyptian Company for Packaging",
    "ESAC": "El Shams for Agricultural Crops",
    "ESRS": "Ezz Steel",
    "ETEL": "Telecom Egypt",
    "ETRS": "Egyptian Transport (Egytrans)",
    "EXPA": "Export Development Bank of Egypt",
    "FAIT": "Faisal Islamic Bank of Egypt",
    "FCMD": "Future Care Medical",
    "FERC": "Egyptians Abroad for Investment and Development",
    "FIRE": "Egyptian Gulf Financial Investments",
    "FNAR": "Al Fanar for Investment",
    "FTNS": "Future Nations Financial Investments",
    "FWRY": "Fawry for Banking Technology",
    "GBCO": "GB Corp",
    "GDWA": "Golden Coast",
    "GGCC": "Giza General Contracting",
    "GGRN": "Golden Green Investments",
    "GIHD": "Golden Pyramids Plaza Holding",
    "GMCI": "General Misr Company for Cinema",
    "GOCO": "Golden Coast Company",
    "GOUR": "Gourmet Egypt",
    "GPIM": "Giza Poultry and Investment",
    "GPPL": "Golden Pyramids Plaza",
    "GRCA": "Giza Real Estate Company",
    "GSSC": "General Silos and Storage",
    "GTEX": "Global Telecom Holding",
    "GTHE": "Golden Textiles",
    "GTWL": "Gulf Trade Well",
    "HBCO": "Housing and Building Company",
    "HCFI": "Housing Company for Finance and Investment",
    "HDBK": "Housing and Development Bank",
    "HELI": "Heliopolis Housing",
    "HRHO": "EFG Holding",
    "IBCT": "International Business Corporation for Trade",
    "ICFC": "International Company for Fertilizers and Chemicals",
    "ICID": "International Company for Investment and Development",
    "ICLE": "International Company for Leasing",
    "ICMI": "International Company For Medical Industries",
    "IDRE": "International Dredging",
    "IEEC": "Industrial and Engineering Enterprises",
    "IFAP": "International Agricultural Products",
    "INEG": "Integrated Engineering Group",
    "INFI": "Ismailia National Food Industries",
    "IRAX": "Al Ezz Dekheila Steel",
    "IRON": "Egyptian Iron and Steel",
    "ISMA": "Ismailia Misr Poultry",
    "ISMQ": "Iron and Steel for Mines and Quarries",
    "ISPH": "Ibnsina Pharma",
    "JUFO": "Juhayna Food Industries",
    "KABO": "El Nasr Clothes and Textiles",
    "KORA": "Korra Energi",
    "KRDI": "Al Khair River for Development",
    "KWIN": "El Kahera El Watania Investment",
    "KZPC": "Kafr El Zayat Pesticides",
    "LCSW": "Lecico Egypt",
    "LUTS": "Lotus for Development and Agriculture",
    "MAAL": "Marseille Almasreia Alkhalegeya",
    "MASR": "Madinet Masr for Housing and Development",
    "MBEG": "M.B Engineering",
    "MBSC": "Misr Beni Suef Cement",
    "MCQE": "Misr Cement (Qena)",
    "MCRO": "Macro Group Pharmaceuticals",
    "MEGM": "Middle East Glass Manufacturing",
    "MENA": "Mena Touristic and Real Estate Investment",
    "MEPA": "Medical Packaging Company",
    "MFPC": "Misr Fertilizers Production (Mopco)",
    "MFSC": "Misr Duty Free Shops",
    "MHOT": "Misr Hotels",
    "MICH": "Misr Chemical Industries",
    "MILS": "North Cairo Mills",
    "MIPH": "Minapharm Pharmaceuticals",
    "MISR": "Misr Intercontinental for Granite",
    "MKIT": "Misr Kuwait Investment and Trading",
    "MMAT": "Marsa Alam for Tourism Development",
    "MOED": "Egyptian Modern Education Systems",
    "MOIL": "Maridive and Oil Services",
    "MOIN": "Mohandes Insurance",
    "MOSC": "Misr Oils and Soap",
    "MPCI": "Memphis Pharmaceuticals",
    "MPCO": "Mansourah Poultry",
    "MPRC": "Egyptian Media Production",
    "MTIE": "MM Group for Industry and International Trade",
    "NAHO": "Naeem Holding",
    "NAPR": "National Printing",
    "NARE": "Al Naeem Real Estate Holding",
    "NBKE": "National Bank of Kuwait - Egypt",
    "NCCW": "Nasr Company for Civil Works",
    "NCGC": "Nile Cotton Ginning",
    "NDRL": "National Drilling Company",
    "NEDA": "Northern Upper Egypt Development",
    "NHPS": "National Housing for Professional Syndicates",
    "NINH": "Nozha International Hospital",
    "NIPH": "El-Nile Company for Pharmaceuticals",
    "OBRI": "El Obour Real Estate Investment",
    "OCDI": "Six of October Development (Sodic)",
    "OCPH": "October Pharma",
    "ODIN": "Odin Investments",
    "OFH": "OB Financial Holding",
    "OIH": "Orascom Investment Holding",
    "OLFI": "Obour Land for Food Industries",
    "ORAS": "Orascom Construction",
    "ORHD": "Orascom Development Egypt",
    "ORWE": "Oriental Weavers",
    "PACH": "Paint and Chemicals Industries (Pachin)",
    "PHAR": "Egyptian International Pharmaceuticals (Eipico)",
    "PHDC": "Palm Hills Developments",
    "PHGC": "Premium Healthcare Group",
    "PHTV": "Pyramisa Hotels",
    "POUL": "Cairo Poultry",
    "PRCL": "Ceramic and Porcelain (Sheeni)",
    "PRDC": "Pioneers Properties for Development",
    "PRMH": "Prime Holding",
    "QNBE": "Qatar National Bank Alahli",
    "RACC": "Raya Contact Center",
    "RAKT": "Rakta Paper Manufacturing",
    "RAYA": "Raya Holding for Financial Investments",
    "RKAZ": "Rekaz Financial Holding",
    "RMDA": "Rameda Pharmaceuticals",
    "RMTV": "Rowad Misr Tourism Investment",
    "ROTO": "Rowad Tourism (Al Rowad)",
    "RREI": "Arab Real Estate Investment",
    "RTVC": "Remco for Touristic Villages Construction",
    "RUBX": "Rubex International for Plastics",
    "SAIB": "Societe Arabe Internationale de Banque",
    "SAUD": "Al Baraka Bank Egypt",
    "SCEM": "Sinai Cement",
    "SCFM": "South Cairo and Giza Mills and Bakeries",
    "SCTS": "Suez Canal Company for Technology",
    "SDTI": "Sharm Dreams for Tourism Investment",
    "SEIG": "Saudi Egyptian Investment and Finance",
    "SIMO": "Paper Middle East (Simo)",
    "SIPC": "Sabaa International Company",
    "SKPC": "Sidi Kerir Petrochemicals",
    "SMFR": "Samad Misr (Egyfert)",
    "SMPP": "Modern Shorouk Printing and Packaging",
    "SNFC": "Sharkia National Food",
    "SNFI": "Sohag National Company",
    "SPHT": "El Shams Pyramids for Hotels",
    "SPIN": "Alexandria Spinning and Weaving (Spinalex)",
    "SPMD": "Speed Medical",
    "SUCE": "Suez Cement",
    "SUGR": "Delta Sugar",
    "SVCE": "South Valley Cement",
    "SWDY": "Elsewedy Electric",
    "TALM": "Taaleem Management Services",
    "TANM": "Tanmiya for Real Estate Investment",
    "TAQA": "TAQA Arabia",
    "TMGH": "Talaat Moustafa Group",
    "TORA": "Torah Cement",
    "TRTO": "TransOceans Tours",
    "TWSA": "Tawasoa for Factoring",
    "TYCN": "Tycoon Investments Holding",
    "UASG": "United Arab Shipping",
    "UBEE": "The United Bank",
    "UEFM": "Upper Egypt Flour Mills",
    "UEGC": "Elsaeed Contracting and Real Estate",
    "UNIP": "Universal for Paper and Packaging",
    "UNIT": "United Housing and Development",
    "UPMS": "Union Pharmacist Company",
    "UTOP": "Utopia Real Estate Investment",
    "VALU": "U Consumer Finance (Valu)",
    "VERT": "Vertika for Industry and Trade",
    "VLMRA": "Valmore Holding",
    "WATP": "Modern Company for Water Treatment",
    "WCDF": "Middle and West Delta Flour Mills",
    "WKOL": "Wadi Kom Ombo Land Reclamation",
    "ZEOT": "Extracted Oils",
    "ZMID": "Zahraa Maadi Investment and Development",
}

# --- Instruments deliberately excluded from the stock universe --------------
# Ticker -> (kind, plain-English reason). Shown in the coverage report so the
# smaller company count is explained rather than merely asserted.
EXCLUDED: dict[str, tuple[str, str]] = {
    "AMES_r2": ("rights", "Rights issue of Alexandria New Medical Center "
                          "(AMES) -- a temporary right to subscribe, not the "
                          "company's shares"),
    "ARAB_r2": ("rights", "Rights issue of ARAB Developers Holding (ARAB)"),
    "ASPI_r3": ("rights", "Subscription rights of Aspire Capital (ASPI)"),
    "FCMD_r3": ("rights", "Rights issue of Future Care Medical (FCMD)"),
    "KRDI_r1": ("rights", "Rights issue of Al Khair River (KRDI)"),
    "SVCE_r1": ("rights", "Subscription rights of South Valley Cement (SVCE)"),

    "EGX30ETF": ("etf", "An exchange-traded fund tracking the EGX30 index. "
                        "It is a basket of thirty companies, not a company"),

    "KASABF": ("certificate", "Certificates over Odin Egyptian -- a wrapper "
                              "around a holding, not a listed company. Odin "
                              "itself is covered as ODIN"),

    "EGREF": ("fund", "A listed real-estate fund, not an operating company. "
                      "Funds are covered on the funds side of the platform"),

    "FAITA": ("class", "The US-dollar quoted class of Faisal Islamic Bank. "
                       "The company is covered once, as FAIT"),
    "VLMR": ("class", "The US-dollar quoted class of Valmore Holding. The "
                      "company is covered once, as VLMRA"),
    "CCAPP": ("class", "Preferred shares of Qalaa Holdings. The company is "
                       "covered once, as CCAP"),
    "SEIGA": ("class", "A second quoted class of Saudi Egyptian Investment. "
                       "The company is covered once, as SEIG"),
    "EKHOA": ("class", "The Egyptian-pound quoted class of Egypt Kuwait "
                       "Holding. The company is covered once, as EKHO"),
    "AREHA": ("class", "Bearer shares of Real Estate Egyptian Consortium"),
    "SMCSA": ("class", "Preferred shares of Samcrete Misr"),
    "AIVCB": ("class", "A second quoted class of Al Arafa Investment"),
}

# --- Stale tickers that are really a company we already list ----------------
# old ticker -> current ticker. The row is renamed rather than duplicated, so
# whatever price history it carries is preserved.
RENAMES: dict[str, str] = {
    "AUTO": "GBCO",    # GB Auto renamed itself GB Corp
    "OTMT": "OIH",     # Orascom Telecom Media -> Orascom Investment Holding
    "OCIC": "ORAS",    # Orascom Construction Industries -> Orascom Construction
    "QNBA": "QNBE",    # spelling variant of Qatar National Bank Alahli
    "MBEN": "MBEG",    # spelling variant of M.B Engineering
    "ABRD": "FERC",    # Egyptians Abroad for Investment and Development
    "ALRA": "AIFI",    # Atlas for Investment and Food Industries
    "ALEXA": "ALEX",   # Alexandria Portland Cement
    "MNHD": "MASR",    # Medinet Nasr Housing -> Madinet Masr
    "SRWA": "CNFN",    # Sarwa Capital -> Contact Financial Holding
    "ODID": "ODIN",    # Odin for Investment and Development
}

# --- Real companies the reference broker does not offer ---------------------
# Kept because they have genuine, recent price history: a company that trades
# on the exchange should not vanish from research merely because one broker's
# app skips it. Flagged in the UI so the difference is visible.
KEEP_EXTRA: dict[str, str] = {
    "DCCC": "Damietta Container and Cargo Handling",
    "EDBM": "Egyptian For Developing Building Materials",
    "NDRL": "National Drilling Company",
    "EKHO": "Egypt Kuwait Holding",
    "ARVA": "Arab Valves Company",
    "EIUD": "Egyptians For Investment and Urban Development",
    "ICMI": "International Company For Medical Industries",
}

NOTE_NOT_ON_REFERENCE = (
    "Listed and trading on the EGX, but not offered by the broker whose "
    "instrument list this universe is built from. Included because it has real "
    "price history; you may not be able to buy it through every broker.")


# Rights-issue tickers carry a lower-case suffix ("AMES_r2"), so a plain
# .upper() would fail to match them. Every lookup goes through a case-folded
# index instead.
_FOLDED = {t.upper(): ("ordinary", t) for t in ORDINARY}
_FOLDED.update({t.upper(): ("excluded", t) for t in EXCLUDED})
_FOLDED.update({t.upper(): ("rename", t) for t in RENAMES})


def canonical(ticker: str) -> str | None:
    """The reference list's own spelling of a ticker, or None if unknown."""
    hit = _FOLDED.get((ticker or "").strip().upper())
    return hit[1] if hit else None


def classify(ticker: str) -> str:
    """'ordinary', 'excluded', 'rename' or 'unknown' for one ticker."""
    hit = _FOLDED.get((ticker or "").strip().upper())
    return hit[0] if hit else "unknown"


def reference_tickers() -> set[str]:
    """Every ticker that belongs in the searchable stock universe."""
    return set(ORDINARY)


def summary() -> dict[str, int]:
    kinds: dict[str, int] = {}
    for kind, _ in EXCLUDED.values():
        kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "ordinary": len(ORDINARY),
        "excluded_total": len(EXCLUDED),
        "renames": len(RENAMES),
        "kept_off_reference": len(KEEP_EXTRA),
        **{"excluded_" + k: v for k, v in kinds.items()},
    }
