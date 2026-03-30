use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub enum EnvironmentType {
    HostLinux,
    Wsl,
    Container,
    HostWindows,
    Unknown,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EnvironmentInfo {
    pub env_type: EnvironmentType,
    pub os_version: String,
}

pub struct EnvironmentDetector {
    pub info: EnvironmentInfo,
}

impl EnvironmentDetector {
    pub fn new() -> Self {
        let env_type = Self::detect_type();
        let os_version = sysinfo::System::os_version().unwrap_or_else(|| "unknown".to_string());
        
        Self {
            info: EnvironmentInfo {
                env_type,
                os_version,
            }
        }
    }

    fn detect_type() -> EnvironmentType {
        if std::path::Path::new("/.dockerenv").exists() {
            return EnvironmentType::Container;
        }
        
        let release_info = std::fs::read_to_string("/proc/version").unwrap_or_default();
        if release_info.to_lowercase().contains("microsoft") {
            return EnvironmentType::Wsl;
        }
        
        if cfg!(target_os = "linux") {
            return EnvironmentType::HostLinux;
        } else if cfg!(target_os = "windows") {
            return EnvironmentType::HostWindows;
        }
        
        EnvironmentType::Unknown
    }
}
