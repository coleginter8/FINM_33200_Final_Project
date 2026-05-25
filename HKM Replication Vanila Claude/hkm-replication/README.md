# HKM 2017 Replication — Tables 2 & 3

Replicates Tables 2 and 3 of He, Kelly, and Manela (2017), *Intermediary Asset
Pricing: New Evidence from Many Asset Classes*, JFE 126(1).

See `PLAN.md` for the full design. Outputs land in `tables/` and a validation
report in `logs/validation_report.md`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
# WRDS_USERNAME and WRDS_PASSWORD must be in .env
```

## Run end-to-end

```bash
source .venv/bin/activate
python scripts/00_setup.py
python scripts/01_fetch_all.py
python scripts/02_build_pd_panel.py
python scripts/03_build_series.py
python scripts/04_table2.py
python scripts/05_table3.py
python scripts/99_validate.py
```

## Scope caveats

- US-only primary dealers (no Datastream → foreign parents excluded).
- Table 2 should match published values closely; Table 3 will diverge in
  magnitude (not sign) for cells involving the market/book capital ratio.
- FRED accessed via `pandas-datareader` (no API key).
