"""Shared IO: project paths, settings, logging, .env / WRDS pgpass setup."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib  # py3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_settings() -> dict[str, Any]:
    cfg = PROJECT_ROOT / "config" / "settings.toml"
    with open(cfg, "rb") as fh:
        return tomllib.load(fh)


def load_env() -> None:
    """Load .env (idempotent)."""
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def paths() -> dict[str, Path]:
    s = load_settings()
    out = {k: (PROJECT_ROOT / v) for k, v in s["paths"].items()}
    for p in out.values():
        p.mkdir(parents=True, exist_ok=True)
    return out


def raw(subdir: str) -> Path:
    p = paths()["data_raw"] / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p


def processed() -> Path:
    return paths()["data_processed"]


def tables_dir() -> Path:
    return paths()["tables"]


def logs_dir() -> Path:
    return paths()["logs"]


def get_logger(name: str, *, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)s | %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    fh = logging.FileHandler(logs_dir() / f"{name}.log", mode="a")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.propagate = False
    return logger


def ensure_wrds_pgpass() -> str:
    """Create ~/.pgpass from .env credentials so wrds.Connection() doesn't prompt.

    Returns the WRDS username so callers can pass it explicitly to wrds.Connection.
    """
    load_env()
    user = os.environ.get("WRDS_USERNAME")
    pw = os.environ.get("WRDS_PASSWORD")
    if not user or not pw:
        raise RuntimeError(
            "WRDS_USERNAME / WRDS_PASSWORD not in environment. Check .env."
        )
    s = load_settings()["wrds"]
    host, port, db = s["host"], s["port"], s["db"]
    pgpass = Path.home() / ".pgpass"
    line = f"{host}:{port}:{db}:{user}:{pw}\n"
    existing = pgpass.read_text() if pgpass.exists() else ""
    needle = f"{host}:{port}:{db}:{user}:"
    if not any(ln.startswith(needle) for ln in existing.splitlines()):
        with open(pgpass, "a") as fh:
            fh.write(line)
    os.chmod(pgpass, 0o600)
    return user


def wrds_connect():
    """Open a WRDS connection without interactive prompts.

    Reads credentials from .env, materializes ~/.pgpass, sets PG* env vars so
    psycopg2 picks up the password, then calls wrds.Connection. This avoids
    the interactive 'enter username' prompt.
    """
    import wrds
    user = ensure_wrds_pgpass()
    pw = os.environ["WRDS_PASSWORD"]
    # psycopg2 reads PGPASSWORD if no password is passed; this lets wrds.Connection
    # — which never threads our password through — still authenticate non-interactively.
    os.environ["PGPASSWORD"] = pw
    os.environ["PGUSER"] = user
    return wrds.Connection(wrds_username=user, wrds_password=pw)
