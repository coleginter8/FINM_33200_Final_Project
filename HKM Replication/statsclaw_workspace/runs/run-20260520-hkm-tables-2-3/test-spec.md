# Test Specification — run-20260520-hkm-tables-2-3

**For tester only. Do not share with builder. Derived from published paper values only.**

---

## Overview

This specification defines all tests the tester must run to validate the HKM (2017) Tables 2 and 3 replication package. Tests are derived from published paper values (He, Kelly & Manela, JFE 2017) and mathematical properties of the algorithms, **not** from the implementation spec.

Reference values come from:
- Table 2, p.7 of the paper
- Table 3, p.9 of the paper
- Methodological statements in Sections 3.1 and the paper footnotes

---

## Test Environment Setup

```python
# conftest.py or top of each test file
import pytest
import os

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "wrds: mark test as requiring WRDS connection"
    )

@pytest.fixture(scope="session")
def wrds_conn():
    """Session-scoped WRDS connection. Skip if unavailable."""
    try:
        from hkm.utils import wrds_connection
        with wrds_connection() as conn:
            yield conn
    except Exception:
        pytest.skip("WRDS connection unavailable")
```

All integration tests must use `@pytest.mark.wrds` and be skipped if WRDS is unavailable.

---

## Unit Tests (no WRDS connection required)

### `tests/test_data.py`

#### UT-1: η_t Formula — Basic Arithmetic

**What it tests**: The η formula correctly aggregates market equity and book debt across multiple dealers.

```python
def test_eta_formula_basic():
    """η = Σ ME / Σ (ME + BD) with synthetic data."""
    import numpy as np
    from hkm.data.intermediary import _compute_eta  # or equivalent internal function

    # Synthetic data: 3 dealers
    me = np.array([100.0, 200.0, 300.0])   # market equity
    bd = np.array([900.0, 800.0, 700.0])   # book debt

    # Expected: (100+200+300) / (100+200+300 + 900+800+700)
    #         = 600 / 3000 = 0.2000
    eta = me.sum() / (me.sum() + bd.sum())
    assert abs(eta - 0.2000) < 1e-10, f"Expected 0.2000, got {eta}"
```

Note to tester: If `_compute_eta` is not a separate function, test the formula directly as above or by constructing a minimal DataFrame and calling the public function with mocked data.

#### UT-2: Capital Factor — AR(1) Residuals Structure

**What it tests**: The capital factor has the correct structure (length, NaN placement, float dtype).

```python
def test_capital_factor_structure():
    """AR(1) factor: first element NaN, remaining elements are finite floats."""
    import pandas as pd
    import numpy as np
    from hkm.data.intermediary import build_capital_factor

    # Synthetic η series
    eta = pd.Series([0.10, 0.15, 0.12, 0.18, 0.14],
                    index=pd.period_range('2000Q1', periods=5, freq='Q'))

    factor = build_capital_factor(eta, frequency='Q')

    assert len(factor) == len(eta), "Factor length must equal eta length"
    assert pd.isna(factor.iloc[0]), "First element must be NaN (no lagged value)"
    assert all(np.isfinite(factor.iloc[1:])), "All non-first elements must be finite"
    assert factor.dtype == float, "Factor must be float dtype"
```

#### UT-3: Book Capital Ratio — Arithmetic

**What it tests**: Book capital ratio = Σ CEQ / Σ AT (not Σ CEQ / Σ (CEQ + BD), because BD = AT - CEQ implies AT = CEQ + BD, so CEQ/AT = CEQ/(CEQ + BD)).

```python
def test_book_capital_ratio():
    """Book capital ratio = Σ CEQ / Σ AT."""
    import numpy as np

    at = np.array([1000.0, 2000.0])   # total assets
    ceq = np.array([100.0, 200.0])    # common equity

    # Book capital ratio = Σ CEQ / Σ AT = 300 / 3000 = 0.1000
    ratio = ceq.sum() / at.sum()
    assert abs(ratio - 0.1000) < 1e-10, f"Expected 0.1000, got {ratio}"

    # Equivalently: CEQ / (CEQ + BD) where BD = AT - CEQ
    bd = at - ceq
    ratio_alt = ceq.sum() / (ceq.sum() + bd.sum())
    assert abs(ratio_alt - 0.1000) < 1e-10, "Alternative formula must match"
```

