let isReportLoading = false;

window.render_report = async function(container) {
    const currentId = State.latestShutdownId ? String(State.latestShutdownId).trim() : '';
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
                <div class="hero-kicker">Incident Inspection</div>
                <h1 class="hero-title">
                    Verifiable <span class="highlight-red">AI Agent</span> Shutdown Report
                </h1>
                <p class="hero-subtitle">
                    Incident inspection, multi-channel revocations, in-flight action telemetry, and verifiable attestation.
                </p>
            </div>
            <div>
                <button class="btn-secondary" onclick="loadView('dashboard')">← Back to Dashboard</button>
            </div>
        </div>

        <!-- Section 01: Incident Lookup -->
        <div class="section-heading">
            <span class="sec-num">01</span>
            <span class="sec-title">Incident Event Lookup</span>
            <div class="sec-line"></div>
        </div>

        <div class="panel" style="margin-bottom:25px;">
            <div style="margin:0;">
                <label for="report-id" style="font-weight:700; font-size:11px; color:var(--text-secondary); margin-bottom:6px; display:block; text-transform:uppercase;">
                    Enter Shutdown Event ID:
                </label>
                <div style="display:flex; gap:10px; max-width:650px;">
                    <input type="text" id="report-id" placeholder="e.g. 550e8400-e29b-41d4-a716-446655440000" value="${currentId}" style="flex:1; padding:8px 12px; font-family:var(--font-mono); font-size:12px;" onkeydown="if(event.key==='Enter') loadReport()">
                    <button id="load-report-btn" class="btn-shutdown" onclick="loadReport()">Load Report</button>
                </div>
            </div>
        </div>

        <div id="report-content"></div>
    `;

    if (currentId) {
        loadReport(currentId);
    } else {
        const content = document.getElementById('report-content');
        if (content) {
            content.innerHTML = `
                <div class="panel" style="padding: 45px 25px; text-align: center;">
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; max-width: 650px; margin: 0 auto;">
                        <!-- Line 1: Title -->
                        <h3 style="margin: 0; color: var(--text-primary); font-size: 17px; font-weight: 700; display: block; width: 100%;">
                            No Run Selected
                        </h3>
                        <!-- Line 2: Description -->
                        <p style="margin: 0; font-size: 13.5px; color: var(--text-muted); line-height: 1.5; display: block; width: 100%;">
                            Enter a Shutdown Event ID above or select any run from the Test History table on the Live Dashboard.
                        </p>
                        <!-- Line 3: Action Button -->
                        <div style="margin-top: 6px; display: block; width: 100%;">
                            <button class="btn-secondary" onclick="loadView('dashboard')" style="padding: 8px 22px; font-size: 12px; font-weight: 600;">
                                Go to Dashboard
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }
    }
};

