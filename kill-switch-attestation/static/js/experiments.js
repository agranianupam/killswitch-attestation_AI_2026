/*
static/js/experiments.js — Strategy Comparison View
Runs N cycles per strategy (A, B, C) using execute_shutdown_cycle (triggered_by="experiment"),
displays live progress, and renders a comparative table and chart plus history list.
*/

let comparisonChart = null;

window.render_experiments = async function(container) {
    container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 20px;">
            <div>
                <h2 style="margin:0;">Strategy Comparison</h2>
                <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                    Evaluate Strategies A, B, and C under identical simulation workloads.
                </div>
            </div>
        </div>

        <!-- Run Controls Panel -->
        <div class="panel" style="margin-bottom: 25px;">
            <h3 style="margin-top:0; border-bottom: 1px solid var(--border); padding-bottom: 10px;">Run New Comparison</h3>
            <div style="display:flex; gap:20px; align-items:flex-end; flex-wrap:wrap; margin-top:15px;">
                <div class="form-group" style="margin-bottom:0;">
                    <label for="cmp-cycles" style="font-weight:600; font-size:12px; color:var(--text-muted); margin-bottom:6px; display:block;">
                        Cycles per Strategy (1 - 30)
                    </label>
                    <input type="number" id="cmp-cycles" value="5" min="1" max="30" style="width:140px; padding:8px 12px; background:var(--bg-main); border:1px solid var(--border); border-radius:6px; color:#fff;">
                </div>
                <div>
                    <button id="btn-run-comparison" onclick="runStrategyComparison()" style="padding:9px 24px; font-weight:bold; background:var(--neon-blue); color:#000; border:none; border-radius:6px; cursor:pointer;">
                        Run Comparison
                    </button>
                </div>
            </div>

            <!-- Progress Bar -->
            <div id="cmp-progress-box" class="hidden" style="margin-top:20px; padding:15px; background:rgba(0,0,0,0.3); border:1px solid var(--border); border-radius:8px;">
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:8px;">
                    <span id="cmp-progress-status" style="color:var(--neon-blue); font-weight:600;">Starting evaluation...</span>
                    <span id="cmp-progress-percent" style="color:#aaa; font-family:monospace;">0%</span>
                </div>
                <div style="background:rgba(255,255,255,0.1); border-radius:6px; height:10px; overflow:hidden;">
                    <div id="cmp-progress-bar" style="background:var(--neon-blue); width:0%; height:100%; transition:width 0.3s ease;"></div>
                </div>
            </div>
        </div>

        <!-- Latest Comparison Results -->
        <div id="cmp-results-panel" class="panel hidden" style="margin-bottom: 25px;">
            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px;">
                <h3 style="margin:0;">Comparison Results</h3>
                <span id="cmp-results-timestamp" style="font-size:11px; color:var(--text-muted);"></span>
            </div>

            <!-- Comparison Table -->
            <div style="overflow-x:auto; margin-bottom:25px;">
                <table id="cmp-results-table" style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border); color:var(--text-muted); text-align:left;">
                            <th style="padding:10px;">Strategy</th>
                            <th style="padding:10px;">Runs</th>
                            <th style="padding:10px;">Success Rate</th>
                            <th style="padding:10px;">Leak Rate</th>
                            <th style="padding:10px;">Mean Latency</th>
                            <th style="padding:10px;">Mean Residual Risk</th>
                        </tr>
                    </thead>
                    <tbody id="cmp-results-tbody"></tbody>
                </table>
            </div>

            <!-- Bar Chart -->
            <div style="height:320px; position:relative; background:rgba(0,0,0,0.2); padding:15px; border-radius:8px; border:1px solid var(--border);">
                <canvas id="comparisonChart"></canvas>
            </div>
        </div>

        <!-- Comparison History List -->
        <div class="panel">
            <h3 style="margin-top:0; border-bottom: 1px solid var(--border); padding-bottom: 10px;">Comparison History</h3>
            <div style="overflow-x:auto;">
                <table id="cmp-history-table" style="width:100%; border-collapse:collapse; font-size:12px;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border); color:var(--text-muted); text-align:left;">
                            <th style="padding:10px;">Timestamp</th>
                            <th style="padding:10px;">Cycles / Strat</th>
                            <th style="padding:10px;">Strategy A (Success / Leak)</th>
                            <th style="padding:10px;">Strategy B (Success / Leak)</th>
                            <th style="padding:10px;">Strategy C (Success / Leak)</th>
                            <th style="padding:10px;">Action</th>
                        </tr>
                    </thead>
                    <tbody id="cmp-history-tbody">
                        <tr><td colspan="6" style="text-align:center; padding:25px; color:var(--text-muted);">Loading history...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    setupComparisonWsListener();
    loadComparisonHistory();
};

