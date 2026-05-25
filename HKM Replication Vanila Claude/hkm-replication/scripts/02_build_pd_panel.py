"""Build the PD-to-PERMNO map and the firm × month panel."""
from __future__ import annotations

import sys

from hkm import build_pd_panel, map_pd
from hkm.io import get_logger

LOG = get_logger("02_build_pd_panel")


def main() -> int:
    LOG.info("=== Building PD-to-PERMNO map ===")
    map_pd.build_map()
    LOG.info("=== Building firm panel ===")
    build_pd_panel.build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
