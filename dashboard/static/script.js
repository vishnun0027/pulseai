// ── Chart setup ──────────────────────────────────────────────────────────────
const ctx = document.getElementById('telemetryChart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [
            {
                label: 'CPU (%)',
                borderColor: '#00ff88',
                backgroundColor: 'rgba(0, 255, 136, 0.08)',
                borderWidth: 2,
                pointRadius: 0,
                fill: true,
                tension: 0.4,
                data: [],
                yAxisID: 'y',
            },
            {
                label: 'Mem (GB)',
                borderColor: '#7c6cff',
                backgroundColor: 'rgba(124, 108, 255, 0.06)',
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false,
                tension: 0.4,
                data: [],
                yAxisID: 'y2',
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
            legend: {
                display: true,
                labels: { color: '#8b92a5', font: { family: 'Inter' } }
            }
        },
        scales: {
            y: {
                beginAtZero: true, max: 100,
                grid: { color: 'rgba(255,255,255,0.04)' },
                ticks: { color: '#8b92a5' },
                title: { display: true, text: 'CPU %', color: '#8b92a5' }
            },
            y2: {
                position: 'right',
                grid: { display: false },
                ticks: { color: '#7c6cff' },
                title: { display: true, text: 'Mem GB', color: '#7c6cff' }
            },
            x: {
                grid: { display: false },
                ticks: { color: '#8b92a5', maxRotation: 0, maxTicksLimit: 8 }
            }
        },
        animation: { duration: 150 }
    }
});

const MAX_POINTS = 40;

function updateChart(timeLabel, cpuVal, memVal) {
    chart.data.labels.push(timeLabel);
    chart.data.datasets[0].data.push(cpuVal);
    chart.data.datasets[1].data.push(memVal);
    if (chart.data.labels.length > MAX_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
        chart.data.datasets[1].data.shift();
    }
    chart.update('none');
}

// ── Event log ────────────────────────────────────────────────────────────────
function addLog(msg, type = 'normal') {
    const logBox = document.getElementById('event-log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timeStr = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="log-msg">${msg}</span><span class="log-time">${timeStr}</span>`;
    logBox.prepend(entry);
    if (logBox.children.length > 30) logBox.removeChild(logBox.lastChild);
}

// ── SHAP bar renderer ─────────────────────────────────────────────────────────
function renderShap(explanation, agentId) {
    const empty = document.getElementById('shap-empty');
    const bars = document.getElementById('shap-bars');
    const agentLabel = document.getElementById('shap-agent-label');

    if (!explanation || Object.keys(explanation).length === 0) {
        empty.style.display = '';
        bars.style.display = 'none';
        return;
    }

    agentLabel.textContent = agentId;
    empty.style.display = 'none';
    bars.style.display = '';
    bars.innerHTML = '';

    const entries = Object.entries(explanation).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 0.001);

    entries.forEach(([feature, value]) => {
        const pct = Math.min(Math.abs(value) / maxAbs * 100, 100).toFixed(1);
        const color = value > 0 ? '#ff3366' : '#00cc66';
        const bar = document.createElement('div');
        bar.className = 'shap-row';
        bar.innerHTML = `
            <div class="shap-label">${feature}</div>
            <div class="shap-bar-track">
                <div class="shap-bar-fill" style="width:${pct}%;background:${color}"></div>
            </div>
            <div class="shap-value" style="color:${color}">${value > 0 ? '+' : ''}${value.toFixed(4)}</div>
        `;
        bars.appendChild(bar);
    });
}

// ── State tracking ────────────────────────────────────────────────────────────
let lastEventId = null;
let lastAgentId = '';

// ── SSE stream ───────────────────────────────────────────────────────────────
const eventSource = new EventSource('/api/stream');

eventSource.onopen = () => {
    document.getElementById('connection-status').textContent = 'Live';
    document.getElementById('connection-status').style.color = '#00ff88';
};

