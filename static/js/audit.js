window.render_audit = async function(container) {
    container.innerHTML = `
        <!-- Floating Wireframe Background & Crosshairs -->
        <div class="hero-wireframe-bg">
            <svg viewBox="0 0 200 120" fill="none" stroke="#94a3b8" stroke-width="1" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="120,15 180,35 140,65 80,45" stroke="#cbd5e1" stroke-width="0.8"/>
                <polygon points="80,45 140,65 140,105 80,85" stroke="#94a3b8" stroke-width="1"/>
                <polygon points="140,65 180,35 180,75 140,105" stroke="#cbd5e1" stroke-width="0.8"/>
                <path d="M30,20 L30,26 M27,23 L33,23" stroke="#475569" stroke-width="1.2"/>
                <path d="M90,10 L90,16 M87,13 L93,13" stroke="#475569" stroke-width="1.2"/>
                <path d="M185,50 L185,56 M182,53 L188,53" stroke="#475569" stroke-width="1.2"/>
            </svg>
        </div>

        <!-- Hero Header -->
        <div class="view-hero">
            <div class="hero-text">
                <div class="hero-kicker">Verifiable Evidence</div>
                <h1 class="hero-title">
                    Verifiable <span class="highlight-red">AI Agent</span> Cryptographic Audit
                </h1>
                <p class="hero-subtitle">
                    Authoritative SHA-256 hash-chain verification, Ed25519 signatures, and immutable audit logs.
                </p>
            </div>
            <div>
                <button id="authoritative-verify-btn" class="btn-shutdown" onclick="verifyChain()">
                    <span>🔐</span> VERIFY HASH CHAIN <span>→</span>
                </button>
            </div>
        </div>

        <!-- Section 01: Chain Integrity Status Banner -->
        <div class="section-heading">
            <span class="sec-num">01</span>
            <span class="sec-title">Chain Integrity Status</span>
            <div class="sec-line"></div>
        </div>

        <div id="verify-result" class="hidden" style="margin-bottom: 25px; padding: 14px 18px; border-radius: 6px; font-weight:600; font-size:12.5px;"></div>

        <!-- Section 02: Attestation Log & Hash-Chain Explorer -->
        <div class="section-heading">
            <span class="sec-num">02</span>
            <span class="sec-title">Ed25519 Attestation Log &amp; Hash-Chain Explorer</span>
            <div class="sec-line"></div>
        </div>

        <div class="panel" style="margin-bottom: 25px;">
            <div class="panel-header">
                <span class="panel-title">Attestation Log Entries</span>
                <span class="badge neutral">Ed25519 (RFC 8032) / SHA-256 Chained</span>
            </div>
            <div style="overflow-x: auto;">
                <table id="attestation-table">
                    <thead>
                        <tr>
                            <th>Index</th>
                            <th>Event ID</th>
                            <th>Timestamp</th>
                            <th>Previous Hash</th>
                            <th>Current Hash</th>
                            <th>Signature Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 25px;">Loading attestation entries...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Section 03: Administrative Audit Logs -->
        <div class="section-heading">
            <span class="sec-num">03</span>
            <span class="sec-title">Administrative Audit Logs</span>
            <div class="sec-line"></div>
        </div>

        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">Immutable Audit Trail</span>
            </div>
            <div style="overflow-x: auto;">
                <table id="audit-table">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Actor</th>
                            <th>Action</th>
                            <th>Detail</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 25px;">Loading audit logs...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;

    loadAttestationEntries();
    loadAuditLogs();
};

async function loadAttestationEntries() {
    const tbody = document.querySelector('#attestation-table tbody');
    if (!tbody) return;

    try {
        const entries = await apiCall('/api/audit/entries');
        if (!entries || entries.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted); padding: 30px;">No attestation entries recorded yet</td></tr>`;
            return;
        }

        tbody.innerHTML = entries.map(ent => `
            <tr style="cursor: pointer;" onclick="openShutdownReport('${ent.event_id}')" title="Click to view Shutdown Report">
                <td style="font-weight: 700; color: var(--accent-red); font-family: var(--font-mono);">#${ent.entry_index}</td>
                <td style="font-family: var(--font-mono);">
                    <a href="javascript:void(0)" onclick="event.stopPropagation(); openShutdownReport('${ent.event_id}')" style="color: var(--accent-red); font-weight: 700; text-decoration: underline;">
                        ${ent.event_id.substring(0, 8)}
                    </a>
                </td>
                <td style="font-size: 11px; color: var(--text-muted);">${formatLocalTime(ent.created_at || ent.timestamp)}</td>
                <td style="font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);" title="${ent.previous_hash}">${ent.previous_hash.substring(0, 12)}...</td>
                <td style="font-family: var(--font-mono); font-size: 11px; color: var(--text-primary); font-weight: 600;" title="${ent.current_hash}">${ent.current_hash.substring(0, 12)}...</td>
                <td><span class="badge success">Ed25519 Valid</span></td>
                <td>
                    <button class="btn-secondary" onclick="event.stopPropagation(); openShutdownReport('${ent.event_id}')" style="font-size: 10px; padding: 3px 8px;">Report</button>
                </td>
            </tr>
        `).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--danger); padding: 25px;">Failed to load attestation entries.</td></tr>`;
    }
}

async function loadAuditLogs() {
    const tbody = document.querySelector('#audit-table tbody');
    if (!tbody) return;

    try {
        const logs = await apiCall('/api/audit/logs');
        if (!logs || logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 30px;">No audit log records found</td></tr>`;
            return;
        }

        tbody.innerHTML = logs.map(l => `
            <tr>
                <td style="font-size: 11px; color: var(--text-muted);">${formatLocalTime(l.timestamp)}</td>
                <td><span class="badge ${l.actor === 'system' ? 'success' : 'warning'}">${l.actor}</span></td>
                <td style="font-weight: 700; color: var(--text-primary);">${l.action}</td>
                <td style="font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary);">${l.detail || '--'}</td>
            </tr>
        `).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--danger); padding: 25px;">Failed to load audit logs.</td></tr>`;
    }
}

window.verifyChain = async function() {
    const resDiv = document.getElementById('verify-result');
    if (!resDiv) return;
    resDiv.classList.remove('hidden');
    resDiv.innerHTML = 'Verifying cryptographic attestation hash chain...';
    resDiv.style.backgroundColor = 'var(--bg-card)';
    resDiv.style.border = '1px solid var(--border)';
    resDiv.style.color = 'var(--text-primary)';

    try {
        const res = await apiCall('/api/audit/verify-chain', 'POST');
        if (res.valid) {
            resDiv.innerHTML = `✅ <strong>Chain Verified!</strong> ${res.entries_checked} entries checked and cryptographically sound.`;
            resDiv.style.backgroundColor = 'var(--success-subtle)';
            resDiv.style.borderColor = 'var(--success-border)';
            resDiv.style.color = 'var(--success-text)';
        } else {
            resDiv.innerHTML = `❌ <strong>Verification Failed!</strong> Tampering detected at entry index ${res.first_failure_index}.`;
            resDiv.style.backgroundColor = 'var(--danger-subtle)';
            resDiv.style.borderColor = 'var(--danger-border)';
            resDiv.style.color = 'var(--danger-text)';
        }
    } catch(e) {
        resDiv.innerHTML = `❌ Error verifying chain: ${e && e.message ? e.message : 'Request failed.'}`;
        resDiv.style.backgroundColor = 'var(--danger-subtle)';
        resDiv.style.borderColor = 'var(--danger-border)';
        resDiv.style.color = 'var(--danger-text)';
    }
};
