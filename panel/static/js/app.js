/**
 * OCServ Panel - Main JavaScript
 * توابع اصلی جاوااسکریپت
 */

// ========== API Helper Functions ==========

const API_BASE = '';

function getToken() {
    return localStorage.getItem('token');
}

function setAuthHeader() {
    return {
        'Authorization': `Bearer ${getToken()}`,
        'Content-Type': 'application/json'
    };
}

async function apiRequest(method, endpoint, data = null) {
    const options = {
        method,
        headers: setAuthHeader()
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(`${API_BASE}${endpoint}`, options);

    if (response.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }

    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.detail || 'خطا در درخواست');
    }

    return result;
}

async function apiGet(endpoint) {
    return apiRequest('GET', endpoint);
}

async function apiPost(endpoint, data = {}) {
    return apiRequest('POST', endpoint, data);
}

async function apiPut(endpoint, data) {
    return apiRequest('PUT', endpoint, data);
}

async function apiDelete(endpoint) {
    return apiRequest('DELETE', endpoint);
}

// ========== Authentication ==========

function checkAuth() {
    const token = getToken();
    if (!token) {
        window.location.href = '/login';
        return false;
    }
    return true;
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}

// ========== UI Functions ==========

// Toast notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;

    container.appendChild(toast);

    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Sidebar toggle
function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('collapsed');
    document.querySelector('.main-content').classList.toggle('expanded');
}

// Theme toggle
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
}

function applyTheme(theme) {
    if (theme === 'auto') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        theme = prefersDark ? 'dark' : 'light';
    }
    document.documentElement.setAttribute('data-theme', theme);
}

// ========== Formatting Functions ==========

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    if (bytes < 0) return '∞';

    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('fa-IR');
}

function formatTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' });
}

// ========== Server Status ==========

async function updateServerStatus() {
    try {
        const status = await apiGet('/api/dashboard/server-status');
        const container = document.getElementById('server-status');

        if (container) {
            container.className = `server-status ${status.online ? 'online' : 'offline'}`;
            container.innerHTML = `
                <span class="status-dot ${status.online ? 'pulse' : ''}"></span>
                <span class="status-text">${status.online ? 'در حال اجرا' : 'متوقف'}</span>
            `;
        }
    } catch (error) {
        console.error('Error updating server status:', error);
    }
}

// ========== Initialization ==========

document.addEventListener('DOMContentLoaded', () => {
    // Apply saved theme
    const savedTheme = localStorage.getItem('theme') || 'dark';
    applyTheme(savedTheme);

    // Update server status periodically (on pages with sidebar)
    if (document.getElementById('server-status')) {
        updateServerStatus();
        setInterval(updateServerStatus, 30000);
    }

    // Close modal on escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.querySelector('.modal.active');
            if (modal) {
                modal.classList.remove('active');
            }
        }
    });
});
