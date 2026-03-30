# Data Storage Components (Python)

## Overview
The `storage/` directory governs connections across all distributed services to TimescaleDB, PostgreSQL, and Redis clusters.

## Responsibilities
- **Schema Management**: Holds all Python ORM models defining the layout of `system_metrics` (hypertables) and `agent_profiles` contexts.
- **Connection Pools**: Mediates robust Postgres read-replica connections.
- **Cache**: Manages fast access Redis implementations used internally for leader election, caching warm-up epochs, and temporary correlation buffers.
