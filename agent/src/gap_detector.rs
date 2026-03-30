use std::time::{SystemTime, UNIX_EPOCH};

pub struct GapDetector {
    last_send_ts: u64,
}

impl GapDetector {
    pub fn new() -> Self {
        Self {
            last_send_ts: Self::now(),
        }
    }

    pub fn mark_sent(&mut self) {
        self.last_send_ts = Self::now();
    }

    pub fn check_gap(&self) -> String {
        let current = Self::now();
        let diff = current.saturating_sub(self.last_send_ts);
        
        if diff > 600 {
            "long_gap".to_string()
        } else if diff > 60 {
            "short_gap".to_string()
        } else if diff > 10 {
            "micro_gap".to_string()
        } else {
            "none".to_string()
        }
    }

    fn now() -> u64 {
        SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs()
    }
}
