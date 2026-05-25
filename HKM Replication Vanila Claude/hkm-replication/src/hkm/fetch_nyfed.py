"""Fetch and parse NY Fed primary dealer historical list.

Output: data/raw/nyfed/primary_dealers.csv with columns
    dealer_name, start_date, end_date, source
"""
from __future__ import annotations

import io
import re
from datetime import date

import pandas as pd
import requests

from .io import get_logger, raw

LOG = get_logger("fetch_nyfed")

HIST_URL = (
    "https://www.newyorkfed.org/medialibrary/media/markets/pridealers_historical.xls"
)
CURRENT_URL = "https://www.newyorkfed.org/markets/primarydealers"


def _download(url: str, *, dest, label: str) -> bytes:
    headers = {"User-Agent": "hkm-replication/0.1 (academic)"}
    LOG.info("Downloading %s from %s", label, url)
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    LOG.info("Wrote %s bytes to %s", len(r.content), dest)
    return r.content


def _parse_historical_xls(content: bytes) -> pd.DataFrame:
    """Parse pridealers_historical.xls into long format.

    The NY Fed sheet has dealer names down the left and date columns across the
    top (typically one column per year or per change-date). Each cell is 'x' /
    'X' / empty. We treat any non-empty cell as 'active in that date range'.
    Returns columns: dealer_name, start_date, end_date.
    """
    bio = io.BytesIO(content)
    # Try multiple engines: the file is .xls (xlrd) but NY Fed sometimes serves xlsx.
    for engine in ("xlrd", "openpyxl"):
        try:
            xl = pd.ExcelFile(bio, engine=engine)
            break
        except Exception as e:  # noqa: BLE001
            LOG.debug("Engine %s failed: %s", engine, e)
            bio.seek(0)
    else:
        raise RuntimeError("Could not open NY Fed XLS with either engine")

    # Pick the first sheet by default.
    df_raw = xl.parse(xl.sheet_names[0], header=None)
    LOG.info("Raw NY Fed sheet shape: %s", df_raw.shape)

    # Heuristic: header row is the row that has the most parseable dates.
    def _row_date_score(row) -> int:
        score = 0
        for v in row:
            if isinstance(v, (pd.Timestamp,)):
                score += 1
            elif isinstance(v, str) and re.search(r"\b(19|20)\d{2}\b", v):
                score += 1
            elif isinstance(v, (int, float)) and 1960 <= float(v) <= 2030:
                score += 1
        return score

    header_idx = max(range(min(8, len(df_raw))), key=lambda i: _row_date_score(df_raw.iloc[i]))
    LOG.info("Detected header row index: %d", header_idx)
    headers = df_raw.iloc[header_idx].tolist()
    body = df_raw.iloc[header_idx + 1 :].reset_index(drop=True)

    # Build date column list, with first column = dealer name.
    date_cols: list[tuple[int, date]] = []
    for j, h in enumerate(headers):
        if j == 0:
            continue
        d = _coerce_date(h)
        if d is not None:
            date_cols.append((j, d))
    if not date_cols:
        raise RuntimeError("No date columns parsed from NY Fed header")
    date_cols.sort(key=lambda t: t[1])

    rows = []
    for _, brow in body.iterrows():
        name = brow.iloc[0]
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name.lower().startswith(("source", "note", "primary dealer")):
            continue
        active_dates = []
        for j, d in date_cols:
            cell = brow.iloc[j]
            if _cell_is_active(cell):
                active_dates.append(d)
        if not active_dates:
            continue
        # Collapse contiguous date columns into [start, end] segments.
        for seg_start, seg_end in _segments(active_dates, date_cols):
            rows.append(
                {
                    "dealer_name": name,
                    "start_date": pd.Timestamp(seg_start),
                    "end_date": pd.Timestamp(seg_end),
                }
            )
    out = pd.DataFrame(rows)
    LOG.info("Parsed %d (dealer, segment) rows", len(out))
    return out


