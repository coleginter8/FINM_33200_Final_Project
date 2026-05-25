"""Generate tables/table_3.csv and tables/table_3.tex."""
from __future__ import annotations

import sys

from hkm import table3
from hkm.io import get_logger

LOG = get_logger("05_table3")


def main() -> int:
    d = table3.build()
    LOG.info("Table 3 rows: %d", len(d["df"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
