const State = {
    token: sessionStorage.getItem('ks_token') || null,
    currentView: 'dashboard',
    ws: null,
    latestShutdownId: null
};

function init() {
    setupNavigation();
    setupWebSocket();
    renderAuth();
    loadView('dashboard');

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
    const tokenQuery = State.token ? `?token=${encodeURIComponent(State.token)}` : '';
    State.ws = new WebSocket(`${protocol}//${window.location.host}/ws${tokenQuery}`);

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
        window.dispatchEvent(new CustomEvent(eventName, { detail: msg.data }));
    };

    State.ws.onclose = () => {
        const badge = document.getElementById('ws-status');
        if (badge) {
            badge.innerHTML = '● DISCONNECTED';
            badge.style.color = 'var(--danger)';
        }
        setTimeout(setupWebSocket, 2000);
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
    if (res.status === 401 && endpoint !== '/api/auth/login') {
        logout();
        throw new Error('Unauthorized');
    }
    return res.ok ? res.json() : Promise.reject(await res.json());
}

function renderAuth() {
    const section = document.getElementById('auth-section');
    const headerUser = document.getElementById('header-user');

    if (State.token) {
        if (section) {
            section.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:8px;">
                    <div style="font-size:11px; color:var(--success); font-weight:bold;">Authenticated as Admin</div>
                    <button type="button" style="width:100%; padding:6px; font-size:11px;" class="secondary" onclick="logout()">Log Out</button>
                </div>
            `;
        }
        if (headerUser) {
            headerUser.textContent = 'Administrator';
            headerUser.style.color = 'var(--success)';
        }
    } else {
        if (section) {
            section.innerHTML = `<button type="button" style="width:100%; padding:8px;" onclick="showLogin()">Admin Login</button>`;
        }
        if (headerUser) {
            headerUser.textContent = 'Guest';
            headerUser.style.color = 'var(--text-muted)';
        }
    }
}

function showLogin() {
    const modal = document.getElementById('login-modal');
    if (modal) {
        const errEl = document.getElementById('login-error');
        if (errEl) {
            errEl.style.display = 'none';
            errEl.textContent = '';
        }
        modal.classList.remove('hidden');
    }
}

function closeLoginModal() {
    const modal = document.getElementById('login-modal');
    if (modal) modal.classList.add('hidden');
}

async function doLogin() {
    const userEl = document.getElementById('login-user');
    const passEl = document.getElementById('login-pass');
    const errEl = document.getElementById('login-error');
    const user = userEl ? userEl.value : '';
    const pass = passEl ? passEl.value : '';

    const params = new URLSearchParams();
    params.append('username', user);
    params.append('password', pass);

    try {
        const res = await apiCall('/api/auth/login', 'POST', params);
        State.token = res.access_token;
        sessionStorage.setItem('ks_token', State.token);
        closeLoginModal();
        renderAuth();
        if (State.ws) {
            State.ws.close();
        }
        setupWebSocket();
    } catch (e) {
        if (errEl) {
            errEl.textContent = 'Invalid username or password.';
            errEl.style.display = 'block';
        }
    }
}

async function logout() {
    if (State.token) {
        try {
            await apiCall('/api/auth/logout', 'POST');
        } catch (e) {
        }
    }
    State.token = null;
    sessionStorage.removeItem('ks_token');
    renderAuth();
    if (State.ws) {
        State.ws.close();
    }
    setupWebSocket();
    showLogin();
}

window.onload = init;