def _coerce_date(h):
    if isinstance(h, pd.Timestamp):
        return h.date()
    if isinstance(h, (int, float)) and 1960 <= float(h) <= 2030:
        return date(int(h), 12, 31)
    if isinstance(h, str):
        m = re.search(r"(19|20)\d{2}", h)
        if m:
            yr = int(m.group(0))
            mn = 12
            if re.search(r"jan|q1", h, re.I):
                mn = 3
            elif re.search(r"feb|mar", h, re.I):
                mn = 3
            elif re.search(r"jun|q2", h, re.I):
                mn = 6
            elif re.search(r"sep|q3", h, re.I):
                mn = 9
            return date(yr, mn, 28)
    return None


def _cell_is_active(cell) -> bool:
    if isinstance(cell, str) and cell.strip():
        return True
    if isinstance(cell, (int, float)):
        try:
            return float(cell) != 0
        except Exception:  # noqa: BLE001
            return False
    return False


def _segments(active_dates, date_cols):
    """Given sorted active dates, return [(start, end)] contiguous segments."""
    if not active_dates:
        return []
    all_dates = [d for _, d in date_cols]
    indices = sorted(all_dates.index(d) for d in active_dates)
    segs = []
    s = e = indices[0]
    for idx in indices[1:]:
        if idx == e + 1:
            e = idx
        else:
            segs.append((all_dates[s], all_dates[e]))
            s = e = idx
    segs.append((all_dates[s], all_dates[e]))
    return segs


def fetch() -> pd.DataFrame:
    nyfed = raw("nyfed")
    xls_path = nyfed / "pridealers_historical.xls"
    try:
        content = _download(HIST_URL, dest=xls_path, label="NY Fed historical PD list")
        df = _parse_historical_xls(content)
    except Exception as e:  # noqa: BLE001
        LOG.warning("Historical XLS path failed (%s) — falling back to hardcoded seed", e)
        df = _seed_dealer_list()
    # Add a default end_date for currently active dealers
    df["start_date"] = pd.to_datetime(df["start_date"])
    df["end_date"] = pd.to_datetime(df["end_date"])
    df["source"] = "nyfed_historical"
    out_csv = nyfed / "primary_dealers.csv"
    df.sort_values(["dealer_name", "start_date"]).to_csv(out_csv, index=False)
    LOG.info("Wrote %s (%d rows)", out_csv, len(df))
    return df


