import os
import shutil
import subprocess
import psutil
import json
import time
import threading
import schedule
import re
import socket
import base64
import sys
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# ⚙️ KONFIGURASI UTAMA & DIREKTORI
# ==========================================
APP_PORT = 8080 # Port lokal untuk callback Auth
SHARED_SECRET = "jokowi123"
MASTER_AUTH_URL = "https://colab.bahliljaya.tech"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.expanduser("~/.colab-manager-profiles")

# Direktori & File Lokal
EMAIL_FILE = os.path.join(BASE_DIR, "email.txt")
MANAGER_EMAILS_FILE = os.path.join(BASE_DIR, "manager_emails.txt")
MASTER_CONFIG_FILE = os.path.join(BASE_DIR, "master_config.json")
SYS_LOG_FILE = os.path.join(BASE_DIR, "sys_log.txt")

os.makedirs(PROFILE_DIR, exist_ok=True)

# Regex untuk Tmux log parsing
ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\\[[0-?]*[ -/]*[@-~])')
screen_spam = re.compile(r'\\[\d+\\]\s+\d+:bash\*')

for file_path in [EMAIL_FILE, MANAGER_EMAILS_FILE, SYS_LOG_FILE]:
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8') as f: 
            f.write("")

# ==========================================
# 🌐 MICRO HTTP SERVER (UNTUK TERIMA AUTH)
# ==========================================
class AuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Matikan log bawaan agar terminal tidak kotor

    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/api/receive_token':
            params = parse_qs(parsed_path.query)
            secret = params.get('secret', [''])[0]
            profile = params.get('profile', [''])[0]
            data_b64 = params.get('data', [''])[0]

            if secret != SHARED_SECRET:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return
            
            try:
                t_data = json.loads(base64.b64decode(data_b64).decode('utf-8'))
                c_dir = os.path.join(PROFILE_DIR, profile, ".config", "colab-cli")
                os.makedirs(c_dir, exist_ok=True)
                with open(os.path.join(c_dir, "token.json"), 'w') as f: 
                    json.dump(t_data, f, indent=2)
                with open(os.path.join(c_dir, "token_master.json"), 'w') as f: 
                    json.dump(t_data, f, indent=2)
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"<body style='background:#09090b;color:#10b981;font-family:monospace;text-align:center;padding-top:20%;'><h1>Auth Berhasil!</h1><p>Token tersimpan. Silakan kembali ke terminal VPS.</p></body>")
                
                print(f"\n\033[1;32m[+] Token Auth berhasil diterima untuk profil: {profile}\033[0m")
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Error: {str(e)}".encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_local_server():
    server = HTTPServer(('127.0.0.1', APP_PORT), AuthHandler)
    server.serve_forever()

# ==========================================
# 🌐 FUNGSI BANTUAN (HELPER)
# ==========================================
def clear_screen(): 
    os.system('cls' if os.name == 'nt' else 'clear')

def append_log(msg):
    timestamp = time.strftime('%H:%M:%S')
    line = f"[{timestamp}] {msg}"
    print(f"\033[0;32m{line}\033[0m")
    try:
        with open(SYS_LOG_FILE, "a", encoding='utf-8') as f: 
            f.write(line + "\n")
    except: 
        pass

def run_cmd(cmd): 
    subprocess.run(cmd, shell=True, close_fds=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ==========================================
# ⚙️ KONFIGURASI OTOMATISASI & GLOBAL
# ==========================================
DEFAULT_CONFIG = {
    "secret": "jokowi123", 
    "interval_jam": 11,
    "script_loop": "cd /tmp/\n{{CREATE_EMAIL}}\nwget -qO- https://script.bahliljaya.tech/memek.sh | bash"
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(MASTER_CONFIG_FILE):
        try:
            with open(MASTER_CONFIG_FILE, 'r', encoding='utf-8') as f: 
                config.update(json.load(f))
        except: 
            pass
    return config

def save_config(data):
    with open(MASTER_CONFIG_FILE, 'w', encoding='utf-8') as f: 
        json.dump(data, f, indent=4)
    reload_scheduler()

# ==========================================
# ☁️ FUNGSI INTI COLAB MANAGER (TMUX)
# ==========================================
def get_auto_profile_name():
    hari_id = {'monday': 'senin', 'tuesday': 'selasa', 'wednesday': 'rabu', 'thursday': 'kamis', 'friday': 'jumat', 'saturday': 'sabtu', 'sunday': 'minggu'}.get(datetime.now().strftime('%A').lower(), 'unknown')
    e = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d)) and d.startswith(f"{hari_id}-")]
    return f"{hari_id}-{len(e) + 1:02d}"

