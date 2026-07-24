import os
import shutil
import subprocess
import time
import re
import json
import secrets
import hashlib
import base64
from datetime import datetime
import urllib.request
from functools import wraps
from flask import Flask, request, jsonify, render_template_string, redirect, session, url_for
from google_auth_oauthlib.flow import Flow
from werkzeug.middleware.proxy_fix import ProxyFix

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# =========================================================================
# LOAD HUGGING FACE SECRETS (ENVIRONMENT VARIABLES)
# =========================================================================
# Otomatis membuat file client_secret.json dari Hugging Face Secret
if 'GOOGLE_CLIENT_SECRET' in os.environ:
    with open("client_secret.json", "w") as f:
        f.write(os.environ['GOOGLE_CLIENT_SECRET'])

# =========================================================================
# KONFIGURASI KEAMANAN WEB
# =========================================================================
# Mengambil password dari Hugging Face Secret, default ke "jokowi123" jika kosong
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "jokowi123")

# =========================================================================
# KONFIGURASI DIREKTORI & OAUTH
# =========================================================================
PROFILE_DIR = os.path.expanduser("~/.colab-manager-profiles")
SECRET_FILE = os.path.expanduser("~/.colab-manager-secret")
CLIENT_SECRETS_FILE = "client_secret.json"

os.makedirs(PROFILE_DIR, exist_ok=True)

if not os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, 'w') as f:
        f.write(secrets.token_hex(32))

with open(SECRET_FILE, 'r') as f:
    FLASK_SECRET_KEY = f.read().strip()