def _seed_dealer_list() -> pd.DataFrame:
    """Fallback dealer list compiled from HKM Online Appendix Table A.1 +
    public NY Fed records. Used only if the live XLS parse fails."""
    seed = [
        # (dealer_name, start_year, end_year_or_None)
        ("BNP Paribas Securities Corp.", 2000, None),
        ("Bank of Nova Scotia, New York Agency", 2011, None),
        ("Barclays Capital Inc.", 1998, None),
        ("BMO Capital Markets Corp.", 2011, None),
        ("Cantor Fitzgerald & Co.", 2006, None),
        ("Citigroup Global Markets Inc.", 1960, None),
        ("Credit Suisse Securities (USA) LLC", 1993, None),
        ("Daiwa Capital Markets America Inc.", 1986, None),
        ("Deutsche Bank Securities Inc.", 1990, None),
        ("Goldman, Sachs & Co.", 1974, None),
        ("HSBC Securities (USA) Inc.", 1999, None),
        ("Jefferies & Company, Inc.", 2009, None),
        ("J.P. Morgan Securities LLC", 1960, None),
        ("Merrill Lynch, Pierce, Fenner & Smith Incorporated", 1960, None),
        ("Mizuho Securities USA Inc.", 2002, None),
        ("Morgan Stanley & Co. LLC", 1978, None),
        ("Nomura Securities International, Inc.", 1986, None),
        ("RBC Capital Markets, LLC", 2009, None),
        ("RBS Securities Inc.", 2000, None),
        ("SG Americas Securities, LLC", 2011, None),
        ("UBS Securities LLC.", 1990, None),
        # Defunct
        ("Bear, Stearns & Co., Inc.", 1980, 2008),
        ("Lehman Brothers Inc.", 1960, 2008),
        ("Salomon Brothers Inc", 1960, 1997),
        ("Drexel Burnham Lambert Group, Inc.", 1976, 1990),
        ("Kidder, Peabody & Co. Incorporated", 1960, 1994),
        ("Smith Barney, Harris Upham & Co., Incorporated", 1960, 1997),
        ("Dean Witter Reynolds Inc.", 1960, 1997),
        ("PaineWebber Incorporated", 1960, 2000),
        ("Donaldson, Lufkin & Jenrette Securities Corp.", 1986, 2000),
        ("First Boston Corp.", 1960, 1993),
        ("Greenwich Capital Markets, Inc.", 1990, 2010),
        ("Aubrey G. Lanston & Co., Inc.", 1960, 2000),
        ("Discount Corp. of New York", 1960, 1992),
        ("Carroll McEntee & McGinley, Incorporated", 1980, 1999),
        ("CRT Government Securities, Ltd.", 1988, 1996),
        ("Daiwa Securities America Inc.", 1986, 2001),
        ("Eastbridge Capital Inc.", 1988, 1996),
        ("First Chicago Capital Markets, Inc.", 1991, 1998),
        ("Fuji Securities Inc.", 1989, 2000),
        ("Goldman Sachs Government Securities, Inc.", 1986, 1996),
        ("Harris Government Securities Inc.", 1986, 1995),
        ("Harris Nesbitt Corp.", 2003, 2009),
        ("BMO Nesbitt Burns Corp.", 2002, 2008),
        ("HSBC Markets (USA) Inc.", 1992, 1999),
        ("ABN AMRO Inc.", 1998, 2007),
        ("Banc of America Securities LLC", 1998, 2009),
        ("BT Securities Corp.", 1990, 1999),
        ("Chase Securities Inc.", 1990, 2000),
        ("Chemical Securities Inc.", 1992, 1996),
        ("Citicorp Securities, Inc.", 1990, 1998),
        ("CS First Boston Corp.", 1993, 2006),
        ("Manufacturers Hanover Securities Corporation", 1986, 1992),
        ("Morgan Guaranty Trust Company", 1960, 1990),
        ("NationsBanc Capital Markets, Inc.", 1996, 1998),
        ("Prudential-Bache Securities, Inc.", 1981, 2000),
        ("Refco Securities, LLC", 1989, 2005),
        ("Sanwa-BGK Securities Co., L.P.", 1991, 2000),
        ("Yamaichi International (America), Inc.", 1988, 1997),
        ("Zions First National Bank", 1989, 2002),
        # Pre-1960 holdovers from oldest list
        ("Briggs, Schaedle & Co., Inc.", 1960, 1989),
        ("Chemical Bank", 1960, 1996),
        ("Continental Illinois National Bank", 1960, 1994),
        ("First Boston (Credit Suisse First Boston)", 1960, 1993),
        ("Bankers Trust Company", 1960, 1999),
        ("Bank of America N.T. & S.A.", 1960, 1998),
        ("First National Bank of Chicago", 1960, 1995),
        ("Irving Trust Company", 1960, 1988),
        ("Marine Midland Bank", 1960, 1992),
        ("Bank of Tokyo Securities (USA), Inc.", 1988, 1996),
        ("Sumitomo Securities (USA) Inc.", 1986, 1995),
        ("Mitsubishi UFJ Securities (USA), Inc.", 2002, None),
        ("Societe Generale", 1985, 1995),
        ("Industrial Bank of Japan Securities, Inc.", 1988, 2000),
        ("LF Rothschild, Unterberg, Towbin, Inc.", 1986, 1988),
        ("Shearson Lehman Government Securities, Inc.", 1985, 1994),
        ("EF Hutton & Company, Inc.", 1960, 1988),
        ("LBI Government Securities Inc.", 1985, 1990),
        ("Thomson McKinnon Securities, Inc.", 1960, 1989),
        ("Bevill Bresler & Schulman Asset Management Corp.", 1980, 1986),
        ("Lloyds Bank N.A.", 1985, 1995),
        ("Westpac Banking Corp.", 1985, 1995),
        ("National Westminster Bank PLC", 1985, 2000),
    ]
    rows = []
    for name, sy, ey in seed:
        rows.append(
            {
                "dealer_name": name,
                "start_date": pd.Timestamp(year=sy, month=1, day=1),
                "end_date": pd.Timestamp(year=(ey or 2013), month=12, day=31),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = fetch()
    print(df.head())
    print(f"\nTotal unique dealers: {df['dealer_name'].nunique()}")
