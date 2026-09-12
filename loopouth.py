import os
import time
import subprocess
import sys
import psutil
import mss
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

# ==========================================
# ⚙️ KONFIGURASI MULTI-PROFILE & URL
# ==========================================
PROFILE_PREFIX = "dotaja"     
START_INDEX = 1               

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
CHROME_PATH = "/usr/bin/google-chrome" 
DEBUG_PORT = 9222 

BASE_PATH = os.getcwd() 
BASE_PROFILE_DIR = os.path.join(BASE_PATH, "chrome_profiles")
EMAIL_FILE = os.path.join(BASE_PATH, "email.txt")
HISTORY_FILE = os.path.join(BASE_PATH, "history_sukses.txt") 
IP_FILE = os.path.join(BASE_PATH, "iptarget.txt")

# ==========================================
# 🌐 LOGIKA IP TARGET (WAJIB ADA)
# ==========================================
VPS_PORT = "80" 

if not os.path.exists(IP_FILE):
    print("❌ [FATAL] File iptarget.txt tidak ditemukan! Harap isi IP di Panel Web terlebih dahulu.", flush=True)
    sys.exit(1)

with open(IP_FILE, "r") as f:
    VPS_IP = f.read().strip()

if not VPS_IP:
    print("❌ [FATAL] File iptarget.txt kosong! Harap isi IP di Panel Web terlebih dahulu.", flush=True)
    sys.exit(1)

# KONFIGURASI TELEGRAM
TELEGRAM_TOKEN = "8455364218:AAFoy_mvhZi9HYeTM48hO9aXapE-cYmWuCs"
TELEGRAM_CHAT_ID = "6501677690"
SS_FILE = os.path.join(BASE_PATH, "tangkapan_akhir.png") 

# ==========================================
# FUNGSI PENDUKUNG
# ==========================================
def load_history():
    if not os.path.exists(HISTORY_FILE): return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

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

