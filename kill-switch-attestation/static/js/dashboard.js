/*
static/js/dashboard.js
*/

window.render_dashboard = async function(container) {
    container.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <div>
                <h2 style="margin:0; font-size:28px;">Live Dashboard</h2>
                <p style="color: var(--text-muted); margin-top: 5px;">Real-time telemetry and kill-switch monitoring.</p>
            </div>
            <button class="danger" onclick="loadView('shutdown')" style="font-size: 16px; padding: 15px 30px;">⚠️ EMERGENCY SHUTDOWN</button>
        </div>
        
        <div class="dashboard-grid">
            <div class="panel" id="agent-status-panel">
                <h3>Agent State</h3>
                <div style="margin-top: 15px;">Loading agent state...</div>
            </div>
            <div class="panel">
                <h3>Operations Activity</h3>
                <div class="chart-container">
                    <canvas id="opsActivityChart"></canvas>
                </div>
            </div>
        </div>

        <div class="panel">
            <h3>Recent In-Flight Operations</h3>
            <table id="ops-table">
                <thead><tr><th>Op ID</th><th>Operation Type</th><th>Status</th><th>Duration (ms)</th><th>Start Time</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
    `;
    
    // Initialize chart
    window.opsChartInstance = new Chart(document.getElementById('opsActivityChart').getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: ['RUNNING', 'COMPLETED', 'FAILED'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: ['#06b6d4', '#10b981', '#ef4444'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { position: 'right', labels: { color: '#e0e0e0' } }
            }
        }
    });

    await updateAgentState();
    await updateOperations();
    
    // Listen for WS events
    window.addEventListener('ws_agent_status', handleAgentStatus);
    window.addEventListener('ws_operation_started', updateOperations);
    window.addEventListener('ws_operation_status', updateOperations);
};

// Cleanup event listeners when leaving dashboard
window.cleanup_dashboard = function() {
    window.removeEventListener('ws_agent_status', handleAgentStatus);
    window.removeEventListener('ws_operation_started', updateOperations);
    window.removeEventListener('ws_operation_status', updateOperations);
    if(window.opsChartInstance) {
        window.opsChartInstance.destroy();
    }
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
            <h3>Agent State</h3>
            <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 15px;">
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border); padding-bottom:10px;">
                    <strong style="color:var(--text-muted)">Agent ID:</strong> 
                    <span style="font-family:monospace">${agent.id}</span>
                </div>
                <div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border); padding-bottom:10px;">
                    <strong style="color:var(--text-muted)">Current Status:</strong> 
                    <span class="badge ${statusClass}">${agent.status}</span>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <strong style="color:var(--text-muted)">Calculated Risk:</strong> 
                    <span class="badge ${riskClass}">${agent.risk_level}</span>
                </div>
            </div>
        `;
    } catch(e) {}
}

async function updateOperations() {
    if(State.currentView !== 'dashboard') return;
    try {
        const ops = await apiCall('/api/agent/operations');
        
        // Update Chart
        const running = ops.filter(o => o.status === 'RUNNING').length;
        const completed = ops.filter(o => o.status === 'COMPLETED').length;
        const failed = ops.filter(o => o.status === 'FAILED').length;
        
        if (window.opsChartInstance) {
            window.opsChartInstance.data.datasets[0].data = [running, completed, failed];
            window.opsChartInstance.update();
        }

        // Update Table
        const tbody = document.querySelector('#ops-table tbody');
        if(!tbody) return;
        
        tbody.innerHTML = ops.slice(0, 6).map(op => {
            let statusColor = '#10b981';
            if(op.status === 'RUNNING') statusColor = '#06b6d4';
            if(op.status === 'FAILED') statusColor = '#ef4444';
            
            return `
            <tr>
                <td style="font-family:monospace; color:var(--text-muted)">${op.id.substring(0,8)}</td>
                <td style="font-weight:600">${op.operation_type.replace('_', ' ').toUpperCase()}</td>
                <td><span style="color:${statusColor}; font-weight:bold;">${op.status}</span></td>
                <td>${op.duration_ms} ms</td>
                <td style="color:var(--text-muted); font-size:12px;">${new Date(op.started_at).toLocaleTimeString()}</td>
            </tr>
            `;
        }).join('');
    } catch(e) {}
}

function handleAgentStatus(e) {
    if(State.currentView === 'dashboard') updateAgentState();
}
