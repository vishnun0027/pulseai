use sysinfo::System;
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemMetrics {
    pub cpu_usage: f32,
    pub total_memory: u64,
    pub used_memory: u64,
    pub load_average_1m: f64,
    pub gpu_usage: Option<f32>,
}

pub struct Collector {
    sys: System,
}

impl Collector {
    pub fn new() -> Self {
        let mut sys = System::new_all();
        sys.refresh_all();
        Self { sys }
    }

    fn get_gpu_usage() -> Option<f32> {
        if let Ok(output) = std::process::Command::new("nvidia-smi")
            .arg("--query-gpu=utilization.gpu")
            .arg("--format=csv,noheader,nounits")
            .output()
        {
            if output.status.success() {
                if let Ok(s) = String::from_utf8(output.stdout) {
                    if let Some(first_line) = s.lines().next() {
                        return first_line.trim().parse::<f32>().ok();
                    }
                }
            }
        }
        None
    }

    pub fn gather(&mut self) -> SystemMetrics {
        self.sys.refresh_all();
        
        let cpu_usage = self.sys.global_cpu_info().cpu_usage();
        let total_memory = self.sys.total_memory();
        let used_memory = self.sys.used_memory();
        let load_average_1m = System::load_average().one;
        let gpu_usage = Self::get_gpu_usage();

        SystemMetrics {
            cpu_usage,
            total_memory,
            used_memory,
            load_average_1m,
            gpu_usage,
        }
    }
}
