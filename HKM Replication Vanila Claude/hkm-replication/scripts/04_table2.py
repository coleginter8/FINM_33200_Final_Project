"""Generate tables/table_2.csv and tables/table_2.tex."""
from __future__ import annotations

import sys

from hkm import table2
from hkm.io import get_logger

LOG = get_logger("04_table2")


def main() -> int:
    out = table2.build()
    LOG.info("Table 2:\n%s", out.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
