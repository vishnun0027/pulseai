const ctx = document.getElementById('telemetryChart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: {
        labels: [],
        datasets: [{
            label: 'CPU (%)',
            borderColor: '#00ff88',
            backgroundColor: 'rgba(0, 255, 136, 0.1)',
            borderWidth: 2,
            pointRadius: 0,
            fill: true,
            tension: 0.4,
            data: []
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            y: {
                beginAtZero: true,
                max: 100,
                grid: { color: 'rgba(255, 255, 255, 0.05)' },
                ticks: { color: '#8b92a5' }
            },
            x: {
                grid: { display: false },
                ticks: { color: '#8b92a5', maxRotation: 0 }
            }
        },
        animation: { duration: 0 }
    }
});

const MAX_POINTS = 20;

function updateChart(timeLabel, cpuVal) {
    chart.data.labels.push(timeLabel);
    chart.data.datasets[0].data.push(cpuVal);

    if (chart.data.labels.length > MAX_POINTS) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    chart.update();
}

function addLog(msg, isAnomaly) {
    const logBox = document.getElementById('event-log');
    const entry = document.createElement('div');
    entry.className = isAnomaly ? 'log-entry anomaly' : 'log-entry';

    const now = new Date();
    const timeStr = now.toLocaleTimeString();

    entry.innerHTML = `<span class="log-msg">${msg}</span><span class="log-time">${timeStr}</span>`;

    logBox.prepend(entry);

    if (logBox.children.length > 20) {
        logBox.removeChild(logBox.lastChild);
    }
}

const eventSource = new EventSource('/api/stream');

eventSource.onmessage = function (e) {
    const data = JSON.parse(e.data);

    document.getElementById('agent-id').innerText = data.agent_id;

    document.getElementById('cpu-val').innerText = data.cpu.toFixed(1);
    document.getElementById('mem-val').innerText = data.memory.toFixed(1);

    const scoreEl = document.getElementById('score-val');
    scoreEl.innerText = (data.anomaly_score > 0 ? "+" : "") + data.anomaly_score.toFixed(3);

    if (data.is_anomaly) {
        scoreEl.className = "metric-value status-danger";
        addLog(`High intelligence alert: Outlier detected! (Score: ${data.anomaly_score.toFixed(3)})`, true);

        chart.data.datasets[0].borderColor = '#ff3366';
        chart.data.datasets[0].backgroundColor = 'rgba(255, 51, 102, 0.1)';
        document.querySelector('.pulse-indicator').style.backgroundColor = '#ff3366';
        document.querySelector('.pulse-indicator').style.boxShadow = '0 0 10px #ff3366';
    } else {
        scoreEl.className = "metric-value status-safe";
        addLog(`System baseline stable.`, false);

        chart.data.datasets[0].borderColor = '#00ff88';
        chart.data.datasets[0].backgroundColor = 'rgba(0, 255, 136, 0.1)';
        document.querySelector('.pulse-indicator').style.backgroundColor = '#00ff88';
        document.querySelector('.pulse-indicator').style.boxShadow = '0 0 10px #00ff88';
    }

    const timeLabel = new Date(data.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    updateChart(timeLabel, data.cpu);
};

eventSource.onerror = function () {
    document.getElementById('agent-id').innerText = "Connection lost. Reconnecting...";
};
