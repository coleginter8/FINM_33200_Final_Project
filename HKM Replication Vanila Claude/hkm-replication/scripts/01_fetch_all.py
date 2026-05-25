"""Fetch all external data: NY Fed, FRED, Ken French, Shiller, Zhiguo He, WRDS."""
from __future__ import annotations

import sys
import traceback

from hkm import fetch_ff, fetch_fred, fetch_nyfed, fetch_shiller, fetch_wrds, fetch_zhiguohe
from hkm.io import get_logger

LOG = get_logger("fetch_all")


def _try(label: str, fn):
    LOG.info("=== %s ===", label)
    try:
        fn()
        LOG.info("%s OK", label)
    except Exception as e:  # noqa: BLE001
        LOG.error("%s FAILED: %s\n%s", label, e, traceback.format_exc())


def main() -> int:
    _try("NY Fed PD list", fetch_nyfed.fetch)
    _try("FRED", fetch_fred.fetch_all)
    _try("Ken French", fetch_ff.fetch)
    _try("Shiller", fetch_shiller.fetch)
    _try("Zhiguo He bundled", fetch_zhiguohe.fetch)
    _try("WRDS pulls (msenames, msf, fundq, ccm, dsfvw)", fetch_wrds.pull_all)
    return 0


if __name__ == "__main__":
    sys.exit(main())
