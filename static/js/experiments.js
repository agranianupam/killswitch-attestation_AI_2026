let comparisonChart = null;

window.render_experiments = async function(container) {
    window.cleanup_experiments();

    container.innerHTML = `
        <!-- Floating Wireframe Background & Crosshairs -->
        <div class="hero-wireframe-bg">
            <svg viewBox="0 0 200 120" fill="none" stroke="#94a3b8" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="120,15 180,35 140,65 80,45" stroke="#cbd5e1" stroke-width="0.8"/>
                <polygon points="80,45 140,65 140,105 80,85" stroke="#94a3b8" stroke-width="1"/>
                <polygon points="140,65 180,35 180,75 140,105" stroke="#cbd5e1" stroke-width="0.8"/>
                <path d="M30,20 L30,26 M27,23 L33,23" stroke="#475569" stroke-width="1.2"/>
                <path d="M90,10 L90,16 M87,13 L93,13" stroke="#475569" stroke-width="1.2"/>
                <path d="M185,50 L185,56 M182,53 L188,53" stroke="#475569" stroke-width="1.2"/>
            </svg>
        </div>

        <!-- Hero Header -->
        <div class="view-hero">
            <div class="hero-text">
                <div class="hero-kicker">Simulated Evaluation</div>
                <h1 class="hero-title">
                    Verifiable <span class="highlight-red">AI Agent</span> Strategy Comparison
                </h1>
                <p class="hero-subtitle">
                    Simulated comparative evaluation across Strategies A, B, and C with latency and in-flight leak metrics.
                </p>
            </div>
        </div>

        <!-- Section 01: Experiment Configuration -->
        <div class="section-heading">
            <span class="sec-num">01</span>
            <span class="sec-title">Experiment Configuration &amp; Execution</span>
            <div class="sec-line"></div>
        </div>

        <div class="panel" style="margin-bottom: 25px;">
            <div style="background: var(--warning-subtle); border: 1px solid var(--warning-border); border-radius: 6px; padding: 10px 14px; margin-bottom: 16px;">
                <p style="margin:0; font-size:12px; color: var(--warning-text); font-weight:500;">
                    <strong>Notice:</strong> Outcomes depend on configured probabilities and are modelled, not measured on production systems.
                </p>
            </div>

            <div style="display:flex; gap:16px; align-items:flex-end; flex-wrap:wrap;">
                <div style="margin-bottom:0;">
                    <label for="cmp-cycles" style="font-weight:700; font-size:11px; color:var(--text-secondary); margin-bottom:6px; display:block; text-transform:uppercase;">
                        Cycles per Strategy (1 - 30)
                    </label>
                    <input type="number" id="cmp-cycles" value="5" min="1" max="30" style="width:140px; padding:8px 12px;">
                </div>
                <div>
                    <button id="btn-run-comparison" class="btn-shutdown" onclick="runStrategyComparison()">
                        <span>⚡</span> RUN COMPARISON <span>→</span>
                    </button>
                </div>
            </div>

            <div id="cmp-progress-box" class="hidden" style="margin-top:20px; padding:14px; background:#f8fafc; border:1px solid var(--border); border-radius:6px;">
                <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:8px;">
                    <span id="cmp-progress-status" style="color:var(--accent-red); font-weight:700;">Starting evaluation...</span>
                    <span id="cmp-progress-percent" style="color:var(--text-muted); font-family:var(--font-mono); font-weight:700;">0%</span>
                </div>
                <div style="background:#e2e8f0; border-radius:4px; height:8px; overflow:hidden;">
                    <div id="cmp-progress-bar" style="background:var(--accent-red); width:0%; height:100%; transition:width 0.3s ease;"></div>
                </div>
            </div>
        </div>

        <!-- Section 02: Comparative Evaluation Results -->
        <div id="cmp-results-panel" class="hidden" style="margin-bottom: 25px;">
            <div class="section-heading">
                <span class="sec-num">02</span>
                <span class="sec-title">Comparative Evaluation Results &amp; Charts</span>
                <div class="sec-line"></div>
            </div>

            <div class="panel" style="margin-bottom: 25px;">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Comparison Summary</h3>
                        <div id="cmp-results-timestamp" style="font-size:11px; color:var(--text-muted); margin-top:2px;"></div>
                    </div>
                    <div id="cmp-download-btn-container"></div>
                </div>

                <div style="overflow-x:auto; margin-bottom:25px;">
                    <table id="cmp-results-table">
                        <thead>
                            <tr>
                                <th>Strategy</th>
                                <th>Runs</th>
                                <th>Success Rate</th>
                                <th>Leak Rate (All Runs)</th>
                                <th>Exposed Runs</th>
                                <th>Leak Rate (Exposed Runs)</th>
                                <th>Per-Channel Latency</th>
                                <th>Total Revocation Time</th>
                                <th>Cycle Duration</th>
                                <th>Mean Residual Risk</th>
                            </tr>
                        </thead>
                        <tbody id="cmp-results-tbody"></tbody>
                    </table>
                </div>

                <div style="height:360px; position:relative; background:#ffffff; padding:15px; border-radius:8px; border:1px solid var(--border);">
                    <canvas id="comparisonChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Section 03: Run History -->
        <div class="section-heading">
            <span class="sec-num">03</span>
            <span class="sec-title">Comparison Run History</span>
            <div class="sec-line"></div>
        </div>

        <div class="panel">
            <div style="overflow-x:auto;">
                <table id="cmp-history-table">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Cycles / Strat</th>
                            <th>Strategy A (Success / Leak)</th>
                            <th>Strategy B (Success / Leak)</th>
                            <th>Strategy C (Success / Leak)</th>
                            <th>Action</th>
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
    if(pStatus) pStatus.textContent = 'Initializing comparison across Strategies A, B, and C...';
    if(pPercent) pPercent.textContent = '0%';
    if(pBar) pBar.style.width = '0%';

    try {
        const comp = await apiCall(`/api/experiments/compare?cycles=${cycles}`, 'POST');
        if(pStatus) pStatus.textContent = 'Completed all comparison cycles!';
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
    const dlContainer = document.getElementById('cmp-download-btn-container');

    if(panel) panel.classList.remove('hidden');
    if(tsEl) tsEl.textContent = `Run at: ${formatLocalTime(comp.timestamp)} (${comp.cycles_per_strategy} cycles/strategy)`;

    if(dlContainer && comp.id) {
        dlContainer.innerHTML = `
            <a href="/api/experiments/comparison/${comp.id}/csv" target="_blank" style="text-decoration:none;">
                <button class="btn-secondary" style="font-size:11px; padding:6px 12px;">
                    Download CSV
                </button>
            </a>
        `;
    }

    const strats = ['A', 'B', 'C'];
    if(tbody) {
        tbody.innerHTML = strats.map(s => {
            const data = comp.strategies[s] || { runs: 0, success_rate: 0, leak_rate: 0, runs_with_in_flight: 0, leak_rate_in_flight: 0, mean_revocation_latency: 0, mean_total_revocation_time: 0, mean_cycle_duration: 0, mean_residual_risk: 0 };
            return `
                <tr>
                    <td style="font-weight:700; color:var(--accent-red);">Strategy ${s}</td>
                    <td>${data.runs}</td>
                    <td>
                        <span class="badge ${data.success_rate >= 80 ? 'success' : (data.success_rate >= 40 ? 'warning' : 'danger')}">
                            ${data.success_rate.toFixed(1)}%
                        </span>
                    </td>
                    <td style="color:${data.leak_rate > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:700;">
                        ${data.leak_rate.toFixed(1)}%
                    </td>
                    <td>${data.runs_with_in_flight || 0}</td>
                    <td style="color:${data.leak_rate_in_flight > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:700;">
                        ${data.runs_with_in_flight > 0 ? (data.leak_rate_in_flight.toFixed(1) + '%') : 'n/a'}
                    </td>
                    <td style="font-family:var(--font-mono);">${(data.mean_revocation_latency || 0).toFixed(1)} ms</td>
                    <td style="font-family:var(--font-mono);">${(data.mean_total_revocation_time || data.mean_revocation_latency || 0).toFixed(1)} ms</td>
                    <td style="font-family:var(--font-mono);">${(data.mean_cycle_duration || data.mean_total_revocation_time || 0).toFixed(1)} ms</td>
                    <td style="font-family:var(--font-mono); font-weight:600;">${(data.mean_residual_risk * 100).toFixed(1)}%</td>
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
    const leakRatesAll = ['A', 'B', 'C'].map(s => strategies[s] ? strategies[s].leak_rate : 0);
    const leakRatesInFlight = ['A', 'B', 'C'].map(s => strategies[s] ? strategies[s].leak_rate_in_flight : 0);
    const perChanLatencies = ['A', 'B', 'C'].map(s => strategies[s] ? (strategies[s].mean_revocation_latency || 0) : 0);
    const totalRevTimes = ['A', 'B', 'C'].map(s => strategies[s] ? (strategies[s].mean_total_revocation_time || strategies[s].mean_revocation_latency || 0) : 0);

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
                    borderRadius: 4,
                    yAxisID: 'y'
                },
                {
                    label: 'Leak Rate (All Runs) (%)',
                    data: leakRatesAll,
                    backgroundColor: 'rgba(244, 63, 94, 0.75)',
                    borderColor: '#f43f5e',
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: 'y'
                },
                {
                    label: 'Leak Rate (Exposed Runs) (%)',
                    data: leakRatesInFlight,
                    backgroundColor: 'rgba(234, 179, 8, 0.75)',
                    borderColor: '#eab308',
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: 'y'
                },
                {
                    label: 'Per-Channel Latency (ms)',
                    data: perChanLatencies,
                    backgroundColor: 'rgba(56, 189, 248, 0.75)',
                    borderColor: '#38bdf8',
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: 'y1'
                },
                {
                    label: 'Total Revocation Time (ms)',
                    data: totalRevTimes,
                    backgroundColor: 'rgba(168, 85, 247, 0.75)',
                    borderColor: '#a855f7',
                    borderWidth: 1,
                    borderRadius: 4,
                    yAxisID: 'y1'
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    beginAtZero: true,
                    max: 100,
                    title: { display: true, text: 'Percentage (%)', color: '#10b981' },
                    grid: { color: '#f1f5f9' },
                    ticks: { color: '#64748b', callback: (v) => v + '%' }
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    beginAtZero: true,
                    title: { display: true, text: 'Latency (ms)', color: '#0284c7' },
                    grid: { drawOnChartArea: false },
                    ticks: { color: '#64748b', callback: (v) => v + ' ms' }
                },
                x: {
                    ticks: { color: '#0f172a', font: { weight: 'bold' } },
                    grid: { display: false }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#0f172a', boxWidth: 12 }
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
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:25px; color:var(--text-muted);">No comparison runs recorded yet. Click 'Run Comparison' above to evaluate Strategies A, B, and C.</td></tr>`;
            return;
        }

        tbody.innerHTML = history.map((item) => {
            const stA = item.strategies && item.strategies.A ? `${item.strategies.A.success_rate.toFixed(0)}% / ${item.strategies.A.leak_rate.toFixed(0)}%` : '--';
            const stB = item.strategies && item.strategies.B ? `${item.strategies.B.success_rate.toFixed(0)}% / ${item.strategies.B.leak_rate.toFixed(0)}%` : '--';
            const stC = item.strategies && item.strategies.C ? `${item.strategies.C.success_rate.toFixed(0)}% / ${item.strategies.C.leak_rate.toFixed(0)}%` : '--';
            return `
                <tr>
                    <td style="font-size:11px; color:var(--text-muted);">${formatLocalTime(item.timestamp)}</td>
                    <td style="font-family:var(--font-mono); font-weight:700;">${item.cycles_per_strategy}</td>
                    <td style="font-family:var(--font-mono);">${stA}</td>
                    <td style="font-family:var(--font-mono);">${stB}</td>
                    <td style="font-family:var(--font-mono);">${stC}</td>
                    <td style="display:flex; gap:6px;">
                        <button class="btn-secondary" onclick='window.renderComparisonResults(${JSON.stringify(item)})' style="padding:3px 8px; font-size:10px;">
                            View
                        </button>
                        <a href="/api/experiments/comparison/${item.id}/csv" target="_blank" style="text-decoration:none;">
                            <button class="btn-secondary" style="padding:3px 8px; font-size:10px;">
                                CSV
                            </button>
                        </a>
                    </td>
                </tr>
            `;
        }).join('');

        const panel = document.getElementById('cmp-results-panel');
        if(panel && panel.classList.contains('hidden') && history.length > 0) {
            renderComparisonResults(history[0]);
        }
    } catch(e) {
        console.error('Error loading comparison history:', e);
    }
};

window.cleanup_experiments = function() {
    window.removeEventListener('ws_comparison_progress', window.handleComparisonProgress);
    if(comparisonChart) {
        comparisonChart.destroy();
        comparisonChart = null;
    }
};