SCOPES = [
    "openid", 
    "https://www.googleapis.com/auth/userinfo.profile", 
    "https://www.googleapis.com/auth/userinfo.email", 
    "https://www.googleapis.com/auth/cloud-platform", 
    "https://www.googleapis.com/auth/colaboratory", 
    "https://www.googleapis.com/auth/drive.file"
]

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
screen_spam = re.compile(r'\[\d+\]\s+\d+:bash\*')

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# =========================================================================
# DECORATOR
# =========================================================================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# =========================================================================
# TAMPILAN WEB - HALAMAN LOGIN
# =========================================================================
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="id" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Colab Manager</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>body { font-family: 'Inter', sans-serif; background-color: #09090b; color: #f4f4f5; }</style>
</head>
<body class="min-h-screen flex items-center justify-center p-4">
    <div class="bg-[#18181b] border border-[#27272a] p-8 w-full max-w-sm rounded-2xl shadow-2xl">
        <div class="flex justify-center mb-6">
            <svg class="w-10 h-10 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path></svg>
        </div>
        <h2 class="text-white text-xl font-semibold text-center mb-2">Akses Sistem Tertutup</h2>
        <p class="text-gray-400 text-sm text-center mb-6">Silakan masukkan kata sandi panel untuk melanjutkan.</p>
        
        {% if error %}
        <div class="bg-red-500/10 border border-red-500/50 text-red-500 text-sm rounded-lg p-3 mb-4 text-center">
            Kata sandi salah.
        </div>
        {% endif %}
        
        <form method="POST" action="/login" class="flex flex-col gap-4">
            <div>
                <input type="password" name="password" placeholder="Kata sandi..." required autofocus class="w-full bg-[#09090b] text-gray-200 border border-[#27272a] rounded-lg p-3 text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition">
            </div>
            <button type="submit" class="w-full bg-white text-black font-medium py-3 rounded-lg hover:bg-gray-200 transition">Masuk Panel</button>
        </form>
    </div>
</body>
</html>
"""

# =========================================================================
# TAMPILAN WEB - HALAMAN DASHBOARD
# =========================================================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Colab Manager System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #09090b; color: #f4f4f5; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        ::-webkit-scrollbar { width: 10px; height: 10px; }
        ::-webkit-scrollbar-track { background: #000000; }
        ::-webkit-scrollbar-thumb { background: #3f3f46; border: 2px solid #000000; border-radius: 6px; }
        ::-webkit-scrollbar-thumb:hover { background: #52525b; }
        ::-webkit-scrollbar-corner { background: #000000; }
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="m-0 p-0 min-h-screen flex flex-col">
    
    <div class="sticky top-0 z-50 bg-[#09090b]/80 backdrop-blur-md border-b border-[#27272a] px-3 md:px-6 py-3 flex flex-col md:flex-row justify-between items-start md:items-center gap-3 shadow-lg w-full overflow-hidden">
        <div class="text-lg font-semibold tracking-tight flex items-center gap-2 shrink-0">
            <svg class="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"></path></svg>
            Colab Manager
        </div>
        
        <div class="flex overflow-x-auto md:flex-wrap justify-start md:justify-end gap-2 w-full hide-scrollbar pb-1 md:pb-0 snap-x">
            <button onclick="openModal('modalAuth')" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-[#18181b] text-gray-300 border-[#27272a] hover:bg-[#27272a] hover:text-white">Tambah Akun</button>
            <button onclick="openMassStartModal()" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-white text-black border-transparent hover:bg-gray-200">Sesi Massal</button>
            
            <button onclick="openAccounts()" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-blue-900/30 text-blue-400 border-blue-700/50 hover:bg-blue-800 hover:text-white">Info Akun</button>
            
            <button onclick="stopTmuxOnly()" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-purple-900/40 text-purple-400 border-purple-700/50 hover:bg-purple-800 hover:text-white">Stop Terminal</button>
            
            <button onclick="stopAllSessions()" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-yellow-900/40 text-yellow-500 border-yellow-700/50 hover:bg-yellow-800 hover:text-white">Stop & Reset Sesi</button>
            
            <button onclick="openModal('modalInject')" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-[#18181b] text-gray-300 border-[#27272a] hover:bg-[#27272a] hover:text-white">Inject Massal</button>
            <button onclick="clearAllLogs()" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-[#18181b] text-gray-300 border-[#27272a] hover:bg-[#27272a] hover:text-white">Clear Log</button>
            <button onclick="deleteAll()" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors border shadow-sm bg-[#7f1d1d] text-red-100 border-[#991b1b] hover:bg-[#991b1b]">Hapus Semua</button>
            <div class="w-px h-6 bg-gray-700 hidden md:block mx-1"></div>
            <a href="/logout" class="shrink-0 snap-start flex items-center justify-center gap-2 px-3 py-1.5 md:px-4 md:py-2 rounded-md text-xs md:text-sm font-medium transition-colors text-gray-400 hover:text-white">Keluar</a>
        </div>
    </div>

    <div class="p-2 md:p-6 flex-grow w-full max-w-[1920px] mx-auto">
        <div class="mb-3 md:mb-4 flex justify-between items-center text-[10px] md:text-sm px-1">
            <div class="flex items-center gap-1.5 md:gap-2">
                <span class="relative flex h-1.5 w-1.5 md:h-2 md:w-2">
                  <span id="statusPing" class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span id="statusDot" class="relative inline-flex rounded-full h-1.5 w-1.5 md:h-2 md:w-2 bg-emerald-500"></span>
                </span>
                <span id="connStatus" class="text-gray-300 font-medium">Sistem Terhubung</span>
            </div>
            <div class="text-gray-500 text-[9px] md:text-xs">Auto-refresh: 1s</div>
        </div>
        
        <div class="grid grid-cols-5 gap-1.5 md:gap-4 relative" id="container"></div>
    </div>

    <!-- MODAL: INFO AKUN -->
    <div id="modalAccounts" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-[999] hidden justify-center items-center p-4">
        <div class="bg-[#18181b] border border-[#27272a] p-6 w-full max-w-md rounded-xl shadow-2xl flex flex-col">
            <h2 class="text-white text-lg font-semibold mb-4">Daftar Akun Tersimpan</h2>
            <div id="accountsContainer" class="flex flex-col gap-2 max-h-[50vh] overflow-y-auto mb-4 hide-scrollbar">
                <!-- Daftar akun di-inject lewat JS -->
            </div>
            <button onclick="closeModal('modalAccounts')" class="mt-4 bg-[#27272a] hover:bg-[#3f3f46] text-white py-2 rounded-md transition text-center w-full">Tutup</button>
        </div>
    </div>

    <!-- MODAL: TAMBAH AKUN -->
    <div id="modalAuth" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-[999] hidden justify-center items-center p-4">
        <div class="bg-[#18181b] border border-[#27272a] p-6 w-full max-w-md rounded-xl shadow-2xl flex flex-col">
            <h2 class="text-white text-lg font-semibold mb-4">Tambah Akun Baru</h2>
            <div class="flex flex-col gap-4">
                <p class="text-sm text-gray-400">Login dengan akun Google untuk mengotomatisasi token CLI Colab.</p>
                <button onclick="startAuth()" class="flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors border shadow-sm w-full bg-white text-black border-transparent hover:bg-gray-200">Sign in with Google</button>
            </div>
            <button onclick="closeModal('modalAuth')" class="mt-6 text-sm text-gray-500 hover:text-white transition text-center w-full">Batal / Tutup</button>
        </div>
    </div>

    <!-- MODAL: BUAT SESI MASSAL (DIUBAH) -->
    <div id="modalStart" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-[999] hidden justify-center items-center p-4">
        <div class="bg-[#18181b] border border-[#27272a] p-6 w-full max-w-sm rounded-xl shadow-2xl flex flex-col">
            <h2 class="text-white text-lg font-semibold mb-4">Mulai Sesi Terpilih</h2>
            
            <div class="mb-4">
                <label class="block text-xs text-gray-400 mb-2">Pilih Spesifikasi Hardware:</label>
                <select id="hwSelect" class="w-full bg-[#09090b] text-gray-200 border border-[#27272a] rounded-md p-2.5 font-mono text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition">
                    <option value="1">CPU (Default)</option>
                    <option value="2">GPU T4</option>
                    <option value="3">GPU A100</option>
                    <option value="4">TPU</option>
                </select>
            </div>

            <!-- CONTAINER PILIH AKUN -->
            <div id="profileCheckboxes" class="mb-5 max-h-[30vh] overflow-y-auto bg-[#09090b] border border-[#27272a] rounded-md p-2 hide-scrollbar">
                <!-- Diisi via JS -->
            </div>

            <button onclick="startMass()" class="flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors border shadow-sm w-full bg-white text-black border-transparent hover:bg-gray-200">Eksekusi Terpilih</button>
            <button onclick="closeModal('modalStart')" class="mt-4 text-sm text-gray-500 hover:text-white transition w-full">Batal</button>
        </div>
    </div>

    <!-- MODAL: INJECT SCRIPT MASSAL -->
    <div id="modalInject" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-[999] hidden justify-center items-center p-4">
        <div class="bg-[#18181b] border border-[#27272a] p-6 w-full max-w-2xl rounded-xl shadow-2xl flex flex-col">
            <h2 class="text-white text-lg font-semibold mb-2">Inject Script Massal</h2>
            <p class="text-xs text-gray-400 mb-4">Script akan dieksekusi di <b>SELURUH</b> terminal yang aktif.</p>
            <textarea id="scriptBox" rows="12" placeholder="# Ketik command di sini..." class="w-full bg-[#09090b] text-gray-200 border border-[#27272a] rounded-md p-2.5 font-mono text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition mb-4 resize-y"></textarea>
            <button onclick="injectMass()" class="flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors border shadow-sm w-full bg-white text-black border-transparent hover:bg-gray-200">Broadcast Script</button>
            <button onclick="closeModal('modalInject')" class="mt-4 text-sm text-gray-500 hover:text-white transition w-full">Batal</button>
        </div>
    </div>

    <!-- MODAL: INJECT SCRIPT SINGLE -->
    <div id="modalSingleInject" class="fixed inset-0 bg-black/70 backdrop-blur-sm z-[999] hidden justify-center items-center p-4">
        <div class="bg-[#18181b] border border-[#27272a] p-6 w-full max-w-xl rounded-xl shadow-2xl flex flex-col">
            <h2 class="text-white text-lg font-semibold mb-2">Inject Profil Khusus</h2>
            <p class="text-xs text-gray-400 mb-4">Target: <span id="singleInjectTargetLabel" class="font-bold text-emerald-400"></span></p>
            <input type="hidden" id="singleInjectTargetProfile">
            <textarea id="singleScriptBox" rows="8" placeholder="# Ketik command khusus profil ini..." class="w-full bg-[#09090b] text-gray-200 border border-[#27272a] rounded-md p-2.5 font-mono text-sm focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 transition mb-4 resize-y"></textarea>
            <button onclick="injectSingle()" class="flex items-center justify-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors border shadow-sm w-full bg-emerald-600 text-white border-transparent hover:bg-emerald-500">Kirim Script ke Profil</button>
            <button onclick="closeModal('modalSingleInject')" class="mt-4 text-sm text-gray-500 hover:text-white transition w-full">Batal</button>
        </div>
    </div>

    <script>
        function openModal(id) { 
            const el = document.getElementById(id);
            el.classList.remove('hidden');
            el.classList.add('flex');
        }
        function closeModal(id) { 
            const el = document.getElementById(id);
            el.classList.add('hidden');
            el.classList.remove('flex');
        }

        function openAccounts() {
            fetch('/api/accounts')
                .then(res => res.json())
                .then(data => {
                    const container = document.getElementById('accountsContainer');
                    if (data.profiles.length === 0) {
                        container.innerHTML = '<p class="text-gray-500 text-sm text-center py-6">Belum ada akun yang tersimpan.</p>';
                    } else {
                        container.innerHTML = data.profiles.map(p => `
                            <div class="flex justify-between items-center bg-[#09090b] border border-[#27272a] p-3 rounded-md">
                                <span class="text-gray-300 text-sm font-mono font-semibold uppercase">${p}</span>
                                <button onclick="deleteSingleAccount('${p}')" class="text-xs bg-red-900/40 text-red-500 border border-red-700/50 hover:bg-red-800 hover:text-white px-3 py-1.5 rounded transition-colors flex items-center gap-1">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                                    Hapus
                                </button>
                            </div>
                        `).join('');
                    }
                    openModal('modalAccounts');
                });
        }

        function deleteSingleAccount(profile) {
            if(confirm(`Yakin ingin menghapus akun ${profile.toUpperCase()} secara permanen? Sesi terminalnya juga akan dimatikan.`)) {
                let formData = new FormData();
                formData.append('profile', profile);
                fetch('/api/account/delete', { method: 'POST', body: formData })
                    .then(() => {
                        openAccounts();
                    });
            }
        }

        function openSingleInject(profileName) {
            document.getElementById('singleInjectTargetProfile').value = profileName;
            document.getElementById('singleInjectTargetLabel').innerText = profileName.toUpperCase();
            openModal('modalSingleInject');
            setTimeout(() => document.getElementById('singleScriptBox').focus(), 100);
        }

        // FUNGSI LOAD DAFTAR AKUN UNTUK SESI MASSAL
        function openMassStartModal() {
            fetch('/api/accounts')
                .then(res => res.json())
                .then(data => {
                    const container = document.getElementById('profileCheckboxes');
                    if (data.profiles.length === 0) {
                        container.innerHTML = '<p class="text-xs text-gray-500 text-center py-4">Belum ada akun. Tambah akun dulu.</p>';
                    } else {
                        let html = `
                        <div class="flex justify-between items-center mb-3 px-1">
                            <span class="text-[10px] text-gray-400 uppercase tracking-wider font-bold">Pilih Akun</span>
                            <button type="button" onclick="toggleAllProfiles()" class="text-[10px] text-emerald-500 hover:text-emerald-400 font-semibold">Pilih/Batal Semua</button>
                        </div>
                        <div class="flex flex-col gap-1.5">
                        `;
                        data.profiles.forEach(p => {
                            html += `
                            <label class="flex items-center gap-3 text-xs text-gray-300 bg-[#18181b] border border-[#27272a] p-2.5 rounded cursor-pointer hover:bg-[#27272a] transition">
                                <input type="checkbox" name="selected_profiles" value="${p}" class="profile-cb w-4 h-4 rounded text-emerald-500 focus:ring-emerald-500 focus:ring-offset-0 bg-[#09090b] border-gray-600" checked>
                                <span class="uppercase font-mono font-semibold tracking-wide">${p}</span>
                            </label>`;
                        });
                        html += '</div>';
                        container.innerHTML = html;
                    }
                    openModal('modalStart');
                });
        }

        function toggleAllProfiles() {
            const checkboxes = document.querySelectorAll('.profile-cb');
            const allChecked = Array.from(checkboxes).every(cb => cb.checked);
            checkboxes.forEach(cb => cb.checked = !allChecked);
        }

        function updateMonitors() {
            fetch('/api/logs')
                .then(res => {
                    if (res.status === 401) {
                        window.location.href = '/login';
                        throw new Error('Unauthorized');
                    }
                    return res.json();
                })
                .then(data => {
                    document.getElementById('connStatus').innerText = 'Sistem Terhubung';
                    document.getElementById('connStatus').classList.replace('text-red-400', 'text-gray-300');
                    document.getElementById('statusDot').classList.replace('bg-red-500', 'bg-emerald-500');
                    document.getElementById('statusPing').classList.remove('hidden');
                    
                    const container = document.getElementById('container');
                    
                    if (Object.keys(data).length === 0) {
                        container.innerHTML = `
                            <div id="emptyPlaceholder" class="col-span-5 flex flex-col items-center justify-center py-20 md:py-32 text-gray-500 w-full">
                                <svg class="w-8 h-8 md:w-12 md:h-12 mb-3 md:mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01"></path></svg>
                                <p class="text-[10px] md:text-sm text-center">Tidak ada sesi terminal yang aktif.</p>
                            </div>`;
                        return;
                    } else {
                        const placeholder = document.getElementById('emptyPlaceholder');
                        if (placeholder) placeholder.remove();
                    }

                    for (const [profile, logText] of Object.entries(data)) {
                        let term = document.getElementById('term_' + profile);
                        if (!term) {
                            const card = document.createElement('div');
                            card.className = 'bg-[#18181b] border border-[#27272a] rounded-xl shadow-sm flex flex-col overflow-hidden transition-all hover:border-gray-500 h-[200px] md:h-[380px] group';
                            card.innerHTML = `
                                <div class="flex justify-between items-center bg-[#18181b] border-b border-[#27272a] px-1.5 md:px-3 py-1.5 md:py-2 shrink-0">
                                    <div class="flex items-center gap-1 md:gap-2">
                                        <div class="flex gap-0.5 md:gap-1.5 opacity-50">
                                            <div class="w-1.5 h-1.5 md:w-2.5 md:h-2.5 rounded-full bg-red-500"></div>
                                            <div class="w-1.5 h-1.5 md:w-2.5 md:h-2.5 rounded-full bg-yellow-500"></div>
                                            <div class="w-1.5 h-1.5 md:w-2.5 md:h-2.5 rounded-full bg-green-500"></div>
                                        </div>
                                        <span class="text-gray-300 text-[8px] md:text-xs font-semibold ml-1 md:ml-2 tracking-wide uppercase truncate w-12 md:w-auto">${profile}</span>
                                    </div>
                                    <button onclick="openSingleInject('${profile}')" class="text-[7px] md:text-[10px] bg-[#27272a] hover:bg-emerald-600 hover:text-white hover:border-emerald-500 px-1.5 py-0.5 md:px-2.5 md:py-1 rounded text-gray-400 transition-all flex items-center gap-0.5 md:gap-1 border border-gray-600/30 opacity-70 group-hover:opacity-100 shrink-0">
                                        <svg class="w-2 h-2 md:w-3 md:h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
                                        Inject
                                    </button>
                                </div>
                                <div class="bg-[#000000] flex-grow relative overflow-hidden flex flex-col">
                                    <div class="text-[#d4d4d8] p-1.5 md:p-3 flex-grow overflow-auto text-[7px] md:text-[11px] whitespace-pre font-mono leading-relaxed outline-none" id="term_${profile}"></div>
                                </div>
                            `;
                            container.appendChild(card);
                            term = document.getElementById('term_' + profile);
                        }
                        if(term.innerText !== logText) {
                            term.innerText = logText;
                            term.scrollTop = term.scrollHeight;
                        }
                    }
                    
                    Array.from(container.children).forEach(card => {
                        const termDiv = card.querySelector('[id^="term_"]');
                        if (termDiv) {
                            const id = termDiv.id.replace('term_', '');
                            if (!data[id]) card.remove();
                        }
                    });
                })
                .catch(error => {
                    if (error.message !== 'Unauthorized') {
                        document.getElementById('connStatus').innerText = 'Koneksi Terputus';
                        document.getElementById('connStatus').classList.replace('text-gray-300', 'text-red-400');
                        document.getElementById('statusDot').classList.replace('bg-emerald-500', 'bg-red-500');
                        document.getElementById('statusPing').classList.add('hidden');
                    }
                });
        }
        
        setInterval(updateMonitors, 1000);

        function startAuth() {
            fetch('/api/auth/start', { method: 'POST' })
                .then(r => r.json())
                .then(res => {
                    if (res.error) {
                        alert("Gagal: " + res.error);
                    } else if (res.redirect_url) {
                        window.location.href = res.redirect_url;
                    }
                })
                .catch(err => {
                    alert("Terjadi kesalahan jaringan atau server.");
                });
        }

        // FUNGSI START MASSAL MODIFIKASI TERBARU (MENGIRIMKAN PROFIL YANG DIPILIH)
        function startMass() {
            let formData = new FormData();
            formData.append('hw', document.getElementById('hwSelect').value);
            
            const checkboxes = document.querySelectorAll('.profile-cb:checked');
            if (checkboxes.length > 0) {
                const selected = Array.from(checkboxes).map(cb => cb.value).join(',');
                formData.append('profiles', selected);
            } else {
                if (document.querySelectorAll('.profile-cb').length > 0) {
                    alert('Harap centang setidaknya satu akun!');
                    return;
                }
            }
            
            fetch('/api/mass/start', { method: 'POST', body: formData })
                .then(() => { closeModal('modalStart'); });
        }

        function stopTmuxOnly() {
            if(confirm("Tindakan ini hanya akan mematikan terminal tmux, tetapi riwayat sesi Colab akan dipertahankan. Lanjutkan?")) {
                fetch('/api/mass/stop_tmux', { method: 'POST' })
                    .then(() => {});
            }
        }

        function stopAllSessions() {
            if(confirm("Tindakan ini akan mematikan semua terminal dan me-reset riwayat sesi Colab (akun/profil tetap aman). Lanjutkan?")) {
                fetch('/api/mass/stop', { method: 'POST' })
                    .then(() => {});
            }
        }

        function injectMass() {
            const script = document.getElementById('scriptBox').value;
            if(!script) return alert('Kotak script tidak boleh kosong!');
            
            let formData = new FormData();
            formData.append('script', script);
            fetch('/api/mass/inject', { method: 'POST', body: formData })
                .then(() => {
                    closeModal('modalInject');
                    document.getElementById('scriptBox').value = '';
                });
        }

        function injectSingle() {
            const script = document.getElementById('singleScriptBox').value;
            const profile = document.getElementById('singleInjectTargetProfile').value;
            
            if(!script) return alert('Kotak script tidak boleh kosong!');
            
            let formData = new FormData();
            formData.append('script', script);
            formData.append('profile', profile);
            
            fetch('/api/single/inject', { method: 'POST', body: formData })
                .then(() => {
                    closeModal('modalSingleInject');
                    document.getElementById('singleScriptBox').value = '';
                });
        }

        function clearAllLogs() {
            fetch('/api/mass/clear_logs', { method: 'POST' })
                .then(() => {
                    const terminals = document.querySelectorAll('[id^="term_"]');
                    terminals.forEach(term => term.innerText = '');
                });
        }

        function deleteAll() {
            if(confirm("PERINGATAN: Tindakan ini akan menghentikan seluruh sesi yang berjalan dan menghapus SEMUA PROFIL AKUN secara permanen. Apakah Anda yakin?")) {
                fetch('/api/delete_all', { method: 'POST' })
                    .then(() => {});
            }
        }
    </script>
</body>
</html>
"""

# =========================================================================
# HELPER FUNCTIONS
# =========================================================================
def get_auto_profile_name():
    hari_id = {'monday': 'senin', 'tuesday': 'selasa', 'wednesday': 'rabu', 'thursday': 'kamis', 'friday': 'jumat', 'saturday': 'sabtu', 'sunday': 'minggu'}.get(datetime.now().strftime('%A').lower(), 'unknown')
    existing = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d)) and d.startswith(f"{hari_id}-")]
    return f"{hari_id}-{len(existing) + 1:02d}"

