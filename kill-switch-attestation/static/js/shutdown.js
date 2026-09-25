/*
static/js/shutdown.js
*/

window.render_shutdown = function(container) {
    container.innerHTML = `
        <h2>Emergency Shutdown</h2>
        <div class="panel">
            <h3>Select Strategy</h3>
            <div class="form-group">
                <label><input type="radio" name="strategy" value="A" checked> <strong>Strategy A:</strong> Revoke only</label><br>
                <label><input type="radio" name="strategy" value="B"> <strong>Strategy B:</strong> Revoke + Block new operations</label><br>
                <label><input type="radio" name="strategy" value="C"> <strong>Strategy C:</strong> Revoke + Block + Cancel in-flight</label>
            </div>
            <button class="danger" onclick="triggerShutdown()">INITIATE SHUTDOWN</button>
        </div>
        <div class="panel hidden" id="shutdown-progress">
            <h3>Progress</h3>
            <ul id="progress-log"></ul>
        </div>
    `;
    
    window.addEventListener('ws_shutdown_progress', handleProgress);
};

async function triggerShutdown() {
    if(!State.token) {
        showLogin();
        return;
    }
    const strategy = document.querySelector('input[name="strategy"]:checked').value;
    
    document.getElementById('shutdown-progress').classList.remove('hidden');
    document.getElementById('progress-log').innerHTML = '';
    
    try {
        await apiCall(`/api/shutdown?strategy=${strategy}&trigger_type=manual`, 'POST');
    } catch(e) {
        alert(e.detail || 'Failed to trigger shutdown');
    }
}

function handleProgress(e) {
    if(State.currentView !== 'shutdown') return;
    const log = document.getElementById('progress-log');
    if(log) {
        const li = document.createElement('li');
        li.textContent = `[${e.detail.stage}] ${e.detail.detail}`;
        log.appendChild(li);
        
        if(e.detail.stage === 'complete') {
            const btn = document.createElement('button');
            btn.textContent = 'View Report';
            btn.onclick = () => loadView('report');
            log.appendChild(btn);
        }
    }
}
