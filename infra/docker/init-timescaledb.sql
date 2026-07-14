-- TimescaleDB initialization: run after alembic creates the tables
-- This script is mounted as a Docker entrypoint initdb script.

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;
