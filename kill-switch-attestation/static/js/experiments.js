/*
static/js/experiments.js
*/

window.render_experiments = async function(container) {
    container.innerHTML = `
        <h2>Experiments</h2>
        <div class="panel">
            <h3>Run New Experiment</h3>
            <div class="form-group">
                <label>Strategy</label>
                <select id="exp-strategy">
                    <option value="A">Strategy A</option>
                    <option value="B">Strategy B</option>
                    <option value="C">Strategy C</option>
                </select>
            </div>
            <div class="form-group">
                <label>Cycles (1-100)</label>
                <input type="number" id="exp-cycles" value="40" min="1" max="100">
            </div>
            <button onclick="runExperiment()">Start</button>
        </div>
        <div class="panel">
            <h3>History</h3>
            <table id="exp-table">
                <thead><tr><th>ID</th><th>Strategy</th><th>Cycles</th><th>Status</th><th>Actions</th></tr></thead>
                <tbody></tbody>
            </table>
        </div>
    `;
    
    loadExperiments();
};

window.runExperiment = async function() {
    if(!State.token) {
        showLogin();
        return;
    }
    const strategy = document.getElementById('exp-strategy').value;
    const cycles = document.getElementById('exp-cycles').value;
    
    try {
        await apiCall(`/api/experiments?strategy=${strategy}&cycles=${cycles}`, 'POST');
        setTimeout(loadExperiments, 500);
    } catch(e) {
        alert(e.detail || 'Failed to start experiment');
    }
}

window.loadExperiments = async function() {
    try {
        const exps = await apiCall('/api/experiments');
        const tbody = document.querySelector('#exp-table tbody');
        if(!tbody) return;
        
        tbody.innerHTML = exps.map(e => `
            <tr>
                <td>${e.id.substring(0,8)}</td>
                <td>${e.strategy}</td>
                <td>${e.cycle_count}</td>
                <td>${e.status}</td>
                <td>
                    ${e.status === 'COMPLETED' ? `<a href="/api/experiments/${e.id}/csv" target="_blank">Download CSV</a>` : ''}
                </td>
            </tr>
        `).join('');
    } catch(e) {}
}
