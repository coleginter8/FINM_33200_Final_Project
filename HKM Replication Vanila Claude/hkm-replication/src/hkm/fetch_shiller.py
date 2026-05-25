"""Fetch Robert Shiller's aggregate stock market data (ie_data.xls).

Returns a monthly DataFrame with at least: Price, Dividend, Earnings, CPI,
Long Interest Rate, and computed 12-month trailing P/E. We use 1/P/E as E/P.
"""
from __future__ import annotations

import io

import pandas as pd
import requests

from .io import get_logger, raw

LOG = get_logger("fetch_shiller")

URLS = [
    "http://www.econ.yale.edu/~shiller/data/ie_data.xls",
    "https://shillerdata.com/wp-content/uploads/ie_data.xls",
    "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab02-de8cf25a0db5/ie_data.xls",
]


def fetch() -> pd.DataFrame:
    content = None
    last_err = None
    for url in URLS:
        try:
            LOG.info("Trying Shiller URL: %s", url)
            r = requests.get(
                url,
                timeout=60,
                headers={"User-Agent": "Mozilla/5.0 hkm-replication/0.1"},
            )
            r.raise_for_status()
            content = r.content
            break
        except Exception as e:  # noqa: BLE001
            LOG.warning("Failed %s: %s", url, e)
            last_err = e
    if content is None:
        raise RuntimeError(f"All Shiller URLs failed: {last_err}")

    out = raw("shiller") / "ie_data.xls"
    out.write_bytes(content)

    # The "Data" sheet has 7 header rows; data starts row 8 (index 7).
    bio = io.BytesIO(content)
    for engine in ("xlrd", "openpyxl"):
        try:
            xl = pd.ExcelFile(bio, engine=engine)
            break
        except Exception:  # noqa: BLE001
            bio.seek(0)
    else:
        raise RuntimeError("Could not open ie_data.xls")

    # Identify the "Data" sheet (sometimes called "Data" exactly).
    sheet = next(
        (s for s in xl.sheet_names if s.lower().startswith("data")), xl.sheet_names[0]
    )
    df_raw = xl.parse(sheet, header=None)

    # Find header row: row with "Date" in col 0
    header_idx = None
    for i in range(min(15, len(df_raw))):
        v = df_raw.iat[i, 0]
        if isinstance(v, str) and v.strip().lower() == "date":
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError("Could not locate Shiller Data header row")
    headers_raw = [str(h).strip() if h is not None else "" for h in df_raw.iloc[header_idx]]
    # Dedup column names (Shiller sheet sometimes has duplicates / blank cols)
    seen: dict[str, int] = {}
    headers: list[str] = []
    for h in headers_raw:
        if h in seen:
            seen[h] += 1
            headers.append(f"{h}__{seen[h]}")
        else:
            seen[h] = 0
            headers.append(h or f"_unnamed_{len(headers)}")
    body = df_raw.iloc[header_idx + 1 :].copy()
    body.columns = headers
    # Drop trailing empty rows
    body = body.dropna(subset=[headers[0]])
    # Date is like 1871.01 (year.month). Parse.
    def parse_date(v):
        try:
            f = float(v)
        except Exception:  # noqa: BLE001
            return None
        y = int(f)
        m = int(round((f - y) * 100))
        if m == 0:
            m = 10  # 1871.1 means October
        if 1 <= m <= 12:
            return pd.Timestamp(year=y, month=m, day=1) + pd.offsets.MonthEnd(0)
        return None

    body["date"] = body[headers[0]].apply(parse_date)
    body = body.dropna(subset=["date"]).set_index("date")
    # Drop the trailing CAPE / CAPE TR Yield rows where there's no Price; keep numerics.
    for c in body.columns:
        body[c] = pd.to_numeric(body[c], errors="coerce")

    # Locate P/E column (the canonical "P/E10" is CAPE; we want trailing). Shiller's
    # plain P/E column varies between releases. Strategy:
    #   - find a column called 'Price' and 'Earnings'; recompute trailing TTM P/E.
    price_col = next((c for c in body.columns if str(c).strip().lower() == "price"), None)
    earn_col = next((c for c in body.columns if str(c).strip().lower() == "earnings"), None)
    if price_col is None or earn_col is None:
        raise RuntimeError(
            f"Could not find Price/Earnings columns in Shiller sheet. Got: {list(body.columns)[:15]}"
        )
    # Earnings are annualized 12-month trailing per Shiller's convention already,
    # but to mimic 'trailing 12-month' on a monthly basis, we average earnings over
    # the last 12 months (Shiller's E series is interpolated quarterly → monthly).
    body["E_TTM"] = body[earn_col].rolling(12, min_periods=12).mean()
    body["P_E_TTM"] = body[price_col] / body["E_TTM"]
    body["E_P_TTM"] = body["E_TTM"] / body[price_col]
    cols_keep = [price_col, earn_col, "E_TTM", "P_E_TTM", "E_P_TTM"]
    if "CPI" in body.columns:
        cols_keep.append("CPI")
    if "Long Interest Rate" in body.columns:
        cols_keep.append("Long Interest Rate")
    out_df = body[cols_keep].rename(columns={price_col: "Price", earn_col: "Earnings"})

    csv = raw("shiller") / "shiller_monthly.csv"
    out_df.to_csv(csv)
    LOG.info("Wrote %s rows=%d", csv, len(out_df))
    return out_df


if __name__ == "__main__":
    df = fetch()
    print(df.tail())