window.setupComparisonWsListener = function() {
    window.removeEventListener('ws_comparison_progress', window.handleComparisonProgress);
    window.handleComparisonProgress = function(e) {
        const d = e.detail;
        if(!d) return;
        const pBox = document.getElementById('cmp-progress-box');
        const pStatus = document.getElementById('cmp-progress-status');
        const pPercent = document.getElementById('cmp-progress-percent');
        const pBar = document.getElementById('cmp-progress-bar');

        if(pBox) pBox.classList.remove('hidden');
        if(pStatus) {
            pStatus.textContent = `Evaluating Strategy ${d.strategy} — Cycle ${d.cycle}/${d.cycles_per_strategy} (Overall ${d.overall_cycle}/${d.total_cycles})`;
        }
        if(pPercent) pPercent.textContent = `${d.percent}%`;
        if(pBar) pBar.style.width = `${d.percent}%`;
    };
    window.addEventListener('ws_comparison_progress', window.handleComparisonProgress);
};

window.runStrategyComparison = async function() {
    if(!State.token) {
        showLogin();
        return;
    }

    const cyclesInput = document.getElementById('cmp-cycles');
    const cycles = parseInt(cyclesInput ? cyclesInput.value : '5', 10);
    if(isNaN(cycles) || cycles < 1 || cycles > 30) {
        alert('Please enter a cycle count between 1 and 30.');
        return;
    }

    const btn = document.getElementById('btn-run-comparison');
    const pBox = document.getElementById('cmp-progress-box');
    const pStatus = document.getElementById('cmp-progress-status');
    const pPercent = document.getElementById('cmp-progress-percent');
    const pBar = document.getElementById('cmp-progress-bar');

    if(btn) { btn.disabled = true; btn.textContent = 'Running...'; }
    if(pBox) pBox.classList.remove('hidden');
    if(pStatus) pStatus.textContent = 'Initializing test suites across Strategies A, B, and C...';
    if(pPercent) pPercent.textContent = '0%';
    if(pBar) pBar.style.width = '0%';

    try {
        const comp = await apiCall(`/api/experiments/compare?cycles=${cycles}`, 'POST');
        if(pStatus) pStatus.textContent = 'Completed all cycles successfully!';
        if(pPercent) pPercent.textContent = '100%';
        if(pBar) pBar.style.width = '100%';

        setTimeout(() => {
            if(pBox) pBox.classList.add('hidden');
        }, 2000);

        renderComparisonResults(comp);
        loadComparisonHistory();
    } catch(err) {
        alert(err.detail || 'Failed to complete strategy comparison.');
        if(pBox) pBox.classList.add('hidden');
    } finally {
        if(btn) { btn.disabled = false; btn.textContent = 'Run Comparison'; }
    }
};

window.renderComparisonResults = function(comp) {
    if(!comp || !comp.strategies) return;
    const panel = document.getElementById('cmp-results-panel');
    const tbody = document.getElementById('cmp-results-tbody');
    const tsEl = document.getElementById('cmp-results-timestamp');

    if(panel) panel.classList.remove('hidden');
    if(tsEl) tsEl.textContent = `Run at: ${formatLocalTime(comp.timestamp)} (${comp.cycles_per_strategy} cycles/strategy)`;

    const strats = ['A', 'B', 'C'];
    if(tbody) {
        tbody.innerHTML = strats.map(s => {
            const data = comp.strategies[s] || { runs: 0, success_rate: 0, leak_rate: 0, mean_revocation_latency: 0, mean_residual_risk: 0 };
            return `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                    <td style="padding:10px; font-weight:bold; color:var(--neon-blue);">Strategy ${s}</td>
                    <td style="padding:10px;">${data.runs}</td>
                    <td style="padding:10px;">
                        <span class="badge ${data.success_rate >= 80 ? 'success' : (data.success_rate >= 40 ? 'warning' : 'danger')}">
                            ${data.success_rate.toFixed(1)}%
                        </span>
                    </td>
                    <td style="padding:10px; color:${data.leak_rate > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:bold;">
                        ${data.leak_rate.toFixed(1)}%
                    </td>
                    <td style="padding:10px;">${data.mean_revocation_latency.toFixed(1)} ms</td>
                    <td style="padding:10px;">${(data.mean_residual_risk * 100).toFixed(1)}%</td>
                </tr>
            `;
        }).join('');
    }

    renderComparisonChart(comp.strategies);
};