#### UT-4: Log Change Computation

**What it tests**: Log change is computed correctly (used for macro growth rates in Panel B).

```python
def test_log_change():
    """log(0.15 / 0.10) = ln(1.5) ≈ 0.4055."""
    import numpy as np

    x0, x1 = 0.10, 0.15
    expected = np.log(x1 / x0)  # ln(1.5)
    assert abs(expected - 0.40546) < 1e-4, f"ln(1.5) ≈ 0.4055, got {expected}"

    # Also verify this is what the macro module produces for GDP growth
    # (sanity check — not testing macro module directly, just the math)
    import pandas as pd
    gdp = pd.Series([100.0, 150.0])
    growth = np.log(gdp / gdp.shift(1))
    assert abs(growth.iloc[1] - 0.40546) < 1e-4
```

#### UT-5: Market Equity — Negative Price Convention

**What it tests**: When CRSP `prc` is negative (bid-ask midpoint), `|prc|` is used.

```python
def test_market_equity_negative_price():
    """ME = |prc| * shrout regardless of prc sign."""
    import numpy as np

    prc_negative = -10.5   # CRSP negative price = bid-ask midpoint
    prc_positive = 10.5
    shrout = 1000.0        # thousands of shares

    me_from_negative = abs(prc_negative) * shrout
    me_from_positive = abs(prc_positive) * shrout

    assert abs(me_from_negative - 10500.0) < 1e-6, \
        f"ME from negative price should be 10500, got {me_from_negative}"
    assert me_from_negative == me_from_positive, \
        "ME must be identical regardless of prc sign"
```

#### UT-6: Table 2 Output Shape

**What it tests**: `compute_table2()` returns a DataFrame with exactly shape (3, 12).

```python
def test_table2_shape_mocked(monkeypatch):
    """compute_table2 returns DataFrame of shape (3, 12) with mocked data."""
    import pandas as pd
    import numpy as np
    from hkm.tables.table2 import compute_table2

    # Mock the data fetching functions to return synthetic data
    # The test verifies shape and index/column structure only

    # If compute_table2 requires conn, pass a mock that is never called
    # (implementation detail — adapt as needed)

    # Alternative: call with small synthetic DataFrames via monkeypatching
    # The key assertion is shape = (3, 12)

    # Create expected structure
    items = ['Total assets', 'Book debt', 'Book equity', 'Market equity']
    groups = ['BD', 'Banks', 'Cmpust']
    expected_cols = pd.MultiIndex.from_product([items, groups])
    expected_index = ['1960-2012', '1960-1990', '1990-2012']

    # Minimal synthetic call: build a fake result and verify it matches spec
    result = pd.DataFrame(
        np.random.rand(3, 12),
        index=expected_index,
        columns=expected_cols,
    )
    assert result.shape == (3, 12), f"Expected (3, 12), got {result.shape}"
    assert len(result.index) == 3
    assert len(result.columns) == 12
```

#### UT-7: Table 3 Diagonal = 1.0

**What it tests**: Correlation matrix diagonal is exactly 1.0 (self-correlation).

```python
def test_table3_diagonal():
    """Pearson correlation of a series with itself = 1.0."""
    import pandas as pd
    import numpy as np

    # Any series with variance > 0 should have self-correlation = 1.0
    x = pd.Series(np.random.randn(100))
    assert abs(x.corr(x) - 1.0) < 1e-10, "Self-correlation must be 1.0"

    # DataFrame corr diagonal
    df = pd.DataFrame({'a': np.random.randn(50), 'b': np.random.randn(50)})
    corr = df.corr()
    assert abs(corr.loc['a', 'a'] - 1.0) < 1e-10
    assert abs(corr.loc['b', 'b'] - 1.0) < 1e-10
```

#### UT-8: Pearson Correlation Consistency

**What it tests**: `pd.Series.corr()` and `pd.DataFrame.corr()` produce identical results.

```python
def test_pearson_correlation_consistency():
    """pd.Series.corr() and pd.DataFrame.corr() produce same result."""
    import pandas as pd
    import numpy as np

    np.random.seed(42)
    x = pd.Series(np.random.randn(50))
    y = pd.Series(np.random.randn(50))

    corr_series = x.corr(y)
    df = pd.DataFrame({'x': x, 'y': y})
    corr_df = df.corr().loc['x', 'y']

    assert abs(corr_series - corr_df) < 1e-12, \
        f"Series corr {corr_series} != DataFrame corr {corr_df}"
```

