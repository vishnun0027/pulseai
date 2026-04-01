#!/usr/bin/env python3
"""
CPU spike generator for testing PulseAI anomaly detection.

Usage:
    python cpu_spike.py --duration 30 --intensity 4
    
This will spike CPU usage for 30 seconds using 4 worker threads.
"""

import argparse
import time
import multiprocessing
import sys
from datetime import datetime


def cpu_intensive_worker(duration: float, worker_id: int):
    """Run CPU-intensive operations to spike usage."""
    start_time = time.time()
    iterations = 0
    
    print(f"[Worker {worker_id}] Starting CPU spike for {duration}s", flush=True)
    
    while time.time() - start_time < duration:
        # Compute-heavy operations
        result = 0
        for i in range(1000000):
            result += i ** 2 + i // 2
        iterations += 1
    
    elapsed = time.time() - start_time
    print(f"[Worker {worker_id}] Completed {iterations} iterations in {elapsed:.2f}s", flush=True)


def spike_cpu(duration: float = 30, intensity: int = 4, spike_only: bool = False):
    """
    Generate a CPU spike for testing anomaly detection.
    
    Args:
        duration: How long to spike CPU (seconds)
        intensity: Number of worker processes (roughly correlates to CPU cores)
        spike_only: If True, only spike once and exit. If False, repeat spike.
    """
    print(f"\n{'='*60}")
    print(f"PulseAI CPU Spike Generator")
    print(f"{'='*60}")
    print(f"Duration per spike: {duration}s")
    print(f"Worker threads: {intensity}")
    print(f"Start time: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")
    
    try:
        processes = []
        for i in range(intensity):
            p = multiprocessing.Process(target=cpu_intensive_worker, args=(duration, i))
            p.start()
            processes.append(p)
        
        # Wait for all workers to complete
        for p in processes:
            p.join()
        
        print(f"\n✓ CPU spike completed at {datetime.now().isoformat()}")
        print("The anomaly detection system should have detected this spike.\n")
        
        if not spike_only:
            print("Run again to generate another spike, or use --spike-only to exit.")
            
    except KeyboardInterrupt:
        print("\n\n✗ CPU spike interrupted by user")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join()
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Generate CPU spikes to test PulseAI anomaly detection"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=30,
        help="Duration of CPU spike in seconds (default: 30)",
    )
    parser.add_argument(
        "--intensity",
        type=int,
        default=4,
        help="Number of worker processes (default: 4)",
    )
    parser.add_argument(
        "--spike-only",
        action="store_true",
        help="Generate one spike and exit (default: ready for repeated spikes)",
    )
    
    args = parser.parse_args()
    
    spike_cpu(
        duration=args.duration,
        intensity=args.intensity,
        spike_only=args.spike_only,
    )


if __name__ == "__main__":
    main()