window.renderComparisonChart = function(strategies) {
    const canvas = document.getElementById('comparisonChart');
    if(!canvas) return;

    if(comparisonChart) {
        comparisonChart.destroy();
    }

    const labels = ['Strategy A', 'Strategy B', 'Strategy C'];
    const successRates = ['A', 'B', 'C'].map(s => strategies[s] ? strategies[s].success_rate : 0);
    const leakRates = ['A', 'B', 'C'].map(s => strategies[s] ? strategies[s].leak_rate : 0);
    const latencies = ['A', 'B', 'C'].map(s => strategies[s] ? strategies[s].mean_revocation_latency : 0);
    const risks = ['A', 'B', 'C'].map(s => strategies[s] ? Math.round(strategies[s].mean_residual_risk * 100) : 0);

    comparisonChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Success Rate (%)',
                    data: successRates,
                    backgroundColor: 'rgba(16, 185, 129, 0.75)',
                    borderColor: '#10b981',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Leak Rate (%)',
                    data: leakRates,
                    backgroundColor: 'rgba(244, 63, 94, 0.75)',
                    borderColor: '#f43f5e',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Mean Latency (ms)',
                    data: latencies,
                    backgroundColor: 'rgba(56, 189, 248, 0.75)',
                    borderColor: '#38bdf8',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Residual Risk (%)',
                    data: risks,
                    backgroundColor: 'rgba(234, 179, 8, 0.75)',
                    borderColor: '#eab308',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#a1a1aa' }
                },
                x: {
                    ticks: { color: '#e4e4e7', font: { weight: 'bold' } },
                    grid: { display: false }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#e4e4e7', boxWidth: 12 }
                }
            }
        }
    });
};

window.loadComparisonHistory = async function() {
    try {
        const history = await apiCall('/api/experiments/comparison/history').catch(() => []);
        const tbody = document.getElementById('cmp-history-tbody');
        if(!tbody) return;

        if(!history || history.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:25px; color:var(--text-muted);">No comparison runs yet</td></tr>`;
            return;
        }

        tbody.innerHTML = history.map((item, idx) => {
            const stA = item.strategies && item.strategies.A ? `${item.strategies.A.success_rate.toFixed(0)}% / ${item.strategies.A.leak_rate.toFixed(0)}%` : '--';
            const stB = item.strategies && item.strategies.B ? `${item.strategies.B.success_rate.toFixed(0)}% / ${item.strategies.B.leak_rate.toFixed(0)}%` : '--';
            const stC = item.strategies && item.strategies.C ? `${item.strategies.C.success_rate.toFixed(0)}% / ${item.strategies.C.leak_rate.toFixed(0)}%` : '--';
            return `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                    <td style="padding:10px;">${formatLocalTime(item.timestamp)}</td>
                    <td style="padding:10px;">${item.cycles_per_strategy}</td>
                    <td style="padding:10px;">${stA}</td>
                    <td style="padding:10px;">${stB}</td>
                    <td style="padding:10px;">${stC}</td>
                    <td style="padding:10px;">
                        <button onclick='window.renderComparisonResults(${JSON.stringify(item)})' style="padding:4px 10px; font-size:11px; background:#27272a; color:#38bdf8; border:1px solid #3f3f46; border-radius:4px; cursor:pointer;">
                            View
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        // If results panel is hidden and we have history, show the latest one
        const panel = document.getElementById('cmp-results-panel');
        if(panel && panel.classList.contains('hidden') && history.length > 0) {
            renderComparisonResults(history[0]);
        }
    } catch(e) {
        console.error('Error loading comparison history:', e);
    }
};

window.cleanup_experiments = function() {
    if(comparisonChart) {
        comparisonChart.destroy();
        comparisonChart = null;
    }
};