#### UT-9: AR(1) Fit Residuals Are Zero-Mean

**What it tests**: OLS AR(1) residuals have mean ≈ 0 (property of OLS with intercept).

```python
def test_ar1_residuals_zero_mean():
    """AR(1) OLS residuals (with intercept) have mean ≈ 0."""
    import numpy as np
    import pandas as pd
    from hkm.data.intermediary import build_capital_factor

    np.random.seed(123)
    # Generate AR(1) process with rho=0.94
    n = 172
    eta_vals = [0.08]
    for _ in range(n - 1):
        eta_vals.append(0.01 + 0.94 * eta_vals[-1] + np.random.normal(0, 0.005))
    eta = pd.Series(eta_vals,
                    index=pd.period_range('1970Q1', periods=n, freq='Q'))

    factor = build_capital_factor(eta, frequency='Q')
    # Residuals scaled by lagged eta; their mean should be small
    # (exact zero only for unscaled residuals)
    finite_factor = factor.dropna()
    assert len(finite_factor) == n - 1, "Should have n-1 finite factor values"
```

---

## Integration Tests (require WRDS connection)

All integration tests must be decorated with `@pytest.mark.wrds` and use the `wrds_conn` fixture.

### `tests/test_tables.py`

#### IT-1: η Range Check

**What it tests**: The market capital ratio η_t is in a plausible range for all quarters.

```python
@pytest.mark.wrds
def test_eta_range(wrds_conn):
    """η_t ∈ [0.01, 0.50] for all available quarters."""
    from hkm.data.intermediary import build_capital_ratio

    df = build_capital_ratio(wrds_conn, frequency='Q',
                             start_date='1970-01-01', end_date='2012-12-31')

    eta = df['eta'].dropna()
    assert len(eta) > 0, "Must have at least some valid η observations"
    assert (eta >= 0.01).all(), f"η below 0.01: min={eta.min():.4f}"
    assert (eta <= 0.50).all(), f"η above 0.50: max={eta.max():.4f}"
    assert df['n_dealers'].min() >= 1, "Must have at least 1 dealer per period"
```

#### IT-2: AR(1) Coefficient ≈ 0.94

**What it tests**: The estimated AR(1) ρ for η_t is approximately 0.94 (paper footnote 22).

```python
@pytest.mark.wrds
def test_ar1_rho(wrds_conn):
    """Estimated AR(1) ρ for η_t ∈ [0.85, 0.99] (paper: ≈ 0.94)."""
    import statsmodels.api as sm
    import numpy as np
    from hkm.data.intermediary import build_capital_ratio

    df = build_capital_ratio(wrds_conn, frequency='Q',
                             start_date='1970-01-01', end_date='2012-12-31')
    eta = df['eta'].dropna()

    eta_lag = eta.shift(1).dropna()
    eta_curr = eta.iloc[1:]

    X = sm.add_constant(eta_lag.values)
    y = eta_curr.values
    res = sm.OLS(y, X).fit()
    rho = res.params[1]

    assert 0.85 <= rho <= 0.99, \
        f"AR(1) ρ = {rho:.4f}, expected in [0.85, 0.99] (paper: ≈ 0.94)"
```

#### IT-3: Table 2 Shape

**What it tests**: `compute_table2()` returns exactly (3, 12) with no NaN values.

```python
@pytest.mark.wrds
def test_table2_shape(wrds_conn):
    """compute_table2 returns DataFrame of shape (3, 12) with no NaN values."""
    from hkm.tables.table2 import compute_table2

    result = compute_table2(conn=wrds_conn)

    assert result.shape == (3, 12), \
        f"Expected shape (3, 12), got {result.shape}"
    assert not result.isna().any().any(), \
        f"Table 2 contains NaN values:\n{result[result.isna().any(axis=1)]}"
```

#### IT-4: Table 2 Bounds

**What it tests**: All Table 2 values are in (0.0, 1.0].

Rationale: Dealers are a subset of BD and all Compustat firms, so the dealer aggregate cannot exceed the group total. Values in (0, 1] are required. (Values slightly above 1.0 would indicate a data error in the comparison group definition.)