def get_profile_token_path(profile_name):
    prof_path = os.path.join(PROFILE_DIR, profile_name)
    config_dir = os.path.join(prof_path, ".config", "colab-cli")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "token.json")

def get_profile_env(profile_name):
    prof_path = os.path.join(PROFILE_DIR, profile_name)
    return f"env HOME='{prof_path}' XDG_CONFIG_HOME='{prof_path}' XDG_CACHE_HOME='{prof_path}'"

def get_profile_flags(profile_name):
    prof_path = os.path.join(PROFILE_DIR, profile_name)
    return f"-c '{prof_path}/.config/colab-cli/token.json' --config '{prof_path}/sessions.json'"

# =========================================================================
# ROUTING APLIKASI
# =========================================================================

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        if request.form.get('password') == WEB_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template_string(LOGIN_TEMPLATE, error=True)
    
    if session.get('logged_in'):
        return redirect(url_for('index'))
        
    return render_template_string(LOGIN_TEMPLATE, error=False)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/')
@login_required
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/accounts', methods=['GET'])
@login_required
def api_accounts():
    profiles = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]
    profiles.sort()
    return jsonify({"profiles": profiles})

@app.route('/api/account/delete', methods=['POST'])
@login_required
def api_account_delete():
    profile = request.form.get('profile', '')
    if profile:
        os.system(f"tmux kill-session -t colab_{profile} 2>/dev/null")
        prof_path = os.path.join(PROFILE_DIR, profile)
        if os.path.exists(prof_path):
            shutil.rmtree(prof_path, ignore_errors=True)
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Profile not found"}), 400

