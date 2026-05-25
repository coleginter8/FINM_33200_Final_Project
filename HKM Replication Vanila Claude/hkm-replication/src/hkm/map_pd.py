"""Construct the PD → PERMNO entity map (best-effort, confidence-tagged).

Approach:
  1. Load parsed NY Fed dealer list (data/raw/nyfed/primary_dealers.csv).
  2. Apply manually curated dealer → US parent-holdco rules (mergers, name
     changes, foreign parent exclusions).
  3. Fuzzy-match parent_holdco_name against CRSP comnam (msenames) over the
     dealer's active date range.
  4. Resolve each match to (permno, permco, gvkey) via the CCM link table.
  5. Emit data/pd_to_permno_map.csv with confidence flags.
"""
from __future__ import annotations

import re

import pandas as pd
from rapidfuzz import fuzz, process

from .fetch_wrds import pull_ccm, pull_msenames
from .io import PROJECT_ROOT, get_logger, raw

LOG = get_logger("map_pd")


# Manual PERMNO overrides for parent names whose fuzzy match is unreliable.
# Verified against CRSP msenames in development. Keys must be the normalized
# (uppercase, stripped) parent name as it appears in DEALER_TO_PARENT.
MANUAL_PERMNO: dict[str, int] = {
    "BANK OF AMERICA CORP": 59408,  # BANK OF AMERICA CORP, 1998+
    "BANKAMERICA CORP": 58827,      # BANKAMERICA CORP, 1972+ (legacy)
    "JP MORGAN & CO INC": 48071,    # MORGAN J P & CO INC, 1969-2000
    "LF ROTHSCHILD HOLDINGS INC": 69083,  # ROTHSCHILD L F HOLDGS INC, 1986-1988
}


