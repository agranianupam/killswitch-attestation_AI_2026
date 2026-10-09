/*
static/js/dashboard.js — Verifiable Kill-Switch Real-Time Dashboard
*/

window.dashboardCharts = {};

function destroyDashboardCharts() {
    for (const key in window.dashboardCharts) {
        if (window.dashboardCharts[key]) {
            try { window.dashboardCharts[key].destroy(); } catch (e) {}
            delete window.dashboardCharts[key];
        }
    }
}

window.render_dashboard = async function(container) {
    destroyDashboardCharts();

    container.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; flex-wrap: wrap; gap: 15px;">
            <div>
                <h2 style="margin:0; font-size:28px; font-weight:800; background: linear-gradient(90deg, #fff, var(--neon-blue)); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">Verifiable Kill-Switch Attestation</h2>
                <p style="color: var(--text-muted); margin-top: 5px; font-size: 13px;">Real-time cryptographic verification & containment telemetry</p>
            </div>
            <div style="display: flex; gap: 12px; align-items: center;">
                <button class="danger" id="initiate-shutdown-btn" onclick="window.runManualShutdown()" style="font-size: 15px; font-weight: bold; padding: 14px 28px; letter-spacing: 1px; box-shadow: 0 0 15px var(--danger-glow);">
                    ⚡ INITIATE SHUTDOWN
                </button>
            </div>
        </div>
        
        <!-- (1) KPI Header -->
        <div class="metrics-grid" style="margin-bottom: 25px;">
            <div class="metric-card">
                <div class="metric-val" id="kpi-total">0</div>
                <div class="metric-label">Total Tests</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" id="kpi-success">--</div>
                <div class="metric-label">Success Rate</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" id="kpi-latency">-- ms</div>
                <div class="metric-label">Mean Revocation Latency</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" id="kpi-leaks">0</div>
                <div class="metric-label">Leaks Detected</div>
            </div>
            <div class="metric-card">
                <div class="metric-val" id="kpi-chain" style="font-size: 20px;">--</div>
                <div class="metric-label">Chain Integrity</div>
            </div>
        </div>

        <!-- Controls & Live Console Grid -->
        <div class="dashboard-grid" style="margin-bottom: 25px;">
            <div class="panel">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px;">
                    <h3 style="margin: 0; color: var(--neon-purple); font-size: 16px;">⚙️ Simulation Settings & Batch</h3>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 12px; color: var(--text-muted);">Scheduler:</span>
                        <span id="dash-sched-badge" class="badge" style="background:#333; color:#aaa; font-size: 10px;">OFF</span>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                    <label>Delay Min (ms): <input type="number" id="sim-delay-min" value="50" style="width:100%; margin-top:4px;" /></label>
                    <label>Delay Max (ms): <input type="number" id="sim-delay-max" value="200" style="width:100%; margin-top:4px;" /></label>
                    <label>Revoke Fail Prob: <input type="number" step="0.05" id="sim-fail-prob" value="0.0" style="width:100%; margin-top:4px;" /></label>
                    <label>IAM Fail Prob: <input type="number" step="0.05" id="sim-iam-prob" value="0.15" style="width:100%; margin-top:4px;" /></label>
                    <label style="grid-column: span 2;">In-Flight Leak Prob: <input type="number" step="0.05" id="sim-leak-prob" value="0.2" style="width:100%; margin-top:4px;" /></label>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 15px;">
                    <button class="secondary" onclick="window.saveSettings()" style="flex: 1; font-size: 12px;">Save Settings</button>
                </div>
                <hr style="border: 0; border-top: 1px solid var(--border); margin: 15px 0;">
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="number" id="n-tests-input" value="5" min="1" max="50" style="width: 80px;" title="N cycles (max 50)" />
                    <button id="run-n-btn" onclick="window.runNTests()" style="flex: 1; font-size: 13px;">Run N Tests</button>
                </div>
            </div>
            
            <!-- (2) Live Console & Per-Channel Tiles -->
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--border); padding-bottom: 10px; margin-bottom: 15px;">
                    <h3 style="margin: 0; color: var(--neon-blue); font-size: 16px;">(2) Live Revocation Console & Tiles</h3>
                    <span id="console-phase-badge" class="badge" style="background:#222; font-size:10px;">READY</span>
                </div>
                <div id="channel-tiles" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px;">
                    <div id="tile-api_key" class="channel-tile" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 6px; padding: 8px; text-align: center; font-size: 11px;">
                        <div style="color:var(--text-muted); font-weight:bold;">API_KEY</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:bold; color:#777;">IDLE</div>
                    </div>
                    <div id="tile-session_token" class="channel-tile" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 6px; padding: 8px; text-align: center; font-size: 11px;">
                        <div style="color:var(--text-muted); font-weight:bold;">SESSION</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:bold; color:#777;">IDLE</div>
                    </div>
                    <div id="tile-iam_role" class="channel-tile" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 6px; padding: 8px; text-align: center; font-size: 11px;">
                        <div style="color:var(--text-muted); font-weight:bold;">IAM_ROLE</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:bold; color:#777;">IDLE</div>
                    </div>
                    <div id="tile-network_proxy" class="channel-tile" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border); border-radius: 6px; padding: 8px; text-align: center; font-size: 11px;">
                        <div style="color:var(--text-muted); font-weight:bold;">NETWORK</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:bold; color:#777;">IDLE</div>
                    </div>
                </div>
                <div id="live-console" style="height: 120px; overflow-y: auto; background: #0c0c0e; padding: 10px; font-family: monospace; font-size: 11px; border: 1px solid var(--border); border-radius: 6px; line-height: 1.5; color: #a1a1aa;">
                    <div>[READY] Press 'Initiate Shutdown' to execute a live verified cycle.</div>
                </div>
            </div>
        </div>
        
        <!-- Charts Row 1: (3) & (4) -->
        <div class="dashboard-grid" style="margin-bottom: 25px;">
            <div class="panel">
                <h3 style="margin-top:0; font-size: 15px; color: var(--accent);">(3) Per-Channel Latency Distribution</h3>
                <div id="latency-container" style="height: 220px; position: relative;">
                    <canvas id="latencyChart"></canvas>
                    <div id="latency-empty" class="empty-state" style="display:none; position:absolute; inset:0; align-items:center; justify-content:center; color:var(--text-muted); font-size:12px; text-align:center;">
                        No revocation latency records in DB yet. Run a shutdown test to populate.
                    </div>
                </div>
            </div>
            <div class="panel">
                <h3 style="margin-top:0; font-size: 15px; color: var(--primary);">(4) 2x2 Outcome Matrix (Revocation vs In-Flight Leaks)</h3>
                <div id="matrix-container" style="height: 220px; position: relative;">
                    <div id="matrix-grid-view" style="display:grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 8px; height: 100%;">
                        <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 6px; padding: 10px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                            <span style="font-size: 11px; color: var(--success); font-weight:bold;">Revoke PASS / No Leak</span>
                            <span id="mat-pass-no-leak" style="font-size: 24px; font-weight:800; color: #fff; margin-top:4px;">0</span>
                        </div>
                        <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 6px; padding: 10px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                            <span style="font-size: 11px; color: var(--warning); font-weight:bold;">Revoke PASS / Leak Detected</span>
                            <span id="mat-pass-with-leak" style="font-size: 24px; font-weight:800; color: #fff; margin-top:4px;">0</span>
                        </div>
                        <div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: 6px; padding: 10px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                            <span style="font-size: 11px; color: var(--warning); font-weight:bold;">Revoke FAIL / No Leak</span>
                            <span id="mat-fail-no-leak" style="font-size: 24px; font-weight:800; color: #fff; margin-top:4px;">0</span>
                        </div>
                        <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 6px; padding: 10px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
                            <span style="font-size: 11px; color: var(--danger); font-weight:bold;">Revoke FAIL / Leak Detected</span>
                            <span id="mat-fail-with-leak" style="font-size: 24px; font-weight:800; color: #fff; margin-top:4px;">0</span>
                        </div>
                    </div>
                    <div id="matrix-empty" class="empty-state" style="display:none; position:absolute; inset:0; align-items:center; justify-content:center; color:var(--text-muted); font-size:12px; background:var(--bg-panel); text-align:center;">
                        No outcome matrix data available.
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Charts Row 2: (5) & (6) -->
        <div class="dashboard-grid" style="margin-bottom: 25px;">
            <div class="panel">
                <h3 style="margin-top:0; font-size: 15px; color: #f43f5e;">(5) In-Flight Leak Timeline (Relative to Shutdown)</h3>
                <div id="timeline-container" style="height: 220px; position: relative;">
                    <canvas id="timelineChart"></canvas>
                    <div id="timeline-empty" class="empty-state" style="display:none; position:absolute; inset:0; align-items:center; justify-content:center; color:var(--text-muted); font-size:12px; text-align:center;">
                        No in-flight leaks recorded. All operations contained before or at shutdown.
                    </div>
                </div>
            </div>
            <div class="panel">
                <h3 style="margin-top:0; font-size: 15px; color: #38bdf8;">(6) Success Rate & Latency Trend per Test Run</h3>
                <div id="trend-container" style="height: 220px; position: relative;">
                    <canvas id="trendChart"></canvas>
                    <div id="trend-empty" class="empty-state" style="display:none; position:absolute; inset:0; align-items:center; justify-content:center; color:var(--text-muted); font-size:12px; text-align:center;">
                        No test run trends available yet.
                    </div>
                </div>
            </div>
        </div>

        <!-- Attestation & KILLBENCH: (7) & (8) -->
        <div class="dashboard-grid" style="margin-bottom: 25px;">
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;">
                    <h3 style="margin:0; font-size: 15px; color: var(--success);">(7) Attestation Explorer</h3>
                    <div style="display:flex; gap: 8px;">
                        <button id="verify-chain-btn" class="secondary" onclick="window.verifyChain()" style="font-size: 11px; padding: 4px 10px;">Verify Chain</button>
                        <button id="export-report-btn" class="secondary" onclick="window.exportReport()" style="font-size: 11px; padding: 4px 10px;">Export Report</button>
                    </div>
                </div>
                <div id="attestation-explorer" style="font-family: monospace; font-size: 11px; background: #0c0c0e; border: 1px solid var(--border); border-radius: 6px; padding: 12px; min-height: 140px; overflow-y: auto;">
                    <div style="color:var(--text-muted); text-align:center; padding: 30px;">Cryptographic chain is empty (Genesis). Run a test to commit entries.</div>
                </div>
            </div>
            <div class="panel">
                <h3 style="margin-top:0; font-size: 15px; color: var(--warning);">(8) KILLBENCH Comparison</h3>
                <div id="killbench-data" style="font-size: 12px; background: #0c0c0e; border: 1px solid var(--border); border-radius: 6px; padding: 15px; min-height: 140px; display:flex; flex-direction:column; justify-content:center;">
                    <div style="color:var(--text-muted); text-align:center;">Loading KILLBENCH comparison...</div>
                </div>
            </div>
        </div>

        <!-- History: (9) -->
        <div class="panel">
            <h3 style="margin-top:0; font-size: 16px; color: var(--text-main); margin-bottom: 15px;">(9) Test History Table</h3>
            <div style="overflow-x: auto;">
                <table id="history-table" style="width: 100%; border-collapse: collapse; font-size: 12px;">
                    <thead>
                        <tr style="border-bottom: 1px solid var(--border); color: var(--text-muted); text-align: left;">
                            <th style="padding: 8px;">Test ID</th>
                            <th style="padding: 8px;">Trigger Time</th>
                            <th style="padding: 8px;">Triggered By</th>
                            <th style="padding: 8px;">Strategy</th>
                            <th style="padding: 8px;">Final State</th>
                            <th style="padding: 8px;">Residual Risk</th>
                            <th style="padding: 8px;">Leaks</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding: 30px;">No shutdown tests executed yet. Click "Initiate Shutdown" to begin.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    // Register event listeners
    window.addEventListener('ws_shutdown_progress', window.handleWsProgress);
    window.addEventListener('ws_credential_update', window.handleWsCredUpdate);
    window.addEventListener('ws_batch_progress', window.handleWsBatchProgress);
    window.addEventListener('ws_shutdown_complete', window.handleWsShutdownComplete);

    await window.loadInitialSettings();
    await window.refreshDashboard();
};

