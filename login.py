import os
import time
import subprocess
import sys
import json
import pyautogui
import mss
import psutil

# ==========================================
# ⚙️ KONFIGURASI BOT
# ==========================================
PROFILE_PREFIX = "dotaja"     
START_INDEX = 1               

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
CHROME_PATH = "/usr/bin/google-chrome" 

BASE_PATH = os.getcwd() 
BASE_PROFILE_DIR = os.path.join(BASE_PATH, "chrome_profiles")
EMAIL_FILE = os.path.join(BASE_PATH, "email.txt")
MAPPING_FILE = os.path.join(BASE_PATH, "mapping_profil.txt")
HISTORY_FILE = os.path.join(BASE_PATH, "history_sukses.txt") 

TELEGRAM_TOKEN = "8455364218:AAFoy_mvhZi9HYeTM48hO9aXapE-cYmWuCs"
TELEGRAM_CHAT_ID = "6501677690"

# Target file gambar yang akan disedot oleh agent.py
SS_FILE = os.path.join(BASE_PATH, "bukti_dotaja01.png") 

# ==========================================
# FUNGSI PENDUKUNG
# ==========================================
def load_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_history(email):
    with open(HISTORY_FILE, "a") as f:
        f.write(email + "\n")

def save_mapping(full_path, profile_name):
    if os.path.exists(MAPPING_FILE):
        with open(MAPPING_FILE, "r") as f:
            if any(full_path in line for line in f): return
    with open(MAPPING_FILE, "a") as f:
        f.write(f"{full_path}|{profile_name}\n")

def fix_crash_restore_popup(profile_path):
    pref_file = os.path.join(profile_path, "Default", "Preferences")
    if not os.path.exists(pref_file): return
    try:
        with open(pref_file, "r", encoding="utf-8") as f: data = json.load(f)
        if "profile" in data:
            data["profile"]["exit_type"] = "Normal"
            data["profile"]["exited_cleanly"] = True
            with open(pref_file, "w", encoding="utf-8") as f: json.dump(data, f)
    except: pass

def kill_chrome(proc_instance=None):
    if proc_instance:
        try:
            proc_instance.terminate()
            proc_instance.wait(timeout=2)
        except: pass

    my_pid = os.getpid()
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            if p.pid == my_pid: continue
            name = p.info['name'].lower()
            cmd = ' '.join(p.info['cmdline']) if p.info['cmdline'] else ''
            if 'chrome' in name or 'chrome' in cmd:
                try: p.kill() 
                except: pass
        except: pass
    time.sleep(1)

# ==========================================
# MAIN EXECUTION
# ==========================================
if not os.path.exists(EMAIL_FILE): 
    print("❌ [LOGIN] File email.txt tidak ditemukan!", flush=True)
    sys.exit(1)

with open(EMAIL_FILE, "r") as f:
    CREDENTIALS = [line.strip().split(":", 1) for line in f if line.strip() and ":" in line]

if not CREDENTIALS:
    print("⚠️ [LOGIN] File email.txt kosong atau format tidak sesuai (pastikan format email:pass)! Membatalkan proses.", flush=True)
    sys.exit(1)

COMPLETED_EMAILS = load_history()
kill_chrome()

print(f"🚀 [LOGIN] Memulai antrean login untuk {len(CREDENTIALS)} akun...", flush=True)

for i, (EMAIL, PASSWORD) in enumerate(CREDENTIALS, start=START_INDEX):
    folder_name = f"{PROFILE_PREFIX}{i:02d}"
    full_profile_path = os.path.join(BASE_PROFILE_DIR, folder_name)
    
    if not os.path.exists(full_profile_path): os.makedirs(full_profile_path)
    save_mapping(full_profile_path, folder_name)
    fix_crash_restore_popup(full_profile_path)

    if EMAIL in COMPLETED_EMAILS:
        MODE = "CHECK"
        print(f"⏩ [LOGIN] {EMAIL} sudah pernah login. Melewati eksekusi...", flush=True)
    else:
        MODE = "LOGIN"
        print(f"🔑 [LOGIN] Memproses eksekusi akun: {EMAIL}", flush=True)
        
    TARGET_URL = "https://idx.google.com/joko" 

    cmd = [
        CHROME_PATH, 
        "--no-sandbox",
        "--test-type",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--simulate-outdated-no-au='Tue, 31 Dec 2099 23:59:59 GMT'",
        "--disable-component-update",
        "--disable-session-crashed-bubble",
        "--no-first-run", "--no-default-browser-check", 
        f"--window-size={SCREEN_WIDTH},{SCREEN_HEIGHT}",
        f"--user-data-dir={full_profile_path}", 
        TARGET_URL
    ]
    
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_time = 15 if MODE == "LOGIN" else 10
    time.sleep(wait_time)

    try:
        if MODE == "LOGIN":
            time.sleep(30)
            print("⌨️  [LOGIN] Mengetik email...", flush=True)
            pyautogui.write(EMAIL, interval=0.1)
            pyautogui.press("enter")
            time.sleep(30) 
            
            print("⌨️  [LOGIN] Mengetik password...", flush=True)
            pyautogui.write(PASSWORD, interval=0.1)
            pyautogui.press("enter")
            time.sleep(30)
            
            save_history(EMAIL)
            print(f"✅ [LOGIN] Sukses login: {EMAIL}", flush=True)
        
        try:
            with mss.MSS() as sct: 
                sct.shot(mon=-1, output=SS_FILE)
            print(f"📸 [LOGIN] Tangkapan layar diamankan.", flush=True)
            
            if TELEGRAM_TOKEN != "ISI_TOKEN_BOT_DISINI":
                try:
                    subprocess.run([
                        "curl", "-s", "-X", "POST",
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                        "-F", f"chat_id={TELEGRAM_CHAT_ID}",
                        "-F", f"photo=@{SS_FILE}"
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"✈️ [TELEGRAM] Screenshot terkirim ke Telegram.", flush=True)
                except Exception as e:
                    print(f"⚠️ [TELEGRAM] Gagal mengirim screenshot: {e}", flush=True)

        except Exception as e: 
            print(f"⚠️ [LOGIN] Gagal menyimpan screenshot: {e}", flush=True)
            
    except Exception as e:
        print(f"❌ [LOGIN] Error Interaksi PyAutoGUI: {e}", flush=True)

    kill_chrome(proc)
    time.sleep(2)

print("🏁 [LOGIN] Seluruh antrean selesai dieksekusi.", flush=True)