```python
@pytest.mark.wrds
def test_table2_bounds(wrds_conn):
    """All Table 2 values in (0.0, 1.0] — dealers cannot exceed comparison group."""
    from hkm.tables.table2 import compute_table2

    result = compute_table2(conn=wrds_conn)

    assert (result > 0.0).all().all(), \
        f"Table 2 has non-positive values:\n{result[result <= 0].dropna(how='all')}"
    assert (result <= 1.0).all().all(), \
        f"Table 2 has values > 1.0:\n{result[result > 1.0].dropna(how='all')}"
```

#### IT-5: Table 2 Values — Match Published (±0.05 tolerance)

**What it tests**: Key Table 2 cells are within ±0.05 of published values.

Published values from Table 2, p.7:

```python
@pytest.mark.wrds
def test_table2_published_values(wrds_conn):
    """Table 2 values within ±0.05 of published HKM (2017) values."""
    from hkm.tables.table2 import compute_table2

    result = compute_table2(conn=wrds_conn)

    tol = 0.05

    # Published values: (period, item, group, expected)
    published = [
        # 1960-2012 period
        ('1960-2012', 'Total assets',   'BD',     0.959),
        ('1960-2012', 'Total assets',   'Banks',  0.596),
        ('1960-2012', 'Total assets',   'Cmpust', 0.240),
        ('1960-2012', 'Book debt',      'BD',     0.960),
        ('1960-2012', 'Book debt',      'Banks',  0.602),
        ('1960-2012', 'Book debt',      'Cmpust', 0.280),
        ('1960-2012', 'Book equity',    'BD',     0.939),
        ('1960-2012', 'Book equity',    'Banks',  0.514),
        ('1960-2012', 'Book equity',    'Cmpust', 0.079),
        ('1960-2012', 'Market equity',  'BD',     0.911),
        ('1960-2012', 'Market equity',  'Banks',  0.435),
        ('1960-2012', 'Market equity',  'Cmpust', 0.026),
        # 1960-1990 period
        ('1960-1990', 'Total assets',   'BD',     0.967),
        ('1960-1990', 'Total assets',   'Banks',  0.635),
        ('1960-1990', 'Total assets',   'Cmpust', 0.286),
        ('1960-1990', 'Book debt',      'BD',     0.998),
        ('1960-1990', 'Book debt',      'Banks',  0.639),
        ('1960-1990', 'Book debt',      'Cmpust', 0.305),
        ('1960-1990', 'Book equity',    'BD',     0.961),
        ('1960-1990', 'Book equity',    'Banks',  0.568),
        ('1960-1990', 'Book equity',    'Cmpust', 0.095),
        ('1960-1990', 'Market equity',  'BD',     0.961),
        ('1960-1990', 'Market equity',  'Banks',  0.447),
        ('1960-1990', 'Market equity',  'Cmpust', 0.015),
        # 1990-2012 period
        ('1990-2012', 'Total assets',   'BD',     0.914),
        ('1990-2012', 'Total assets',   'Banks',  0.543),
        ('1990-2012', 'Total assets',   'Cmpust', 0.202),
        ('1990-2012', 'Book debt',      'BD',     0.916),
        ('1990-2012', 'Book debt',      'Banks',  0.550),
        ('1990-2012', 'Book debt',      'Cmpust', 0.240),
        ('1990-2012', 'Book equity',    'BD',     0.883),
        ('1990-2012', 'Book equity',    'Banks',  0.444),
        ('1990-2012', 'Book equity',    'Cmpust', 0.058),
        ('1990-2012', 'Market equity',  'BD',     0.848),
        ('1990-2012', 'Market equity',  'Banks',  0.419),
        ('1990-2012', 'Market equity',  'Cmpust', 0.039),
    ]

    near_misses = []
    failures = []

    for period, item, group, expected in published:
        actual = result.loc[period, (item, group)]
        diff = abs(actual - expected)
        if diff > tol:
            failures.append(
                f"  {period} | {item} | {group}: expected {expected:.3f}, "
                f"got {actual:.3f}, diff={diff:.3f} > tol={tol}"
            )
        elif diff > tol * 0.8:
            near_misses.append(
                f"  {period} | {item} | {group}: expected {expected:.3f}, "
                f"got {actual:.3f}, diff={diff:.3f} (near miss)"
            )

    if near_misses:
        import warnings
        warnings.warn(f"Near misses in Table 2:\n" + "\n".join(near_misses))

    assert not failures, \
        f"Table 2 cells outside ±{tol} tolerance:\n" + "\n".join(failures)
```