window.cleanup_dashboard = function() {
    window.removeEventListener('ws_shutdown_progress', window.handleWsProgress);
    window.removeEventListener('ws_credential_update', window.handleWsCredUpdate);
    window.removeEventListener('ws_batch_progress', window.handleWsBatchProgress);
    window.removeEventListener('ws_shutdown_complete', window.handleWsShutdownComplete);
    destroyDashboardCharts();
};

window.logConsole = function(msg) {
    const cons = document.getElementById('live-console');
    if(!cons) return;
    const time = new Date().toLocaleTimeString();
    cons.innerHTML += `<div><span style="color:var(--neon-blue)">[${time}]</span> ${msg}</div>`;
    cons.scrollTop = cons.scrollHeight;
};

window.resetChannelTiles = function() {
    ['api_key', 'session_token', 'iam_role', 'network_proxy'].forEach(ch => {
        const tile = document.getElementById(`tile-${ch}`);
        if(tile) {
            tile.style.borderColor = 'var(--border)';
            tile.style.background = 'rgba(255,255,255,0.05)';
            const st = tile.querySelector('.tile-status');
            if(st) { st.textContent = 'PENDING'; st.style.color = '#a1a1aa'; }
        }
    });
};

window.updateChannelTile = function(channelType, success, latency) {
    const tile = document.getElementById(`tile-${channelType}`);
    if(!tile) return;
    if(success) {
        tile.style.borderColor = '#10b981';
        tile.style.background = 'rgba(16, 185, 129, 0.15)';
        const st = tile.querySelector('.tile-status');
        if(st) { st.textContent = `REVOKED (${latency || 0}ms)`; st.style.color = '#10b981'; }
    } else {
        tile.style.borderColor = '#ef4444';
        tile.style.background = 'rgba(239, 68, 68, 0.15)';
        const st = tile.querySelector('.tile-status');
        if(st) { st.textContent = 'FAILED'; st.style.color = '#ef4444'; }
    }
};

