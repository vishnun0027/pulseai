use std::fs;
use std::path::Path;
use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize, Clone, Debug)]
pub struct SessionState {
    pub session_token: String,
    pub boot_count: u64,
}

pub struct StateManager {
    state_file: String,
    pub state: SessionState,
}

impl StateManager {
    pub fn new(file_path: &str) -> Self {
        let state = Self::load_or_create(file_path);
        Self {
            state_file: file_path.to_string(),
            state,
        }
    }

    fn load_or_create(file_path: &str) -> SessionState {
        if Path::new(file_path).exists() {
            if let Ok(content) = fs::read_to_string(file_path) {
                if let Ok(state) = serde_json::from_str(&content) {
                    return state;
                }
            }
        }
        
        // Generate new state
        let new_state = SessionState {
            session_token: format!("ses-{}", std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_micros()),
            boot_count: 1,
        };
        
        let _ = fs::write(file_path, serde_json::to_string(&new_state).unwrap());
        new_state
    }
}