@app.route('/api/logs')
@login_required
def api_logs():
    active_screens = subprocess.getoutput("tmux ls 2>/dev/null")
    profiles = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]
    
    logs_data = {}
    for p in profiles:
        if f"colab_{p}" in active_screens:
            raw_output = subprocess.getoutput(f"tmux capture-pane -pt colab_{p} -S -100 2>/dev/null")
            
            if raw_output.strip():
                clean_text = ansi_escape.sub('', raw_output)
                
                final_lines = []
                for line in clean_text.split('\n'):
                    if '\r' in line:
                        line = line.split('\r')[-1] 
                    if screen_spam.search(line) or '0:bash*' in line:
                        continue
                    final_lines.append(line)
                
                logs_data[p] = '\n'.join(final_lines).strip()
            else:
                logs_data[p] = "Menyiapkan antarmuka terminal..."
                
    return jsonify(logs_data)

@app.route('/api/auth/start', methods=['POST'])
@login_required
def api_auth_start():
    if not os.path.exists(CLIENT_SECRETS_FILE):
        return jsonify({"error": "File client_secret.json belum di-upload di folder script."}), 400

    try:
        p_name = get_auto_profile_name()
        prof_path = os.path.join(PROFILE_DIR, p_name)
        os.makedirs(prof_path, exist_ok=True)
        
        session['current_auth_profile'] = p_name

        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        session['code_verifier'] = code_verifier

        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=url_for('oauth2callback', _external=True)
        )

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            code_challenge=code_challenge,
            code_challenge_method='S256'
        )

        session['state'] = state
        return jsonify({"redirect_url": authorization_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/oauth2callback')
@login_required
def oauth2callback():
    try:
        state = session.get('state')
        
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=url_for('oauth2callback', _external=True)
        )

        code_verifier = session.get('code_verifier')
        if not code_verifier:
            return "Error: Session (PKCE) hilang. Pastikan browser tidak memblokir cookie, lalu ulangi login.", 400

        flow.fetch_token(
            authorization_response=request.url,
            code_verifier=code_verifier
        )
        credentials = flow.credentials

        p_name = session.get('current_auth_profile')
        if not p_name:
            return "Error: Sesi profil hilang, silakan ulangi dari dashboard.", 400

        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "universe_domain": getattr(credentials, 'universe_domain', 'googleapis.com'),
            "account": "",
            "expiry": credentials.expiry.strftime('%Y-%m-%dT%H:%M:%SZ') if credentials.expiry else None
        }

        token_file_path = get_profile_token_path(p_name)
        with open(token_file_path, 'w') as f:
            json.dump(token_data, f, indent=2)

        return redirect(url_for('index'))
    except Exception as e:
        return f"Terjadi kesalahan saat otorisasi Google: {str(e)}", 500

