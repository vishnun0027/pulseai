let chart = null;
let eventSource = null;
let authMode = 'login';

function showAuthMessage(message, type = 'error') {
    const el = document.getElementById('auth-message');
    el.style.display = '';
    el.className = `auth-message ${type}`;
    el.textContent = message;
}

function showAppShell(user) {
    document.getElementById('auth-shell').style.display = 'none';
    document.getElementById('app-shell').style.display = '';
    document.getElementById('session-user').textContent = `${user.username} · ${user.role}`;
}

function showAuthShell(isBootstrap = false) {
    document.getElementById('app-shell').style.display = 'none';
    document.getElementById('auth-shell').style.display = '';
    document.getElementById('auth-register-wrap').style.display = isBootstrap ? '' : 'none';
    document.getElementById('auth-submit').textContent = isBootstrap ? 'Create Admin Account' : 'Sign In';
    document.getElementById('auth-copy').textContent = isBootstrap
        ? 'Create the first PulseAI admin account to unlock the dashboard.'
        : 'Sign in to access live telemetry, anomaly history, and reports.';
    authMode = isBootstrap ? 'register' : 'login';
}

async function apiFetch(url, options = {}) {
    const response = await fetch(url, {
        credentials: 'include',
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {})
        }
    });

    if (response.status === 401) {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        showAuthShell(false);
        throw new Error('Authentication required');
    }

    return response;
}

function buildHistoryParams() {
    const agentId = document.getElementById('filter-agent').value.trim();
    const onlyAnomalies = document.getElementById('filter-anomaly-only').value === 'true';
    const fromTs = document.getElementById('filter-from').value;
    const toTs = document.getElementById('filter-to').value;

    const params = new URLSearchParams({ limit: '100', offset: '0' });
    if (agentId) params.set('agent_id', agentId);
    if (onlyAnomalies) params.set('only_anomalies', 'true');
    if (fromTs) params.set('from_ts', new Date(fromTs).toISOString());
    if (toTs) params.set('to_ts', new Date(toTs).toISOString());
    return params;
}

function initChart() {
    const canvas = document.getElementById('telemetryChart');
    if (!canvas || chart) return;

    chart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'CPU (%)',
                    borderColor: '#5de2b3',
                    backgroundColor: 'rgba(93,226,179,0.08)',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    tension: 0.4,
                    data: [],
                    yAxisID: 'y',
                },
                {
                    label: 'Mem (GB)',
                    borderColor: '#ffd166',
                    backgroundColor: 'rgba(255,209,102,0.08)',
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
                    labels: { color: '#95aeb2', font: { family: 'Inter' } }
                }
            },
            scales: {
                y: {
                    beginAtZero: true, max: 100,
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: { color: '#95aeb2' },
                    title: { display: true, text: 'CPU %', color: '#95aeb2' }
                },
                y2: {
                    position: 'right',
                    grid: { display: false },
                    ticks: { color: '#ffd166' },
                    title: { display: true, text: 'Mem GB', color: '#ffd166' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#95aeb2', maxRotation: 0, maxTicksLimit: 8 }
                }
            },
            animation: { duration: 150 }
        }
    });
}

const MAX_POINTS = 40;

