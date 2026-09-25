/*
static/js/report.js
*/

window.render_report = async function(container) {
    container.innerHTML = `<h2>Shutdown Report</h2><div class="form-group">
        <label>Enter Shutdown Event ID:</label>
        <input type="text" id="report-id" placeholder="Event ID">
        <button onclick="loadReport()">Load Report</button>
    </div>
    <div id="report-content"></div>`;
};

window.loadReport = async function() {
    const id = document.getElementById('report-id').value;
    if(!id) return;
    
    try {
        const report = await apiCall(`/api/shutdown/${id}/report`);
        const content = document.getElementById('report-content');
        
        const revs = report.revocations.map(r => `
            <tr>
                <td>${r.channel_type}</td>
                <td>${r.success ? 'Yes' : 'No'}</td>
                <td>${r.latency_ms.toFixed(2)} ms</td>
                <td>${r.retries}</td>
            </tr>
        `).join('');
        
        content.innerHTML = `
            <div class="panel">
                <h3>Summary</h3>
                <p><strong>Strategy:</strong> ${report.strategy}</p>
                <p><strong>Residual Risk:</strong> ${report.residual_risk}</p>
                <p><strong>Final State:</strong> ${report.final_state}</p>
                <p><strong>Leaked Channels:</strong> ${report.leaked_channels}</p>
                <p><strong>In-flight Failures:</strong> ${report.in_flight_failures}</p>
            </div>
            <div class="panel">
                <h3>Revocations</h3>
                <table>
                    <thead><tr><th>Channel</th><th>Success</th><th>Latency</th><th>Retries</th></tr></thead>
                    <tbody>${revs}</tbody>
                </table>
            </div>
            <a href="/api/audit/export/${id}" target="_blank"><button>Export Signed Report (MD)</button></a>
        `;
    } catch(e) {
        document.getElementById('report-content').innerHTML = `<p style="color:var(--danger)">Report not found.</p>`;
    }
}
