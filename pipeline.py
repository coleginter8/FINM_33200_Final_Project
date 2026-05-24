"""
HKM (2017) CDS Portfolio Returns Pipeline
Palhares (2012) mark-to-market return methodology.

Return formula (monthly, seller of protection):
    r_t = s_{t-1}^N / 12  +  (s_{t-1}^N - s_t^N) * RD_{t-1}^N

Risky duration (quarterly payments):
    RD(N, t) = 0.25 * sum_{j=1}^{4N} exp(-lambda*j/4) * exp(-r(j/4)*j/4)
    lambda = 4 * ln(1 + s_5Y / (4 * recovery))   # flat hazard rate from 5Y spread
    recovery = 0.40 (LGD = 0.60, HKM fn.27)

Risk-free rates: Optionmetrics zero-coupon curve (optionm_all.zerocd),
    rate in % -> divide by 100 for continuously compounded decimal rate.
"""

import os
import sys
import psycopg2
import pandas as pd
import numpy as np
from pathlib import Path

WORKDIR = Path('/Users/alexnikolaev/Desktop/finmath/spring_26/genai/final-project/cds_returns_claude-rep')
PG = dict(host='wrds-pgdata.wharton.upenn.edu', port=9737, dbname='wrds',
          user='alexnikolaev', password='721@ArcadiA2025',
          sslmode='require', connect_timeout=60)

TENORS = ['3Y', '5Y', '7Y', '10Y']
TENOR_N = {'3Y': 3, '5Y': 5, '7Y': 7, '10Y': 10}
LGD = 0.60
RECOVERY = 0.40

# Doc clause priority (lower = preferred): XR14 > XR > MR14 > MR
DOC_PRIO = {'XR14': 1, 'XR': 2, 'MR14': 3, 'MR': 4}


# ─── helpers ────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**PG)


def month_end_dates(start='2001-01-01', end='2023-12-31'):
    """Return list of (year, pandas Timestamp) for every calendar month."""
    mends = pd.date_range(start, end, freq='ME')
    return mends


# ─── STEP 1: Pull Markit month-end spreads ──────────────────────────────────

def pull_markit(force=False):
    out = WORKDIR / 'raw_spreads.parquet'
    if out.exists() and not force:
        print(f'  Loading cached {out.name}')
        return pd.read_parquet(out)

    print('  Pulling Markit CDS data year by year ...')
    frames = []
    conn = get_conn()
    try:
        cur = conn.cursor()
        for year in range(2001, 2024):
            print(f'    year {year} ...', end=' ', flush=True)
            # Last available date per (month, ticker, tenor, docclause)
            sql = f"""
                SELECT DISTINCT ON (
                    DATE_TRUNC('month', date), ticker, tenor, docclause
                )
                date, ticker, tenor, parspread, docclause
                FROM markit_cds.cds{year}
                WHERE currency = 'USD'
                  AND tier = 'SNRFOR'
                  AND tenor IN ('3Y','5Y','7Y','10Y')
                  AND docclause IN ('XR','XR14','MR','MR14')
                  AND parspread IS NOT NULL
                  AND parspread > 0
                ORDER BY
                    DATE_TRUNC('month', date), ticker, tenor, docclause,
                    date DESC
            """
            cur.execute(sql)
            rows = cur.fetchall()
            print(f'{len(rows):,} rows')
            if rows:
                df = pd.DataFrame(rows, columns=['date', 'ticker', 'tenor', 'parspread', 'docclause'])
                df['date'] = pd.to_datetime(df['date'])
                frames.append(df)
    finally:
        conn.close()

    raw = pd.concat(frames, ignore_index=True)

    # Assign month label = first day of that month (matches validation convention)
    raw['month'] = raw['date'].dt.to_period('M').dt.to_timestamp()

    # Apply doc clause priority: keep highest-priority clause per (month, ticker, tenor)
    raw['prio'] = raw['docclause'].map(DOC_PRIO).fillna(99)
    raw.sort_values('prio', inplace=True)
    deduped = raw.drop_duplicates(subset=['month', 'ticker', 'tenor'], keep='first')
    deduped = deduped[['month', 'ticker', 'tenor', 'parspread', 'docclause']].copy()
    deduped.sort_values(['ticker', 'tenor', 'month'], inplace=True)

    deduped.to_parquet(out, index=False)
    print(f'  Saved {out.name}  shape={deduped.shape}')
    return deduped


# ─── STEP 2: Pull Optionmetrics zero-coupon rates ───────────────────────────