# =========================================================================
# ROUTE START MASSAL TERBARU
# =========================================================================
@app.route('/api/mass/start', methods=['POST'])
@login_required
def api_mass_start():
    hw = request.form.get('hw', '1')
    hw_flag = {"2": "--gpu T4", "3": "--gpu A100", "4": "--tpu"}.get(hw, "")
    
    # Ambil list profile spesifik yang diceklis dari frontend
    selected_profiles_str = request.form.get('profiles', '')
    
    if selected_profiles_str:
        # Filter hanya yang dipilih dan foldernya benar-benar ada
        profiles = [p.strip() for p in selected_profiles_str.split(',') if os.path.isdir(os.path.join(PROFILE_DIR, p.strip()))]
    else:
        profiles = []
    
    for p in profiles:
        env = get_profile_env(p)
        flags = get_profile_flags(p)
        sname = f"colab_{p}"
        sessions_file = os.path.join(PROFILE_DIR, p, "sessions.json")
        
        # Bersihkan jendela terminal tmux supaya selalu fresh
        os.system(f"tmux kill-session -t {sname} 2>/dev/null")
        os.system(f"tmux new-session -d -s {sname} bash")
        time.sleep(0.2)
        
        # Cek apakah profil ini sudah punya sesi Colab yang masih nyantol
        existing_session = None
        if os.path.exists(sessions_file):
            try:
                with open(sessions_file, 'r') as f:
                    s_data = json.load(f)
                    if s_data and isinstance(s_data, dict):
                        existing_session = list(s_data.keys())[-1]
            except:
                pass
        
        if existing_session:
            cmd = f"{env} colab {flags} console -s {existing_session}"
        else:
            cmd = f"{env} colab {flags} new {hw_flag} && {env} colab {flags} console"
            
        os.system(f"tmux send-keys -t {sname} '{cmd}' C-m")
        
    return jsonify({"status": "started"})

