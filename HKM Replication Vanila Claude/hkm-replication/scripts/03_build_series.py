"""Build capital ratios, AEM leverage, innovation factors, and macro panel."""
from __future__ import annotations

import sys

from hkm import build_aem_leverage, build_capital_ratios, build_factors, build_macro_panel
from hkm.io import get_logger

LOG = get_logger("03_build_series")


def main() -> int:
    LOG.info("Capital ratios")
    build_capital_ratios.build()
    LOG.info("AEM leverage / implied capital / factor")
    build_aem_leverage.build()
    LOG.info("Innovation factors")
    build_factors.build()
    LOG.info("Macro panel")
    build_macro_panel.build()
    return 0


if __name__ == "__main__":
    sys.exit(main())