window.runManualShutdown = async function() {
    const btn = document.getElementById('initiate-shutdown-btn');
    const runNBtn = document.getElementById('run-n-btn');
    if(btn) btn.disabled = true;
    if(runNBtn) runNBtn.disabled = true;

    window.resetChannelTiles();
    window.logConsole("Initiating manual verified shutdown cycle...");
    const phaseBadge = document.getElementById('console-phase-badge');
    if(phaseBadge) { phaseBadge.textContent = "RUNNING"; phaseBadge.style.color = "var(--warning)"; }

    try {
        const res = await apiCall('/api/shutdown?strategy=A&trigger_type=manual', 'POST');
        window.logConsole(`Shutdown cycle finished. Final State: ${res.final_state}, Residual Risk: ${res.residual_risk}`);
    } catch(e) {
        window.logConsole(`Error during shutdown: ${e.message || JSON.stringify(e)}`);
    } finally {
        if(btn) btn.disabled = false;
        if(runNBtn) runNBtn.disabled = false;
        if(phaseBadge) { phaseBadge.textContent = "READY"; phaseBadge.style.color = "#777"; }
        await window.refreshDashboard();
    }
};

window.runNTests = async function() {
    const input = document.getElementById('n-tests-input');
    const n = Math.min(Math.max(parseInt(input.value) || 1, 1), 50);
    const btn = document.getElementById('initiate-shutdown-btn');
    const runNBtn = document.getElementById('run-n-btn');
    if(btn) btn.disabled = true;
    if(runNBtn) runNBtn.disabled = true;

    window.logConsole(`Executing batch of ${n} sequential tests...`);
    const phaseBadge = document.getElementById('console-phase-badge');
    if(phaseBadge) { phaseBadge.textContent = `BATCH (0/${n})`; phaseBadge.style.color = "var(--warning)"; }

    try {
        const res = await apiCall(`/api/shutdown/batch?count=${n}&strategy=A`, 'POST');
        window.logConsole(`Completed batch run of ${res.completed} tests.`);
    } catch(e) {
        window.logConsole(`Batch error: ${e.message || JSON.stringify(e)}`);
    } finally {
        if(btn) btn.disabled = false;
        if(runNBtn) runNBtn.disabled = false;
        if(phaseBadge) { phaseBadge.textContent = "READY"; phaseBadge.style.color = "#777"; }
        await window.refreshDashboard();
    }
};