@app.route('/api/mass/stop_tmux', methods=['POST'])
@login_required
def api_mass_stop_tmux():
    os.system("tmux ls -F '#{session_name}' 2>/dev/null | grep -E 'colab_' | xargs -I {} tmux kill-session -t {} 2>/dev/null")
    return jsonify({"status": "tmux_stopped"})

@app.route('/api/mass/stop', methods=['POST'])
@login_required
def api_mass_stop():
    os.system("tmux ls -F '#{session_name}' 2>/dev/null | grep -E 'colab_' | xargs -I {} tmux kill-session -t {} 2>/dev/null")
    
    profiles = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]
    for p in profiles:
        sessions_file = os.path.join(PROFILE_DIR, p, "sessions.json")
        if os.path.exists(sessions_file):
            os.remove(sessions_file)
            
    return jsonify({"status": "stopped"})

@app.route('/api/mass/inject', methods=['POST'])
@login_required
def api_mass_inject():
    script = request.form.get('script', '')
    profiles = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]
    
    for line in script.split('\n'):
        if not line.strip(): continue
        safe_line = line.replace("'", "'\\''")
        for p in profiles:
            os.system(f"tmux send-keys -t colab_{p} '{safe_line}' C-m")
        time.sleep(0.3)
        
    return jsonify({"status": "injected mass"})