window.loadReport = async function(customId) {
    if (isReportLoading) return;

    let targetId = customId;
    if (targetId === undefined || targetId === null) {
        const input = document.getElementById('report-id');
        targetId = input ? input.value : '';
    }
    targetId = String(targetId).trim();

    const content = document.getElementById('report-content');
    if (!content) return;

    if (!targetId) {
        content.innerHTML = `
            <div class="panel" style="border-left: 3px solid var(--warning);">
                <h4 style="margin:0 0 6px 0; color:var(--warning);">Missing Run ID</h4>
                <p style="margin:0; font-size:13px; color:var(--text-muted);">
                    Please enter a valid Shutdown Event UUID or choose a test run from the <a href="javascript:void(0)" onclick="loadView('dashboard')" style="color:var(--accent-red); font-weight:700;">Live Dashboard</a>.
                </p>
            </div>
        `;
        return;
    }

    const input = document.getElementById('report-id');
    if (input && input.value !== targetId) {
        input.value = targetId;
    }
    State.latestShutdownId = targetId;

    isReportLoading = true;
    const btn = document.getElementById('load-report-btn');
    if (btn) btn.disabled = true;

    content.innerHTML = `
        <div class="panel" style="text-align:center; padding:40px 20px;">
            <div style="color:var(--accent-red); font-size:15px; font-weight:700; margin-bottom:8px;">
                Loading report for event <code>${targetId}</code>...
            </div>
            <div style="font-size:12px; color:var(--text-muted);">
                Fetching containment outcome, per-channel revocations, in-flight classifications, and cryptographic attestation proof.
            </div>
        </div>
    `;

    try {
        const report = await apiCall(`/api/shutdown/${encodeURIComponent(targetId)}/report`);

        const revs = (report.revocations || []).map(r => `
            <tr>
                <td style="font-weight:700; color:var(--accent-red); padding:10px;">${r.channel_type === 'network' ? 'NETWORK (External Tool/API)' : r.channel_type.toUpperCase()}</td>
                <td style="padding:10px;"><span class="badge ${r.success ? 'success' : 'danger'}">${r.success ? 'REVOKED' : 'FAILED'}</span></td>
                <td style="padding:10px; font-family:var(--font-mono); font-weight:600;">${Number(r.latency_ms || 0).toFixed(2)} ms</td>
                <td style="padding:10px; font-family:var(--font-mono);">${r.retries || 0}</td>
                <td style="padding:10px; color:${r.error ? 'var(--danger)' : 'var(--text-muted)'}; font-family:var(--font-mono); font-size:11px;">${r.error || 'None'}</td>
            </tr>
        `).join('');

        const actions = (report.agent_actions || []).map(a => `
            <tr>
                <td style="font-family:var(--font-mono); font-weight:700; color:var(--text-secondary); padding:8px 10px;">#${a.step_number}</td>
                <td style="font-weight:700; color:var(--text-primary); padding:8px 10px;">${a.tool_name}</td>
                <td style="padding:8px 10px;"><span class="badge ${a.outcome === 'accepted' ? 'success' : 'danger'}">${a.outcome.toUpperCase()}</span></td>
                <td style="color:${a.rejection_reason ? 'var(--danger)' : 'var(--text-muted)'}; font-size:11px; font-family:var(--font-mono); padding:8px 10px;">${a.rejection_reason || 'None'}</td>
                <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary); padding:8px 10px;">${a.prompt_tokens !== null && a.prompt_tokens !== undefined ? a.prompt_tokens : '--'} / ${a.completion_tokens !== null && a.completion_tokens !== undefined ? a.completion_tokens : '--'}</td>
                <td style="font-family:var(--font-mono); font-size:11px; color:var(--accent-red); font-weight:700; padding:8px 10px;">${a.model_duration_ms !== null && a.model_duration_ms !== undefined ? a.model_duration_ms.toFixed(0) + ' ms' : '--'}</td>
                <td style="font-family:var(--font-mono); font-size:11px; color:var(--text-secondary); padding:8px 10px;">${a.framework_wait_ms !== null && a.framework_wait_ms !== undefined ? a.framework_wait_ms.toFixed(0) + ' ms' : '--'}</td>
                <td style="font-size:11px; color:var(--text-muted); padding:8px 10px;">${formatLocalTime(a.timestamp)}</td>
            </tr>
        `).join('');

        const actionsSection = actions ? `
            <!-- Section 05: Agent Activity Telemetry -->
            <div class="section-heading">
                <span class="sec-num">05</span>
                <span class="sec-title">In-Flight Agent Activity Telemetry</span>
                <div class="sec-line"></div>
            </div>

            <div class="panel" style="margin-bottom:25px;">
                <div class="panel-header">
                    <span class="panel-title">Logged Agent Actions &amp; Interceptions</span>
                    <span class="badge neutral">${(report.agent_actions || []).length} Recorded Steps</span>
                </div>
                <div style="overflow-x:auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Step</th>
                                <th>Tool</th>
                                <th>Outcome</th>
                                <th>Rejection Reason</th>
                                <th>Tokens (In/Out)</th>
                                <th>Model RTT</th>
                                <th>Wait/Gap</th>
                                <th>Timestamp</th>
                            </tr>
                        </thead>
                        <tbody>${actions}</tbody>
                    </table>
                </div>
            </div>
        ` : `
            <!-- Section 05: Agent Activity Telemetry -->
            <div class="section-heading">
                <span class="sec-num">05</span>
                <span class="sec-title">In-Flight Agent Activity Telemetry</span>
                <div class="sec-line"></div>
            </div>

            <div class="panel" style="margin-bottom:25px;">
                <div class="empty-state" style="padding:20px; text-align:center; color:var(--text-muted); font-size:12px;">
                    No agent activity logged for this run
                </div>
            </div>
        `;

        let attestationBlock = '';
        if (report.attestation) {
            attestationBlock = `
                <!-- Section 04: Cryptographic Attestation -->
                <div class="section-heading">
                    <span class="sec-num">04</span>
                    <span class="sec-title">Cryptographic Attestation Evidence</span>
                    <div class="sec-line"></div>
                </div>

                <div class="panel" style="margin-bottom:25px; border-left: 3px solid var(--success);">
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border); padding-bottom:10px; margin-bottom:14px; flex-wrap:wrap; gap:8px;">
                        <h3 style="margin:0; color:var(--text-primary); font-size:15px;">🔐 Cryptographic Attestation Evidence</h3>
                        <span class="badge success">SIGNED &amp; CHAINED</span>
                    </div>
                    <div style="display:grid; grid-template-columns: 1fr; gap:10px; font-family:var(--font-mono); font-size:12px;">
                        <div style="background:var(--bg-card); padding:10px 14px; border-radius:6px; border:1px solid var(--border); display:flex; justify-content:space-between; flex-wrap:wrap; gap:6px;">
                            <span style="color:var(--text-muted)">Attestation Entry ID:</span>
                            <span style="color:var(--text-primary); font-weight:700;">${report.attestation.id}</span>
                        </div>
                        <div style="background:var(--bg-card); padding:10px 14px; border-radius:6px; border:1px solid var(--border); word-break:break-all;">
                            <span style="color:var(--text-muted); display:block; margin-bottom:3px;">Entry Hash (SHA-256):</span>
                            <strong style="color:var(--accent-red); display:block; font-size:12.5px;">${report.attestation.entry_hash}</strong>
                        </div>
                        <div style="background:var(--bg-card); padding:10px 14px; border-radius:6px; border:1px solid var(--border); word-break:break-all;">
                            <span style="color:var(--text-muted); display:block; margin-bottom:3px;">Previous Hash:</span>
                            <span style="color:var(--text-secondary); display:block;">${report.attestation.prev_hash}</span>
                        </div>
                        <div style="background:var(--bg-card); padding:10px 14px; border-radius:6px; border:1px solid var(--border); word-break:break-all;">
                            <span style="color:var(--text-muted); display:block; margin-bottom:3px;">Ed25519 Signature:</span>
                            <span style="color:var(--warning); display:block; font-size:11px;">${report.attestation.signature}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; align-items:center; font-size:11px; color:var(--text-muted); padding-top:4px; flex-wrap:wrap; gap:6px;">
                            <span>Attested At: ${formatLocalTime(report.attestation.created_at)}</span>
                            <span style="color:var(--success); font-weight:700;">Algorithm: Ed25519 (RFC 8032) / SHA-256</span>
                        </div>
                    </div>
                </div>
            `;
        } else {
            attestationBlock = `
                <!-- Section 04: Cryptographic Attestation -->
                <div class="section-heading">
                    <span class="sec-num">04</span>
                    <span class="sec-title">Cryptographic Attestation Evidence</span>
                    <div class="sec-line"></div>
                </div>

                <div class="panel" style="margin-bottom:25px; border-left: 3px solid var(--border);">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <h3 style="margin:0; color:var(--text-muted); font-size:15px;">🔐 Cryptographic Attestation Evidence</h3>
                        <span class="badge neutral">NOT RECORDED</span>
                    </div>
                    <div class="empty-state" style="padding:15px; color:var(--text-muted); font-size:12px; text-align:left;">
                        No cryptographic attestation entry recorded for this event. This cycle may have terminated before attestation emission.
                    </div>
                </div>
            `;
        }

        content.innerHTML = `
            <!-- Section 02: Incident Summary & Telemetry -->
            <div class="section-heading">
                <span class="sec-num">02</span>
                <span class="sec-title">Incident Summary &amp; Execution Telemetry</span>
                <div class="sec-line"></div>
            </div>

            <div class="panel" style="margin-bottom:25px;">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--border); padding-bottom:12px; margin-bottom:15px; flex-wrap:wrap; gap:10px;">
                    <div>
                        <h3 style="margin:0; font-size:16px;">Incident Summary: Strategy ${report.strategy}</h3>
                        <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">Event ID: <code style="color:var(--accent-red); font-weight:700;">${report.id}</code></div>
                    </div>
                    <div style="display:flex; gap:10px; flex-wrap:wrap;">
                        <a href="/api/audit/export/${targetId}" target="_blank" style="text-decoration:none;">
                            <button class="btn-shutdown" style="font-size:11px; padding:6px 14px;">Export Signed Report (MD)</button>
                        </a>
                    </div>
                </div>

                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap:12px; font-size:12px;">
                    <div><span style="color:var(--text-muted)">Strategy:</span> <strong>Strategy ${report.strategy}</strong></div>
                    <div><span style="color:var(--text-muted)">Triggered By:</span> <span>${report.triggered_by || report.trigger_type || 'manual'}</span></div>
                    <div><span style="color:var(--text-muted)">Trigger Time:</span> <span>${formatLocalTime(report.trigger_timestamp || report.started_at)}</span></div>
                    <div><span style="color:var(--text-muted)">Started At:</span> <span>${formatLocalTime(report.started_at)}</span></div>
                    <div><span style="color:var(--text-muted)">Finished At:</span> <span>${formatLocalTime(report.finished_at)}</span></div>
                    <div><span style="color:var(--text-muted)">Final State:</span> <span class="badge ${report.final_state === 'TERMINATED' ? 'success' : 'danger'}">${report.final_state}</span></div>
                    <div><span style="color:var(--text-muted)">Residual Risk:</span> <strong style="color:var(--warning);">${(report.residual_risk * 100).toFixed(1)}%</strong></div>
                    <div><span style="color:var(--text-muted)">Agent Mode:</span> <span class="badge neutral" style="font-size:11px;">${report.agent_mode || 'Gemini'}</span></div>
                    <div><span style="color:var(--text-muted)">Agent Model:</span> <span>${report.agent_model || 'gemini-3.5-flash-lite'}</span></div>
                    <div><span style="color:var(--text-muted)">Shutdown Delay:</span> <span>${Number(report.shutdown_delay || 0).toFixed(2)}s</span></div>
                    <div><span style="color:var(--text-muted)">Total Revocation Time:</span> <strong>${Number(report.total_revocation_ms || 0).toFixed(2)} ms</strong></div>
                    <div><span style="color:var(--text-muted)">Retries Total:</span> <span>${report.retries_total || 0}</span></div>
                    <div><span style="color:var(--text-muted)">Leaked Channels:</span> <span style="color:${report.leaked_channels > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:bold;">${report.leaked_channels}</span></div>
                    <div><span style="color:var(--text-muted)">In-Flight Failures:</span> <span style="color:${report.in_flight_failures > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:bold;">${report.in_flight_failures}</span></div>
                </div>

                <div style="margin-top:18px; padding-top:14px; border-top:1px solid var(--border);">
                    <div style="font-size:12px; font-weight:700; color:var(--text-primary); margin-bottom:8px; text-transform:uppercase;">LLM Token Usage & Timing Telemetry:</div>
                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap:10px; font-size:12px;">
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">PROMPT TOKENS</span>
                            <span class="kpi-num" style="font-size:18px;">${report.prompt_tokens !== null && report.prompt_tokens !== undefined ? report.prompt_tokens : '<span style="color:var(--text-muted); font-size:13px;">N/A</span>'}</span>
                        </div>
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">COMPLETION TOKENS</span>
                            <span class="kpi-num" style="font-size:18px;">${report.completion_tokens !== null && report.completion_tokens !== undefined ? report.completion_tokens : '<span style="color:var(--text-muted); font-size:13px;">N/A</span>'}</span>
                        </div>
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">TOTAL TOKENS</span>
                            <span class="kpi-num" style="font-size:18px; color:var(--accent-red);">${report.total_tokens !== null && report.total_tokens !== undefined ? report.total_tokens : '<span style="color:var(--text-muted); font-size:13px;">N/A</span>'}</span>
                        </div>
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">MODEL ROUND-TRIP</span>
                            <span class="kpi-num" style="font-size:18px;">${Number(report.model_total_duration_ms || 0).toFixed(1)} ms</span>
                        </div>
                    </div>
                </div>

                <div style="margin-top:18px; padding-top:14px; border-top:1px solid var(--border);">
                    <div style="font-size:12px; font-weight:700; color:var(--text-primary); margin-bottom:8px; text-transform:uppercase;">In-Flight Operation Classifications at Kill Cutoff:</div>
                    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:10px; font-size:12px;">
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">ACTIVE AT CUTOFF</span>
                            <span class="kpi-num" style="font-size:18px; color:var(--accent-red);">${report.actions_running || 0}</span>
                        </div>
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">COMPLETED PRE-CUTOFF</span>
                            <span class="kpi-num" style="font-size:18px; color:var(--success);">${report.actions_completed || 0}</span>
                        </div>
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">TOTAL ACTIONS STARTED</span>
                            <span class="kpi-num" style="font-size:18px;">${report.actions_started || 0}</span>
                        </div>
                        <div class="kpi-tile" style="padding:10px 14px;">
                            <span class="kpi-title">POST-KILL LEAKS</span>
                            <span class="kpi-num ${(report.in_flight_failures || 0) > 0 ? 'color-danger' : 'color-success'}" style="font-size:18px;">${report.in_flight_failures || 0}</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Section 03: Multi-Channel Revocations -->
            <div class="section-heading">
                <span class="sec-num">03</span>
                <span class="sec-title">Multi-Channel Revocation Breakdown</span>
                <div class="sec-line"></div>
            </div>

            <div class="panel" style="margin-bottom:25px;">
                <div class="panel-header">
                    <span class="panel-title">Revocation Channel Telemetry</span>
                </div>
                <div style="overflow-x:auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Channel</th>
                                <th>Status</th>
                                <th>Latency</th>
                                <th>Retries</th>
                                <th>Error</th>
                            </tr>
                        </thead>
                        <tbody>${revs || '<tr><td colspan="5" style="text-align:center; padding:15px; color:var(--text-muted);">No revocations recorded for this run</td></tr>'}</tbody>
                    </table>
                </div>
            </div>

            ${attestationBlock}

            ${actionsSection}
        `;
    } catch(e) {
        content.innerHTML = `
            <div class="panel" style="border-left: 3px solid var(--danger);">
                <h3 style="color:var(--danger); margin-top:0;">Report Not Found</h3>
                <p style="color:var(--text-muted); font-size:13px; margin-bottom:12px;">
                    Could not load report for ID <code>${targetId}</code>. ${e && e.detail ? e.detail : 'The record may not exist or authentication has expired.'}
                </p>
                <button class="btn-secondary" onclick="loadView('dashboard')">Return to Dashboard</button>
            </div>
        `;
    } finally {
        isReportLoading = false;
        const btn = document.getElementById('load-report-btn');
        if (btn) btn.disabled = false;
    }
};
