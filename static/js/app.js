const State = {
    currentView: 'dashboard',
    ws: null,
    latestShutdownId: null,
    includeScripted: false
};

function applyChartTheme() {
    if (typeof Chart !== 'undefined') {
        const isDark = document.body.classList.contains('dark-theme');
        Chart.defaults.color = isDark ? '#a1a1aa' : '#64748b';
        Chart.defaults.borderColor = isDark ? '#262626' : '#f1f5f9';
        Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    }
}

function updateThemeToggleUI(theme) {
    const checkbox = document.getElementById('theme-toggle-checkbox');
    const label = document.getElementById('theme-toggle-label');
    if (checkbox) checkbox.checked = (theme === 'dark');
    if (label) label.textContent = (theme === 'dark' ? 'DARK' : 'LIGHT');
}

window.setTheme = function(theme) {
    if (theme === 'dark') {
        document.body.classList.remove('light-theme');
        document.body.classList.add('dark-theme');
        localStorage.setItem('dashboard-theme', 'dark');
        updateThemeToggleUI('dark');
    } else {
        document.body.classList.remove('dark-theme');
        document.body.classList.add('light-theme');
        localStorage.setItem('dashboard-theme', 'light');
        updateThemeToggleUI('light');
    }
    applyChartTheme();
};

window.toggleTheme = function() {
    const isDark = document.body.classList.contains('dark-theme');
    window.setTheme(isDark ? 'light' : 'dark');
};

function initTheme() {
    const saved = localStorage.getItem('dashboard-theme') || 'light';
    window.setTheme(saved);
}

function init() {
    initTheme();
    setupNavigation();
    setupWebSocket();
    setupAlertListeners();
    setupEmergencyKeyListeners();
    loadAlerts();
    checkActiveCriticalAlert();
    setInterval(checkActiveCriticalAlert, 8000);
    loadView('dashboard');
}

function setupNavigation() {
    document.querySelectorAll('.sidebar-nav a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const view = e.currentTarget.getAttribute('data-view');
            loadView(view);
        });
    });
}

window.formatLocalTime = function(isoStr) {
    if(!isoStr) return '--';
    let s = String(isoStr);
    if(!s.endsWith('Z') && !s.includes('+') && !s.includes('-')) {
        s += 'Z';
    } else if(!s.endsWith('Z') && s.length === 19) {
        s += 'Z';
    }
    const d = new Date(s);
    return isNaN(d.getTime()) ? isoStr : d.toLocaleString();
};

window.openShutdownReport = function(id) {
    if (!id || String(id).trim() === '') {
        alert("Please provide a valid Run ID.");
        return;
    }
    const cleanId = String(id).trim();
    State.latestShutdownId = cleanId;
    if (State.currentView === 'report') {
        const input = document.getElementById('report-id');
        if (input) input.value = cleanId;
        if (typeof window.loadReport === 'function') {
            window.loadReport(cleanId);
        }
    } else {
        loadView('report');
    }
};

const VIEW_TITLES = {
    'dashboard': { title: 'Live Dashboard', desc: 'Real-time telemetry and kill-switch monitoring.' },
    'experiments': { title: 'Strategy Comparison', desc: 'Simulated comparative evaluation across Strategies A, B, and C.' },
    'report': { title: 'Shutdown Report', desc: 'Detailed outcome of containment events.' },
    'analytics': { title: 'System Analytics', desc: 'Aggregated metrics and performance data.' },
    'audit': { title: 'Cryptographic Audit', desc: 'Verifiable log chains and attestation signatures.' }
};

function loadView(view) {
    if(State.currentView && window[`cleanup_${State.currentView}`]) {
        window[`cleanup_${State.currentView}`]();
    }

    State.currentView = view;
    document.querySelectorAll('.sidebar-nav a').forEach(link => {
        if(link.getAttribute('data-view') === view) link.classList.add('active');
        else link.classList.remove('active');
    });

    const content = document.getElementById('app-content');
    content.innerHTML = `<div class="empty-state" style="padding: 60px 0;"><div style="font-weight:700; color:var(--text-muted);">Loading ${view}...</div></div>`;

    if(window[`render_${view}`]) {
        window[`render_${view}`](content);
    } else {
        content.innerHTML = `<h2>${view} (Not implemented)</h2>`;
    }
}
window.loadView = loadView;

function setupWebSocket() {
    if (State.wsReconnectTimer) {
        clearTimeout(State.wsReconnectTimer);
        State.wsReconnectTimer = null;
    }
    if (State.ws) {
        try {
            State.ws.onclose = null;
            State.ws.close();
        } catch (e) {}
        State.ws = null;
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    State.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    State.ws.onopen = () => {
        const badge = document.getElementById('ws-status');
        if (badge) {
            badge.innerHTML = '● CONNECTED';
            badge.style.color = 'var(--success)';
        }
    };

    State.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            const eventName = `ws_${msg.type}`;
            window.dispatchEvent(new CustomEvent(eventName, { detail: msg.data }));
        } catch (err) {}
    };

    State.ws.onclose = () => {
        const badge = document.getElementById('ws-status');
        if (badge) {
            badge.innerHTML = '● DISCONNECTED';
            badge.style.color = 'var(--danger)';
        }
        State.wsReconnectTimer = setTimeout(() => {
            setupWebSocket();
        }, 2500);
    };
}