def get_profile_env(p): 
    path = os.path.join(PROFILE_DIR, p)
    return f"env HOME='{path}' XDG_CONFIG_HOME='{path}' XDG_CACHE_HOME='{path}'"

def get_profile_flags(p): 
    path = os.path.join(PROFILE_DIR, p)
    return f"-c '{path}/.config/colab-cli/token.json' --config '{path}/sessions.json'"

def core_delete_all():
    run_cmd("tmux ls -F '#{session_name}' 2>/dev/null | grep -E 'colab_|auth_' | xargs -I {} tmux kill-session -t {} 2>/dev/null")
    shutil.rmtree(PROFILE_DIR, ignore_errors=True)
    os.makedirs(PROFILE_DIR, exist_ok=True)

def core_mass_start(hw="1"):
    hw_f = {"2": "--gpu T4", "3": "--gpu A100", "4": "--tpu"}.get(str(hw), "")
    profiles = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]
    
    if not profiles:
        append_log(" -> Tidak ada profil akun yang ditemukan.")
        return

    for p in profiles:
        env, flags, sname, sf = get_profile_env(p), get_profile_flags(p), f"colab_{p}", os.path.join(PROFILE_DIR, p, "sessions.json")
        run_cmd(f"tmux kill-session -t {sname} 2>/dev/null")
        run_cmd(f"tmux new-session -d -s {sname} bash")
        time.sleep(0.2)
        
        ex = list(json.load(open(sf, 'r')).keys())[-1] if os.path.exists(sf) else None
        cmd = f"{env} colab {flags} console -s {ex} || (rm -f '{sf}' && {env} colab {flags} new {hw_f} && {env} colab {flags} console)" if ex else f"{env} colab {flags} new {hw_f} && {env} colab {flags} console"
        run_cmd(f"tmux send-keys -t {sname} '{cmd}' C-m")

def core_clear_logs():
    for p in [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]:
        run_cmd(f"tmux send-keys -t colab_{p} 'clear' C-m 2>/dev/null")
        run_cmd(f"tmux clear-history -t colab_{p} 2>/dev/null")

def core_mass_inject(script_text):
    manager_emails = []
    if os.path.exists(MANAGER_EMAILS_FILE):
        with open(MANAGER_EMAILS_FILE, 'r', encoding='utf-8') as f:
            manager_emails = [line.strip() for line in f if line.strip()]
            
    profiles = [d for d in os.listdir(PROFILE_DIR) if os.path.isdir(os.path.join(PROFILE_DIR, d))]
    profiles.sort()
    
    if not profiles:
        append_log(" -> Tidak ada profil akun yang ditemukan.")
        return

    for idx, p in enumerate(profiles):
        start_idx = idx * 4
        chunk = manager_emails[start_idx : start_idx + 4]
        
        for line in script_text.split('\n'):
            if not line.strip(): continue
            if "{{CREATE_EMAIL}}" in line:
                run_cmd(f"tmux send-keys -t colab_{p} 'cat << '\\'EOF'\\' > email.txt' C-m")
                time.sleep(2)
                for mail in chunk:
                    run_cmd(f"tmux send-keys -t colab_{p} '{mail}' C-m")
                    time.sleep(2)
                run_cmd(f"tmux send-keys -t colab_{p} 'EOF' C-m")
                time.sleep(2)
            else:
                safe_line = line.replace("'", "'\\''")
                run_cmd(f"tmux send-keys -t colab_{p} '{safe_line}' C-m")
                time.sleep(2)

