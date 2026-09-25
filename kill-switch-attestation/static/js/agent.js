/*
static/js/agent.js
*/

window.render_agent = async function(container) {
    container.innerHTML = `<h2>Agent Details</h2><div id="agent-creds">Loading...</div>`;
    
    try {
        const creds = await apiCall('/api/agent/credentials');
        const tbody = creds.map(c => `
            <tr>
                <td>${c.channel_type}</td>
                <td><code>${c.credential_value}</code></td>
                <td><span class="badge ${c.status === 'ACTIVE' ? 'success' : (c.status === 'REVOKED' ? 'danger' : 'warning')}">${c.status}</span></td>
            </tr>
        `).join('');
        
        container.innerHTML = `
            <h2>Agent Details</h2>
            <div class="panel">
                <h3>Credentials</h3>
                <table>
                    <thead><tr><th>Channel</th><th>Value</th><th>Status</th></tr></thead>
                    <tbody>${tbody}</tbody>
                </table>
            </div>
        `;
    } catch(e) {
        container.innerHTML = `<h2>Agent Details</h2><div class="panel">Failed to load</div>`;
    }
};
