-- ════════════════════════════════════════════════════════════════════════════
-- TimescaleDB post-migration setup.
--
-- Run this script AFTER Alembic creates the tables on a TimescaleDB instance.
-- This is NOT part of the Alembic migration because TimescaleDB extensions
-- require a live TimescaleDB instance and cannot be emulated in SQLite tests.
--
-- Execute with:
--   psql $DATABASE_URL -f infra/docker/setup-timescaledb.sql
-- ════════════════════════════════════════════════════════════════════════════

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ─── Convert ohlcv to a hypertable ───────────────────────────────────────────
-- Partition by time with 1-day chunks — optimal for minute-bar queries.
SELECT create_hypertable(
    'ohlcv',
    'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- ─── Convert ticks to a hypertable ───────────────────────────────────────────
-- Partition by time with 1-hour chunks — tick data is high-frequency.
SELECT create_hypertable(
    'ticks',
    'time',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ─── TimescaleDB compression (enable after data flows in) ────────────────────
-- Compress chunks older than 7 days to save disk space.
-- Uncomment and run after initial data has been loaded.
--
-- ALTER TABLE ohlcv SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'symbol, timeframe'
-- );
-- SELECT add_compression_policy('ohlcv', INTERVAL '7 days');
--
-- ALTER TABLE ticks SET (
--     timescaledb.compress,
--     timescaledb.compress_segmentby = 'symbol'
-- );
-- SELECT add_compression_policy('ticks', INTERVAL '1 day');

-- ─── Continuous aggregate: daily OHLCV from 1-minute bars ────────────────────
-- Auto-refreshes as new 1m bars are inserted.
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_daily
    WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    symbol,
    first(open, time)           AS open,
    max(high)                   AS high,
    min(low)                    AS low,
    last(close, time)           AS close,
    sum(volume)                 AS volume,
    sum(volume * vwap) / NULLIF(sum(volume), 0) AS vwap
FROM ohlcv
WHERE timeframe = '1m'
GROUP BY bucket, symbol
WITH NO DATA;

-- Refresh policy: keep the aggregate up to date, lag 1 hour to avoid hot chunks.
SELECT add_continuous_aggregate_policy(
    'ohlcv_daily',
    start_offset    => INTERVAL '7 days',
    end_offset      => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists   => TRUE
);

-- ─── Retention policy: drop raw tick data older than 90 days ─────────────────
-- Retain OHLCV bars indefinitely; ticks are high-volume and rarely needed old.
-- Uncomment when ready to enable.
-- SELECT add_retention_policy('ticks', INTERVAL '90 days', if_not_exists => TRUE);