# Manually curated parent holding company mapping. For dealers with multiple
# parents over time, use a list of (start_year, end_year, parent_name).
# parent_name = None  →  foreign / non-listed / excluded.
# This covers the major HKM PDs.
DEALER_TO_PARENT: dict[str, list[tuple[int, int, str | None]]] = {
    # === US bulge-bracket and survivors ===
    "Goldman, Sachs & Co.": [(1999, 2013, "GOLDMAN SACHS GROUP INC")],
    "Goldman Sachs Government Securities, Inc.": [(1986, 1999, None)],  # pre-IPO
    "J.P. Morgan Securities LLC": [(1960, 2013, "JPMORGAN CHASE & CO")],
    "JP Morgan Securities Inc.": [(1960, 2013, "JPMORGAN CHASE & CO")],
    "J.P. Morgan Securities, Inc.": [(1960, 2013, "JPMORGAN CHASE & CO")],
    "Chase Securities Inc.": [(1990, 2000, "CHASE MANHATTAN CORP")],
    "Morgan Guaranty Trust Company": [(1960, 2000, "JP MORGAN & CO INC")],
    "Citigroup Global Markets Inc.": [(1998, 2013, "CITIGROUP INC")],
    "Salomon Brothers Inc": [
        (1960, 1997, "SALOMON INC"),
        (1997, 1998, "TRAVELERS GROUP INC"),
    ],
    "Salomon Smith Barney Inc.": [
        (1998, 1998, "TRAVELERS GROUP INC"),
        (1998, 2013, "CITIGROUP INC"),
    ],
    "Smith Barney, Harris Upham & Co., Incorporated": [(1960, 1997, "PRIMERICA CORP")],
    "Citicorp Securities, Inc.": [(1990, 1998, "CITICORP")],
    "Merrill Lynch, Pierce, Fenner & Smith Incorporated": [
        (1971, 2008, "MERRILL LYNCH & CO INC"),
        (2009, 2013, "BANK OF AMERICA CORP"),
    ],
    "Merrill Lynch Government Securities Inc.": [(1980, 2009, "MERRILL LYNCH & CO INC")],
    "Morgan Stanley & Co. Incorporated": [(1986, 2013, "MORGAN STANLEY")],
    "Morgan Stanley & Co. LLC": [(1986, 2013, "MORGAN STANLEY")],
    "Bear, Stearns & Co., Inc.": [(1985, 2008, "BEAR STEARNS COMPANIES INC")],
    "Lehman Brothers Inc.": [
        (1994, 2008, "LEHMAN BROTHERS HOLDINGS INC"),
        (1984, 1994, "AMERICAN EXPRESS CO"),  # Shearson/Lehman era
    ],
    "Drexel Burnham Lambert Group, Inc.": [(1976, 1990, "DREXEL BURNHAM LAMBERT GROUP")],
    "Donaldson, Lufkin & Jenrette Securities Corp.": [
        (1986, 2000, "DONALDSON LUFKIN & JENRETTE INC"),
    ],
    "Dean Witter Reynolds Inc.": [(1960, 1997, "DEAN WITTER DISCOVER & CO")],
    "PaineWebber Incorporated": [(1960, 2000, "PAINE WEBBER GROUP INC")],
    "Kidder, Peabody & Co. Incorporated": [(1986, 1994, "GENERAL ELECTRIC CO")],
    "Prudential-Bache Securities, Inc.": [(1981, 2000, "PRUDENTIAL FINANCIAL INC")],
    "First Boston Corp.": [(1960, 1988, "FIRST BOSTON INC")],
    "CS First Boston Corp.": [(1993, 2006, None)],  # Credit Suisse — foreign
    "Cantor Fitzgerald & Co.": [(2006, 2013, None)],  # private
    "Jefferies & Company, Inc.": [(2009, 2013, "JEFFERIES GROUP INC")],
    "Greenwich Capital Markets, Inc.": [(1990, 2010, None)],  # RBS-owned (foreign)
    "Refco Securities, LLC": [(1989, 2005, "REFCO INC")],
    "Aubrey G. Lanston & Co., Inc.": [(1960, 2000, None)],  # private
    "Discount Corp. of New York": [(1960, 1992, None)],  # private/acquired
    "Carroll McEntee & McGinley, Incorporated": [(1980, 1999, None)],
    "EF Hutton & Company, Inc.": [(1960, 1988, "HUTTON E F GROUP INC")],
    "LF Rothschild, Unterberg, Towbin, Inc.": [(1986, 1988, "LF ROTHSCHILD HOLDINGS INC")],
    "Shearson Lehman Government Securities, Inc.": [(1985, 1994, "AMERICAN EXPRESS CO")],
    "LBI Government Securities Inc.": [(1985, 1990, "AMERICAN EXPRESS CO")],
    "Thomson McKinnon Securities, Inc.": [(1960, 1989, None)],
    "Banc of America Securities LLC": [(1998, 2013, "BANK OF AMERICA CORP")],
    "Bank of America N.T. & S.A.": [(1960, 1998, "BANKAMERICA CORP")],
    "NationsBanc Capital Markets, Inc.": [(1996, 1998, "NATIONSBANK CORP")],
    "Chemical Securities Inc.": [(1992, 1996, "CHEMICAL BANKING CORP")],
    "Manufacturers Hanover Securities Corporation": [
        (1986, 1991, "MANUFACTURERS HANOVER CORP"),
    ],
    "First Chicago Capital Markets, Inc.": [(1991, 1998, "FIRST CHICAGO CORP")],
    "Continental Illinois National Bank": [(1960, 1994, "CONTINENTAL ILLINOIS CORP")],
    "First National Bank of Chicago": [(1960, 1995, "FIRST CHICAGO CORP")],
    "Bankers Trust Company": [(1960, 1999, "BANKERS TRUST NEW YORK CORP")],
    "BT Securities Corp.": [(1990, 1999, "BANKERS TRUST NEW YORK CORP")],
    "Irving Trust Company": [(1960, 1988, "IRVING BANK CORP")],
    "Marine Midland Bank": [(1960, 1992, None)],  # HSBC subsidiary
    "Chemical Bank": [(1960, 1996, "CHEMICAL BANKING CORP")],
    "Zions First National Bank": [(1989, 2002, "ZIONS BANCORPORATION")],
    # === Foreign-parent dealers (excluded) ===
    "BNP Paribas Securities Corp.": [(2000, 2013, None)],
    "Bank of Nova Scotia, New York Agency": [(2011, 2013, None)],
    "Barclays Capital Inc.": [(1998, 2013, None)],
    "BMO Capital Markets Corp.": [(2011, 2013, None)],
    "BMO Nesbitt Burns Corp.": [(2002, 2008, None)],
    "Harris Nesbitt Corp.": [(2003, 2009, None)],
    "Credit Suisse Securities (USA) LLC": [(1993, 2013, None)],
    "Daiwa Capital Markets America Inc.": [(1986, 2013, None)],
    "Daiwa Securities America Inc.": [(1986, 2001, None)],
    "Deutsche Bank Securities Inc.": [(1990, 2013, None)],
    "HSBC Securities (USA) Inc.": [(1999, 2013, None)],
    "HSBC Markets (USA) Inc.": [(1992, 1999, None)],
    "Mizuho Securities USA Inc.": [(2002, 2013, None)],
    "Nomura Securities International, Inc.": [(1986, 2013, None)],
    "RBC Capital Markets, LLC": [(2009, 2013, None)],
    "RBS Securities Inc.": [(2000, 2013, None)],
    "SG Americas Securities, LLC": [(2011, 2013, None)],
    "UBS Securities LLC.": [(1990, 2013, None)],
    "Societe Generale": [(1985, 1995, None)],
    "ABN AMRO Inc.": [(1998, 2007, None)],
    "Fuji Securities Inc.": [(1989, 2000, None)],
    "Industrial Bank of Japan Securities, Inc.": [(1988, 2000, None)],
    "Mitsubishi UFJ Securities (USA), Inc.": [(2002, 2013, None)],
    "Bank of Tokyo Securities (USA), Inc.": [(1988, 1996, None)],
    "Sumitomo Securities (USA) Inc.": [(1986, 1995, None)],
    "Sanwa-BGK Securities Co., L.P.": [(1991, 2000, None)],
    "Yamaichi International (America), Inc.": [(1988, 1997, None)],
    "Lloyds Bank N.A.": [(1985, 1995, None)],
    "Westpac Banking Corp.": [(1985, 1995, None)],
    "National Westminster Bank PLC": [(1985, 2000, None)],
    "Eastbridge Capital Inc.": [(1988, 1996, None)],  # foreign / private
    "CRT Government Securities, Ltd.": [(1988, 1996, None)],
    "Harris Government Securities Inc.": [(1986, 1995, None)],  # foreign (BMO)
    "Briggs, Schaedle & Co., Inc.": [(1960, 1989, None)],
    "Bevill Bresler & Schulman Asset Management Corp.": [(1980, 1986, None)],
    "First Boston (Credit Suisse First Boston)": [(1960, 1993, "FIRST BOSTON INC")],
    "Carroll McEntee & McGinley": [(1980, 1999, None)],
}


