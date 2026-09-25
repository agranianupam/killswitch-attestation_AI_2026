/*
static/js/dashboard.js
*/

window.render_dashboard = async function(container) {
    container.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Dashboard</h2>
            <button class="danger" onclick="loadView('shutdown')">EMERGENCY SHUTDOWN</button>
        </div>
        <div class="panel" id="agent-status-panel">Loading agent state...</div>
        <div class="panel">
            <h3>Recent Operations</h3>
            <table id="ops-table">
                <thead><tr><th>ID</th><th>Type</th><th>Status</th><th>Duration (ms)</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
    `;
    
    updateAgentState();
    updateOperations();
    
    // Listen for WS events
    window.addEventListener('ws_agent_status', handleAgentStatus);
    window.addEventListener('ws_operation_started', updateOperations);
    window.addEventListener('ws_operation_status', updateOperations);
};

async function updateAgentState() {
    if(State.currentView !== 'dashboard') return;
    try {
        const agent = await apiCall('/api/agent');
        let riskClass = 'success';
        if(agent.risk_level === 'HIGH') riskClass = 'danger';
        else if(agent.risk_level === 'MEDIUM') riskClass = 'warning';
        
        let statusClass = 'success';
        if(agent.status.includes('SHUTDOWN') || agent.status === 'CONTAINING') statusClass = 'warning';
        else if(agent.status === 'TERMINATED' || agent.status === 'CONTAINED') statusClass = 'danger';
        
        document.getElementById('agent-status-panel').innerHTML = `
            <div><strong>Agent ID:</strong> ${agent.id}</div>
            <div><strong>Status:</strong> <span class="badge ${statusClass}">${agent.status}</span></div>
            <div><strong>Risk Level:</strong> <span class="badge ${riskClass}">${agent.risk_level}</span></div>
        `;
    } catch(e) {}
}

async function updateOperations() {
    if(State.currentView !== 'dashboard') return;
    try {
        const ops = await apiCall('/api/agent/operations');
        const tbody = document.querySelector('#ops-table tbody');
        if(!tbody) return;
        tbody.innerHTML = ops.slice(0, 5).map(op => `
            <tr>
                <td>${op.id.substring(0,8)}</td>
                <td>${op.operation_type}</td>
                <td>${op.status}</td>
                <td>${op.duration_ms}</td>
            </tr>
        `).join('');
    } catch(e) {}
}

function handleAgentStatus(e) {
    if(State.currentView === 'dashboard') updateAgentState();
}
