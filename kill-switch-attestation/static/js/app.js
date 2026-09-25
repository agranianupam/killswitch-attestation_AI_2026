/*
static/js/app.js — Router, WS client, shared state
*/

const State = {
    token: localStorage.getItem('ks_token') || null,
    currentView: 'dashboard',
    ws: null
};

function init() {
    setupNavigation();
    setupWebSocket();
    renderAuth();
    loadView('dashboard');
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

function loadView(view) {
    if(State.currentView && window[`cleanup_${State.currentView}`]) {
        window[`cleanup_${State.currentView}`]();
    }
    
    State.currentView = view;
    document.querySelectorAll('.sidebar a').forEach(link => {
        if(link.getAttribute('data-view') === view) link.classList.add('active');
        else link.classList.remove('active');
    });

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
    
    State.ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        const eventName = `ws_${msg.type}`;
        // dispatch custom event
        window.dispatchEvent(new CustomEvent(eventName, { detail: msg.data }));
    };
    
    State.ws.onclose = () => {
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
    if (State.token) {
        section.innerHTML = `<button class="secondary" onclick="logout()">Logout</button>`;
    } else {
        section.innerHTML = `<button class="secondary" onclick="showLogin()">Login</button>`;
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