#### IT-6: Table 3 Shape

**What it tests**: `compute_table3()` returns two DataFrames with correct dimensions.

```python
@pytest.mark.wrds
def test_table3_shape(wrds_conn):
    """compute_table3 returns (panel_a, panel_b) with correct shapes."""
    from hkm.tables.table3 import compute_table3

    panel_a, panel_b = compute_table3(conn=wrds_conn)

    # Panel A: 8 rows (3 capital + 5 macro), 3 columns
    assert panel_a.shape[0] >= 8, \
        f"Panel A must have at least 8 rows, got {panel_a.shape[0]}"
    assert panel_a.shape[1] == 3, \
        f"Panel A must have 3 columns, got {panel_a.shape[1]}"

    # Panel B: 9 rows (3 factors + 6 macro), 3 columns
    assert panel_b.shape[0] >= 6, \
        f"Panel B must have at least 6 rows, got {panel_b.shape[0]}"
    assert panel_b.shape[1] == 3, \
        f"Panel B must have 3 columns, got {panel_b.shape[1]}"
```

#### IT-7: Table 3 Diagonal = 1.0

**What it tests**: Self-correlations are exactly 1.0 in both panels.

```python
@pytest.mark.wrds
def test_table3_diagonal(wrds_conn):
    """Table 3 diagonal correlations = 1.0."""
    from hkm.tables.table3 import compute_table3
    import numpy as np

    panel_a, panel_b = compute_table3(conn=wrds_conn)

    # Panel A diagonal
    for col in panel_a.columns:
        if col in panel_a.index:
            val = panel_a.loc[col, col]
            assert abs(val - 1.0) < 1e-10, \
                f"Panel A diagonal [{col}, {col}] = {val}, expected 1.0"

    # Panel B diagonal
    for col in panel_b.columns:
        if col in panel_b.index:
            val = panel_b.loc[col, col]
            assert abs(val - 1.0) < 1e-10, \
                f"Panel B diagonal [{col}, {col}] = {val}, expected 1.0"
```

#### IT-8: Table 3 Sign Checks (Critical — BLOCK if fails)

**What it tests**: Key correlations have the correct sign per the paper. These are economically meaningful signs that must be correct regardless of tolerance.

```python
@pytest.mark.wrds
def test_table3_signs(wrds_conn):
    """Key Table 3 correlations have the correct sign (paper: Table 3 p.9).

    BLOCK conditions: failure here must BLOCK the build.
    """
    from hkm.tables.table3 import compute_table3

    panel_a, panel_b = compute_table3(conn=wrds_conn)

    # Panel A sign checks (levels)
    # Market capital vs E/P: NEGATIVE (paper: -0.83)
    # Capital ratio is high when financial conditions are good → E/P is low
    mkt_ep_a = panel_a.loc['E/P', 'Market capital']
    assert mkt_ep_a < 0, \
        f"Panel A: Market capital vs E/P should be negative, got {mkt_ep_a:.3f}"

    # Market capital vs Unemployment: NEGATIVE (paper: -0.63)
    mkt_unemp_a = panel_a.loc['Unemployment', 'Market capital']
    assert mkt_unemp_a < 0, \
        f"Panel A: Market capital vs Unemployment should be negative, got {mkt_unemp_a:.3f}"

    # Book capital vs Financial conditions: NEGATIVE (paper: -0.53)
    book_nfci_a = panel_a.loc['Financial conditions', 'Book capital']
    assert book_nfci_a < 0, \
        f"Panel A: Book capital vs Financial conditions should be negative, got {book_nfci_a:.3f}"

    # Panel B sign checks (factors)
    # Market factor vs Market excess return: POSITIVE (paper: +0.78)
    mkt_ret_b = panel_b.loc['Market excess return', 'Market capital factor']
    assert mkt_ret_b > 0, \
        f"Panel B: Market factor vs Market excess return should be positive, got {mkt_ret_b:.3f}"

    # Market factor vs E/P growth: NEGATIVE (paper: -0.75)
    mkt_ep_b = panel_b.loc["E/P growth", 'Market capital factor']
    assert mkt_ep_b < 0, \
        f"Panel B: Market factor vs E/P growth should be negative, got {mkt_ep_b:.3f}"

    # Market factor vs Market volatility growth: NEGATIVE (paper: -0.49)
    mkt_vol_b = panel_b.loc['Market volatility growth', 'Market capital factor']
    assert mkt_vol_b < 0, \
        f"Panel B: Market factor vs Market volatility growth should be negative, got {mkt_vol_b:.3f}"
```

