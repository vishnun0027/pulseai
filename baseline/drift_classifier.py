from river import drift

class DriftDetector:
    def __init__(self):
        # ADWIN is great for detecting concept drift in continuous streams.
        self.adwin_cpu = drift.ADWIN()
        self.adwin_mem = drift.ADWIN()
        
    def check_drift(self, cpu_val: float, mem_val: float) -> bool:
        """
        Updates ADWIN buffers and returns True if drift is detected.
        """
        drift_cpu = self.adwin_cpu.update(cpu_val)
        drift_mem = self.adwin_mem.update(mem_val)
        
        return drift_cpu or drift_mem
