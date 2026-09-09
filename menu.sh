#!/bin/bash

# Pastikan script dijalankan di direktori yang sama dengan main.py
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

# Cek apakah file main.py ada di folder ini
if [ ! -f "main.py" ]; then
    echo -e "\e[1;31m[-] Error: File main.py tidak ditemukan di $DIR\e[0m"
    echo "Pastikan menu.sh dan main.py berada di dalam folder yang sama."
    exit 1
fi

# ==========================================
# ⚙️ AUTO GENERATE FILE PENDUKUNG
# ==========================================
if [ ! -f "iptarget.txt" ]; then
    echo "127.0.0.1" > iptarget.txt
fi

# Fungsi untuk memastikan Python Daemon berjalan
check_daemon() {
    if ! pgrep -f "python3 main.py --daemon" > /dev/null; then
        echo -e "\e[1;33m[!] Menghidupkan GHOST-DOT Background Daemon (HTTP, Scheduler)...\e[0m"
        nohup python3 main.py --daemon > daemon.log 2>&1 &
        sleep 1 
    fi
}

# ==========================================
# 🖥️ LOOP MENU MINIMALIS
# ==========================================
while true; do
    check_daemon
    clear
    echo -e "\e[1;36m=================================================\e[0m"
    echo -e "\e[1;32m       🤖 GHOST-DOT MASTER - MINIMAL CLI        \e[0m"
    echo -e "\e[1;36m=================================================\e[0m"
    
    # Status HTTP Server Localhost
    echo -e " \e[1;33m[🌐] Auth Listener:\e[0m \e[4;34mhttp://127.0.0.1:80\e[0m"
    
    # Hitung total profil
    if [ -d "$HOME/.colab-manager-profiles" ]; then
        TOTAL_PROF=$(find "$HOME/.colab-manager-profiles" -mindepth 1 -maxdepth 1 -type d | wc -l)
    else
        TOTAL_PROF=0
    fi
    echo -e " \e[1;35m[👤] Total Profil Google:\e[0m $TOTAL_PROF Profil"
    echo -e "\e[1;36m=================================================\e[0m\n"

    echo -e "  \e[1;37m[1]\e[0m 🔄 Jalankan Rantai Otomatis (Trigger Manual)"
    echo -e "  \e[1;37m[2]\e[0m ⚙️  Pengaturan Global & Data Lokal (email.txt)"
    echo -e "  \e[1;37m[3]\e[0m 🤖 Jalankan Bot Manual (login.py)"
    echo -e "  \e[1;31m[0]\e[0m ❌ Keluar Menu (Sistem tetap jalan di background)"
    echo -e "\n\e[1;36m=================================================\e[0m"
    
    echo -en "\e[1;32mPilih Menu [0-3]: \e[0m"
    read pilihan

    case $pilihan in
        1)
            echo -e "\n\e[1;33m[!] Menjalankan Rantai Otomatisasi di Background...\e[0m"
            nohup python3 main.py --trigger-chain > /dev/null 2>&1 &
            echo -e "\e[1;32m[+] Berjalan di background. Cek sys_log.txt untuk memantau log-nya.\e[0m"
            echo -en "\nTekan ENTER untuk kembali..."
            read
            ;;
        2)
            # Masuk ke menu pengaturan Python
            python3 main.py --settings
            ;;
        3)
            echo -e "\n\e[1;33m[!] Menjalankan login.py di Virtual Display...\e[0m"
            RES=$(python3 main.py --run-bot "login.py")
            
            if [ "$RES" == "SUCCESS" ]; then
                echo -e "\e[1;32m[+] Bot login.py berhasil dijalankan di background!\e[0m"
            else
                echo -e "\e[1;31m[-] Gagal! Pastikan file login.py ada di folder ini.\e[0m"
            fi
            echo -en "\nTekan ENTER untuk kembali..."
            read
            ;;
        0)
            echo -e "\n\e[1;32mKeluar dari Menu...\e[0m"
            echo -e "\e[1;33m[ℹ️] GHOST-DOT MASTER (HTTP Server & Scheduler) tetap HIDUP di background!\e[0m\n"
            exit 0
            ;;
        *)
            echo -e "\e[1;31mPilihan tidak valid!\e[0m"
            sleep 1
            ;;
    esac
done