eventSource.onmessage = function (e) {
    const data = JSON.parse(e.data);

    lastAgentId = data.agent_id;
    document.getElementById('agent-id').textContent = data.agent_id;
    document.getElementById('cpu-val').textContent = data.cpu.toFixed(1);
    document.getElementById('mem-val').textContent = data.memory.toFixed(2);
    document.getElementById('feedback-agent-id').value = data.agent_id;

    const scoreEl = document.getElementById('score-val');
    scoreEl.textContent = (data.anomaly_score > 0 ? '+' : '') + data.anomaly_score.toFixed(3);

    const driftEl = document.getElementById('drift-val');
    driftEl.textContent = data.drift_detected ? 'YES' : 'No';
    driftEl.style.color = data.drift_detected ? '#ffaa00' : '#8b92a5';

    const pulse = document.getElementById('pulse');
    if (data.is_anomaly) {
        scoreEl.className = 'metric-value status-danger';
        addLog(`Outlier detected! Score: ${data.anomaly_score.toFixed(3)} | Agent: ${data.agent_id}`, 'anomaly');
        chart.data.datasets[0].borderColor = '#ff3366';
        chart.data.datasets[0].backgroundColor = 'rgba(255,51,102,0.08)';
        pulse.style.backgroundColor = '#ff3366';
        pulse.style.boxShadow = '0 0 14px #ff3366';

        // Show SHAP explanation
        renderShap(data.explanation, data.agent_id);
    } else {
        scoreEl.className = 'metric-value status-safe';
        addLog(`Baseline stable. CPU: ${data.cpu.toFixed(1)}%`, 'normal');
        chart.data.datasets[0].borderColor = '#00ff88';
        chart.data.datasets[0].backgroundColor = 'rgba(0,255,136,0.08)';
        pulse.style.backgroundColor = '#00ff88';
        pulse.style.boxShadow = '0 0 10px #00ff88';
    }

    if (data.drift_detected) {
        addLog(`Concept drift detected for ${data.agent_id}.`, 'drift');
    }

    const timeLabel = new Date(data.timestamp * 1000)
        .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    updateChart(timeLabel, data.cpu, data.memory);
};

eventSource.onerror = () => {
    document.getElementById('connection-status').textContent = 'Reconnecting…';
    document.getElementById('connection-status').style.color = '#ff3366';
    document.getElementById('agent-id').textContent = 'Connection lost';
};

// ── Feedback submission ───────────────────────────────────────────────────────
async function submitFeedback(label) {
    const agentId = document.getElementById('feedback-agent-id').value;
    const note = document.getElementById('feedback-note').value.trim();
    const resultEl = document.getElementById('feedback-result');

    if (!agentId) {
        resultEl.style.display = '';
        resultEl.className = 'feedback-result error';
        resultEl.textContent = 'No active agent — wait for the first telemetry event.';
        return;
    }

    resultEl.style.display = '';
    resultEl.className = 'feedback-result loading';
    resultEl.textContent = 'Submitting…';

    try {
        const resp = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agent_id: agentId, label, note: note || null })
        });
        const json = await resp.json();
        resultEl.className = 'feedback-result success';
        resultEl.textContent = `✓ ${json.action}`;
        document.getElementById('feedback-note').value = '';
    } catch (err) {
        resultEl.className = 'feedback-result error';
        resultEl.textContent = `Error: ${err.message}`;
    }
}

// ── Historical anomaly browser ────────────────────────────────────────────────
async function loadHistory() {
    const agentId = document.getElementById('filter-agent').value.trim();
    const onlyAnomalies = document.getElementById('filter-anomaly-only').value === 'true';
    const fromTs = document.getElementById('filter-from').value;
    const toTs = document.getElementById('filter-to').value;

    document.getElementById('history-loading').style.display = '';

    const params = new URLSearchParams({ limit: 100, offset: 0 });
    if (agentId) params.set('agent_id', agentId);
    if (onlyAnomalies) params.set('only_anomalies', 'true');
    if (fromTs) params.set('from_ts', new Date(fromTs).toISOString());
    if (toTs) params.set('to_ts', new Date(toTs).toISOString());

    try {
        const resp = await fetch(`/api/anomalies?${params}`);
        const data = await resp.json();
        renderHistory(data.items || []);
    } catch (e) {
        console.error('History load failed:', e);
    } finally {
        document.getElementById('history-loading').style.display = 'none';
    }
}

function renderHistory(items) {
    const tbody = document.getElementById('history-body');
    if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="history-empty">No events match the current filters.</td></tr>';
        return;
    }
    tbody.innerHTML = items.map(e => `
        <tr class="${e.is_anomaly ? 'row-anomaly' : ''}">
            <td>${new Date(e.ts).toLocaleString()}</td>
            <td class="mono">${e.agent_id}</td>
            <td>${e.cpu_usage != null ? e.cpu_usage.toFixed(1) : '—'}</td>
            <td>${e.used_memory_gb != null ? e.used_memory_gb.toFixed(2) : '—'}</td>
            <td class="${e.anomaly_score > 0 ? 'score-high' : 'score-low'}">${e.anomaly_score.toFixed(3)}</td>
            <td>${e.is_anomaly ? '<span class="badge badge-red">YES</span>' : '<span class="badge badge-green">no</span>'}</td>
            <td>${e.drift_detected ? '<span class="badge badge-orange">drift</span>' : '—'}</td>
        </tr>
    `).join('');
}

// Auto-load history on page open
loadHistory();
