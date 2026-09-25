/*
static/js/audit.js
*/

window.render_audit = async function(container) {
    container.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Audit Logs & Attestation</h2>
            <button onclick="verifyChain()">Verify Hash Chain</button>
        </div>
        <div id="verify-result" class="hidden" style="margin-bottom: 20px; padding: 15px; border-radius: 4px;"></div>
        <div class="panel">
            <table id="audit-table">
                <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Detail</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
    `;
    
    loadAuditLogs();
};

async function loadAuditLogs() {
    try {
        const logs = await apiCall('/api/audit/logs');
        const tbody = document.querySelector('#audit-table tbody');
        if(!tbody) return;
        
        tbody.innerHTML = logs.map(l => `
            <tr>
                <td>${new Date(l.timestamp).toLocaleString()}</td>
                <td><span class="badge ${l.actor === 'system' ? 'success' : 'warning'}">${l.actor}</span></td>
                <td>${l.action}</td>
                <td>${l.detail}</td>
            </tr>
        `).join('');
    } catch(e) {}
}

window.verifyChain = async function() {
    const resDiv = document.getElementById('verify-result');
    resDiv.classList.remove('hidden');
    resDiv.innerHTML = 'Verifying...';
    resDiv.style.backgroundColor = 'var(--bg-panel)';
    
    try {
        const res = await apiCall('/api/audit/verify-chain', 'POST');
        if(res.valid) {
            resDiv.innerHTML = `✅ <strong>Chain Verified!</strong> ${res.entries_checked} entries checked and cryptographically sound.`;
            resDiv.style.backgroundColor = 'rgba(3, 218, 198, 0.2)';
            resDiv.style.color = 'var(--success)';
        } else {
            resDiv.innerHTML = `❌ <strong>Verification Failed!</strong> Tampering detected at index ${res.first_failure_index}.`;
            resDiv.style.backgroundColor = 'rgba(207, 102, 121, 0.2)';
            resDiv.style.color = 'var(--danger)';
        }
    } catch(e) {
        resDiv.innerHTML = `❌ Error verifying chain.`;
        resDiv.style.backgroundColor = 'rgba(207, 102, 121, 0.2)';
        resDiv.style.color = 'var(--danger)';
    }
}
