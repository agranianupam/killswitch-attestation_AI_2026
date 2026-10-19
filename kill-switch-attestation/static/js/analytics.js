let analyticsLeakChart = null;
let analyticsGapsChart = null;
let _analyticsIncludeScripted = false;

window.render_analytics = async function(container) {
    container.innerHTML = `<h2>Analytics</h2><p>Loading analytics data...</p>`;

    try {
        const qParam = _analyticsIncludeScripted ? '?include_scripted=true' : '?include_scripted=false';
        const [summary, killbench, gapsData] = await Promise.all([
            apiCall(`/api/analytics/summary${qParam}`),
            apiCall(`/api/analytics/killbench-comparison${qParam}`),
            apiCall(`/api/analytics/shutdown-gaps${qParam}`).catch(() => null)
        ]);

        const capRows = (killbench.capability_table || [
            { capability: "Single-channel external shutdown test", killbench: "Yes", this_framework: "Yes" },
            { capability: "Multi-channel simultaneous revocation", killbench: "No", this_framework: "Yes" },
            { capability: "In-flight action detection", killbench: "No", this_framework: "Yes" },
            { capability: "Signed tamper-evident evidence", killbench: "No", this_framework: "Yes" },
            { capability: "Strategy comparison", killbench: "Not claimed", this_framework: "Yes" },
            { capability: "Continuous scheduled random testing", killbench: "No", this_framework: "Yes" }
        ]).map(row => `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                <td style="padding:10px; color:#fff;">${row.capability}</td>
                <td style="padding:10px; color:${row.killbench === 'Yes' ? 'var(--success)' : (row.killbench === 'No' ? 'var(--danger)' : '#aaa')}; font-weight:bold;">${row.killbench}</td>
                <td style="padding:10px; color:var(--neon-blue); font-weight:bold;">${row.this_framework}</td>
            </tr>
        `).join('');

        const kbMetrics = killbench.system_metrics || {
            total_runs: summary.total_shutdowns || 0,
            success_rate_percent: summary.success_rate || 0.0,
            mean_revocation_latency_ms: summary.mean_revocation_latency_ms || summary.mean_latency_ms || 0.0,
            mean_total_revocation_ms: summary.mean_total_revocation_ms || 0.0,
            mean_cycle_duration_ms: summary.mean_cycle_duration_ms || 0.0,
            total_leaks_detected: summary.total_leaks || 0
        };

        const gapsList = (gapsData && gapsData.last_20_gaps && gapsData.last_20_gaps.length > 0)
            ? gapsData.last_20_gaps.map((g, idx) => `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05); font-size:12px;">
                    <td style="padding:6px 10px;">${idx + 1}</td>
                    <td style="padding:6px 10px; font-family:monospace; color:var(--neon-blue); font-weight:bold;">${g.gap_seconds}s</td>
                    <td style="padding:6px 10px;"><span class="badge" style="background:#222; font-size:9px;">SCHEDULER</span></td>
                    <td style="padding:6px 10px;">
                        <span class="badge ${(g.agent_mode || 'gemini').toLowerCase() === 'scripted' ? 'warning' : 'info'}" style="font-size:9px;">
                            ${(g.agent_mode || 'gemini').toUpperCase()}
                        </span>
                    </td>
                    <td style="padding:6px 10px; font-size:11px; color:var(--text-muted);">${formatLocalTime(g.timestamp)}</td>
                </tr>
            `).join('')
            : `<tr><td colspan="5" style="text-align:center; padding:15px; color:var(--text-muted);">No scheduled gap telemetry recorded yet</td></tr>`;

        const manualRunsList = (gapsData && gapsData.manual_runs && gapsData.manual_runs.length > 0)
            ? gapsData.manual_runs.map((m, idx) => `
                <tr style="border-bottom:1px solid rgba(255,255,255,0.05); font-size:12px;">
                    <td style="padding:6px 10px; font-family:monospace; color:var(--neon-blue);">${m.id.substring(0,8)}</td>
                    <td style="padding:6px 10px;"><span class="badge" style="background:#333; font-size:9px;">${(m.triggered_by || m.trigger_type || 'manual').toUpperCase()}</span></td>
                    <td style="padding:6px 10px;">
                        <span class="badge ${(m.agent_mode || 'gemini').toLowerCase() === 'scripted' ? 'warning' : 'info'}" style="font-size:9px;">
                            ${(m.agent_mode || 'gemini').toUpperCase()}
                        </span>
                    </td>
                    <td style="padding:6px 10px; font-weight:bold;">Strategy ${m.strategy}</td>
                    <td style="padding:6px 10px;"><span class="badge ${m.final_state === 'TERMINATED' ? 'success' : 'danger'}" style="font-size:9px;">${m.final_state}</span></td>
                    <td style="padding:6px 10px; font-size:11px; color:var(--text-muted);">${formatLocalTime(m.timestamp)}</td>
                </tr>
            `).join('')
            : `<tr><td colspan="6" style="text-align:center; padding:15px; color:var(--text-muted);">No manual or ad-hoc runs recorded yet</td></tr>`;

        container.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:15px;">
                <div>
                    <h2 style="margin:0;">System Analytics & Verification</h2>
                    <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Comparative benchmarking and empirical telemetry distributions.</div>
                </div>
                <div>
                    <label style="font-size:12px; color:var(--text-muted); display:inline-flex; align-items:center; gap:6px; cursor:pointer; background:rgba(255,255,255,0.05); padding:6px 12px; border-radius:4px; border:1px solid var(--border);">
                        <input type="checkbox" id="analytics-scripted-toggle" ${_analyticsIncludeScripted ? 'checked' : ''} onchange="window.toggleAnalyticsScripted(this.checked)">
                        <span>Include scripted runs</span>
                    </label>
                </div>
            </div>

            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:15px; margin-bottom:25px;">
                <div class="kpi-card">
                    <span class="label">Total Evaluated Runs</span>
                    <span class="value" style="color:var(--neon-blue);">${summary.total_shutdowns}</span>
                </div>
                <div class="kpi-card">
                    <span class="label">Overall Success Rate</span>
                    <span class="value" style="color:var(--success);">${summary.success_rate}%</span>
                </div>
                <div class="kpi-card">
                    <span class="label">Per-Channel Revocation Latency</span>
                    <span class="value">${summary.mean_revocation_latency_ms || summary.mean_latency_ms || 0.0} ms</span>
                </div>
                <div class="kpi-card">
                    <span class="label">Total Revocation Time (Until Last Revoked)</span>
                    <span class="value">${summary.mean_total_revocation_ms || summary.mean_total_revocation_time || 0.0} ms</span>
                </div>
                <div class="kpi-card">
                    <span class="label">Cycle Duration</span>
                    <span class="value">${summary.mean_cycle_duration_ms || 0.0} ms</span>
                </div>
                <div class="kpi-card">
                    <span class="label">Total Leaks Detected</span>
                    <span class="value" style="color:${summary.total_leaks > 0 ? 'var(--danger)' : 'var(--success)'};">${summary.total_leaks}</span>
                </div>
            </div>

            <div class="panel" style="margin-bottom:25px;">
                <h3 style="margin-top:0; color:var(--warning);">KILLBENCH Architectural & Empirical Comparison</h3>
                <div style="display:grid; grid-template-columns: 2fr 1fr; gap:25px; align-items:start;">
                    <div>
                        <table style="width:100%; border-collapse:collapse; font-size:12px;">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border); color:var(--text-muted); text-align:left;">
                                    <th style="padding:10px;">Capability</th>
                                    <th style="padding:10px;">KILLBENCH</th>
                                    <th style="padding:10px;">This Framework</th>
                                </tr>
                            </thead>
                            <tbody>${capRows}</tbody>
                        </table>
                        <div style="font-size:11px; color:#888; margin-top:10px; font-style:italic;">
                            ${killbench.footnote || "The KILLBENCH column reflects the Review-1 report reading of Lee and Park (2025). No KILLBENCH benchmark numbers are shown. Live statistics from this framework appear beside the table."}
                        </div>
                    </div>
                    <div style="background:#0c0c0e; border:1px solid var(--border); border-radius:6px; padding:15px; font-size:12px;">
                        <h4 style="margin-top:0; color:var(--neon-blue); border-bottom:1px solid var(--border); padding-bottom:6px;">Framework Live Metrics</h4>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                            <span style="color:var(--text-muted);">Evaluated Runs:</span> <strong>${kbMetrics.total_runs}</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                            <span style="color:var(--text-muted);">Success Rate:</span> <strong style="color:var(--success);">${kbMetrics.success_rate_percent}%</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                            <span style="color:var(--text-muted);">Per-Channel Revocation Latency:</span> <strong>${kbMetrics.mean_revocation_latency_ms} ms</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                            <span style="color:var(--text-muted);">Total Revocation Time:</span> <strong>${kbMetrics.mean_total_revocation_ms || kbMetrics.mean_revocation_latency_ms} ms</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                            <span style="color:var(--text-muted);">Cycle Duration:</span> <strong>${kbMetrics.mean_cycle_duration_ms || kbMetrics.mean_total_revocation_ms || 0.0} ms</strong>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                            <span style="color:var(--text-muted);">Total Leaks:</span> <strong style="color:${kbMetrics.total_leaks_detected > 0 ? 'var(--danger)' : 'var(--success)'};">${kbMetrics.total_leaks_detected}</strong>
                        </div>
                        <div style="margin-top:10px; padding-top:8px; border-top:1px solid var(--border); font-size:11px; color:#888;">
                            Baseline: External dataset unconfigured (Lee & Park, 2025)
                        </div>
                    </div>
                </div>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; margin-bottom:25px;">
                <div class="panel">
                    <h3 style="margin-top:0;">In-Flight Failures by Strategy</h3>
                    <div style="height:260px; position:relative;">
                        <canvas id="analyticsLeakChart"></canvas>
                        <div id="analytics-leak-empty" class="empty-state" style="display:none; position:absolute; inset:0; align-items:center; justify-content:center; color:var(--text-muted); font-size:13px; text-align:center;">
                            No data yet
                        </div>
                    </div>
                </div>
                <div class="panel">
                    <h3 style="margin-top:0;">Timing Gaps Distribution (Scheduler Runs Only)</h3>
                    <div style="height:260px; position:relative;">
                        <canvas id="analyticsGapsChart"></canvas>
                        <div id="analytics-gaps-empty" class="empty-state" style="display:none; position:absolute; inset:0; align-items:center; justify-content:center; color:var(--text-muted); font-size:13px; text-align:center;">
                            No data yet
                        </div>
                    </div>
                </div>
            </div>

            <div class="dashboard-grid" style="margin-bottom:25px;">
                <div class="panel">
                    <h3 style="margin-top:0;">Recent Scheduled Timing Gaps</h3>
                    <div style="overflow-x:auto;">
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border); color:var(--text-muted); text-align:left; font-size:12px;">
                                    <th style="padding:8px 10px;">#</th>
                                    <th style="padding:8px 10px;">Gap</th>
                                    <th style="padding:8px 10px;">Trigger</th>
                                    <th style="padding:8px 10px;">Mode</th>
                                    <th style="padding:8px 10px;">Timestamp</th>
                                </tr>
                            </thead>
                            <tbody>${gapsList}</tbody>
                        </table>
                    </div>
                </div>
                <div class="panel">
                    <h3 style="margin-top:0;">Manual & Non-Scheduled Runs (Separately Labelled)</h3>
                    <div style="overflow-x:auto;">
                        <table style="width:100%; border-collapse:collapse;">
                            <thead>
                                <tr style="border-bottom:1px solid var(--border); color:var(--text-muted); text-align:left; font-size:12px;">
                                    <th style="padding:8px 10px;">Run ID</th>
                                    <th style="padding:8px 10px;">Trigger</th>
                                    <th style="padding:8px 10px;">Mode</th>
                                    <th style="padding:8px 10px;">Strategy</th>
                                    <th style="padding:8px 10px;">State</th>
                                    <th style="padding:8px 10px;">Timestamp</th>
                                </tr>
                            </thead>
                            <tbody>${manualRunsList}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        const leakEmpty = document.getElementById('analytics-leak-empty');
        const leakCanvas = document.getElementById('analyticsLeakChart');
        const hasLeakData = summary.total_shutdowns > 0 && summary.strategy_stats && Object.keys(summary.strategy_stats).length > 0;

        if (!hasLeakData) {
            if (leakEmpty) leakEmpty.style.display = 'flex';
            if (leakCanvas) leakCanvas.style.display = 'none';
        } else {
            if (leakEmpty) leakEmpty.style.display = 'none';
            if (leakCanvas) leakCanvas.style.display = 'block';

            const ctxLeak = leakCanvas.getContext('2d');
            const labels = Object.keys(summary.strategy_stats);
            const inFlightData = labels.map(l => summary.strategy_stats[l].in_flight_leaks || 0);

            if (analyticsLeakChart) analyticsLeakChart.destroy();
            analyticsLeakChart = new Chart(ctxLeak, {
                type: 'bar',
                data: {
                    labels: labels.map(l => `Strategy ${l}`),
                    datasets: [{
                        label: 'In-Flight Failures (Leaks)',
                        data: inFlightData,
                        backgroundColor: 'rgba(239, 68, 68, 0.8)',
                        borderColor: '#ef4444',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#e0e0e0' } }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: '#a1a1aa' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#a1a1aa' }
                        }
                    }
                }
            });
        }

        const gapsEmpty = document.getElementById('analytics-gaps-empty');
        const gapsCanvas = document.getElementById('analyticsGapsChart');
        const hasGapsData = gapsData && gapsData.histogram && gapsData.histogram.bins && gapsData.histogram.bins.length > 0;

        if (!hasGapsData) {
            if (gapsEmpty) gapsEmpty.style.display = 'flex';
            if (gapsCanvas) gapsCanvas.style.display = 'none';
        } else {
            if (gapsEmpty) gapsEmpty.style.display = 'none';
            if (gapsCanvas) gapsCanvas.style.display = 'block';

            const ctxGaps = gapsCanvas.getContext('2d');
            if (analyticsGapsChart) analyticsGapsChart.destroy();
            analyticsGapsChart = new Chart(ctxGaps, {
                type: 'bar',
                data: {
                    labels: gapsData.histogram.bins,
                    datasets: [{
                        label: 'Observed Gap Frequency (Scheduler Runs)',
                        data: gapsData.histogram.counts,
                        backgroundColor: 'rgba(0, 240, 255, 0.6)',
                        borderColor: 'var(--neon-blue)',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#e0e0e0' } }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            ticks: { color: '#a1a1aa', stepSize: 1 }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#a1a1aa', maxRotation: 45, minRotation: 0 }
                        }
                    }
                }
            });
        }
    } catch(err) {
        container.innerHTML = `<h2>Analytics</h2><div class="panel" style="color:var(--danger)">Error loading analytics: ${err.message}</div>`;
    }
};

window.toggleAnalyticsScripted = function(checked) {
    _analyticsIncludeScripted = checked;
    const content = document.getElementById('app-content');
    if (content) window.render_analytics(content);
};

window.cleanup_analytics = function() {
    if (analyticsLeakChart) {
        analyticsLeakChart.destroy();
        analyticsLeakChart = null;
    }
    if (analyticsGapsChart) {
        analyticsGapsChart.destroy();
        analyticsGapsChart = null;
    }
};
