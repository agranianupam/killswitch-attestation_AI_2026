window.render_agent = async function(container) {
    container.innerHTML = `<h2>Agent Details</h2><div class="panel">Loading agent credentials...</div>`;

    try {
        const [agent, creds, status] = await Promise.all([
            apiCall('/api/agent'),
            apiCall('/api/agent/credentials'),
            apiCall('/api/agent/status').catch(() => ({}))
        ]);

        let credsHtml = '';
        if(!creds || creds.length === 0) {
            credsHtml = `<tr><td colspan="3" style="text-align:center; color:var(--text-muted); padding:20px;">No credentials provisioned yet.</td></tr>`;
        } else {
            credsHtml = creds.map(c => `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="font-weight:bold; color:var(--neon-blue); padding:12px;">${c.channel_type === 'network' ? 'NETWORK (External Tool/API)' : c.channel_type.toUpperCase()}</td>
                    <td style="font-family:monospace; color:#ccc; padding:12px;"><code>${c.credential_value}</code></td>
                    <td style="padding:12px;"><span class="badge ${c.status === 'ACTIVE' ? 'success' : (c.status === 'REVOKED' ? 'danger' : 'warning')}">${c.status}</span></td>
                </tr>
            `).join('');
        }

        container.innerHTML = `
            <div style="margin-bottom: 25px;">
                <h2 style="margin:0; font-size:28px; font-weight:800;">Agent Profile & Credentials</h2>
                <p style="color:var(--text-muted); margin-top:5px;">
                    Active identity: <strong style="color:var(--text-main);">${agent.name || 'Sandbox Agent'}</strong> (ID: <code>${agent.id ? agent.id.substring(0,8) : 'N/A'}</code>) — Status: <span class="badge ${agent.status === 'ACTIVE' ? 'success' : 'warning'}" style="font-size:11px;">${agent.status || 'UNKNOWN'}</span>
                </p>
                <div style="display:flex; gap:15px; margin-top:10px; font-size:12px;">
                    <div style="background:rgba(255,255,255,0.05); padding:6px 12px; border-radius:6px; border:1px solid var(--border);">
                        <span style="color:var(--text-muted)">Runtime Mode:</span> <strong>${status.mode || 'Gemini'}</strong>
                    </div>
                    <div style="background:rgba(255,255,255,0.05); padding:6px 12px; border-radius:6px; border:1px solid var(--border);">
                        <span style="color:var(--text-muted)">Configured Model:</span> <code>${status.model || 'gemini-3.5-flash-lite'}</code>
                    </div>
                    <div style="background:rgba(255,255,255,0.05); padding:6px 12px; border-radius:6px; border:1px solid var(--border);">
                        <span style="color:var(--text-muted)">API Key:</span> <span class="badge ${status.key_status === 'configured' ? 'success' : 'warning'}" style="font-size:10px;">${status.key_status || 'missing'}</span>
                    </div>
                </div>
            </div>
            <div class="panel">
                <h3 style="margin-top:0; color:var(--neon-purple);">Assigned Credentials & Access Channels</h3>
                <table style="width:100%; border-collapse:collapse; margin-top:15px; font-size:13px;">
                    <thead>
                        <tr style="border-bottom:1px solid var(--border); text-align:left; color:var(--text-muted);">
                            <th style="padding:10px;">Channel</th>
                            <th style="padding:10px;">Masked Value</th>
                            <th style="padding:10px;">Status</th>
                        </tr>
                    </thead>
                    <tbody>${credsHtml}</tbody>
                </table>
            </div>
        `;
    } catch(e) {
        container.innerHTML = `<h2>Agent Details</h2><div class="panel">Failed to load agent details.</div>`;
    }
};