def _normalize_name(s: str) -> str:
    s = s.upper()
    s = re.sub(r"[.,&]", " ", s)
    s = re.sub(r"\b(INC|CORP|CO|LLC|LP|LTD|HOLDINGS|GROUP|COMPANIES?|THE)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _candidates_for(parent_name: str, msenames: pd.DataFrame) -> pd.DataFrame:
    """Return msenames rows with the best fuzzy match to parent_name.

    Uses token_sort_ratio (preserves order) + length penalty so that strict
    substring matches outrank merely-token-overlapping matches.
    """
    target = _normalize_name(parent_name)
    if not target:
        return msenames.iloc[0:0]
    target_toks = target.split()
    first_tok = target_toks[0]
    # Pre-filter: any comnam containing the first significant token
    norm_comnam = msenames["comnam"].fillna("").str.upper()
    mask = norm_comnam.str.contains(rf"\b{first_tok}", regex=True)
    pre = msenames[mask].copy()
    if pre.empty:
        return pre

    pre["_norm"] = pre["comnam"].apply(_normalize_name)
    # Combine two scorers: token_sort_ratio (order-sensitive) + ratio (length-sensitive)
    sort_scores = pre["_norm"].apply(lambda n: fuzz.token_sort_ratio(target, n))
    ratio_scores = pre["_norm"].apply(lambda n: fuzz.ratio(target, n))
    # Final score: weighted average, biased toward order-sensitive matching
    pre["_score"] = 0.6 * sort_scores + 0.4 * ratio_scores
    pre = pre[pre["_score"] >= 70].sort_values("_score", ascending=False)
    return pre


def _resolve_permnos(parent_name: str, msenames: pd.DataFrame, ccm: pd.DataFrame) -> pd.DataFrame:
    # Manual override path
    target_norm = parent_name.strip().upper()
    if target_norm in MANUAL_PERMNO:
        pn = MANUAL_PERMNO[target_norm]
        row = msenames[msenames["permno"] == pn]
        if row.empty:
            LOG.warning("MANUAL_PERMNO %s → %s not found in msenames", target_norm, pn)
            return row
        first = row.iloc[0]
        link = ccm[ccm["permno"] == pn].drop_duplicates(subset=["permno"])
        return pd.DataFrame(
            [
                {
                    "permno": int(pn),
                    "permco": int(first["permco"]) if pd.notna(first["permco"]) else None,
                    "comnam": first["comnam"],
                    "_score": 100.0,
                    "gvkey": link["gvkey"].iloc[0] if len(link) else None,
                }
            ]
        )
    cands = _candidates_for(parent_name, msenames)
    if cands.empty:
        return cands
    permnos = cands["permno"].unique()
    link = ccm[ccm["permno"].isin(permnos)].drop_duplicates(subset=["permno"])[["permno", "gvkey"]]
    out = (
        cands.drop_duplicates("permno")[["permno", "permco", "comnam", "_score"]]
        .merge(link, on="permno", how="left")
    )
    return out


def build_map() -> pd.DataFrame:
    LOG.info("Loading NY Fed dealer list")
    nyfed_csv = raw("nyfed") / "primary_dealers.csv"
    if not nyfed_csv.exists():
        raise FileNotFoundError(f"Missing {nyfed_csv} — run fetch_nyfed first")
    dealers = pd.read_csv(nyfed_csv, parse_dates=["start_date", "end_date"])
    LOG.info("Loaded %d dealer rows", len(dealers))

    LOG.info("Loading CRSP msenames + CCM link")
    msenames = pull_msenames()
    # Restrict to US common stocks so we don't match ETFs / closed-end funds
    msenames = msenames[msenames["shrcd"].isin([10, 11])].copy()
    LOG.info("msenames after SHRCD filter: %d rows", len(msenames))
    ccm = pull_ccm()

    rows = []
    unknown = []
    for d in dealers["dealer_name"].dropna().unique():
        rules = DEALER_TO_PARENT.get(d.strip())
        if rules is None:
            unknown.append(d)
            rows.append(
                {
                    "dealer_name": d,
                    "parent_holdco_name": "",
                    "permno": None,
                    "permco": None,
                    "gvkey": None,
                    "start_date": dealers.query("dealer_name == @d")["start_date"].min(),
                    "end_date": dealers.query("dealer_name == @d")["end_date"].max(),
                    "confidence": "low",
                    "notes": "no manual parent rule",
                }
            )
            continue
        for (sy, ey, parent) in rules:
            sd = pd.Timestamp(f"{sy}-01-01")
            ed = pd.Timestamp(f"{ey}-12-31")
            if parent is None:
                rows.append(
                    {
                        "dealer_name": d,
                        "parent_holdco_name": "",
                        "permno": None,
                        "permco": None,
                        "gvkey": None,
                        "start_date": sd,
                        "end_date": ed,
                        "confidence": "foreign_excluded",
                        "notes": "foreign or non-listed",
                    }
                )
                continue
            matches = _resolve_permnos(parent, msenames, ccm)
            if matches.empty:
                rows.append(
                    {
                        "dealer_name": d,
                        "parent_holdco_name": parent,
                        "permno": None,
                        "permco": None,
                        "gvkey": None,
                        "start_date": sd,
                        "end_date": ed,
                        "confidence": "low",
                        "notes": "no CRSP name match",
                    }
                )
                continue
            # Restrict to matches active during the period
            matches = matches.merge(
                msenames[["permno", "namedt", "nameendt", "shrcd", "exchcd"]],
                on="permno",
                how="left",
            )
            matches = matches[(matches["namedt"] <= ed) & (matches["nameendt"] >= sd)]
            if matches.empty:
                rows.append(
                    {
                        "dealer_name": d,
                        "parent_holdco_name": parent,
                        "permno": None,
                        "permco": None,
                        "gvkey": None,
                        "start_date": sd,
                        "end_date": ed,
                        "confidence": "low",
                        "notes": "name found but no overlap with PD active window",
                    }
                )
                continue
            top = matches.sort_values("_score", ascending=False).iloc[0]
            conf = "high" if top["_score"] >= 92 else "medium"
            rows.append(
                {
                    "dealer_name": d,
                    "parent_holdco_name": parent,
                    "permno": int(top["permno"]),
                    "permco": int(top["permco"]) if pd.notna(top["permco"]) else None,
                    "gvkey": top["gvkey"] if pd.notna(top["gvkey"]) else None,
                    "start_date": sd,
                    "end_date": ed,
                    "confidence": conf,
                    "notes": f"comnam={top['comnam']}, score={top['_score']:.0f}",
                }
            )

    out = pd.DataFrame(rows).sort_values(["dealer_name", "start_date"])
    csv_path = PROJECT_ROOT / "data" / "pd_to_permno_map.csv"
    out.to_csv(csv_path, index=False)
    LOG.info("Wrote %s rows=%d", csv_path, len(out))

    summary = out.groupby("confidence").size().to_dict()
    LOG.info("Confidence summary: %s", summary)
    if unknown:
        LOG.warning("Dealers with NO manual parent rule (%d): %s", len(unknown), unknown[:20])
    low_rows = out[out["confidence"] == "low"]
    if len(low_rows):
        LOG.warning("LOW-CONFIDENCE rows (%d) — review %s", len(low_rows), csv_path)
    return out


if __name__ == "__main__":
    df = build_map()
    print(df.head(20))
    print("\nBy confidence:")
    print(df["confidence"].value_counts())
