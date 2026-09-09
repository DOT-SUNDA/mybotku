#!/bin/bash

# 1. Set password user 'dotaja' secara dinamis saat container nyala
# Mengambil password dari Environment Variable Railway. Jika kosong, pakai 'defaultpass'
echo "dotaja:${SSH_PASSWORD:-defaultpass}" | chpasswd

# 2. Pastikan folder sshd ada dan permissionnya benar
mkdir -p /var/run/sshd
chmod 755 /var/run/sshd

echo "Password berhasil di-set. Memulai SSH Daemon..."

# 3. Jalankan SSH Daemon di foreground (agar container tidak mati)
exec /usr/sbin/sshd -D
