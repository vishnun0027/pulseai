# Correlation Engine (Go)

## Overview
The `correlation/` engine runs continuously behind the scenes pulling from the centralized message queues to detect inter-machine telemetry relationships in specific time intervals.

## Responsibilities
- **Event Correlating**: Aggregates event windows (e.g., analyzing packets over a 30-second rolling interval).
- **Cross-Boundary Analysis**: Relates spikes across different environments (e.g., a CPU spike in the WSL environment tied logically to a network spike on the native Host layer).
- **Threat Detection**: Flags advanced lateral traversal possibilities (container anomaly correlating with host memory expansion).
