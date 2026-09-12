FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive

# 1. Install sistem dasar, openssh-server, tmux, xvfb, dan dependensi bot
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server tmux xvfb sudo htop curl wget jq unzip nano procps \
    python3-pip python3-venv python3-dev python3-tk xauth scrot \
    libxi6 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# 2. Konfigurasi SSH Server
# Tambahkan -p agar tidak error jika folder sudah ada
RUN mkdir -p /var/run/sshd

# Buat user 'dotaja' dan tambahkan ke grup sudo (JANGAN set password di sini)
RUN useradd -m -s /bin/bash dotaja \
    && usermod -aG sudo dotaja \
    && echo "dotaja ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dotaja \
    && chmod 0440 /etc/sudoers.d/dotaja

# Konfigurasi SSH: Matikan root login, izinkan password auth untuk user biasa
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config
RUN sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
# Hilangkan batasan PAM jika diperlukan agar login lancar
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

# 3. Install Google Chrome 109 & Colab CLI
RUN wget -q -O /tmp/chrome109.deb https://file.bahliljaya.tech/google-chrome-stable_109.0.5414.74-1_amd64.deb \
    && apt-get update && apt-get install -y /tmp/chrome109.deb || apt-get install -f -y \
    && apt-mark hold google-chrome-stable \
    && rm /tmp/chrome109.deb

RUN pip3 install --no-cache-dir google-colab-cli

# 4. Setup Direktori Kerja untuk User 'dotaja'
WORKDIR /home/dotaja/app

# Copy seluruh file project dari repo
COPY --chown=dotaja:dotaja . /home/dotaja/app

RUN chown -R dotaja:dotaja /home/dotaja/app

# Install Python packages yang dibutuhkan bot
RUN pip3 install --no-cache-dir flask psutil requests selenium pyautogui colorama Pillow pyvirtualdisplay mss schedule google-auth-oauthlib Werkzeug

# Berikan hak akses eksekusi ke menu.sh
RUN chmod +x menu.sh

# 5. OTOMATIS BUKA MENU: Masukkan eksekusi menu.sh ke .bashrc user dotaja
RUN echo 'if [ -n "$SSH_CONNECTION" ] && [ -z "$TMUX" ]; then cd /home/dotaja/app && ./menu.sh && exit; fi' >> /home/dotaja/.bashrc

# Buka port SSH
EXPOSE 22

# 6. Setup Entrypoint (Script yang akan dijalankan saat container nyala)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Jalankan entrypoint sebagai proses utama
ENTRYPOINT ["/entrypoint.sh"]