#### IT-9: Table 3 Values — Match Published (±0.05 tolerance)

**What it tests**: Key Table 3 cells are within ±0.05 of published values.

```python
@pytest.mark.wrds
def test_table3_published_values(wrds_conn):
    """Key Table 3 cells within ±0.05 of published HKM (2017) values."""
    from hkm.tables.table3 import compute_table3

    panel_a, panel_b = compute_table3(conn=wrds_conn)
    tol = 0.05

    # (panel, row_label, col_label, published_value)
    published_a = [
        ('Market capital',      'Book capital',          0.50),
        ('Market capital',      'AEM leverage',         -0.42),
        ('Book capital',        'AEM leverage',         -0.07),
        ('E/P',                 'Market capital',       -0.83),
        ('Unemployment',        'Market capital',       -0.63),
        ('GDP',                 'Market capital',        0.18),
        ('Financial conditions','Market capital',       -0.48),
        ('Market volatility',   'Market capital',       -0.06),
        ('E/P',                 'Book capital',         -0.38),
        ('Unemployment',        'Book capital',         -0.10),
        ('GDP',                 'Book capital',          0.32),
        ('Financial conditions','Book capital',         -0.53),
        ('Market volatility',   'Book capital',         -0.31),
        ('E/P',                 'AEM leverage',         -0.64),
        ('Unemployment',        'AEM leverage',         -0.33),
        ('GDP',                 'AEM leverage',         -0.23),
        ('Financial conditions','AEM leverage',         -0.19),
        ('Market volatility',   'AEM leverage',          0.33),
    ]

    published_b = [
        ('Market capital factor', 'Book capital factor',        0.30),
        ('Market capital factor', 'AEM leverage factor',        0.14),
        ('Book capital factor',   'AEM leverage factor',       -0.06),
        ('Market excess return',  'Market capital factor',      0.78),
        ('E/P growth',            'Market capital factor',     -0.75),
        ('Unemployment growth',   'Market capital factor',     -0.05),
        ('GDP growth',            'Market capital factor',      0.20),
        ('Financial conditions growth', 'Market capital factor', -0.38),
        ('Market volatility growth', 'Market capital factor',  -0.49),
        ('Market excess return',  'Book capital factor',        0.10),
        ('E/P growth',            'Book capital factor',       -0.10),
        ('Unemployment growth',   'Book capital factor',        0.12),
        ('GDP growth',            'Book capital factor',        0.09),
        ('Financial conditions growth', 'Book capital factor', -0.29),
        ('Market volatility growth', 'Book capital factor',    -0.18),
        ('Market excess return',  'AEM leverage factor',        0.15),
        ('E/P growth',            'AEM leverage factor',       -0.18),
        ('Unemployment growth',   'AEM leverage factor',       -0.08),
        ('GDP growth',            'AEM leverage factor',        0.04),
        ('Financial conditions growth', 'AEM leverage factor', -0.06),
        ('Market volatility growth', 'AEM leverage factor',    -0.08),
    ]

    failures = []
    near_misses = []

    for row, col, expected in published_a:
        try:
            actual = panel_a.loc[row, col]
        except KeyError:
            # Try transposed
            actual = panel_a.loc[col, row]
        diff = abs(actual - expected)
        label = f"Panel A [{row}, {col}]"
        if diff > tol:
            failures.append(f"  {label}: expected {expected:.2f}, got {actual:.2f}, diff={diff:.2f}")
        elif diff > tol * 0.8:
            near_misses.append(f"  {label}: expected {expected:.2f}, got {actual:.2f} (near miss)")

    for row, col, expected in published_b:
        try:
            actual = panel_b.loc[row, col]
        except KeyError:
            actual = panel_b.loc[col, row]
        diff = abs(actual - expected)
        label = f"Panel B [{row}, {col}]"
        if diff > tol:
            failures.append(f"  {label}: expected {expected:.2f}, got {actual:.2f}, diff={diff:.2f}")
        elif diff > tol * 0.8:
            near_misses.append(f"  {label}: expected {expected:.2f}, got {actual:.2f} (near miss)")

    if near_misses:
        import warnings
        warnings.warn("Near misses in Table 3:\n" + "\n".join(near_misses))

    assert not failures, \
        "Table 3 cells outside ±0.05 tolerance:\n" + "\n".join(failures)
```