def capture_and_send(status, email):
    """Fungsi screenshot, kirim telegram, lalu langsung hapus filenya"""
    try:
        with mss.MSS() as sct:
            sct.shot(mon=-1, output=SS_FILE)
        
        simbol = "✅" if status == "SUKSES" else "❌"
        print(f"📸 [SCREENSHOT] Mengambil gambar status: {status}", flush=True)
        
        if TELEGRAM_TOKEN != "ISI_TOKEN_BOT_DISINI":
            subprocess.run([
                "curl", "-s", "-X", "POST",
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                "-F", f"chat_id={TELEGRAM_CHAT_ID}",
                "-F", f"photo=@{SS_FILE}",
                "-F", f"caption={simbol} Status: {status}\n📧 Akun: {email}"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        # Hapus file SS setelah dikirim agar tidak nyampah di VPS
        if os.path.exists(SS_FILE):
            os.remove(SS_FILE)
            
    except Exception as e:
        print(f"⚠️ [SCREENSHOT] Gagal memproses gambar: {e}")

# ==========================================
# MAIN EXECUTION
# ==========================================
if not os.path.exists(EMAIL_FILE): 
    print("❌ File email.txt tidak ditemukan!")
    sys.exit(1)

with open(EMAIL_FILE, "r") as f:
    CREDENTIALS = [line.strip().split(":", 1) for line in f if line.strip() and ":" in line]

COMPLETED_EMAILS = load_history()

print(f"🚀 Memulai Auto-OAuth ke {len(CREDENTIALS)} profil dengan Target IP: {VPS_IP}...", flush=True)

for i, (EMAIL, PASSWORD) in enumerate(CREDENTIALS, start=START_INDEX):
    if EMAIL not in COMPLETED_EMAILS:
        continue 

    kill_chrome()
    folder_name = f"{PROFILE_PREFIX}{i:02d}"
    full_profile_path = os.path.join(BASE_PROFILE_DIR, folder_name)

    print(f"\n========================================================")
    print(f"🔑 PROSES AKUN: {EMAIL} ({folder_name})")
    print(f"========================================================")
    
    TARGET_URL = f"https://colab.bahliljaya.tech/start_auth?agent_url=http://{VPS_IP}:{VPS_PORT}&profile={folder_name}"

    cmd = [
        CHROME_PATH, 
        f"--remote-debugging-port={DEBUG_PORT}", 
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
    time.sleep(8) 

    # ========================================================    
    # AMBIL ALIH DENGAN SELENIUM UNTUK KLIK OAUTH    
    # ========================================================    
    print("🤖 [SELENIUM] Mengaitkan Selenium ke browser aktif...", flush=True)    
    chrome_options = Options()    
    chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")        
    
    driver = None
    try:
        try:        
            service = Service(log_path=os.devnull)        
            driver = webdriver.Chrome(service=service, options=chrome_options)    
        except Exception:        
            driver = webdriver.Chrome(options=chrome_options, service_log_path=os.devnull)    
        
        wait = WebDriverWait(driver, 10)

        # 1. CEK PILIH AKUN
        try:
            print("🔎 [SELENIUM] Cek layar pilih akun...")
            email_div = wait.until(EC.element_to_be_clickable((By.XPATH, f"//div[@data-email='{EMAIL}']")))
            driver.execute_script("arguments[0].click();", email_div)
            time.sleep(3)
            print("✅ [SELENIUM] Berhasil klik pilihan akun.")
        except TimeoutException:
            print("ℹ️ [SELENIUM] Layar pilih akun tidak muncul, aman...")

        # 2. CEK PASSWORD
        try:
            print("🔎 [SELENIUM] Cek verifikasi password...")
            pass_input = wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
            pass_input.send_keys(PASSWORD)
            pass_input.send_keys(Keys.ENTER)
            time.sleep(5)
            print("✅ [SELENIUM] Berhasil mengisi password.")
        except TimeoutException:
            print("ℹ️ [SELENIUM] Verifikasi password tidak diminta, aman...")

        # 3. BYPASS TIDAK AMAN    
        try:        
            print("🔎 [SELENIUM] Mencari peringatan keamanan Google...")        
            lanjutan_btn = wait.until(EC.element_to_be_clickable(            
                (By.XPATH, "//a[@jsname='BO4nrb' or contains(text(), 'Lanjutan')]")        
            ))        
            driver.execute_script("arguments[0].click();", lanjutan_btn)        
            time.sleep(1.5)        
            buka_tidak_aman_btn = wait.until(EC.element_to_be_clickable(            
                (By.XPATH, "//a[@jsname='ehL7e' or contains(text(), 'tidak aman')]")        
            ))        
            driver.execute_script("arguments[0].click();", buka_tidak_aman_btn)        
            time.sleep(5)        
            print("✅ [SELENIUM] Berhasil melewati peringatan keamanan (Lanjutan).")        
        except TimeoutException:        
            print("ℹ️ [SELENIUM] Layar peringatan keamanan tidak muncul, lanjut...")    
            
        # 4. LANJUTKAN PERTAMA
        try:        
            print("🔎 [SELENIUM] Menunggu tombol 'Lanjutkan' pertama...")        
            lanjutkan_1 = wait.until(EC.element_to_be_clickable(            
                (By.XPATH, "//span[@jsname='V67aGc' and contains(text(), 'Lanjutkan')]")        
            ))        
            driver.execute_script("arguments[0].click();", lanjutkan_1)        
            time.sleep(5)        
            print("✅ [SELENIUM] Tombol Lanjutkan ke-1 diklik.")    
        except TimeoutException:        
            print("⚠️ [SELENIUM] Tombol Lanjutkan ke-1 tidak ditemukan.")    
            
        # 5. LANJUTKAN KEDUA
        try:        
            print("🔎 [SELENIUM] Menunggu tombol 'Lanjutkan' kedua...")        
            lanjutkan_2 = wait.until(EC.element_to_be_clickable(            
                (By.XPATH, "//span[@jsname='V67aGc' and contains(text(), 'Lanjutkan')]")        
            ))        
            driver.execute_script("arguments[0].click();", lanjutkan_2)        
            print("✅ [SELENIUM] Tombol Lanjutkan ke-2 diklik.")    
        except TimeoutException:        
            print("⚠️ [SELENIUM] Tombol Lanjutkan ke-2 tidak ditemukan.")    
            
        print("⏳ Menunggu callback token (10 detik)...", flush=True)    
        time.sleep(10)        
        
        print(f"✅ [SUKSES] Akun {EMAIL} selesai diproses.", flush=True)    
        capture_and_send("SUKSES", EMAIL)

    except Exception as e:
        print(f"❌ [FATAL ERROR] Terjadi kesalahan pada akun {EMAIL}: {e}", flush=True)
        capture_and_send("ERROR", EMAIL)

    finally:
        if driver:
            try: driver.quit()    
            except: pass    
        kill_chrome(proc)    
        time.sleep(3)

print("\n🏁 SEMUA AKUN SELESAI DIPROSES.")