function updateChart(timeLabel, cpuVal, memVal) {
    if (!chart) return;
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

function addLog(msg, type = 'normal') {
    const logBox = document.getElementById('event-log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const timeStr = new Date().toLocaleTimeString();
    entry.innerHTML = `<span class="log-msg">${msg}</span><span class="log-time">${timeStr}</span>`;
    logBox.prepend(entry);
    if (logBox.children.length > 30) logBox.removeChild(logBox.lastChild);
}

function renderShap(explanation, agentId) {
    const empty = document.getElementById('shap-empty');
    const bars = document.getElementById('shap-bars');
    const agentLabel = document.getElementById('shap-agent-label');
    const contributors = explanation?.top_contributors || [];

    if (!contributors.length) {
        empty.style.display = '';
        bars.style.display = 'none';
        agentLabel.textContent = '—';
        return;
    }

    agentLabel.textContent = agentId;
    empty.style.display = 'none';
    bars.style.display = '';
    bars.innerHTML = '';

    const maxAbs = Math.max(...contributors.map((item) => Math.abs(item.impact)), 0.001);
    contributors.forEach(({ feature, impact }) => {
        const pct = Math.min((Math.abs(impact) / maxAbs) * 100, 100).toFixed(1);
        const color = impact > 0 ? '#ff6b6b' : '#5de2b3';
        const bar = document.createElement('div');
        bar.className = 'shap-row';
        bar.innerHTML = `
            <div class="shap-label">${feature}</div>
            <div class="shap-bar-track">
                <div class="shap-bar-fill" style="width:${pct}%;background:${color}"></div>
            </div>
            <div class="shap-value" style="color:${color}">${impact > 0 ? '+' : ''}${impact.toFixed(4)}</div>
        `;
        bars.appendChild(bar);
    });
}

function connectStream() {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource('/api/stream', { withCredentials: true });
    eventSource.onopen = () => {
        document.getElementById('connection-status').textContent = 'Live';
        document.getElementById('connection-status').style.color = '#5de2b3';
    };

    eventSource.onmessage = function (e) {
        const data = JSON.parse(e.data);

        document.getElementById('agent-id').textContent = data.agent_id;
        document.getElementById('cpu-val').textContent = data.cpu.toFixed(1);
        document.getElementById('mem-val').textContent = data.memory.toFixed(2);
        document.getElementById('feedback-agent-id').value = data.agent_id;

        const scoreEl = document.getElementById('score-val');
        scoreEl.textContent = (data.anomaly_score > 0 ? '+' : '') + data.anomaly_score.toFixed(3);

        const driftEl = document.getElementById('drift-val');
        driftEl.textContent = data.drift_detected ? 'YES' : 'No';
        driftEl.style.color = data.drift_detected ? '#ffb84d' : '#95aeb2';

        const pulse = document.getElementById('pulse');
        if (data.is_anomaly) {
            scoreEl.className = 'metric-value status-danger';
            addLog(`Outlier detected. Score ${data.anomaly_score.toFixed(3)} on ${data.agent_id}.`, 'anomaly');
            chart.data.datasets[0].borderColor = '#ff6b6b';
            chart.data.datasets[0].backgroundColor = 'rgba(255,107,107,0.08)';
            pulse.style.backgroundColor = '#ff6b6b';
            pulse.style.boxShadow = '0 0 14px #ff6b6b';
            renderShap(data.explanation, data.agent_id);
        } else {
            scoreEl.className = 'metric-value status-safe';
            addLog(`Baseline stable. CPU ${data.cpu.toFixed(1)}% on ${data.agent_id}.`, 'normal');
            chart.data.datasets[0].borderColor = '#5de2b3';
            chart.data.datasets[0].backgroundColor = 'rgba(93,226,179,0.08)';
            pulse.style.backgroundColor = '#5de2b3';
            pulse.style.boxShadow = '0 0 10px #5de2b3';
        }

        if (data.drift_detected) {
            addLog(`Concept drift detected for ${data.agent_id}.`, 'drift');
        }

        const timeLabel = new Date(data.timestamp * 1000)
            .toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
        updateChart(timeLabel, data.cpu, data.memory);
    };

    eventSource.onerror = async () => {
        document.getElementById('connection-status').textContent = 'Reconnecting…';
        document.getElementById('connection-status').style.color = '#ff6b6b';
        try {
            await ensureAuthenticated();
        } catch {
            if (eventSource) {
                eventSource.close();
                eventSource = null;
            }
        }
    };
}

async function ensureAuthenticated() {
    const response = await fetch('/api/auth/me', { credentials: 'include' });
    if (response.ok) {
        const payload = await response.json();
        return payload.user;
    }
    if (response.status === 401) {
        const registerResponse = await fetch('/api/auth/bootstrap-status', { credentials: 'include' });
        if (registerResponse.ok) {
            const data = await registerResponse.json();
            showAuthShell(data.bootstrap_required);
        } else {
            showAuthShell(false);
        }
    }
    throw new Error('Not authenticated');
}

async function submitFeedback(label) {
    const agentId = document.getElementById('feedback-agent-id').value;
    const note = document.getElementById('feedback-note').value.trim();
    const resultEl = document.getElementById('feedback-result');

    if (!agentId) {
        resultEl.style.display = '';
        resultEl.className = 'feedback-result error';
        resultEl.textContent = 'No active agent available yet.';
        return;
    }

    resultEl.style.display = '';
    resultEl.className = 'feedback-result loading';
    resultEl.textContent = 'Submitting…';

    try {
        const resp = await apiFetch('/api/feedback', {
            method: 'POST',
            body: JSON.stringify({ agent_id: agentId, label, note: note || null })
        });
        const rawBody = await resp.text();
        let json;
        try {
            json = rawBody ? JSON.parse(rawBody) : {};
        } catch {
            throw new Error(rawBody || `Request failed with status ${resp.status}`);
        }
        if (!resp.ok) {
            throw new Error(json.detail || json.error || rawBody || `Request failed with status ${resp.status}`);
        }
        resultEl.className = 'feedback-result success';
        resultEl.textContent = `OK: ${json.action}`;
        document.getElementById('feedback-note').value = '';
    } catch (err) {
        resultEl.className = 'feedback-result error';
        resultEl.textContent = `Error: ${err.message}`;
    }
}

async function loadHistory() {
    document.getElementById('history-loading').style.display = '';
    const params = buildHistoryParams();

    try {
        const resp = await apiFetch(`/api/anomalies?${params.toString()}`);
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
    tbody.innerHTML = items.map((e) => `
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

async function exportCsv() {
    const params = buildHistoryParams();
    const response = await fetch(`/api/reports/export?${params.toString()}`, {
        credentials: 'include'
    });
    if (!response.ok) {
        throw new Error('CSV export failed');
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    const disposition = response.headers.get('Content-Disposition') || '';
    const filenameMatch = disposition.match(/filename="(.+)"/);
    link.download = filenameMatch ? filenameMatch[1] : 'pulseai-report.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    if (eventSource) {
        eventSource.close();
        eventSource = null;
    }
    showAuthShell(false);
}

async function bootstrapStatus() {
    const response = await fetch('/api/auth/bootstrap-status', { credentials: 'include' });
    if (!response.ok) return { bootstrap_required: false };
    return response.json();
}

async function initApp() {
    try {
        const user = await ensureAuthenticated();
        showAppShell(user);
        initChart();
        connectStream();
        await loadHistory();
    } catch {
        const bootstrap = await bootstrapStatus();
        showAuthShell(bootstrap.bootstrap_required);
    }
}

document.getElementById('auth-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value;

    try {
        const endpoint = authMode === 'register' ? '/api/auth/register' : '/api/auth/login';
        const response = await fetch(endpoint, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Authentication failed');
        }

        showAuthMessage(
            authMode === 'register' ? 'Admin account created. Loading dashboard…' : 'Signed in. Loading dashboard…',
            'success'
        );
        document.getElementById('auth-password').value = '';
        await initApp();
    } catch (error) {
        showAuthMessage(error.message, 'error');
    }
});

document.getElementById('logout-btn').addEventListener('click', logout);
document.getElementById('export-btn').addEventListener('click', async () => {
    try {
        await exportCsv();
        addLog('CSV export generated from current history filters.', 'normal');
    } catch (error) {
        addLog(`Export failed: ${error.message}`, 'anomaly');
    }
});

window.submitFeedback = submitFeedback;
window.loadHistory = loadHistory;

initApp();