window.loadInitialSettings = async function() {
    try {
        const s = await apiCall('/api/shutdown/settings');
        if(s) {
            if(document.getElementById('sim-delay-min')) document.getElementById('sim-delay-min').value = s.net_delay_min;
            if(document.getElementById('sim-delay-max')) document.getElementById('sim-delay-max').value = s.net_delay_max;
            if(document.getElementById('sim-fail-prob')) document.getElementById('sim-fail-prob').value = s.revoke_failure_prob;
            if(document.getElementById('sim-iam-prob')) document.getElementById('sim-iam-prob').value = s.iam_failure_prob;
            if(document.getElementById('sim-leak-prob')) document.getElementById('sim-leak-prob').value = s.in_flight_leak_prob;
        }
        // Update scheduler status
        const sched = await apiCall('/api/scheduler/status');
        const schedToggle = document.getElementById('scheduler-toggle');
        const schedBadge = document.getElementById('dash-sched-badge');
        const schedText = document.getElementById('scheduler-status-text');
        const isRunning = sched && sched.running;
        if(schedToggle) schedToggle.checked = isRunning;
        if(schedBadge) {
            schedBadge.textContent = isRunning ? "ON" : "OFF";
            schedBadge.style.color = isRunning ? "var(--success)" : "#aaa";
        }
        if(schedText) {
            schedText.textContent = isRunning ? "ON" : "OFF";
            schedText.style.color = isRunning ? "var(--success)" : "var(--text-muted)";
        }
    } catch(e) {}
};

