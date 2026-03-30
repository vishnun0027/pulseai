mod collector;
mod environment;
mod state_manager;
mod gap_detector;

use std::time::Duration;
use serde::Serialize;
use collector::Collector;
use environment::EnvironmentDetector;
use state_manager::StateManager;
use gap_detector::GapDetector;

#[derive(Serialize)]
struct AgentPayload {
    agent_id: String,
    timestamp: u64,
    metrics: collector::SystemMetrics,
    environment: environment::EnvironmentInfo,
    session: state_manager::SessionState,
    gap_type: String,
}

#[tokio::main]
async fn main() {
    println!("Starting AI Behavior Anomaly Rust Agent...");

    let mut col = Collector::new();
    let env_detector = EnvironmentDetector::new();
    let state_manager = StateManager::new(".agent_state.json");
    let mut gap_detector = GapDetector::new();
    
    let agent_id = format!("agent-{}", sysinfo::System::host_name().unwrap_or_else(|| "unknown".to_string()));

    let client = reqwest::Client::new();
    let telemetry_url = std::env::var("TELEMETRY_URL")
        .unwrap_or_else(|_| "http://localhost:8080/v1/telemetry".to_string());
    let mut interval = tokio::time::interval(Duration::from_secs(5));

    loop {
        interval.tick().await;

        let metrics = col.gather();
        let gap_type = gap_detector.check_gap();

        let payload = AgentPayload {
            agent_id: agent_id.clone(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            metrics,
            environment: env_detector.info.clone(),
            session: state_manager.state.clone(),
            gap_type,
        };

        match client.post(&telemetry_url).json(&payload).send().await {
            Ok(res) => {
                if !res.status().is_success() {
                    eprintln!("Failed to send telemetry: {}", res.status());
                }
            }
            Err(e) => eprintln!("Error sending telemetry: {}", e),
        }
        
        gap_detector.mark_sent();
    }
}
