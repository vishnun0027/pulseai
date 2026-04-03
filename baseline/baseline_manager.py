"""
baseline/baseline_manager.py
Manages the statistical baseline profile of normal system behavior.
Records rolling statistics for each known agent and detects when their
behavior deviates from their own historical norm — per-agent personalization.
"""

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, Optional
import statistics


@dataclass
class AgentProfile:
    """Rolling statistical profile for a single agent."""

    agent_id: str
    cpu_window: deque = field(default_factory=lambda: deque(maxlen=100))
    mem_window: deque = field(default_factory=lambda: deque(maxlen=100))
    samples_seen: int = 0
    last_seen: float = field(default_factory=time.time)

    @property
    def is_mature(self) -> bool:
        """True once we have enough samples for stable statistics."""
        return self.samples_seen >= 20

    @property
    def cpu_mean(self) -> Optional[float]:
        return statistics.mean(self.cpu_window) if self.cpu_window else None

    @property
    def cpu_stdev(self) -> Optional[float]:
        return statistics.stdev(self.cpu_window) if len(self.cpu_window) >= 2 else None

    @property
    def mem_mean(self) -> Optional[float]:
        return statistics.mean(self.mem_window) if self.mem_window else None

    def update(self, cpu: float, mem: float):
        self.cpu_window.append(cpu)
        self.mem_window.append(mem)
        self.samples_seen += 1
        self.last_seen = time.time()

    def zscore(self, cpu: float, mem: float) -> Dict[str, Optional[float]]:
        """Returns z-scores for current cpu/mem vs this agent's profile."""
        result = {"cpu_zscore": None, "mem_zscore": None}
        if self.cpu_stdev and self.cpu_stdev > 0:
            result["cpu_zscore"] = (cpu - self.cpu_mean) / self.cpu_stdev
        if self.mem_mean:
            mem_vals = list(self.mem_window)
            if len(mem_vals) >= 2:
                mem_std = statistics.stdev(mem_vals)
                if mem_std > 0:
                    result["mem_zscore"] = (mem - self.mem_mean) / mem_std
        return result


class BaselineManager:
    """
    Maintains per-agent behavioral baselines.
    Provides z-score deviation alerts when an agent's metrics
    deviate significantly from their own historical norm.
    """

    def __init__(self, zscore_threshold: float = 3.0):
        self._profiles: Dict[str, AgentProfile] = defaultdict(
            lambda: AgentProfile(agent_id="unknown")
        )
        self.zscore_threshold = zscore_threshold

    def update(self, agent_id: str, cpu: float, mem: float) -> dict:
        """
        Feed a new telemetry sample. Returns a deviation report
        once the agent profile is mature.
        """
        if agent_id not in self._profiles:
            self._profiles[agent_id] = AgentProfile(agent_id=agent_id)

        profile = self._profiles[agent_id]

        # Compute deviation BEFORE updating the window
        report = {
            "agent_id": agent_id,
            "is_mature": profile.is_mature,
            "samples_seen": profile.samples_seen,
            "deviation": None,
            "alert": False,
        }

        if profile.is_mature:
            zscores = profile.zscore(cpu, mem)
            report["deviation"] = zscores
            report["alert"] = any(
                v is not None and abs(v) > self.zscore_threshold
                for v in zscores.values()
            )
            if report["alert"]:
                print(
                    f"[Baseline] DEVIATION ALERT: {agent_id} "
                    f"cpu_z={zscores['cpu_zscore']:.2f} "
                    f"mem_z={zscores['mem_zscore']}"
                )

        profile.update(cpu, mem)
        return report

    def get_profile(self, agent_id: str) -> Optional[AgentProfile]:
        return self._profiles.get(agent_id)

    def list_agents(self) -> list:
        return list(self._profiles.keys())

    def summary(self) -> dict:
        return {
            agent_id: {
                "samples": p.samples_seen,
                "cpu_mean": round(p.cpu_mean, 2) if p.cpu_mean else None,
                "mem_mean": round(p.mem_mean, 2) if p.mem_mean else None,
                "mature": p.is_mature,
                "last_seen": p.last_seen,
            }
            for agent_id, p in self._profiles.items()
        }


if __name__ == "__main__":
    import random

    mgr = BaselineManager(zscore_threshold=2.5)
    agent = "agent-test"

    print("Building profile with 30 normal samples...")
    for _ in range(30):
        mgr.update(agent, cpu=random.gauss(5.0, 1.0), mem=random.gauss(2e9, 1e8))

    print("\nInjecting a CPU spike...")
    report = mgr.update(agent, cpu=90.0, mem=2e9)
    print(f"Alert: {report['alert']}, Deviation: {report['deviation']}")
    print(f"\nSummary: {mgr.summary()}")