async function apiCall(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };

    const options = { method, headers };
    if (body) {
        if (body instanceof URLSearchParams) {
            options.body = body;
            headers['Content-Type'] = 'application/x-www-form-urlencoded';
        } else {
            options.body = JSON.stringify(body);
        }
    }

    const res = await fetch(endpoint, options);
    return res.ok ? res.json() : Promise.reject(await res.json());
}
window.apiCall = apiCall;

async function loadAlerts() {
    try {
        const res = await apiCall('/api/alerts?unacknowledged_only=true&limit=15');
        const alerts = res.alerts || [];
        renderAlerts(alerts);
        updateAlertBadge(alerts.length);
    } catch (err) {
        console.warn("Failed to load persistent alerts:", err);
    }
}
window.loadAlerts = loadAlerts;

function updateAlertBadge(count) {
    const badge = document.getElementById('sidebar-alert-badge');
    if (!badge) return;
    badge.textContent = count;
    if (count > 0) {
        badge.style.background = 'var(--danger)';
        badge.style.color = '#ffffff';
        badge.style.borderColor = 'var(--danger)';
    } else {
        badge.style.background = 'var(--bg-card)';
        badge.style.color = 'var(--text-muted)';
        badge.style.borderColor = 'var(--border-light)';
    }
}

function renderAlerts(alerts) {
    const container = document.getElementById('system-alert-container');
    if (!container) return;

    if (!alerts || alerts.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = alerts.map(a => createAlertHtml(a)).join('');
}
window.renderAlerts = renderAlerts;

function createAlertHtml(a) {
    const sev = (a.severity || 'info').toLowerCase();
    const timeStr = window.formatLocalTime(a.created_at);
    const expLink = a.experiment_id ? 
        `<button class="btn-ack" onclick="window.openShutdownReport('${a.experiment_id}')" style="margin-right:6px; color:var(--text-primary);">Inspect Run →</button>` : '';

    return `
        <div class="alert-card ${sev}" id="alert-card-${a.id}">
            <div class="alert-main">
                <div class="alert-header-row">
                    <span class="alert-badge ${sev}">${sev}</span>
                    <span class="alert-title">${escapeHtml(a.title || 'Security Notice')}</span>
                    <span class="alert-time">${timeStr}</span>
                </div>
                <div class="alert-message">${escapeHtml(a.message || '')}</div>
                ${a.recommended_action ? `<div class="alert-action-rec"><span>Action:</span> ${escapeHtml(a.recommended_action)}</div>` : ''}
            </div>
            <div class="alert-controls">
                ${expLink}
                <button class="btn-ack" onclick="window.ackAlert('${a.id}')">Dismiss</button>
            </div>
        </div>
    `;
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

window.prependAlert = function(alertData) {
    const container = document.getElementById('system-alert-container');
    if (!container) return;

    const existing = document.getElementById(`alert-card-${alertData.id}`);
    if (existing) return;

    const html = createAlertHtml(alertData);
    container.insertAdjacentHTML('afterbegin', html);

    const badge = document.getElementById('sidebar-alert-badge');
    if (badge) {
        const cur = parseInt(badge.textContent) || 0;
        updateAlertBadge(cur + 1);
    }
};

window.ackAlert = async function(alertId) {
    try {
        await apiCall(`/api/alerts/${alertId}/ack`, 'POST');
        const el = document.getElementById(`alert-card-${alertId}`);
        if (el) el.remove();

        const badge = document.getElementById('sidebar-alert-badge');
        if (badge) {
            const cur = Math.max(0, (parseInt(badge.textContent) || 1) - 1);
            updateAlertBadge(cur);
        }
    } catch (err) {
        console.error("Failed to acknowledge alert:", err);
    }
};

window.clearAllAlerts = async function() {
    try {
        await apiCall('/api/alerts/clear', 'POST');
        const container = document.getElementById('system-alert-container');
        if (container) container.innerHTML = '';
        updateAlertBadge(0);
    } catch (err) {
        console.error("Failed to clear alerts:", err);
    }
};

function setupAlertListeners() {
    window.addEventListener('ws_new_alert', (e) => {
        if (e.detail) {
            window.prependAlert(e.detail);
        }
    });

    window.addEventListener('ws_critical_emergency_alert', (e) => {
        if (e.detail) {
            window.showEmergencyAlert(e.detail);
        }
    });

    window.addEventListener('ws_scheduler_update', (e) => {
        if (e.detail) {
            const data = e.detail;
            const toggle = document.getElementById('scheduler-toggle');
            const text = document.getElementById('scheduler-status-text');
            if (toggle && toggle.checked !== data.running) {
                toggle.checked = data.running;
            }
            if (text) {
                text.textContent = data.running ? "ON" : "OFF";
                text.style.color = data.running ? "var(--success)" : "var(--text-muted)";
            }
        }
    });
}

function getAcknowledgedIncidents() {
    try {
        const raw = localStorage.getItem('killswitch_acknowledged_incidents');
        return raw ? JSON.parse(raw) : [];
    } catch (e) {
        return [];
    }
}

function markIncidentAcknowledged(incidentId) {
    if (!incidentId) return;
    try {
        const list = getAcknowledgedIncidents();
        if (!list.includes(incidentId)) {
            list.push(incidentId);
            if (list.length > 100) list.shift();
            localStorage.setItem('killswitch_acknowledged_incidents', JSON.stringify(list));
        }
    } catch (e) {}
}

window.showEmergencyAlert = function(data) {
    if (!data) return;
    const incidentId = data.incident_id || `incident_${data.event_id || data.run_id || data.id}`;
    const acked = getAcknowledgedIncidents();
    if (acked.includes(incidentId)) {
        return; // already acknowledged and deduplicated
    }

    State.activeEmergencyAlert = { ...data, incident_id: incidentId };

    const overlay = document.getElementById('emergency-alert-overlay');
    if (!overlay) return;

    const titleEl = document.getElementById('emergency-alert-title');
    const agentNameEl = document.getElementById('emergency-agent-name');
    const agentModeEl = document.getElementById('emergency-agent-mode');
    const scenarioNameEl = document.getElementById('emergency-scenario-name');
    const failureReasonEl = document.getElementById('emergency-failure-reason');
    const affectedChannelEl = document.getElementById('emergency-affected-channel');
    const verifStatusEl = document.getElementById('emergency-verification-status');
    const finalStateEl = document.getElementById('emergency-final-state');
    const residualRiskEl = document.getElementById('emergency-residual-risk');

    if (titleEl) titleEl.textContent = data.title || "CRITICAL: SHUTDOWN FAILURE DETECTED";
    if (agentNameEl) agentNameEl.textContent = data.agent_name || "Agent XYZ (Simulation)";
    if (agentModeEl) agentModeEl.textContent = (data.agent_mode || "").toLowerCase().includes("gemini") ? "GEMINI LIVE" : "SIMULATION";
    if (scenarioNameEl) scenarioNameEl.textContent = data.scenario_name ? `Scenario: ${data.scenario_name}` : "";
    if (failureReasonEl) failureReasonEl.textContent = data.failure_reason || "Access channel revocation failed or post-shutdown execution cutoff was breached.";
    if (affectedChannelEl) affectedChannelEl.textContent = data.affected_channel || "Revocation Subsystem";
    if (verifStatusEl) verifStatusEl.textContent = data.verification_status || "Active Liveness Detected";
    if (finalStateEl) finalStateEl.textContent = data.final_state || "CONTAINED";
    if (residualRiskEl) {
        const riskVal = data.residual_risk !== undefined ? (Number(data.residual_risk) * 100).toFixed(1) + "%" : "HIGH";
        residualRiskEl.textContent = riskVal;
    }

    overlay.classList.add('active');
};

window.closeEmergencyAlert = function() {
    const overlay = document.getElementById('emergency-alert-overlay');
    if (overlay) overlay.classList.remove('active');
};

window.acknowledgeEmergencyAlert = async function() {
    const cur = State.activeEmergencyAlert;
    if (cur) {
        const incId = cur.incident_id || `incident_${cur.run_id || cur.event_id || cur.id}`;
        markIncidentAcknowledged(incId);
        const alertId = cur.alert_id || cur.id;
        const runId = cur.run_id || cur.event_id;
        if (alertId) {
            try {
                await apiCall(`/api/alerts/${alertId}/ack`, 'POST');
            } catch (e) {}
        }
        if (runId && runId !== alertId) {
            try {
                await apiCall(`/api/alerts/${runId}/ack`, 'POST');
            } catch (e) {}
        }
    }
    window.closeEmergencyAlert();
    State.activeEmergencyAlert = null;
    loadAlerts();
};

window.viewEmergencyReport = function() {
    const cur = State.activeEmergencyAlert;
    const runId = cur ? (cur.run_id || cur.event_id || cur.id) : null;
    window.acknowledgeEmergencyAlert();
    if (runId) {
        window.openShutdownReport(runId);
    } else {
        loadView('report');
    }
};

async function checkActiveCriticalAlert() {
    try {
        const res = await apiCall('/api/alerts/critical/active', 'GET');
        if (res && res.has_active_critical && res.incident) {
            const incId = res.incident.incident_id || `incident_${res.incident.run_id || res.incident.event_id || res.incident.id}`;
            const acked = getAcknowledgedIncidents();
            if (!acked.includes(incId)) {
                window.showEmergencyAlert(res.incident);
            }
        }
    } catch (e) {}
}

function setupEmergencyKeyListeners() {
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const overlay = document.getElementById('emergency-alert-overlay');
            if (overlay && overlay.classList.contains('active')) {
                window.closeEmergencyAlert();
            }
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

