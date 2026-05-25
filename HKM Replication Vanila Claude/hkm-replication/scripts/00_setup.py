"""Verify WRDS + FRED access and directory layout."""
from __future__ import annotations

import sys

from hkm.io import ensure_wrds_pgpass, get_logger, paths

LOG = get_logger("setup")


def main() -> int:
    LOG.info("Project paths: %s", {k: str(v) for k, v in paths().items()})

    LOG.info("Checking WRDS pgpass / connection…")
    try:
        from hkm.io import wrds_connect
        with wrds_connect() as c:
            row = c.raw_sql("SELECT current_database() AS db, current_user AS usr")
            LOG.info("WRDS connection OK: %s", row.iloc[0].to_dict())
    except Exception as e:  # noqa: BLE001
        LOG.error("WRDS connection FAILED: %s", e)
        return 1

    LOG.info("Checking FRED via pandas-datareader…")
    try:
        from pandas_datareader import data as pdr
        s = pdr.DataReader("GDPC1", "fred", "2020-01-01", "2020-06-30")
        LOG.info("FRED OK: GDPC1 rows=%d", len(s))
    except Exception as e:  # noqa: BLE001
        LOG.warning("FRED pdr failed (%s) — will rely on CSV fallback at runtime", e)

    LOG.info("Setup OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