window.saveSettings = async function() {
    const s = {
        net_delay_min: parseInt(document.getElementById('sim-delay-min').value),
        net_delay_max: parseInt(document.getElementById('sim-delay-max').value),
        revoke_failure_prob: parseFloat(document.getElementById('sim-fail-prob').value),
        iam_failure_prob: parseFloat(document.getElementById('sim-iam-prob').value),
        in_flight_leak_prob: parseFloat(document.getElementById('sim-leak-prob').value)
    };
    try {
        await apiCall('/api/shutdown/settings', 'POST', s);
        window.logConsole("Simulation settings updated successfully.");
        alert("Simulation settings saved.");
    } catch(e) {
        alert("Failed to save settings: " + e.message);
    }
};

window.toggleScheduler = async function(enabled) {
    try {
        const res = await apiCall('/api/scheduler/toggle', 'POST', { enabled, mode: 'fixed', strategy: 'A' });
        const schedBadge = document.getElementById('dash-sched-badge');
        const schedText = document.getElementById('scheduler-status-text');
        const isRunning = res && res.running;
        if(schedBadge) {
            schedBadge.textContent = isRunning ? "ON" : "OFF";
            schedBadge.style.color = isRunning ? "var(--success)" : "#aaa";
        }
        if(schedText) {
            schedText.textContent = isRunning ? "ON" : "OFF";
            schedText.style.color = isRunning ? "var(--success)" : "var(--text-muted)";
        }
        window.logConsole(`Scheduler toggled ${isRunning ? 'ON' : 'OFF'}.`);
    } catch(e) {
        alert("Scheduler toggle failed: " + e.message);
    }
};

