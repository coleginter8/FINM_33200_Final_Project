"""Run all validation checks; write logs/validation_report.md."""
from __future__ import annotations

import sys

from hkm import validation
from hkm.io import get_logger

LOG = get_logger("99_validate")


def main() -> int:
    out = validation.run()
    LOG.info("Validation report: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
