/*
static/js/agent.js — Agent Details & Credentials
*/

window.render_agent = async function(container) {
    container.innerHTML = `<h2>Agent Details</h2><div class="panel">Loading agent credentials...</div>`;
    
    try {
        const agent = await apiCall('/api/agent');
        const creds = await apiCall('/api/agent/credentials');
        
        let credsHtml = '';
        if(!creds || creds.length === 0) {
            credsHtml = `<tr><td colspan="3" style="text-align:center; color:var(--text-muted); padding:20px;">No credentials provisioned yet.</td></tr>`;
        } else {
            credsHtml = creds.map(c => `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <td style="font-weight:bold; color:var(--neon-blue); padding:12px;">${c.channel_type.toUpperCase()}</td>
                    <td style="font-family:monospace; color:#ccc; padding:12px;"><code>${c.credential_value}</code></td>
                    <td style="padding:12px;"><span class="badge ${c.status === 'ACTIVE' ? 'success' : (c.status === 'REVOKED' ? 'danger' : 'warning')}">${c.status}</span></td>
                </tr>
            `).join('');
        }
        
        container.innerHTML = `
            <div style="margin-bottom: 25px;">
                <h2 style="margin:0; font-size:28px; font-weight:800;">Agent Profile & Credentials</h2>
                <p style="color:var(--text-muted); margin-top:5px;">Active identity: <strong style="color:var(--text-main);">${agent.name || 'Sandbox Agent'}</strong> (ID: <code>${agent.id ? agent.id.substring(0,8) : 'N/A'}</code>) — Status: <span class="badge ${agent.status === 'ACTIVE' ? 'success' : 'warning'}" style="font-size:11px;">${agent.status || 'UNKNOWN'}</span></p>
            </div>
            <div class="panel">
                <h3 style="margin-top:0; color:var(--neon-purple);">Assigned Credentials & Channels</h3>
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
