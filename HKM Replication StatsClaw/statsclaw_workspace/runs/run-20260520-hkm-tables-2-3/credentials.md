# Credentials — run-20260520-hkm-tables-2-3

## GitHub (target repo)

- **Repo**: coleginter8/hkm-replication
- **Method**: gh-cli (keyring)
- **User**: coleginter8
- **Push dry-run**: PASS (Everything up-to-date — local at 9871b28 matches remote)
- **Verified**: 2026-05-20

## GitHub (workspace repo)

- **Repo**: coleginter8/workspace
- **Status**: PASS — cloned to .repos/workspace/, git status clean

## WRDS PostgreSQL

- **Host**: wrds-pgdata.wharton.upenn.edu
- **Port**: 9737
- **Database**: wrds
- **Username**: coleginter
- **Credential file**: ~/.pgpass (present)
- **Status**: PRESENT — not live-tested here; builder will verify connection at runtime

## Summary

| System | Status |
|---|---|
| GitHub target repo | PASS |
| GitHub workspace repo | PASS |
| WRDS credentials | PRESENT (file exists) |
