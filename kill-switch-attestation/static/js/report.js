window.render_report = async function(container) {
    container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h2>Shutdown Report</h2>
        </div>
        <div class="panel">
            <div class="form-group">
                <label>Enter Shutdown Event ID:</label>
                <div style="display:flex; gap:10px;">
                    <input type="text" id="report-id" placeholder="Event ID" value="${State.latestShutdownId || ''}">
                    <button onclick="loadReport()">Load Report</button>
                </div>
            </div>
        </div>
        <div id="report-content"></div>
    `;

    if (State.latestShutdownId) {
        loadReport();
    }
};

window.loadReport = async function() {
    const id = document.getElementById('report-id').value;
    if(!id) return;

    try {
        const report = await apiCall(`/api/shutdown/${id}/report`);
        const content = document.getElementById('report-content');

        const revs = (report.revocations || []).map(r => `
            <tr>
                <td style="font-weight:600; color:var(--neon-blue);">${r.channel_type === 'network' ? 'NETWORK (External Tool/API)' : r.channel_type.toUpperCase()}</td>
                <td><span class="badge ${r.success ? 'success' : 'danger'}">${r.success ? 'REVOKED' : 'FAILED'}</span></td>
                <td>${Number(r.latency_ms || 0).toFixed(2)} ms</td>
                <td>${r.retries || 0}</td>
                <td style="color:${r.error ? 'var(--danger)' : 'var(--text-muted)'}; font-family:monospace; font-size:11px;">${r.error || 'None'}</td>
            </tr>
        `).join('');

        const actions = (report.agent_actions || []).map(a => `
            <tr>
                <td style="font-family:monospace;">${a.step_number}</td>
                <td style="font-weight:600; color:var(--text-main);">${a.tool_name}</td>
                <td><span class="badge ${a.outcome === 'accepted' ? 'success' : 'danger'}">${a.outcome.toUpperCase()}</span></td>
                <td style="color:${a.rejection_reason ? 'var(--danger)' : 'var(--text-muted)'}; font-size:11px; font-family:monospace;">${a.rejection_reason || 'None'}</td>
                <td style="font-family:monospace; font-size:11px; color:#aaa;">${a.operation_id ? a.operation_id.substring(0,8) : 'None'}</td>
                <td style="font-size:11px; color:var(--text-muted);">${formatLocalTime(a.timestamp)}</td>
            </tr>
        `).join('');

        const actionsTable = actions ? `
            <div class="panel" style="margin-top:20px;">
                <h3 style="margin-top:0; color:var(--warning);">Agent Activity Table</h3>
                <table>
                    <thead><tr><th>Step</th><th>Tool</th><th>Outcome</th><th>Rejection Reason</th><th>Operation ID</th><th>Local Time</th></tr></thead>
                    <tbody>${actions}</tbody>
                </table>
            </div>
        ` : `
            <div class="panel" style="margin-top:20px;">
                <h3 style="margin-top:0; color:var(--warning);">Agent Activity Table</h3>
                <div class="empty-state">No agent activity logged for this run</div>
            </div>
        `;

        content.innerHTML = `
            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid var(--border); padding-bottom:10px; margin-bottom:15px;">
                    <h3 style="margin:0;">Incident Summary</h3>
                    <div style="display:flex; gap:10px;">
                        <button onclick="verifySingleEvent('${id}')" style="background:#222; border:1px solid var(--border); color:#fff; font-size:11px; padding:6px 12px; cursor:pointer;">Verify Entry</button>
                        <a href="/api/audit/export/${id}" target="_blank" style="text-decoration:none;"><button style="font-size:11px; padding:6px 12px;">Export Signed Report (MD)</button></a>
                    </div>
                </div>
                <div id="single-verify-banner" class="hidden" style="margin-bottom:15px; padding:10px; border-radius:4px; font-size:12px;"></div>
                <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:15px; font-size:13px;">
                    <div><span style="color:var(--text-muted)">Event ID:</span> <code style="color:var(--neon-blue);">${report.id}</code></div>
                    <div><span style="color:var(--text-muted)">Strategy:</span> <strong>Strategy ${report.strategy}</strong></div>
                    <div><span style="color:var(--text-muted)">Triggered By:</span> <span>${report.triggered_by || report.trigger_type || 'manual'}</span></div>
                    <div><span style="color:var(--text-muted)">Trigger Time:</span> <span>${formatLocalTime(report.trigger_timestamp || report.started_at)}</span></div>
                    <div><span style="color:var(--text-muted)">Started At:</span> <span>${formatLocalTime(report.started_at)}</span></div>
                    <div><span style="color:var(--text-muted)">Finished At:</span> <span>${formatLocalTime(report.finished_at)}</span></div>
                    <div><span style="color:var(--text-muted)">Final State:</span> <span class="badge ${report.final_state === 'TERMINATED' ? 'success' : 'danger'}">${report.final_state}</span></div>
                    <div><span style="color:var(--text-muted)">Residual Risk:</span> <strong style="color:var(--warning);">${(report.residual_risk * 100).toFixed(1)}%</strong></div>
                    <div><span style="color:var(--text-muted)">Agent Mode:</span> <span class="badge" style="background:#222; font-size:11px;">${report.agent_mode || 'Gemini'}</span></div>
                    <div><span style="color:var(--text-muted)">Agent Model:</span> <span>${report.agent_model || 'gemini-3.5-flash-lite'}</span></div>
                    <div><span style="color:var(--text-muted)">Shutdown Delay:</span> <span>${Number(report.shutdown_delay || 0).toFixed(2)}s</span></div>
                    <div><span style="color:var(--text-muted)">Total Revocation Time:</span> <strong>${Number(report.total_revocation_ms || 0).toFixed(2)} ms</strong></div>
                    <div><span style="color:var(--text-muted)">Retries Total:</span> <span>${report.retries_total || 0}</span></div>
                    <div><span style="color:var(--text-muted)">Leaked Channels:</span> <span style="color:${report.leaked_channels > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:bold;">${report.leaked_channels}</span></div>
                    <div><span style="color:var(--text-muted)">In-Flight Failures:</span> <span style="color:${report.in_flight_failures > 0 ? 'var(--danger)' : 'var(--success)'}; font-weight:bold;">${report.in_flight_failures}</span></div>
                    <div><span style="color:var(--text-muted)">Actions Running At Kill:</span> <span>${report.actions_running || 0}</span></div>
                    <div><span style="color:var(--text-muted)">Actions Completed Before Kill:</span> <span>${report.actions_completed || 0}</span></div>
                    <div><span style="color:var(--text-muted)">Total Actions Started:</span> <span>${report.actions_started || 0}</span></div>
                </div>
            </div>
            <div class="panel" style="margin-top:20px;">
                <h3 style="margin-top:0;">Multi-Channel Revocations</h3>
                <table>
                    <thead><tr><th>Channel</th><th>Status</th><th>Latency</th><th>Retries</th><th>Error</th></tr></thead>
                    <tbody>${revs || '<tr><td colspan="5" style="text-align:center;">No revocations</td></tr>'}</tbody>
                </table>
            </div>
            ${actionsTable}
        `;
    } catch(e) {
        document.getElementById('report-content').innerHTML = `<p style="color:var(--danger)">Report not found or error loading report.</p>`;
    }
};

window.verifySingleEvent = async function(id) {
    const banner = document.getElementById('single-verify-banner');
    if(!banner) return;
    banner.classList.remove('hidden');
    banner.style.background = '#222';
    banner.style.color = '#fff';
    banner.textContent = 'Verifying cryptographic attestation for entry...';
    try {
        const res = await apiCall('/api/shutdown/verify-chain');
        if(res.valid) {
            banner.style.background = 'rgba(3, 218, 198, 0.2)';
            banner.style.color = 'var(--success)';
            banner.innerHTML = `✅ <strong>Attestation Verified!</strong> Chain is cryptographically sound across all ${res.entries_checked} entries.`;
        } else {
            banner.style.background = 'rgba(207, 102, 121, 0.2)';
            banner.style.color = 'var(--danger)';
            banner.innerHTML = `❌ <strong>Verification Alert:</strong> Chain break detected at entry index ${res.first_failure_index}.`;
        }
    } catch(err) {
        banner.style.background = 'rgba(207, 102, 121, 0.2)';
        banner.style.color = 'var(--danger)';
        banner.textContent = 'Verification error: ' + err.message;
    }
};
