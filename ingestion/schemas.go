package main

type SystemMetrics struct {
	CpuUsage      float64  `json:"cpu_usage"`
	TotalMemory   uint64   `json:"total_memory"`
	UsedMemory    uint64   `json:"used_memory"`
	LoadAverage1m float64  `json:"load_average_1m"`
	GpuUsage      *float32 `json:"gpu_usage,omitempty"`
}

type EnvironmentInfo struct {
	EnvType   string `json:"env_type"`
	OsVersion string `json:"os_version"`
}

type SessionState struct {
	SessionToken string `json:"session_token"`
	BootCount    uint64 `json:"boot_count"`
}

type AgentPayload struct {
	AgentID     string          `json:"agent_id"`
	Timestamp   uint64          `json:"timestamp"`
	Metrics     SystemMetrics   `json:"metrics"`
	Environment EnvironmentInfo `json:"environment"`
	Session     SessionState    `json:"session"`
	GapType     string          `json:"gap_type"`
}