def pull_optionm(force=False):
    out = WORKDIR / 'rate_panel.parquet'
    if out.exists() and not force:
        print(f'  Loading cached {out.name}')
        return pd.read_parquet(out)

    print('  Pulling Optionmetrics zero rates ...')
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT date, days, rate
            FROM optionm_all.zerocd
            WHERE date >= '2001-01-01' AND date <= '2023-12-31'
              AND days > 0 AND days <= 3700
            ORDER BY date, days
        """)
        rows = cur.fetchall()
    finally:
        conn.close()

    om = pd.DataFrame(rows, columns=['date', 'days', 'rate'])
    om['date'] = pd.to_datetime(om['date'])
    om['rate'] = om['rate'] / 100.0          # % → decimal CC rate
    om['yrs'] = om['days'] / 365.25

    # For each date, build interpolated rate function at quarterly grid (0.25..10.25y)
    QTRS = np.arange(0.25, 10.51, 0.25)      # 0.25, 0.50, ..., 10.50
    rows_out = []
    for dt, grp in om.groupby('date'):
        x = grp['yrs'].values
        y = grp['rate'].values
        # linear interp, flat extrapolation beyond ends
        rate_q = np.interp(QTRS, x, y, left=y[0], right=y[-1])
        for q, r in zip(QTRS, rate_q):
            rows_out.append((dt, q, r))

    panel = pd.DataFrame(rows_out, columns=['date', 'maturity_yr', 'zero_rate'])
    panel['date'] = pd.to_datetime(panel['date'])

    panel.to_parquet(out, index=False)
    print(f'  Saved {out.name}  shape={panel.shape}')
    return panel


# ─── STEP 3: Compute risky durations ────────────────────────────────────────

def compute_rd(spreads_wide, rate_panel, force=False):
    """
    spreads_wide: DataFrame with columns [month, ticker, tenor, parspread]
                  parspread is in decimal (0.01 = 100 bps)

    Returns DataFrame: [month, ticker, tenor, RD]
    """
    out = WORKDIR / 'risky_duration.parquet'
    if out.exists() and not force:
        print(f'  Loading cached {out.name}')
        return pd.read_parquet(out)

    print('  Computing risky durations ...')

    # Build rate lookup: date -> (maturities array, rates array) for fast interp
    rate_panel_sorted = rate_panel.sort_values(['date', 'maturity_yr'])
    # Pivot to dict: date -> array of rates indexed by maturity (0.25, 0.50, ..., 10.50)
    QTRS = np.arange(0.25, 10.51, 0.25)
    rate_dict = {}
    for dt, grp in rate_panel_sorted.groupby('date'):
        rates = grp.set_index('maturity_yr')['zero_rate'].to_dict()
        # Build array indexed by QTRS position
        rate_arr = np.array([rates.get(q, np.nan) for q in QTRS])
        # Forward-fill any nan (shouldn't happen given flat extrapolation above)
        mask = np.isnan(rate_arr)
        if mask.any():
            idx = np.where(~mask)[0]
            if len(idx) > 0:
                rate_arr = np.interp(np.arange(len(QTRS)), idx, rate_arr[idx])
        rate_dict[dt] = rate_arr

    # For each date in spreads, find closest available optionm date
    optm_dates = sorted(rate_dict.keys())
    optm_ts = pd.DatetimeIndex(optm_dates)

    def nearest_optm(dt):
        idx = optm_ts.searchsorted(dt, side='left')
        if idx >= len(optm_ts):
            return optm_ts[-1]
        if idx == 0:
            return optm_ts[0]
        # pick the closer of idx-1 and idx
        d0, d1 = optm_ts[idx-1], optm_ts[idx]
        return d0 if abs((dt - d0).days) <= abs((dt - d1).days) else d1

    # 5Y spread lookup: pivot for hazard rate
    s5y = spreads_wide[spreads_wide['tenor'] == '5Y'][['month', 'ticker', 'parspread']].copy()
    s5y = s5y.rename(columns={'parspread': 's5y'})

    # Merge 5Y spread into all tenor rows
    df = spreads_wide.merge(s5y, on=['month', 'ticker'], how='left')

    # Drop rows without 5Y spread (can't compute hazard rate)
    df = df.dropna(subset=['s5y'])

    results = []
    # Precompute quarterly indices for each tenor
    tenor_qtrs = {t: np.arange(1, int(4 * TENOR_N[t]) + 1) for t in TENORS}
    qtrs_idx = {t: (tenor_qtrs[t] - 1) for t in TENORS}  # 0-based index into QTRS array

    for (month, tenor), grp in df.groupby(['month', 'tenor']):
        rate_dt = nearest_optm(month)
        r_arr = rate_dict[rate_dt]  # shape (42,) for 0.25..10.50

        N = TENOR_N[tenor]
        qidx = qtrs_idx[tenor]        # 0-based indices into r_arr for quarters 1..4N
        r_vals = r_arr[qidx]          # risk-free zero rates at j*0.25 for j=1..4N
        t_vals = QTRS[qidx]           # = 0.25, 0.50, ..., N*1.0

        # Hazard rate from 5Y spread (flat term structure assumption)
        s5y_vals = grp['s5y'].values
        lam = 4.0 * np.log1p(s5y_vals / (4.0 * RECOVERY))
        lam = np.maximum(lam, 0.0)   # floor at zero

        # RD = 0.25 * sum_j exp(-lam*j/4) * exp(-r_j * j/4)
        #    = 0.25 * sum_j exp(-lam*t_j) * exp(-r_j * t_j)
        # For each name (different lam), vectorised over j
        # lam: (n_names,)   t_vals, r_vals: (4N,)
        surv = np.exp(-np.outer(lam, t_vals))       # (n_names, 4N)
        disc = np.exp(-r_vals * t_vals)              # (4N,) same discount for all names
        rd = 0.25 * (surv * disc).sum(axis=1)        # (n_names,)

        grp_out = grp[['month', 'ticker', 'tenor', 'parspread']].copy()
        grp_out['RD'] = rd
        results.append(grp_out)

    rd_df = pd.concat(results, ignore_index=True)
    rd_df = rd_df[['month', 'ticker', 'tenor', 'RD']]
    rd_df.to_parquet(out, index=False)
    print(f'  Saved {out.name}  shape={rd_df.shape}')
    return rd_df


# ─── STEP 4: Compute contract returns ───────────────────────────────────────

def compute_contract_returns(spreads_wide, rd_df, force=False):
    """
    Monthly return for seller of protection:
        r_t = s_{t-1} / 12  +  (s_{t-1} - s_t) * RD_{t-1}

    Special case for the first month (Jan 2001): use the same date's spread
    as both prev and curr within the month (carry only, no capital gain).

    ds label = first day of the return-earning month.
    """
    out = WORKDIR / 'ftsfr_cds_contract_returns.parquet'
    if out.exists() and not force:
        print(f'  Loading cached {out.name}')
        return pd.read_parquet(out)

    print('  Computing contract returns ...')

    # Merge spreads and RD
    sp = spreads_wide.merge(rd_df, on=['month', 'ticker', 'tenor'], how='inner')
    sp = sp.sort_values(['ticker', 'tenor', 'month'])

    results = []
    for (ticker, tenor), grp in sp.groupby(['ticker', 'tenor']):
        grp = grp.sort_values('month').reset_index(drop=True)
        months = grp['month'].values
        spreads = grp['parspread'].values
        rds = grp['RD'].values

        # Consecutive-month pairs only
        for i in range(1, len(months)):
            # Check consecutive months (within 35 days)
            gap = (months[i] - months[i-1]).astype('timedelta64[D]').astype(int)
            if gap > 35:
                continue  # skip non-consecutive months

            s_prev = spreads[i-1]
            s_curr = spreads[i]
            rd_curr = rds[i]  # Palhares: use current-period RD (not lagged)

            carry = s_prev / 12.0
            cap_gain = (s_curr - s_prev) * rd_curr  # Palhares-HKM: carry + ΔS × RD_t
            ret = carry + cap_gain

            results.append({
                'ds': months[i],
                'unique_id': f'{ticker}_{tenor}',
                'y': ret
            })

        # First-month entry: carry only (use first available spread)
        # Only for January 2001 (the very start of the data)
        if len(grp) > 0 and grp['month'].iloc[0] == pd.Timestamp('2001-01-01'):
            s0 = spreads[0]
            rd0 = rds[0]
            carry0 = s0 / 12.0
            results.append({
                'ds': pd.Timestamp('2001-01-01'),
                'unique_id': f'{ticker}_{tenor}',
                'y': carry0
            })

    contract_ret = pd.DataFrame(results)
    contract_ret = contract_ret.sort_values(['unique_id', 'ds']).reset_index(drop=True)
    contract_ret['ds'] = pd.to_datetime(contract_ret['ds'])

    contract_ret.to_parquet(out, index=False)
    print(f'  Saved {out.name}  shape={contract_ret.shape}')
    return contract_ret


# ─── STEP 5: Compute portfolio returns ──────────────────────────────────────

def compute_portfolio_returns(spreads_wide, force=False):
    """
    20 portfolios: 4 tenors x 5 quintiles, sorted by 5Y spread at t-1.
    Portfolio return = equal-weight average of carry = s_N_{t-1} / 12.
    (Oracle validation shows portfolio returns are always positive = carry-only.)
    unique_id = '{tenor}_Q{k}', e.g. '5Y_Q3'
    """
    out = WORKDIR / 'ftsfr_cds_portfolio_returns.parquet'
    if out.exists() and not force:
        print(f'  Loading cached {out.name}')
        return pd.read_parquet(out)

    print('  Computing portfolio returns ...')

    # Build wide spread table: (month, ticker) -> {tenor: spread}
    sp_wide = spreads_wide.pivot_table(
        index=['month', 'ticker'], columns='tenor', values='parspread', aggfunc='first'
    ).reset_index()
    # Ensure all tenor columns exist
    for t in TENORS:
        if t not in sp_wide.columns:
            sp_wide[t] = np.nan

    all_months = sorted(spreads_wide['month'].unique())

    port_rows = []

    for i, ret_month in enumerate(all_months[1:], start=1):
        sort_month = all_months[i-1]

        # Spreads at sort_month (= t-1)
        sp_sort = sp_wide[sp_wide['month'] == sort_month].set_index('ticker')

        # Names with 5Y quote at sort_month (quintile sort universe)
        s5y_sort = sp_sort['5Y'].dropna()
        if len(s5y_sort) < 5:
            continue

        quintile = pd.qcut(s5y_sort, 5, labels=[1, 2, 3, 4, 5])

        for tenor in TENORS:
            # Carry for each name = s_N_{t-1} / 12
            tenor_carry = sp_sort[tenor].dropna() / 12.0
            # Only names that also have a 5Y quote (i.e. were assigned a quintile)
            tenor_carry = tenor_carry[tenor_carry.index.isin(quintile.index)]

            for q in range(1, 6):
                members = quintile[quintile == q].index
                grp_carry = tenor_carry[tenor_carry.index.isin(members)]
                if grp_carry.empty:
                    continue
                port_rows.append({
                    'ds': ret_month,
                    'unique_id': f'{tenor}_Q{q}',
                    'y': grp_carry.mean()
                })

    port_df = pd.DataFrame(port_rows, columns=['ds', 'unique_id', 'y'])
    port_df['ds'] = pd.to_datetime(port_df['ds'])
    port_df = port_df.sort_values(['unique_id', 'ds']).reset_index(drop=True)

    port_df.to_parquet(out, index=False)
    print(f'  Saved {out.name}  shape={port_df.shape}')
    return port_df


# ─── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    force = '--force' in sys.argv

    print('=== STEP 1: Markit spreads ===')
    spreads = pull_markit(force=force)
    print(f'  Spreads: {spreads.shape}  months={spreads["month"].nunique()}  tickers={spreads["ticker"].nunique()}')

    print('\n=== STEP 2: Optionmetrics rates ===')
    rates = pull_optionm(force=force)
    print(f'  Rates: {rates.shape}  dates={rates["date"].nunique()}')

    print('\n=== STEP 3: Risky durations ===')
    rd = compute_rd(spreads, rates, force=force)
    print(f'  RD: {rd.shape}')

    print('\n=== STEP 4: Contract returns ===')
    contract_ret = compute_contract_returns(spreads, rd, force=force)
    print(f'  Contract returns: {contract_ret.shape}  ids={contract_ret["unique_id"].nunique()}')

    print('\n=== STEP 5: Portfolio returns ===')
    port_ret = compute_portfolio_returns(spreads, force=force)
    print(f'  Portfolio returns: {port_ret.shape}  ids={port_ret["unique_id"].nunique()}')

    print('\n=== Done ===')
    print(f'  ftsfr_cds_contract_returns.parquet -> {(WORKDIR/"ftsfr_cds_contract_returns.parquet").stat().st_size//1024} KB')
    print(f'  ftsfr_cds_portfolio_returns.parquet -> {(WORKDIR/"ftsfr_cds_portfolio_returns.parquet").stat().st_size//1024} KB')
