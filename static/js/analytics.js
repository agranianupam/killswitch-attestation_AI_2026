let analyticsGapsChart = null;

window.render_analytics = async function(container) {
    container.innerHTML = `<h2>Analytics</h2><p>Loading analytics data...</p>`;

    try {
        const includeScripted = State.includeScripted;
        const qParam = includeScripted ? '?include_scripted=true' : '?include_scripted=false';
        const [killbench, gapsData, exposure] = await Promise.all([
            apiCall(`/api/analytics/killbench-comparison${qParam}`).catch(() => null),
            apiCall(`/api/analytics/shutdown-gaps${qParam}`).catch(() => null),
            apiCall(`/api/analytics/exposure${qParam}`).catch(() => null)
        ]);

        const capRows = ((killbench && killbench.capability_table) ? killbench.capability_table : [
            { capability: "Single-channel external shutdown test", killbench: "Yes", this_framework: "Yes" },
            { capability: "Multi-channel simultaneous revocation", killbench: "No", this_framework: "Yes" },
            { capability: "In-flight action detection", killbench: "No", this_framework: "Yes" },
            { capability: "Signed tamper-evident evidence", killbench: "No", this_framework: "Yes" },
            { capability: "Strategy comparison", killbench: "Not claimed", this_framework: "Yes" },
            { capability: "Continuous scheduled random testing", killbench: "No", this_framework: "Yes" }
        ]).map(row => `
            <tr>
                <td style="font-weight:600; color:var(--text-primary);">${row.capability}</td>
                <td style="color:${row.killbench === 'Yes' ? 'var(--success)' : (row.killbench === 'No' ? 'var(--danger)' : 'var(--text-muted)')}; font-weight:700;">${row.killbench}</td>
                <td style="color:var(--accent-red); font-weight:700;">${row.this_framework}</td>
            </tr>
        `).join('');

        const gapsList = (gapsData && gapsData.last_20_gaps && gapsData.last_20_gaps.length > 0)
            ? gapsData.last_20_gaps.map((g, idx) => `
                <tr>
                    <td>${idx + 1}</td>
                    <td style="font-family:var(--font-mono); color:var(--accent-red); font-weight:700;">${g.gap_seconds}s</td>
                    <td><span class="badge neutral" style="font-size:9px;">SCHEDULER</span></td>
                    <td>
                        <span class="badge ${(g.agent_mode || 'gemini').toLowerCase() === 'scripted' ? 'warning' : 'info'}" style="font-size:9px;">
                            ${(g.agent_mode || 'gemini').toUpperCase()}
                        </span>
                    </td>
                    <td style="font-size:11px; color:var(--text-muted);">${formatLocalTime(g.timestamp)}</td>
                </tr>
            `).join('')
            : `<tr><td colspan="5" style="text-align:center; padding:15px; color:var(--text-muted);">No scheduled gap telemetry recorded yet</td></tr>`;

        let exposureHtml = '';
        if (!exposure) {
            exposureHtml = `
                <div class="panel" style="margin-bottom:25px;">
                    <h3 style="margin-top:0; color:var(--accent-red);">Exposure-Aware Conditioning & In-Flight Metrics</h3>
                    <div class="empty-state" style="padding:20px; text-align:center; color:var(--text-muted);">Exposure analytics temporarily unavailable</div>
                </div>
            `;
        } else {
            const strats = exposure.strategies || {};
            const stratRows = ['A', 'B', 'C'].map(s => {
                const d = strats[s] || { runs: 0, exposed_runs: 0, leak_rate_all: 0, leak_rate_exposed: 0 };
                return `
                    <tr>
                        <td style="font-weight:700; color:var(--accent-red);">Strategy ${s}</td>
                        <td>${d.runs}</td>
                        <td>${d.exposed_runs}</td>
                        <td style="color:${d.leak_rate_all > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:700;">${d.leak_rate_all}%</td>
                        <td style="color:${d.leak_rate_exposed > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:700;">${d.leak_rate_exposed}%</td>
                    </tr>
                `;
            }).join('');

            exposureHtml = `
                <!-- Section 01: Exposure-Aware Metrics -->
                <div class="section-heading">
                    <span class="sec-num">01</span>
                    <span class="sec-title">Exposure-Aware Conditioning &amp; In-Flight Metrics</span>
                    <div class="sec-line"></div>
                </div>

                <div class="panel" style="margin-bottom:25px;">
                    <div style="font-size:11.5px; color:var(--text-muted); margin-bottom:16px;">
                        Conditioned failure metrics: distinguishes active in-flight operations at kill cutoff from unexposed runs.
                    </div>

                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:12px; margin-bottom:18px;">
                        <div class="kpi-tile">
                            <div class="kpi-body">
                                <span class="kpi-title">TOTAL EVALUATED RUNS</span>
                                <span class="kpi-num">${exposure.total_valid_runs}</span>
                                <span style="font-size:10px; color:var(--text-muted); margin-top:2px;">Valid completed cycles</span>
                            </div>
                        </div>
                        <div class="kpi-tile">
                            <div class="kpi-body">
                                <span class="kpi-title">EXPOSED RUNS</span>
                                <span class="kpi-num" style="color:var(--accent-red);">${exposure.exposed_runs}</span>
                                <span style="font-size:10px; color:var(--text-muted); margin-top:2px;">Active ops at kill cutoff</span>
                            </div>
                        </div>
                        <div class="kpi-tile">
                            <div class="kpi-body">
                                <span class="kpi-title">UNEXPOSED RUNS</span>
                                <span class="kpi-num">${exposure.unexposed_runs}</span>
                                <span style="font-size:10px; color:var(--text-muted); margin-top:2px;">Idle at cutoff (dilution factor)</span>
                            </div>
                        </div>
                        <div class="kpi-tile">
                            <div class="kpi-body">
                                <span class="kpi-title">ALL-RUNS LEAK RATE</span>
                                <span class="kpi-num ${exposure.leak_rate_all > 0 ? 'color-danger' : 'color-success'}">${exposure.leak_rate_all}%</span>
                                <span style="font-size:10px; color:var(--text-muted); margin-top:2px;">${exposure.runs_with_any_leak} / ${exposure.total_valid_runs} runs</span>
                            </div>
                        </div>
                        <div class="kpi-tile">
                            <div class="kpi-body">
                                <span class="kpi-title">EXPOSED LEAK RATE</span>
                                <span class="kpi-num ${exposure.leak_rate_exposed > 0 ? 'color-danger' : 'color-success'}">${exposure.leak_rate_exposed}%</span>
                                <span style="font-size:10px; color:var(--text-muted); margin-top:2px;">${exposure.exposed_runs_with_leak} / ${exposure.exposed_runs} exposed runs</span>
                            </div>
                        </div>
                        <div class="kpi-tile">
                            <div class="kpi-body">
                                <span class="kpi-title">TOTAL LEAKED OPS</span>
                                <span class="kpi-num ${exposure.total_leaked_operations > 0 ? 'color-danger' : 'color-success'}">${exposure.total_leaked_operations}</span>
                                <span style="font-size:10px; color:var(--text-muted); margin-top:2px;">Actions completed post-kill</span>
                            </div>
                        </div>
                    </div>

                    <div style="overflow-x:auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Strategy</th>
                                    <th>Total Runs</th>
                                    <th>Exposed Runs</th>
                                    <th>All-Runs Leak Rate</th>
                                    <th>Conditioned Exposed Leak Rate</th>
                                </tr>
                            </thead>
                            <tbody>${stratRows}</tbody>
                        </table>
                    </div>
                </div>
            `;
        }

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
                    <div class="hero-kicker">Performance &amp; Gaps</div>
                    <h1 class="hero-title">
                        Verifiable <span class="highlight-red">AI Agent</span> System Analytics
                    </h1>
                    <p class="hero-subtitle">
                        Comparative benchmarking, conditioned exposure telemetry, and empirical distributions.
                    </p>
                </div>
                <div>
                    <label class="scripted-checkbox-label">
                        <input type="checkbox" id="analytics-scripted-toggle" ${includeScripted ? 'checked' : ''} onchange="window.toggleAnalyticsScripted(this.checked)">
                        <span>Include scripted runs</span>
                    </label>
                </div>
            </div>

            ${exposureHtml}

            <!-- Section 02: KillBench Comparison -->
            <div class="section-heading">
                <span class="sec-num">02</span>
                <span class="sec-title">KillBench Architectural &amp; Empirical Comparison</span>
                <div class="sec-line"></div>
            </div>

            <div class="panel" style="margin-bottom:25px;">
                <div style="overflow-x:auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Capability</th>
                                <th>KILLBENCH</th>
                                <th>This Framework</th>
                            </tr>
                        </thead>
                        <tbody>${capRows}</tbody>
                    </table>
                </div>
                <div style="font-size:11px; color:var(--text-muted); margin-top:10px; font-style:italic;">
                    ${(killbench && killbench.footnote) ? killbench.footnote : "The KILLBENCH column reflects the Review-1 report reading of Lee and Park (2025). No KILLBENCH benchmark numbers are shown. Live statistics from this framework appear beside the table."}
                </div>
            </div>

            <!-- Section 03: Timing Gaps -->
            <div class="section-heading">
                <span class="sec-num">03</span>
                <span class="sec-title">Continuous Testing Timing Gaps</span>
                <div class="sec-line"></div>
            </div>

            <div class="panels-grid">
                <div class="panel">
                    <div class="panel-header">
                        <h3 class="panel-title">Timing Gaps Distribution (Scheduler Runs Only)</h3>
                    </div>
                    <div style="height:260px; position:relative;">
                        <canvas id="analyticsGapsChart"></canvas>
                        <div id="analytics-gaps-empty" class="empty-state" style="display:none; position:absolute; inset:0;">
                            No data yet
                        </div>
                    </div>
                </div>
                <div class="panel">
                    <div class="panel-header">
                        <h3 class="panel-title">Recent Scheduled Timing Gaps</h3>
                    </div>
                    <div style="overflow-x:auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>#</th>
                                    <th>Gap</th>
                                    <th>Trigger</th>
                                    <th>Mode</th>
                                    <th>Timestamp</th>
                                </tr>
                            </thead>
                            <tbody>${gapsList}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        const gapsEmpty = document.getElementById('analytics-gaps-empty');
        const gapsCanvas = document.getElementById('analyticsGapsChart');
        const hasGapsData = gapsData && gapsData.histogram && gapsData.histogram.bins && gapsData.histogram.bins.length > 0;

        if (!hasGapsData) {
            if (gapsEmpty) {
                gapsEmpty.textContent = "No scheduler activity recorded yet. Enable the scheduler to record timing intervals between runs.";
                gapsEmpty.style.display = 'flex';
            }
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
                        backgroundColor: '#ea384c',
                        borderColor: '#dc2626',
                        borderWidth: 1,
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { labels: { color: '#0f172a' } }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: '#f1f5f9' },
                            ticks: { color: '#64748b', stepSize: 1 }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#64748b', maxRotation: 45, minRotation: 0 }
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
    State.includeScripted = checked;
    const content = document.getElementById('app-content');
    if (content) window.render_analytics(content);
};

window.cleanup_analytics = function() {
    if (analyticsGapsChart) {
        analyticsGapsChart.destroy();
        analyticsGapsChart = null;
    }
};
