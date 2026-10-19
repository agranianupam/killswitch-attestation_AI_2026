window.render_shutdown = async function(container) {
    window.cleanup_shutdown();

    container.innerHTML = `
        <div style="margin-bottom: 25px;">
            <h2 style="margin:0; font-size:32px; font-weight:800; color:var(--danger)">Emergency Shutdown Control</h2>
            <p style="color:var(--text-muted); margin-top:5px;">Immediately contain or terminate the selected agent.</p>
        </div>
        
        <div class="guidelines-box" style="background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3);">
            <h4 style="color: #f87171;">⚠️ Administrative Warning</h4>
            <p style="color: #f87171; margin:0;">Executing a shutdown will instantly revoke credentials. Depending on the strategy, running operations may be forcibly terminated. This action is irreversible.</p>
        </div>

        <div class="strategy-grid">
            <div class="strategy-card">
                <h3 style="color:var(--success)">Strategy A<br><span style="font-size:14px; color:var(--text-muted); font-weight:normal">Immediate Revocation</span></h3>
                <ul>
                    <li>Revokes all API keys & IAM roles.</li>
                    <li><strong>In-flight ops:</strong> Allowed to continue.</li>
                    <li>Expected State: <span class="badge warning" style="padding:2px 6px">CONTAINED</span> (or <span class="badge success" style="padding:2px 6px">TERMINATED</span> if clean)</li>
                </ul>
                <button style="width:100%" onclick="confirmShutdown('A')">EXECUTE STRATEGY A</button>
            </div>
            <div class="strategy-card">
                <h3 style="color:var(--warning)">Strategy B<br><span style="font-size:14px; color:var(--text-muted); font-weight:normal">Graceful Containment</span></h3>
                <ul>
                    <li>Revokes all credentials.</li>
                    <li><strong>New work blocked.</strong></li>
                    <li><strong>In-flight ops:</strong> Allowed to complete.</li>
                    <li>Expected State: <span class="badge warning" style="padding:2px 6px">CONTAINED</span></li>
                </ul>
                <button style="width:100%" onclick="confirmShutdown('B')">EXECUTE STRATEGY B</button>
            </div>
            <div class="strategy-card danger-hover">
                <h3 style="color:var(--danger)">Strategy C<br><span style="font-size:14px; color:var(--text-muted); font-weight:normal">Immediate Containment</span></h3>
                <ul>
                    <li>Revokes all credentials.</li>
                    <li><strong>New work blocked.</strong></li>
                    <li><strong>In-flight ops:</strong> Forcibly cancelled.</li>
                    <li>Expected State: <span class="badge danger" style="padding:2px 6px">CONTAINED</span></li>
                </ul>
                <button class="danger" style="width:100%" onclick="confirmShutdown('C')">EXECUTE STRATEGY C</button>
            </div>
        </div>

        <div class="panel hidden" id="shutdown-progress" style="margin-top: 30px;">
            <h3>Live Progress Log</h3>
            <ul id="progress-log" style="list-style:none; padding:0; font-family:monospace; color:#ccc;"></ul>
        </div>
    `;
    window.addEventListener('ws_shutdown_progress', handleProgress);
};

window.confirmShutdown = async function(strategy) {
    if(!State.token) {
        showLogin();
        return;
    }
    const modal = document.getElementById('shutdown-modal');
    document.getElementById('modal-strategy').textContent = `Strategy ${strategy}`;
    
    try {
        const agent = await apiCall('/api/agent');
        document.getElementById('modal-agent-id').textContent = `${agent.name} (${agent.id.substring(0,8)})`;
    } catch(e) {
        document.getElementById('modal-agent-id').textContent = 'Sandboxed-Agent';
    }

    const confirmBtn = document.getElementById('modal-confirm-btn');
    confirmBtn.onclick = () => {
        modal.classList.add('hidden');
        triggerShutdown(strategy);
    };
    
    modal.classList.remove('hidden');
};

window.triggerShutdown = async function(strategy) {
    document.getElementById('shutdown-progress').classList.remove('hidden');
    const log = document.getElementById('progress-log');
    log.innerHTML = '<li><span style="color:var(--warning)">[INIT]</span> Requesting emergency shutdown...</li>';
    
    try {
        await apiCall(`/api/shutdown?strategy=${strategy}&trigger_type=manual`, 'POST');
    } catch(e) {
        alert(e.message || e.detail || 'Failed to trigger shutdown');
    }
};

function handleProgress(e) {
    if(State.currentView !== 'shutdown') return;
    const log = document.getElementById('progress-log');
    if(log) {
        const li = document.createElement('li');
        li.innerHTML = `<span style="color:var(--accent)">[${e.detail.stage.toUpperCase()}]</span> ${e.detail.detail}`;
        log.appendChild(li);
        
        if(e.detail.stage === 'complete') {
            State.latestShutdownId = e.detail.shutdown_id;
            const btn = document.createElement('button');
            btn.textContent = 'View Report';
            btn.style.marginTop = '15px';
            btn.onclick = () => loadView('report');
            log.appendChild(btn);
        }
    }
}

window.cleanup_shutdown = function() {
    window.removeEventListener('ws_shutdown_progress', handleProgress);
};