# ==========================================
# 🚀 RANTAI EKSEKUSI BACKGROUND (TRIGGER)
# ==========================================
def trigger_chain():
    config = load_config()
    script = config.get('script_loop', '')
    
    append_log(f"=== MEMULAI SIKLUS LOOP OTOMATIS ===")
    
    append_log("[1/6] Menghapus sesi lama (Internal)...")
    try:
        core_delete_all()
        append_log(" -> Hapus sesi berhasil.")
    except Exception as e:
        append_log(f" -> Error Hapus Sesi: {e}")
        
    time.sleep(5)

    append_log("[2/6] Menjalankan bot OAuth lokal (loopouth.py)...")
    script_path = os.path.join(BASE_DIR, "loopouth.py")
    if os.path.exists(script_path):
        cmd = f'xvfb-run -a -s "-screen 0 1280x720x24" python3 {script_path}'
        subprocess.run(cmd, shell=True, cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        append_log(" -> loopouth.py telah selesai.")
    else:
        append_log(" -> Error: File loopouth.py tidak ditemukan!")

    append_log("[3/6] Memulai sesi terminal massal (Internal)...")
    try:
        core_mass_start()
        append_log(" -> Instruksi mulai sesi terkirim.")
    except Exception as e:
        append_log(f" -> Error Mulai Sesi: {e}")

    append_log("[4/6] Menunggu 3 menit (180 detik) booting sesi...")
    time.sleep(180)

    append_log("[5/6] Melakukan Clear Log 3x (Jeda 20 detik)...")
    for i in range(1, 4):
        try:
            core_clear_logs()
            append_log(f" -> Clear log ke-{i} sukses.")
        except: 
            pass
        if i < 3: 
            time.sleep(20)

    if script.strip():
        append_log(f"[6/6] Mengirim Script Eksekusi ke Terminal...")
        try:
            core_mass_inject(script)
            append_log(" -> Script berhasil terkirim!")
        except Exception as e:
            append_log(f" -> Error Inject: {e}")
            
    append_log("=== SIKLUS LOOP SELESAI ===")

def run_scheduler():
    while True: 
        schedule.run_pending()
        time.sleep(1)
        
def reload_scheduler():
    schedule.clear()
    config = load_config()
    try: 
        interval = int(config.get('interval_jam', 11))
    except: 
        interval = 11
        
    if interval > 0:
        schedule.every(interval).hours.do(trigger_chain)

# ==========================================
# ⚙️ SETTINGS INTERACTIVE MENU
# ==========================================
def settings_menu():
    config = load_config()
    while True:
        clear_screen()
        print("\033[1;35m--- ⚙️ PENGATURAN GLOBAL & LOKAL ---\033[0m")
        print("1. Set Secret Key API (Saat ini: {})".format(config.get('secret', '')))
        print("2. Edit Manager Emails (Colab Target)")
        print("3. Edit Data email.txt (Lokal)")
        print("4. Edit Script Loop Eksekusi")
        print("5. Set Interval Eksekusi (Saat ini: {} Jam)".format(config.get('interval_jam', 11)))
        print("0. Kembali ke Menu Utama")
        
        sub_pil = input("\nPilih Pengaturan [0-5]: ")
        
        if sub_pil == '1':
            baru = input("Masukkan Secret Key baru: ")
            if baru: 
                config['secret'] = baru
                save_config(config)
                print("\033[1;32mTersimpan!\033[0m")
            time.sleep(1)
            
        elif sub_pil == '2':
            print("\nSilakan paste daftar email (bisa langsung copy-paste banyak baris).")
            print("Tekan Enter 2x beruntun di baris kosong untuk otomatis menyimpan:")
            lines = []
            empty_count = 0
            while True:
                try:
                    line = input()
                    if line.strip() == '':
                        empty_count += 1
                        if empty_count >= 2: break
                    else:
                        empty_count = 0
                        
                    if line.strip(): 
                        lines.extend([x.strip() for x in line.replace(',', '\n').split('\n') if x.strip()])
                except EOFError:
                    break
            
            with open(MANAGER_EMAILS_FILE, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            print("\n\033[1;32mData Manager Emails Tersimpan!\033[0m")
            time.sleep(1.5)
            
        elif sub_pil == '3':
            print("\nSilakan paste isi file email.txt lokal (bisa langsung copy-paste banyak baris).")
            print("Tekan Enter 2x beruntun di baris kosong untuk otomatis menyimpan:")
            lines = []
            empty_count = 0
            while True:
                try:
                    line = input()
                    if line == '':
                        empty_count += 1
                        if empty_count >= 2: 
                            if lines and lines[-1] == '':
                                lines.pop() # Hapus 1 baris kosong sisa dari trigger double enter
                            break
                    else:
                        empty_count = 0
                    lines.append(line)
                except EOFError:
                    break
                    
            with open(EMAIL_FILE, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            print("\n\033[1;32mData email.txt Tersimpan!\033[0m")
            time.sleep(1.5)
            
        elif sub_pil == '4':
            print("\nSilakan PASTE seluruh Script Loop kamu di bawah ini (mendukung multi-baris).")
            print("Tekan Enter 2x beruntun di baris kosong untuk otomatis menyimpan:")
            lines = []
            empty_count = 0
            while True:
                try:
                    line = input()
                    if line == '':
                        empty_count += 1
                        if empty_count >= 2: 
                            if lines and lines[-1] == '':
                                lines.pop() # Hapus 1 baris kosong sisa dari trigger double enter
                            break
                    else:
                        empty_count = 0
                    lines.append(line)
                except EOFError:
                    break
            
            if lines:
                config['script_loop'] = "\n".join(lines)
                save_config(config)
                print("\n\033[1;32m[+] Script berhasil disimpan secara global!\033[0m")
            else:
                print("\n\033[1;31m[-] Dibatalkan karena input kosong.\033[0m")
            time.sleep(1.5)
            
        elif sub_pil == '5':
            baru_int = input("Masukkan Interval Jam baru: ")
            if baru_int.strip().isdigit():
                config['interval_jam'] = int(baru_int.strip())
                save_config(config)
                print("\033[1;32mInterval berhasil diubah! Scheduler di-reset.\033[0m")
            time.sleep(1)
            
        elif sub_pil == '0':
            break

# ==========================================
# 🎛️ CLI ARGUMENT HANDLER (PENGGANTI MENU)
# ==========================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Gunakan argumen perintah. Contoh: python3 main.py --daemon")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "--daemon":
        # Mode latar belakang 24/7 (Tanpa Cloudflare)
        reload_scheduler()
        threading.Thread(target=run_scheduler, daemon=True).start()
        threading.Thread(target=start_local_server, daemon=True).start()
        
        # Loop abadi agar daemon tidak mati
        while True: 
            time.sleep(60) 
            
    elif cmd == "--get-auth":
        p_name = get_auto_profile_name()
        os.makedirs(os.path.join(PROFILE_DIR, p_name), exist_ok=True)
        # Langsung bypass agent_url ke localhost
        agent_url = f"http://127.0.0.1:{APP_PORT}"
        print(f"{MASTER_AUTH_URL}/start_auth?agent_url={agent_url}&profile={p_name}")

    elif cmd == "--mass-start":
        hw = sys.argv[2] if len(sys.argv) > 2 else "1"
        core_mass_start(hw)

    elif cmd == "--mass-inject":
        file_path = sys.argv[2] if len(sys.argv) > 2 else ""
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f: 
                script_text = f.read()
            core_mass_inject(script_text)
        else:
            print("ERROR_FILE_NOT_FOUND")

    elif cmd == "--stop-all":
        run_cmd("tmux ls -F '#{session_name}' 2>/dev/null | grep -E 'colab_' | xargs -I {} tmux kill-session -t {} 2>/dev/null")
        for p in os.listdir(PROFILE_DIR):
            sf = os.path.join(PROFILE_DIR, p, "sessions.json")
            if os.path.exists(sf): os.remove(sf)

    elif cmd == "--clear-logs":
        core_clear_logs()

    elif cmd == "--wipe-data":
        core_delete_all()

    elif cmd == "--trigger-chain":
        trigger_chain()

    elif cmd == "--resource":
        try: 
            print(f"CPU Usage: {min(100, int((os.getloadavg()[0] / (os.cpu_count() or 1)) * 100))}%")
        except: 
            pass
        try:
            with open('/proc/meminfo', 'r') as f: 
                mem = f.read()
            tot = int(re.search(r'MemTotal:\s+(\d+)', mem).group(1)) / 1024
            ava = int(re.search(r'MemAvailable:\s+(\d+)', mem).group(1)) / 1024
            print(f"RAM Usage: {int(tot - ava)}MB / {int(tot)}MB")
        except: 
            pass

    elif cmd == "--settings":
        settings_menu()
        
    elif cmd == "--run-bot":
        bot_name = sys.argv[2] if len(sys.argv) > 2 else ""
        if bot_name:
            script_path = os.path.join(BASE_DIR, bot_name)
            if os.path.exists(script_path):
                cmd_run = f'xvfb-run -a -s "-screen 0 1280x720x24" python3 {script_path}'
                subprocess.Popen(cmd_run, shell=True, cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("SUCCESS")
            else:
                print("NOT_FOUND")