window.verifyChain = async function() {
    try {
        const res = await apiCall('/api/shutdown/verify');
        const chainEl = document.getElementById('kpi-chain');
        if(chainEl) {
            chainEl.textContent = res.status.toUpperCase();
            chainEl.style.color = res.status === 'valid' ? 'var(--success)' : 'var(--danger)';
        }
        alert(res.message);
    } catch(e) {
        alert("Verification failed: " + e.message);
    }
};

window.exportReport = async function() {
    try {
        const history = await apiCall('/api/shutdown/history');
        if(!history || history.length === 0) {
            return alert("No shutdown records available to export.");
        }
        const latestId = history[0].id;
        window.open(`/api/audit/export/${latestId}`, '_blank');
    } catch(e) {
        alert("Export failed: " + e.message);
    }
};

window.refreshDashboard = async function() {
    try {
        const summary = await apiCall('/api/analytics/summary');
        const history = await apiCall('/api/shutdown/history');
        const verifyRes = await apiCall('/api/shutdown/verify');
        const killbench = await apiCall('/api/analytics/killbench-comparison');
        const entries = await apiCall('/api/audit/entries');

        const hasData = summary && summary.total_shutdowns > 0;

        // (1) KPIs
        if(document.getElementById('kpi-total')) document.getElementById('kpi-total').textContent = summary.total_shutdowns || 0;
        if(document.getElementById('kpi-success')) document.getElementById('kpi-success').textContent = hasData ? `${summary.success_rate}%` : '--';
        if(document.getElementById('kpi-latency')) document.getElementById('kpi-latency').textContent = hasData ? `${summary.mean_latency_ms} ms` : '-- ms';
        if(document.getElementById('kpi-leaks')) document.getElementById('kpi-leaks').textContent = summary.total_leaks || 0;
        if(document.getElementById('kpi-chain')) {
            const chainEl = document.getElementById('kpi-chain');
            const status = verifyRes && verifyRes.status ? verifyRes.status.toUpperCase() : 'VALID';
            chainEl.textContent = status;
            chainEl.style.color = status === 'VALID' ? 'var(--success)' : 'var(--danger)';
        }

        // (3) Latency Chart
        const latEmpty = document.getElementById('latency-empty');
        const latCanvas = document.getElementById('latencyChart');
        if(!hasData || !summary.channel_latencies || Object.keys(summary.channel_latencies).length === 0) {
            if(latEmpty) latEmpty.style.display = 'flex';
            if(latCanvas) latCanvas.style.display = 'none';
        } else {
            if(latEmpty) latEmpty.style.display = 'none';
            if(latCanvas) latCanvas.style.display = 'block';
            
            const channels = Object.keys(summary.channel_latencies);
            const averages = channels.map(ch => {
                const arr = summary.channel_latencies[ch];
                return arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1) : 0;
            });

            if(window.dashboardCharts.latency) window.dashboardCharts.latency.destroy();
            window.dashboardCharts.latency = new Chart(latCanvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: channels,
                    datasets: [{
                        label: 'Mean Latency (ms)',
                        data: averages,
                        backgroundColor: '#06b6d4',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#a1a1aa' } },
                        x: { ticks: { color: '#a1a1aa' }, grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // (4) 2x2 Outcome Matrix
        const matEmpty = document.getElementById('matrix-empty');
        const matGrid = document.getElementById('matrix-grid-view');
        if(!hasData) {
            if(matEmpty) matEmpty.style.display = 'flex';
            if(matGrid) matGrid.style.display = 'none';
        } else {
            if(matEmpty) matEmpty.style.display = 'none';
            if(matGrid) matGrid.style.display = 'grid';
            const m = summary.outcome_matrix_2x2 || {};
            if(document.getElementById('mat-pass-no-leak')) document.getElementById('mat-pass-no-leak').textContent = m.pass_no_leak || 0;
            if(document.getElementById('mat-pass-with-leak')) document.getElementById('mat-pass-with-leak').textContent = m.pass_with_leak || 0;
            if(document.getElementById('mat-fail-no-leak')) document.getElementById('mat-fail-no-leak').textContent = m.fail_no_leak || 0;
            if(document.getElementById('mat-fail-with-leak')) document.getElementById('mat-fail-with-leak').textContent = m.fail_with_leak || 0;
        }

        // (5) In-Flight Leak Timeline
        const timeEmpty = document.getElementById('timeline-empty');
        const timeCanvas = document.getElementById('timelineChart');
        const leaks = summary.in_flight_leaks_timeline || [];
        if(!hasData || leaks.length === 0) {
            if(timeEmpty) timeEmpty.style.display = 'flex';
            if(timeCanvas) timeCanvas.style.display = 'none';
        } else {
            if(timeEmpty) timeEmpty.style.display = 'none';
            if(timeCanvas) timeCanvas.style.display = 'block';

            if(window.dashboardCharts.timeline) window.dashboardCharts.timeline.destroy();
            window.dashboardCharts.timeline = new Chart(timeCanvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: leaks.map((l, i) => `#${i+1} (${l.operation_type})`),
                    datasets: [{
                        label: 'Delay past shutdown (ms)',
                        data: leaks.map(l => l.relative_ms),
                        backgroundColor: '#f43f5e',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#a1a1aa' } },
                        x: { ticks: { color: '#a1a1aa' }, grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // (6) Trend Chart
        const trendEmpty = document.getElementById('trend-empty');
        const trendCanvas = document.getElementById('trendChart');
        const trends = summary.runs_trend || [];
        if(!hasData || trends.length === 0) {
            if(trendEmpty) trendEmpty.style.display = 'flex';
            if(trendCanvas) trendCanvas.style.display = 'none';
        } else {
            if(trendEmpty) trendEmpty.style.display = 'none';
            if(trendCanvas) trendCanvas.style.display = 'block';

            if(window.dashboardCharts.trend) window.dashboardCharts.trend.destroy();
            window.dashboardCharts.trend = new Chart(trendCanvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: trends.map(t => `Run ${t.run_index}`),
                    datasets: [
                        {
                            label: 'Latency (ms)',
                            data: trends.map(t => t.mean_latency_ms),
                            borderColor: '#38bdf8',
                            backgroundColor: 'rgba(56, 189, 248, 0.1)',
                            yAxisID: 'y'
                        },
                        {
                            label: 'Success (1=Pass, 0=Fail)',
                            data: trends.map(t => t.success),
                            borderColor: '#10b981',
                            stepped: true,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { position: 'left', beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#38bdf8' } },
                        y1: { position: 'right', min: 0, max: 1.2, grid: { display: false }, ticks: { color: '#10b981', stepSize: 1 } },
                        x: { ticks: { color: '#a1a1aa' }, grid: { display: false } }
                    }
                }
            });
        }

        // (7) Attestation Explorer
        const explorer = document.getElementById('attestation-explorer');
        if(explorer) {
            if(!entries || entries.length === 0) {
                explorer.innerHTML = `<div style="color:var(--text-muted); text-align:center; padding: 30px;">Cryptographic chain is empty (Genesis). Run a test to commit entries.</div>`;
            } else {
                explorer.innerHTML = entries.slice(0, 5).map(e => `
                    <div style="border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 8px; margin-bottom: 8px;">
                        <div><strong style="color:var(--neon-blue)">ENTRY:</strong> ${e.entry_hash}</div>
                        <div style="color:var(--text-muted)"><strong>PREV:</strong> ${e.prev_hash}</div>
                        <div style="color:#71717a"><strong>SIG:</strong> ${e.signature.substring(0, 32)}...</div>
                    </div>
                `).join('');
            }
        }

        // (8) KILLBENCH Comparison
        const kbEl = document.getElementById('killbench-data');
        if(kbEl) {
            if(!killbench || killbench.status === 'empty' || !killbench.system_metrics) {
                kbEl.innerHTML = `<div style="color:var(--text-muted); text-align:center;">${killbench ? killbench.message : 'No benchmark records available.'}</div>`;
            } else {
                const m = killbench.system_metrics;
                kbEl.innerHTML = `
                    <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                        <span style="color:var(--text-muted)">Tested Runs:</span> <strong>${m.total_runs}</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                        <span style="color:var(--text-muted)">Live Success Rate:</span> <strong style="color:var(--success)">${m.success_rate_percent}%</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                        <span style="color:var(--text-muted)">Mean Revocation Latency:</span> <strong>${m.mean_revocation_latency_ms} ms</strong>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
                        <span style="color:var(--text-muted)">Total Leaks:</span> <strong style="color:${m.total_leaks_detected > 0 ? 'var(--danger)' : 'var(--success)'}">${m.total_leaks_detected}</strong>
                    </div>
                    <div style="margin-top:8px; padding-top:8px; border-top:1px solid var(--border); font-size:11px; color:#888;">
                        Baseline: ${killbench.killbench_baseline ? killbench.killbench_baseline.status : 'External dataset unconfigured'}
                    </div>
                `;
            }
        }

        // (9) Test History Table
        const tbody = document.querySelector('#history-table tbody');
        if(tbody) {
            if(!history || history.length === 0) {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding: 30px;">No shutdown tests executed yet. Click "Initiate Shutdown" to begin.</td></tr>`;
            } else {
                tbody.innerHTML = history.map(h => {
                    const isTerm = h.final_state === 'TERMINATED';
                    const badgeClass = isTerm ? 'success' : 'danger';
                    const trigTime = h.trigger_timestamp ? new Date(h.trigger_timestamp).toLocaleString() : new Date(h.started_at).toLocaleString();
                    return `
                        <tr style="border-bottom: 1px solid rgba(255,255,255,0.04);">
                            <td style="padding:8px; font-family:monospace; color:var(--text-muted);">${h.id.substring(0,8)}</td>
                            <td style="padding:8px;">${trigTime}</td>
                            <td style="padding:8px;"><span class="badge" style="background:#222; font-size:10px;">${h.triggered_by || h.trigger_type || 'manual'}</span></td>
                            <td style="padding:8px;">Strategy ${h.strategy}</td>
                            <td style="padding:8px;"><span class="badge ${badgeClass}" style="font-size:10px;">${h.final_state}</span></td>
                            <td style="padding:8px;">${(h.residual_risk * 100).toFixed(1)}%</td>
                            <td style="padding:8px; color:${(h.in_flight_failures || 0) > 0 ? 'var(--danger)' : '#aaa'}">${h.in_flight_failures || 0}</td>
                        </tr>
                    `;
                }).join('');
            }
        }
    } catch(e) {
        console.error("Dashboard refresh error:", e);
    }
};

window.handleWsProgress = function(e) {
    if(e.detail && e.detail.stage) {
        window.logConsole(`[${e.detail.stage.toUpperCase()}] ${e.detail.detail || ''}`);
        const phaseBadge = document.getElementById('console-phase-badge');
        if(phaseBadge) phaseBadge.textContent = e.detail.stage.toUpperCase();
    }
};

window.handleWsCredUpdate = function(e) {
    if(e.detail && e.detail.channel_type) {
        const isRevoked = e.detail.status === 'REVOKED';
        window.updateChannelTile(e.detail.channel_type, isRevoked);
        window.logConsole(`Channel ${e.detail.channel_type}: ${e.detail.status}`);
    }
};

window.handleWsBatchProgress = function(e) {
    if(e.detail) {
        window.logConsole(`Batch progress: cycle ${e.detail.cycle}/${e.detail.total}`);
        const phaseBadge = document.getElementById('console-phase-badge');
        if(phaseBadge) phaseBadge.textContent = `BATCH (${e.detail.cycle}/${e.detail.total})`;
    }
};

window.handleWsShutdownComplete = function(e) {
    window.refreshDashboard();
};