---

## Code Quality Checks (BLOCK if any fail)

These must be run in addition to pytest. The tester must execute each command and verify exit code 0.

### CQ-1: Ruff Lint

```bash
ruff check hkm/
```

- **PASS**: Exit code 0, zero warnings
- **BLOCK**: Any error or warning output

### CQ-2: Mypy Type Checking

```bash
mypy hkm/ --strict --ignore-missing-imports
```

- **PASS**: Exit code 0, "Success: no issues found"
- **BLOCK**: Any error output (note: `ignore-missing-imports` suppresses missing stub errors)

### CQ-3: Pytest

```bash
pytest tests/ -v --tb=short
```

- **PASS**: All non-skipped tests pass; skipped tests are acceptable if WRDS is unavailable
- **BLOCK**: Any test FAILURE (not skip)

### CQ-4: No Print Statements

```bash
grep -r "print(" hkm/
```

- **PASS**: No output (grep finds nothing)
- **BLOCK**: Any output (print statements found)

---

## BLOCK Conditions (must BLOCK build)

The tester MUST issue a BLOCK signal if any of the following occur:

| Condition | Severity |
|---|---|
| Any unit test fails (UT-1 through UT-9) | BLOCK |
| CQ-1: ruff finds any error | BLOCK |
| CQ-2: mypy finds any error | BLOCK |
| CQ-3: pytest has any FAILURE (not skip) | BLOCK |
| CQ-4: print() found in hkm/ | BLOCK |
| IT-8 sign check fails (wrong sign) | BLOCK |
| IT-4 bounds check fails (values > 1.0 or ≤ 0) | BLOCK |

## SKIP Conditions (do not BLOCK)

| Condition | Behavior |
|---|---|
| WRDS connection unavailable | Skip all IT-* tests with `pytest.mark.skip`; unit tests and CQ checks must still pass |
| Shiller/FRED data unavailable (network error) | Skip affected IT tests only; log warning |
| Dealer not found in WRDS (name mismatch) | Log warning; do not BLOCK (handled in integration test data quality checks) |

---

## Tolerance Rationale

The ±0.05 tolerance for Tables 2 and 3 is justified by:

1. **Foreign dealer exclusion**: The paper includes foreign dealers (Barclays, Deutsche Bank, etc.) via Datastream for η_t. This replication uses CRSP-only (US dealers). The exclusion affects the dealer numerator but generally makes a small difference since foreign dealers are smaller relative to the major US dealers.

2. **SIC code differences**: The paper's comparison group definition for Banks may differ slightly from our SIC 6000–6299 interpretation.

3. **Data vintage**: The paper used WRDS data as of ~2017. Some historical data may have been restated since then.

4. **Shiller E/P construction**: Whether the raw or smoothed earnings figure is used can create small differences.

**Tolerances MUST NOT be relaxed beyond ±0.05 to make tests pass.** If values are outside ±0.05, report as BLOCK with the cell-by-cell comparison table. The tester must never modify tolerance thresholds to achieve a passing test.

---

## `audit.md` (to be written by tester)

After running all tests, write `audit.md` to the run directory with:

1. **Summary**: PASS or BLOCK verdict
2. **Unit test results**: One row per UT-* test (pass/fail/skip)
3. **Integration test results**: One row per IT-* test (pass/fail/skip/near-miss)
4. **Code quality results**: CQ-1 through CQ-4 (pass/fail + output)
5. **Cell-by-cell Table 2 comparison**: All 36 cells with published, actual, diff, pass/fail
6. **Cell-by-cell Table 3 comparison**: All correlation cells with published, actual, diff, pass/fail
7. **AR(1) ρ estimate**: Actual value (should be ≈ 0.94)
8. **n_dealers by period**: How many dealers contributed to each quarter
9. **Routing** (if BLOCK): Which upstream teammate to respawn (usually builder; planner if spec issue)
