/*
static/js/app.js — Router, WS client, shared state
*/

const State = {
    token: localStorage.getItem('ks_token') || null,
    currentView: 'dashboard',
    ws: null,
    latestShutdownId: null
};

function init() {
    setupNavigation();
    setupWebSocket();
    renderAuth();
    loadView('dashboard');
    
    // Update clock every second
    setInterval(() => {
        const clock = document.getElementById('header-clock');
        if(clock) clock.textContent = new Date().toLocaleTimeString();
    }, 1000);
}

function setupNavigation() {
    document.querySelectorAll('.sidebar a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const view = e.target.getAttribute('data-view');
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
    if(!id) return;
    State.latestShutdownId = id;
    loadView('report');
};

const VIEW_TITLES = {
    'dashboard': { title: 'Live Dashboard', desc: 'Real-time telemetry and kill-switch monitoring.' },
    'agent': { title: 'Agent Details', desc: 'Active credentials and risk profiling.' },
    'report': { title: 'Shutdown Report', desc: 'Detailed outcome of containment events.' },
    'experiments': { title: 'Strategy Comparison', desc: 'Simulated comparative evaluation across Strategies A, B, and C.' },
    'analytics': { title: 'System Analytics', desc: 'Aggregated metrics and performance data.' },
    'audit': { title: 'Cryptographic Audit', desc: 'Verifiable log chains and attestation signatures.' }
};

function loadView(view) {
    if(State.currentView && window[`cleanup_${State.currentView}`]) {
        window[`cleanup_${State.currentView}`]();
    }
    
    State.currentView = view;
    document.querySelectorAll('.sidebar a').forEach(link => {
        if(link.getAttribute('data-view') === view) link.classList.add('active');
        else link.classList.remove('active');
    });
    
    const titleObj = VIEW_TITLES[view] || { title: 'Overview', desc: '' };
    const hTitle = document.getElementById('header-title');
    const hDesc = document.getElementById('header-desc');
    if (hTitle) hTitle.textContent = titleObj.title;
    if (hDesc) hDesc.textContent = titleObj.desc;

    const content = document.getElementById('app-content');
    content.innerHTML = `<h2>Loading ${view}...</h2>`;

    if(window[`render_${view}`]) {
        window[`render_${view}`](content);
    } else {
        content.innerHTML = `<h2>${view} (Not implemented)</h2>`;
    }
}

function setupWebSocket() {
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
        const msg = JSON.parse(event.data);
        const eventName = `ws_${msg.type}`;
        // dispatch custom event
        window.dispatchEvent(new CustomEvent(eventName, { detail: msg.data }));
    };
    
    State.ws.onclose = () => {
        const badge = document.getElementById('ws-status');
        if (badge) {
            badge.innerHTML = '● DISCONNECTED';
            badge.style.color = 'var(--danger)';
        }
        setTimeout(setupWebSocket, 2000); // reconnect
    };
}

async function apiCall(endpoint, method = 'GET', body = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (State.token) headers['Authorization'] = `Bearer ${State.token}`;
    
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
    if (res.status === 401) {
        logout();
        throw new Error('Unauthorized');
    }
    return res.ok ? res.json() : Promise.reject(await res.json());
}

function renderAuth() {
    const section = document.getElementById('auth-section');
    const headerUser = document.getElementById('header-user');
    
    // Hardcode for admin demonstration per user feedback
    State.token = 'demo-admin-token';
    
    if (section) {
        section.innerHTML = `<button style="width:100%" class="secondary" disabled>Authenticated as Admin</button>`;
    }
    if (headerUser) {
        headerUser.textContent = 'Administrator';
        headerUser.style.color = 'var(--success)';
    }
}

function showLogin() {
    const modal = document.getElementById('modal');
    const content = document.getElementById('modal-content');
    content.innerHTML = `
        <h3>Admin Login</h3>
        <div class="form-group">
            <label>Username</label>
            <input type="text" id="login-user" value="admin">
        </div>
        <div class="form-group">
            <label>Password</label>
            <input type="password" id="login-pass" value="admin">
        </div>
        <button onclick="doLogin()">Login</button>
        <button class="secondary" onclick="document.getElementById('modal').classList.add('hidden')">Cancel</button>
    `;
    modal.classList.remove('hidden');
}

async function doLogin() {
    const user = document.getElementById('login-user').value;
    const pass = document.getElementById('login-pass').value;
    const params = new URLSearchParams();
    params.append('username', user);
    params.append('password', pass);
    
    try {
        const res = await apiCall('/api/auth/login', 'POST', params);
        State.token = res.access_token;
        localStorage.setItem('ks_token', State.token);
        document.getElementById('modal').classList.add('hidden');
        renderAuth();
    } catch (e) {
        alert('Login failed');
    }
}

function logout() {
    State.token = null;
    localStorage.removeItem('ks_token');
    renderAuth();
}

window.onload = init;
