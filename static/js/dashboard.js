window.dashboardCharts = {};

function destroyDashboardCharts() {
    for (const key in window.dashboardCharts) {
        if (window.dashboardCharts[key]) {
            try { window.dashboardCharts[key].destroy(); } catch (e) {}
            delete window.dashboardCharts[key];
        }
    }
}

function formatLocalTime(isoStr) {
    if (!isoStr) return '--';
    const s = isoStr.endsWith('Z') || isoStr.includes('+') ? isoStr : isoStr + 'Z';
    try {
        const d = new Date(s);
        if (isNaN(d.getTime())) return isoStr;
        return d.toLocaleString();
    } catch (e) {
        return isoStr;
    }
}

window.render_dashboard = async function(container) {
    window.cleanup_dashboard();

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
                <path d="M10,80 L10,86 M7,83 L13,83" stroke="#475569" stroke-width="1.2"/>
            </svg>
        </div>

        <!-- Hero Header & Controls -->
        <div class="view-hero">
            <div class="hero-text">
                <div class="hero-kicker">Live Monitoring</div>
                <h1 class="hero-title">
                    Verifiable <span class="highlight-red">AI Agent</span> Kill-Switch Attestation
                </h1>
                <p class="hero-subtitle">
                    Real-time monitoring, cryptographic verification and containment telemetry.
                </p>
            </div>

            <div class="top-controls-container">
                <div class="agent-badge-card">
                    <div class="agent-icon">🤖</div>
                    <div class="agent-details">
                        <div class="agent-title-row">
                            <span class="agent-name" id="top-agent-name">Sandboxed-Agent-cda59b30</span>
                            <span class="agent-status-dot" id="top-agent-status">● Active</span>
                        </div>
                        <div class="agent-meta-row">
                            <span>Model: <strong id="top-agent-model">Gemini (Simulated)</strong></span>
                            <span style="opacity:0.4;">|</span>
                            <span>Runtime: <strong id="top-agent-runtime">Sandbox</strong></span>
                        </div>
                    </div>
                </div>

                <div class="action-bar-row">
                    <label class="scripted-checkbox-label">
                        <input type="checkbox" id="include-scripted-toggle" onchange="State.includeScripted = this.checked; window.refreshDashboard();">
                        <span>Include scripted runs</span>
                    </label>
                    <div class="strategy-selector-wrap">
                        <label>Strategy:</label>
                        <select id="strategy-select">
                            <option value="A">Strategy A (Soft revocation)</option>
                            <option value="B">Strategy B (Revoke and contain)</option>
                            <option value="C">Strategy C (Concurrent containment)</option>
                        </select>
                    </div>
                    <button class="btn-shutdown" id="initiate-shutdown-btn" onclick="window.runManualShutdown()">
                        <span>⚡</span> INITIATE SHUTDOWN <span>→</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- 3 Numbered Sections of KPI Metric Cards -->
        <div class="kpi-sections-row">
            <!-- 01 Execution Overview -->
            <div class="kpi-group">
                <div class="section-heading">
                    <span class="sec-num">01</span>
                    <span class="sec-title">Execution Overview</span>
                    <div class="sec-line"></div>
                </div>
                <div class="kpi-cards-grid">
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-red">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-total">0</div>
                            <div class="kpi-title">TOTAL TESTS</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-green">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num color-success" id="kpi-success">--</div>
                            <div class="kpi-title">SUCCESS RATE</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-green">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num color-success" id="kpi-chain">VALID</div>
                            <div class="kpi-title">CHAIN INTEGRITY</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-amber">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 4 15 12 5 20 5 4"/><line x1="19" y1="5" x2="19" y2="19"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-skipped">0</div>
                            <div class="kpi-title">SKIPPED RUNS</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 02 Revocation Performance -->
            <div class="kpi-group">
                <div class="section-heading">
                    <span class="sec-num">02</span>
                    <span class="sec-title">Revocation Performance</span>
                    <div class="sec-line"></div>
                </div>
                <div class="kpi-cards-grid">
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-red">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="14" r="8"/><line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="14" x2="15" y2="11"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-latency">-- ms</div>
                            <div class="kpi-title">PER-CHANNEL REVOCATION LATENCY</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-red">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 14 14"/><path d="M16.24 7.76l2.12-2.12"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-total-rev-time">-- ms</div>
                            <div class="kpi-title">TOTAL REVOCATION TIME (UNTIL LAST REVOKED)</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-pink">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-cycle-duration">-- ms</div>
                            <div class="kpi-title">CYCLE DURATION</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-orange">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-retries">0 of 0</div>
                            <div class="kpi-title">RUNS NEEDING RETRIES</div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 03 Security & Resource Exposure -->
            <div class="kpi-group">
                <div class="section-heading">
                    <span class="sec-num">03</span>
                    <span class="sec-title">Security & Resource Exposure</span>
                    <div class="sec-line"></div>
                </div>
                <div class="kpi-cards-grid">
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-red">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-leaked-ops">0</div>
                            <div class="kpi-title">LEAKED OPERATIONS</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-coral">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-runs-with-leaks">0 of 0</div>
                            <div class="kpi-title">RUNS WITH LEAKS</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-orange">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-exposed-runs">0 of 0</div>
                            <div class="kpi-title">EXPOSED RUNS</div>
                        </div>
                    </div>
                    <div class="kpi-tile">
                        <div class="kpi-icon-wrap icon-blue">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>
                        </div>
                        <div class="kpi-body">
                            <div class="kpi-num" id="kpi-llm-calls">0 / 1000</div>
                            <div class="kpi-title" id="kpi-llm-tokens">LLM CALLS (0 TOKENS TODAY)</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Row 1: (1) Simulation Settings & Batch and (2) Live Revocation Console & Tiles -->
        <div class="panels-grid">
            <div class="panel">
                <div class="panel-header">
                    <h3 class="panel-title">(1) Simulation Settings &amp; Batch</h3>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 11px; color: var(--text-muted); font-weight:600;">Scheduler:</span>
                        <span id="dash-sched-badge" class="badge neutral" style="font-size: 10px;">OFF</span>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
                    <label style="font-weight:600; color:var(--text-secondary);">Delay Min (ms): <input type="number" id="sim-delay-min" value="50" style="width:100%; margin-top:4px;" /></label>
                    <label style="font-weight:600; color:var(--text-secondary);">Delay Max (ms): <input type="number" id="sim-delay-max" value="200" style="width:100%; margin-top:4px;" /></label>
                    <label style="font-weight:600; color:var(--text-secondary);">Revoke Fail Prob: <input type="number" step="0.05" id="sim-fail-prob" value="0.10" style="width:100%; margin-top:4px;" /></label>
                    <label style="font-weight:600; color:var(--text-secondary);">IAM Fail Prob: <input type="number" step="0.05" id="sim-iam-prob" value="0.15" style="width:100%; margin-top:4px;" /></label>
                    <label style="font-weight:600; color:var(--text-secondary);">In-Flight Leak Prob: <input type="number" step="0.05" id="sim-leak-prob" value="0.20" style="width:100%; margin-top:4px;" /></label>
                    <label style="font-weight:600; color:var(--text-secondary);">Agent Mode:
                        <select id="sim-agent-mode" style="width:100%; margin-top:4px;">
                            <option value="Gemini">Gemini</option>
                            <option value="Scripted">Scripted</option>
                        </select>
                    </label>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 15px;">
                    <button class="btn-secondary" onclick="window.saveSettings()" style="flex: 1;">Save Settings</button>
                </div>
                <hr style="border: 0; border-top: 1px solid var(--border-light); margin: 15px 0;">
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="number" id="n-tests-input" value="5" min="1" max="50" style="width: 80px;" title="N cycles (max 50)" />
                    <button class="btn-primary" id="run-n-btn" onclick="window.runNTests()" style="flex: 1;">Run N Tests</button>
                </div>
            </div>

            <div class="panel">
                <div class="panel-header">
                    <h3 class="panel-title">(2) Live Revocation Console &amp; Tiles</h3>
                    <span id="console-phase-badge" class="badge neutral">READY</span>
                </div>
                <div id="channel-tiles" style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 12px;">
                    <div id="tile-api_key" class="channel-tile">
                        <div style="color:var(--text-muted); font-weight:700; font-size:10px;">API_KEY</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:800; font-size:11px; color:var(--text-muted);">IDLE</div>
                    </div>
                    <div id="tile-session_token" class="channel-tile">
                        <div style="color:var(--text-muted); font-weight:700; font-size:10px;">SESSION</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:800; font-size:11px; color:var(--text-muted);">IDLE</div>
                    </div>
                    <div id="tile-iam_role" class="channel-tile">
                        <div style="color:var(--text-muted); font-weight:700; font-size:10px;">IAM_ROLE</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:800; font-size:11px; color:var(--text-muted);">IDLE</div>
                    </div>
                    <div id="tile-network" class="channel-tile">
                        <div style="color:var(--text-muted); font-weight:700; font-size:9.5px;">NETWORK (External Tool/API)</div>
                        <div class="tile-status" style="margin-top:4px; font-weight:800; font-size:11px; color:var(--text-muted);">IDLE</div>
                    </div>
                </div>
                <div id="live-console">
                    <div>[READY] Press 'Initiate Shutdown' to execute a live verified cycle.</div>
                </div>
            </div>
        </div>

        <!-- Row 2: (3) Per-Channel Latency Distribution and (4) 2x2 Outcome Matrix -->
        <div class="panels-grid">
            <!-- (3) Latency Distribution -->
            <div class="panel">
                <div class="panel-header">
                    <h3 class="panel-title">(3) Per-Channel Latency Distribution</h3>
                </div>
                <div id="latency-container" style="height: 220px; position: relative;">
                    <canvas id="latencyChart"></canvas>
                    <div id="latency-empty" class="empty-state" style="display:none; position:absolute; inset:0;">
                        No data yet
                    </div>
                </div>
            </div>

            <!-- (4) 2x2 Outcome Matrix -->
            <div class="panel">
                <div class="panel-header">
                    <h3 class="panel-title">(4) 2x2 Outcome Matrix (Revocation vs In-Flight Leaks)</h3>
                </div>
                <div id="matrix-container" style="height: 220px; position: relative;">
                    <div id="matrix-grid-view" class="matrix-quadrants">
                        <div class="matrix-quadrant quadrant-pass-no-leak">
                            <span class="quadrant-label">Revoke PASS / No Leak</span>
                            <span class="quadrant-val" id="mat-pass-no-leak">0</span>
                        </div>
                        <div class="matrix-quadrant quadrant-pass-leak">
                            <span class="quadrant-label">Revoke PASS / Leak Detected</span>
                            <span class="quadrant-val" id="mat-pass-with-leak">0</span>
                        </div>
                        <div class="matrix-quadrant quadrant-fail-no-leak">
                            <span class="quadrant-label">Revoke FAIL / No Leak</span>
                            <span class="quadrant-val" id="mat-fail-no-leak">0</span>
                        </div>
                        <div class="matrix-quadrant quadrant-fail-leak">
                            <span class="quadrant-label">Revoke FAIL / Leak Detected</span>
                            <span class="quadrant-val" id="mat-fail-with-leak">0</span>
                        </div>
                    </div>
                    <div id="matrix-empty" class="empty-state" style="display:none; position:absolute; inset:0;">
                        No data yet
                    </div>
                </div>
            </div>
        </div>

        <!-- Row 3: (5) In-Flight Leak Timeline and (6) Success Rate & Latency Trend -->
        <div class="panels-grid">
            <!-- (5) In-Flight Leak Timeline -->
            <div class="panel">
                <div class="panel-header">
                    <h3 class="panel-title">(5) In-Flight Leak Timeline (Relative to Shutdown)</h3>
                </div>
                <div id="timeline-container" style="height: 220px; position: relative;">
                    <canvas id="timelineChart"></canvas>
                    <div id="timeline-empty" class="empty-state" style="display:none; position:absolute; inset:0;">
                        No data yet
                    </div>
                </div>
            </div>

            <!-- (6) Success Rate & Latency Trend -->
            <div class="panel">
                <div class="panel-header">
                    <h3 class="panel-title">(6) Success Rate & Latency Trend per Test Run</h3>
                </div>
                <div id="trend-container" style="height: 220px; position: relative;">
                    <canvas id="trendChart"></canvas>
                    <div id="trend-empty" class="empty-state" style="display:none; position:absolute; inset:0;">
                        No data yet
                    </div>
                </div>
            </div>
        </div>

        <!-- Panel: Agent Runtime Status & Credentials -->
        <div class="panel" style="margin-bottom: 25px;">
            <div class="panel-header" style="flex-wrap:wrap; gap:10px;">
                <h3 class="panel-title">(7) Agent Runtime Status & Credentials</h3>
                <div id="dash-agent-badges" style="display:flex; gap:10px; font-size:11.5px; flex-wrap:wrap;">
                    <div class="badge neutral" style="padding:4px 8px;">
                        <span>Agent:</span> <strong id="dash-agent-name">Sandbox Agent</strong> (<code id="dash-agent-id">--</code>)
                    </div>
                    <div class="badge success" style="padding:4px 8px;">
                        <span>Status:</span> <span id="dash-agent-status">ACTIVE</span>
                    </div>
                    <div class="badge neutral" style="padding:4px 8px;">
                        <span>Mode:</span> <strong id="dash-agent-mode">Gemini</strong>
                    </div>
                    <div class="badge neutral" style="padding:4px 8px;">
                        <span>Model:</span> <code id="dash-agent-model">gemini-3.5-flash-lite</code>
                    </div>
                    <div class="badge success" id="dash-agent-key" style="padding:4px 8px;">
                        configured
                    </div>
                </div>
            </div>
            <div style="overflow-x:auto;">
                <table id="dash-creds-table">
                    <thead>
                        <tr>
                            <th>Channel</th>
                            <th>Channel Type</th>
                            <th>Masked Value</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="dash-creds-tbody">
                        <tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:15px;">Loading credentials...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Panel: Test History Table -->
        <div class="panel">
            <div class="panel-header">
                <h3 class="panel-title">(8) Test History Table</h3>
            </div>
            <div style="overflow-x: auto;">
                <table id="history-table">
                    <thead>
                        <tr>
                            <th>Test ID</th>
                            <th>Trigger Time (Local)</th>
                            <th>Triggered By</th>
                            <th>Mode</th>
                            <th>Strategy</th>
                            <th>Final State</th>
                            <th>Residual Risk</th>
                            <th>Leaks</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding: 30px;">No data yet</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    window.addEventListener('ws_shutdown_progress', window.handleWsProgress);
    window.addEventListener('ws_credential_update', window.handleWsCredUpdate);
    window.addEventListener('ws_batch_progress', window.handleWsBatchProgress);
    window.addEventListener('ws_shutdown_complete', window.handleWsShutdownComplete);

    await window.loadInitialSettings();
    const toggle = document.getElementById('include-scripted-toggle');
    if (toggle) toggle.checked = State.includeScripted;
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
    ['api_key', 'session_token', 'iam_role', 'network'].forEach(ch => {
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
    let target = channelType;
    if(target === 'network_proxy' || target === 'external_tool') target = 'network';
    const tile = document.getElementById(`tile-${target}`);
    if(!tile) return;
    const lat = Math.round(latency || 0);
    if(success) {
        tile.style.borderColor = '#10b981';
        tile.style.background = 'rgba(16, 185, 129, 0.15)';
        const st = tile.querySelector('.tile-status');
        if(st) { st.textContent = `REVOKED (${lat}ms)`; st.style.color = '#10b981'; }
    } else {
        tile.style.borderColor = '#ef4444';
        tile.style.background = 'rgba(239, 68, 68, 0.15)';
        const st = tile.querySelector('.tile-status');
        if(st) { st.textContent = `FAILED (${lat}ms)`; st.style.color = '#ef4444'; }
    }
};

window.runManualShutdown = async function() {
    const btn = document.getElementById('initiate-shutdown-btn');
    const runNBtn = document.getElementById('run-n-btn');
    const stratSelect = document.getElementById('strategy-select');
    const strategy = stratSelect ? stratSelect.value : 'A';

    if(btn) btn.disabled = true;
    if(runNBtn) runNBtn.disabled = true;

    window.resetChannelTiles();
    window.logConsole(`Initiating manual verified shutdown cycle (Strategy ${strategy})...`);
    const phaseBadge = document.getElementById('console-phase-badge');
    if(phaseBadge) { phaseBadge.textContent = "RUNNING"; phaseBadge.style.color = "var(--warning)"; }

    try {
        const res = await apiCall(`/api/shutdown?strategy=${strategy}&trigger_type=manual`, 'POST');
        window.logConsole(`Shutdown cycle finished. Final State: ${res.final_state}, Residual Risk: ${(res.residual_risk * 100).toFixed(1)}%`);
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
    const stratSelect = document.getElementById('strategy-select');
    const strategy = stratSelect ? stratSelect.value : 'A';

    if(btn) btn.disabled = true;
    if(runNBtn) runNBtn.disabled = true;

    window.logConsole(`Executing batch of ${n} sequential tests (Strategy ${strategy})...`);
    const phaseBadge = document.getElementById('console-phase-badge');
    if(phaseBadge) { phaseBadge.textContent = `BATCH (0/${n})`; phaseBadge.style.color = "var(--warning)"; }

    try {
        const res = await apiCall(`/api/shutdown/batch?count=${n}&strategy=${strategy}`, 'POST');
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
        const agentStatus = await apiCall('/api/agent/status');
        if(agentStatus && agentStatus.mode && document.getElementById('sim-agent-mode')) {
            const m = agentStatus.mode.toLowerCase() === 'scripted' ? 'Scripted' : 'Gemini';
            document.getElementById('sim-agent-mode').value = m;
        }
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
        in_flight_leak_prob: parseFloat(document.getElementById('sim-leak-prob').value),
        agent_mode: document.getElementById('sim-agent-mode') ? document.getElementById('sim-agent-mode').value : 'Gemini'
    };
    try {
        await apiCall('/api/shutdown/settings', 'POST', s);
        window.logConsole("Simulation settings updated successfully.");
        alert("Simulation settings saved.");
    } catch(e) {
        alert("Failed to save settings: " + (e.message || JSON.stringify(e)));
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
        alert("Scheduler toggle failed: " + (e.message || JSON.stringify(e)));
    }
};

let _isRefreshingDashboard = false;

window.refreshDashboard = async function() {
    if (_isRefreshingDashboard) return;
    _isRefreshingDashboard = true;

    try {
        const includeScripted = State.includeScripted;
        const toggle = document.getElementById('include-scripted-toggle');
        if (toggle && toggle.checked !== includeScripted) toggle.checked = includeScripted;
        const qParam = includeScripted ? '?include_scripted=true' : '?include_scripted=false';

        const [summary, history, verifyRes, agent, creds, agentStatus] = await Promise.all([
            apiCall(`/api/analytics/summary${qParam}`).catch(() => null),
            apiCall(`/api/shutdown/history${qParam}`).catch(() => null),
            apiCall('/api/shutdown/verify').catch(() => null),
            apiCall('/api/agent').catch(() => null),
            apiCall('/api/agent/credentials').catch(() => null),
            apiCall('/api/agent/status').catch(() => ({}))
        ]);

        const hasSummary = summary !== null && summary !== undefined;
        const totalRuns = hasSummary ? (summary.total_shutdowns || 0) : 0;
        const hasData = hasSummary && totalRuns > 0;

        if (document.getElementById('kpi-total')) {
            document.getElementById('kpi-total').textContent = hasSummary ? totalRuns : '--';
        }
        if (document.getElementById('kpi-success')) {
            document.getElementById('kpi-success').textContent = hasData ? `${summary.success_rate}%` : '--';
        }
        if (document.getElementById('kpi-latency')) {
            document.getElementById('kpi-latency').textContent = hasData ? `${summary.mean_revocation_latency_ms} ms` : '-- ms';
        }
        if (document.getElementById('kpi-total-rev-time')) {
            document.getElementById('kpi-total-rev-time').textContent = hasData ? `${summary.mean_total_revocation_ms} ms` : '-- ms';
        }
        if (document.getElementById('kpi-cycle-duration')) {
            document.getElementById('kpi-cycle-duration').textContent = hasData ? `${summary.mean_cycle_duration_ms} ms` : '-- ms';
        }
        if (document.getElementById('kpi-leaked-ops')) {
            document.getElementById('kpi-leaked-ops').textContent = hasSummary ? (summary.leaked_operations || 0) : '--';
        }
        if (document.getElementById('kpi-runs-with-leaks')) {
            document.getElementById('kpi-runs-with-leaks').textContent = hasSummary ? (summary.runs_with_leaks_kpi || `${summary.runs_with_leaks || 0} of ${totalRuns}`) : '--';
        }
        if (document.getElementById('kpi-exposed-runs')) {
            document.getElementById('kpi-exposed-runs').textContent = hasSummary ? (summary.exposed_runs_kpi || summary.runs_with_in_flight_kpi || `${summary.exposed_runs || 0} of ${totalRuns}`) : '--';
        }
        if (document.getElementById('kpi-retries')) {
            document.getElementById('kpi-retries').textContent = hasSummary ? (summary.runs_needing_retries_kpi || `${summary.runs_needing_retries || 0} of ${totalRuns}`) : '--';
        }
        if (document.getElementById('kpi-chain')) {
            const chainEl = document.getElementById('kpi-chain');
            const status = verifyRes && verifyRes.status ? verifyRes.status.toUpperCase() : (hasData ? 'VALID' : '--');
            chainEl.textContent = status;
            chainEl.style.color = status === 'VALID' ? 'var(--success)' : (status === '--' ? 'var(--text-muted)' : 'var(--danger)');
        }
        if (document.getElementById('kpi-skipped')) {
            document.getElementById('kpi-skipped').textContent = hasSummary ? (summary.skipped_runs || 0) : '--';
        }
        if (document.getElementById('kpi-llm-calls')) {
            const calls = hasSummary ? (summary.calls_used_today || 0) : '--';
            document.getElementById('kpi-llm-calls').textContent = hasSummary ? `${calls} / 1000` : '--';
            if (document.getElementById('kpi-llm-tokens')) {
                const tokTotal = (summary.tokens_today && summary.tokens_today.total_tokens !== undefined) ? summary.tokens_today.total_tokens : (summary.total_tokens_total || 0);
                document.getElementById('kpi-llm-tokens').textContent = `LLM Calls (${tokTotal} tok today)`;
            }
        }

        const latEmpty = document.getElementById('latency-empty');
        const latCanvas = document.getElementById('latencyChart');
        if (!hasSummary) {
            if (latEmpty) { latEmpty.textContent = "Channel latency data temporarily unavailable."; latEmpty.style.display = 'flex'; }
            if (latCanvas) latCanvas.style.display = 'none';
        } else if (!hasData) {
            if (latEmpty) { latEmpty.textContent = "No runs recorded yet. Initiate a shutdown or batch test to view channel latencies."; latEmpty.style.display = 'flex'; }
            if (latCanvas) latCanvas.style.display = 'none';
        } else if (!summary.channel_latencies || Object.keys(summary.channel_latencies).length === 0) {
            if (latEmpty) { latEmpty.textContent = "No channel revocation records logged."; latEmpty.style.display = 'flex'; }
            if (latCanvas) latCanvas.style.display = 'none';
        } else {
            if (latEmpty) latEmpty.style.display = 'none';
            if (latCanvas) latCanvas.style.display = 'block';

            const channels = Object.keys(summary.channel_latencies);
            const averages = channels.map(ch => {
                const arr = summary.channel_latencies[ch];
                return arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1) : 0;
            });

            if (window.dashboardCharts.latency) window.dashboardCharts.latency.destroy();
            window.dashboardCharts.latency = new Chart(latCanvas.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: channels.map(c => c.toUpperCase()),
                    datasets: [{
                        label: 'Mean Latency (ms)',
                        data: averages,
                        backgroundColor: '#ea384c',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
                        x: { ticks: { color: '#64748b' }, grid: { display: false } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        const matEmpty = document.getElementById('matrix-empty');
        const matGrid = document.getElementById('matrix-grid-view');
        if (!hasSummary) {
            if (matEmpty) { matEmpty.textContent = "Outcome matrix temporarily unavailable."; matEmpty.style.display = 'flex'; }
            if (matGrid) matGrid.style.display = 'none';
        } else if (!hasData) {
            if (matEmpty) { matEmpty.textContent = "No runs recorded yet."; matEmpty.style.display = 'flex'; }
            if (matGrid) matGrid.style.display = 'none';
        } else {
            if (matEmpty) matEmpty.style.display = 'none';
            if (matGrid) matGrid.style.display = 'grid';
            const m = summary.outcome_matrix_2x2 || { pass_no_leak: 0, pass_with_leak: 0, fail_no_leak: 0, fail_with_leak: 0 };
            if (document.getElementById('mat-pass-no-leak')) document.getElementById('mat-pass-no-leak').textContent = m.pass_no_leak;
            if (document.getElementById('mat-pass-with-leak')) document.getElementById('mat-pass-with-leak').textContent = m.pass_with_leak;
            if (document.getElementById('mat-fail-no-leak')) document.getElementById('mat-fail-no-leak').textContent = m.fail_no_leak;
            if (document.getElementById('mat-fail-with-leak')) document.getElementById('mat-fail-with-leak').textContent = m.fail_with_leak;
        }

        const timeEmpty = document.getElementById('timeline-empty');
        const timeCanvas = document.getElementById('timelineChart');
        const exposedCount = hasSummary ? (summary.exposed_runs !== undefined ? summary.exposed_runs : (summary.runs_with_in_flight || 0)) : 0;

        if (!hasSummary) {
            if (timeEmpty) { timeEmpty.textContent = "Timeline data temporarily unavailable."; timeEmpty.style.display = 'flex'; }
            if (timeCanvas) timeCanvas.style.display = 'none';
        } else if (!hasData) {
            if (timeEmpty) { timeEmpty.textContent = "No runs recorded yet."; timeEmpty.style.display = 'flex'; }
            if (timeCanvas) timeCanvas.style.display = 'none';
        } else if (exposedCount === 0) {
            if (timeEmpty) { timeEmpty.textContent = "No exposed runs (0 runs had active in-flight operations at kill cutoff)."; timeEmpty.style.display = 'flex'; }
            if (timeCanvas) timeCanvas.style.display = 'none';
        } else if (!summary.in_flight_leaks_timeline || summary.in_flight_leaks_timeline.length === 0) {
            if (timeEmpty) { timeEmpty.textContent = "No in-flight leaks detected across all exposed runs. All in-flight operations were successfully contained."; timeEmpty.style.display = 'flex'; }
            if (timeCanvas) timeCanvas.style.display = 'none';
        } else {
            if (timeEmpty) timeEmpty.style.display = 'none';
            if (timeCanvas) timeCanvas.style.display = 'block';

            const leakPoints = summary.in_flight_leaks_timeline.map((item, idx) => ({
                x: item.relative_ms,
                y: idx + 1,
                label: `${item.operation_type} (${item.op_id})`
            }));

            if (window.dashboardCharts.timeline) window.dashboardCharts.timeline.destroy();
            window.dashboardCharts.timeline = new Chart(timeCanvas.getContext('2d'), {
                type: 'scatter',
                data: {
                    datasets: [
                        {
                            label: 'Leaked Operations (Post-Shutdown)',
                            data: leakPoints,
                            backgroundColor: '#ea384c',
                            borderColor: '#dc2626',
                            pointRadius: 6,
                            pointHoverRadius: 8
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            title: { display: true, text: 'Time Relative to Shutdown (ms)', color: '#64748b' },
                            grid: { color: '#f1f5f9' },
                            ticks: { color: '#64748b' }
                        },
                        y: {
                            title: { display: true, text: 'Operation Sequence', color: '#64748b' },
                            grid: { color: '#f1f5f9' },
                            ticks: { color: '#64748b', stepSize: 1 }
                        }
                    },
                    plugins: {
                        legend: { labels: { color: '#0f172a' } },
                        tooltip: {
                            callbacks: {
                                label: (ctx) => `${ctx.raw.label}: completed +${ctx.raw.x}ms after shutdown`
                            }
                        }
                    }
                }
            });
        }

        const trendEmpty = document.getElementById('trend-empty');
        const trendCanvas = document.getElementById('trendChart');
        if (!hasSummary) {
            if (trendEmpty) { trendEmpty.textContent = "Trend data temporarily unavailable."; trendEmpty.style.display = 'flex'; }
            if (trendCanvas) trendCanvas.style.display = 'none';
        } else if (!hasData || !summary.runs_trend || summary.runs_trend.length === 0) {
            if (trendEmpty) { trendEmpty.textContent = "No test runs recorded yet."; trendEmpty.style.display = 'flex'; }
            if (trendCanvas) trendCanvas.style.display = 'none';
        } else {
            if (trendEmpty) trendEmpty.style.display = 'none';
            if (trendCanvas) trendCanvas.style.display = 'block';

            const runs = summary.runs_trend;
            const labels = runs.map(r => `Run ${r.run_index}`);
            const latencyData = runs.map(r => r.mean_latency_ms);
            const successData = runs.map(r => r.success * 100);

            if (window.dashboardCharts.trend) window.dashboardCharts.trend.destroy();
            window.dashboardCharts.trend = new Chart(trendCanvas.getContext('2d'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Mean Latency (ms)',
                            data: latencyData,
                            borderColor: '#ea384c',
                            backgroundColor: 'rgba(234, 56, 76, 0.08)',
                            pointBackgroundColor: '#ea384c',
                            pointBorderColor: '#ea384c',
                            yAxisID: 'y',
                            tension: 0.2,
                            fill: true
                        },
                        {
                            label: 'Success (100% = TERMINATED)',
                            data: successData,
                            borderColor: '#0f172a',
                            borderDash: [5, 4],
                            yAxisID: 'y1',
                            pointRadius: 4,
                            pointBackgroundColor: '#0f172a'
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
                            title: { display: true, text: 'Latency (ms)', color: '#ea384c' },
                            ticks: { color: '#64748b' },
                            grid: { color: '#f1f5f9' }
                        },
                        y1: {
                            type: 'linear',
                            position: 'right',
                            min: 0,
                            max: 100,
                            title: { display: true, text: 'Success %', color: '#0f172a' },
                            ticks: { color: '#64748b', stepSize: 50 },
                            grid: { drawOnChartArea: false }
                        },
                        x: { ticks: { color: '#64748b' }, grid: { display: false } }
                    },
                    plugins: {
                        legend: { labels: { color: '#0f172a' } }
                    }
                }
            });
        }

        if (agent) {
            const nameEl = document.getElementById('dash-agent-name');
            const idEl = document.getElementById('dash-agent-id');
            const stEl = document.getElementById('dash-agent-status');
            const topName = document.getElementById('top-agent-name');
            const topStatus = document.getElementById('top-agent-status');

            if (nameEl) nameEl.textContent = agent.name || 'Sandbox Agent';
            if (idEl) idEl.textContent = agent.id ? agent.id.substring(0, 8) : '--';
            if (topName) topName.textContent = agent.name ? `${agent.name}-${(agent.id || '').substring(0, 8)}` : (agent.id || 'Sandboxed-Agent');

            if (stEl) {
                stEl.textContent = agent.status || 'UNKNOWN';
                stEl.className = `badge ${agent.status === 'ACTIVE' ? 'success' : 'warning'}`;
            }
            if (topStatus) {
                topStatus.textContent = agent.status === 'ACTIVE' ? '● Active' : `● ${agent.status}`;
                topStatus.style.color = agent.status === 'ACTIVE' ? 'var(--success)' : 'var(--danger)';
            }
        }
        if (agentStatus) {
            const modeEl = document.getElementById('dash-agent-mode');
            const modelEl = document.getElementById('dash-agent-model');
            const keyEl = document.getElementById('dash-agent-key');
            const topModel = document.getElementById('top-agent-model');
            const topRuntime = document.getElementById('top-agent-runtime');

            if (modeEl) modeEl.textContent = agentStatus.mode || 'Gemini';
            if (modelEl) modelEl.textContent = agentStatus.model || 'gemini-3.5-flash-lite';
            if (topModel) topModel.textContent = `${agentStatus.mode || 'Gemini'} (Simulated)`;
            if (topRuntime) topRuntime.textContent = 'Sandbox';

            if (keyEl) {
                keyEl.textContent = agentStatus.key_status || 'missing';
                keyEl.className = `badge ${agentStatus.key_status === 'configured' ? 'success' : 'warning'}`;
            }
        }
        const credsTbody = document.getElementById('dash-creds-tbody');
        if (credsTbody) {
            if (creds === null) {
                credsTbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:15px;">Credentials temporarily unavailable.</td></tr>`;
            } else if (!creds || creds.length === 0) {
                credsTbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color:var(--text-muted); padding:15px;">No credentials provisioned yet.</td></tr>`;
            } else {
                credsTbody.innerHTML = creds.map(c => `
                    <tr>
                        <td style="font-weight:700; color:var(--accent-red);">${c.channel_type === 'network' ? 'NETWORK' : c.channel_type.toUpperCase()}</td>
                        <td style="color:var(--text-secondary);">${c.channel_type === 'network' ? 'External Tool/API Proxy' : 'Local Channel'}</td>
                        <td style="font-family:var(--font-mono); color:var(--text-primary);"><code>${c.credential_value}</code></td>
                        <td><span class="badge ${c.status === 'ACTIVE' ? 'success' : (c.status === 'REVOKED' ? 'danger' : 'warning')}" style="font-size:10px;">${c.status}</span></td>
                    </tr>
                `).join('');
            }
        }

        const tbody = document.querySelector('#history-table tbody');
        if (tbody) {
            if (history === null) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding: 30px;">Run history temporarily unavailable</td></tr>`;
            } else if (!history || history.length === 0) {
                tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding: 30px;">No runs recorded yet. Use 'Initiate Shutdown' or 'Run N Tests' above to generate test runs.</td></tr>`;
            } else {
                tbody.innerHTML = history.map(h => {
                    const isTerm = h.final_state === 'TERMINATED';
                    const badgeClass = isTerm ? 'success' : 'danger';
                    const trigTime = formatLocalTime(h.trigger_timestamp || h.started_at);
                    const modeVal = (h.agent_mode || 'gemini').toLowerCase();
                    const modeBadge = modeVal === 'scripted'
                        ? '<span class="badge warning" style="font-size:10px;">SCRIPTED</span>'
                        : '<span class="badge info" style="font-size:10px;">GEMINI</span>';
                    return `
                        <tr style="cursor:pointer;" onclick="openShutdownReport('${h.id}')" title="Click to view Shutdown Report">
                            <td><a href="javascript:void(0)" onclick="event.stopPropagation(); openShutdownReport('${h.id}')" style="font-family:var(--font-mono); color:var(--accent-red); font-weight:700; text-decoration:underline;">${h.id.substring(0,8)}</a></td>
                            <td style="font-size:11px; color:var(--text-muted);">${trigTime}</td>
                            <td><span class="badge neutral" style="font-size:10px;">${h.triggered_by || h.trigger_type || 'manual'}</span></td>
                            <td>${modeBadge}</td>
                            <td style="font-weight:700; color:var(--accent-red);">Strategy ${h.strategy}</td>
                            <td><span class="badge ${badgeClass}" style="font-size:10px;">${h.final_state}</span></td>
                            <td style="font-family:var(--font-mono);">${(h.residual_risk * 100).toFixed(1)}%</td>
                            <td style="font-family:var(--font-mono); font-weight:700; color:${(h.in_flight_failures || 0) > 0 ? 'var(--danger)' : 'var(--text-muted)'};">${h.in_flight_failures || 0}</td>
                        </tr>
                    `;
                }).join('');
            }
        }
    } catch(e) {
        console.error("Dashboard refresh error:", e);
    } finally {
        _isRefreshingDashboard = false;
    }
};

window.handleWsProgress = function(e) {
    if(e.detail && e.detail.stage) {
        const stage = e.detail.stage.toLowerCase();
        if(stage === 'agent') {
            window.logConsole(`[AGENT] ${e.detail.detail || ''}`);
        } else if(stage === 'notice') {
            window.logConsole(`[NOTICE] ${e.detail.detail || ''}`);
        } else {
            window.logConsole(`[${e.detail.stage.toUpperCase()}] ${e.detail.detail || ''}`);
        }
        const phaseBadge = document.getElementById('console-phase-badge');
        if(phaseBadge) phaseBadge.textContent = e.detail.stage.toUpperCase();
    }
};

window.handleWsCredUpdate = function(e) {
    if(e.detail && e.detail.channel_type) {
        const isRevoked = e.detail.status === 'REVOKED';
        window.updateChannelTile(e.detail.channel_type, isRevoked, e.detail.latency_ms);
        window.logConsole(`Channel ${e.detail.channel_type}: ${e.detail.status} (${e.detail.latency_ms || 0}ms)`);
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