@app.route('/api/single/inject', methods=['POST'])
@login_required
def api_single_inject():
    profile = request.form.get('profile', '')
    script = request.form.get('script', '')
    
    if not profile or not script:
        return jsonify({"error": "Profile atau script tidak valid"}), 400
        
    for line in script.split('\n'):
        if not line.strip(): continue
        safe_line = line.replace("'", "'\\''")
        os.system(f"tmux send-keys -t colab_{profile} '{safe_line}' C-m")
        time.sleep(0.3)
        
    return jsonify({"status": "injected single"})

@app.route('/api/mass/clear_logs', methods=['POST'])
@login_required
def api_mass_clear_logs():
    profiles = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]
    for p in profiles:
        os.system(f"tmux send-keys -t colab_{p} 'clear' C-m 2>/dev/null")
        os.system(f"tmux clear-history -t colab_{p} 2>/dev/null")
            
    return jsonify({"status": "cleared"})

@app.route('/api/delete_all', methods=['POST'])
@login_required
def api_delete_all():
    os.system("tmux ls -F '#{session_name}' 2>/dev/null | grep -E 'colab_|auth_' | xargs -I {} tmux kill-session -t {} 2>/dev/null")
    shutil.rmtree(PROFILE_DIR, ignore_errors=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    print("\n\033[0;32m\033[1m[!] SYSTEM GHOST-DOT WEB CONTROLLER AKTIF [!]\033[0m")
    print("\033[1;33m>> Menjalankan server pada port 7860\033[0m")
    
    app.run(host='0.0.0.0', port=7860, debug=False, use_reloader=False)
