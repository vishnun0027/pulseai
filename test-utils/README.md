# PulseAI Test Utilities

Testing and development tools for the PulseAI anomaly detection system.

## CPU Spike Generator

Generate controlled CPU spikes to test anomaly detection capabilities.

### Quick Start

```bash
# Basic spike (30s, 4 workers)
python test-utils/cpu_spike.py

# Custom duration and intensity
python test-utils/cpu_spike.py --duration 60 --intensity 8

# Single spike then exit
python test-utils/cpu_spike.py --spike-only
```

### How to Use for Testing

1. **Start the PulseAI stack:**
   ```bash
   docker compose up --build
   ```

2. **In another terminal, generate spikes:**
   ```bash
   python test-utils/cpu_spike.py --duration 30 --intensity 4
   ```

3. **Monitor detection in the dashboard:**
   - Navigate to http://localhost:8000
   - Watch for CPU anomaly alerts
   - Check the correlation engine and alerts logs

### Parameters

- `--duration`: How long to spike CPU (seconds). Default: 30
- `--intensity`: Number of worker processes. Default: 4 (adjust to match your CPU cores for realistic anomalies)
- `--spike-only`: Generate one spike and exit

### Expected Behavior

- The Rust agent will collect telemetry showing elevated CPU usage
- The Python AI consumer will detect the spike via IsolationForest
- The correlation engine will process the anomaly
- The alerts service will trigger notifications
- The dashboard will visualize the anomaly event

### Tips

- **For testing detection latency:** Use short spikes (10-15s) and watch how fast the system reacts
- **For testing recovery detection:** Use longer spikes (60s) and observe the anomaly resolution
- **For testing alert thresholds:** Adjust intensity to find the minimum spike that triggers detection
- **For stress testing:** Run multiple spikes back-to-back

### Performance Notes

- Each worker process uses ~1 CPU core
- Adjust `--intensity` to match available cores
- Leaving intensity too high may impact your system stability
