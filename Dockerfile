FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# 1. Install sistem dasar dan utilitas standar
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server tmux sudo htop curl wget jq unzip nano procps ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Konfigurasi SSH Server & User
RUN mkdir -p /var/run/sshd

RUN useradd -m -s /bin/bash dotaja \
    && usermod -aG sudo dotaja \
    && echo "dotaja ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/dotaja \
    && chmod 0440 /etc/sudoers.d/dotaja

RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd

WORKDIR /home/dotaja

EXPOSE 22

# Jika tetap menggunakan entrypoint.sh untuk set password SSH saat start:
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
