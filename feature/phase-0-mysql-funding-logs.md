# Phase 0 - MySQL Funding Logs

Date: 2026-04-10
Status: Implemented

## Objective

Persist forecast-passed symbols into MySQL for later analysis and audit.

## Scope

- Insert 1 row per passed symbol into `funding_logs`
- Insert on every run cycle when symbol passes forecast gate
- Store fields: `timestamp`, `symbol`, `current`, `next`, `delta`, `r2`

## Implementation

- Added MySQL logger module: `src/internal/mysql_logger.py`
- Added env configs in `.env` for MySQL connection
- Hooked DB insert in `cmd/main.py` right after forecast evaluation
- Keeps Telegram cooldown behavior unchanged (DB logging is independent)

## Env Keys

- `MYSQL_ENABLED`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `MYSQL_TABLE_FUNDING_LOGS`

## Notes

- `MYSQL_ENABLED=false` by default (safe for local)
- If enabled but credentials are missing, system logs a warning and skips DB insert
