FROM python:3.10-slim

# Install system dependencies (tmux + curl & ca-certificates untuk uv)
# Sekaligus download dan install Cloudflare Tunnel (cloudflared)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tmux curl ca-certificates && \
    curl -L 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64' -o /usr/local/bin/cloudflared && \
    chmod +x /usr/local/bin/cloudflared && \
    rm -rf /var/lib/apt/lists/*

# Hugging Face Spaces / Railway mewajibkan user ID 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Install uv dan google-colab-cli
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
RUN uv tool install google-colab-cli

WORKDIR $HOME/app

COPY --chown=user . $HOME/app

# Install dependency Python
RUN pip install --no-cache-dir Flask google-auth-oauthlib Werkzeug

EXPOSE 7860

# CMD menjalankan 3 hal:
# 1. Menulis Google Secret
# 2. Menjalankan Flask (app.py) di background (&)
# 3. Menjalankan Cloudflare Tunnel di foreground menggunakan token
CMD sh -c 'if [ -n "$GOOGLE_CLIENT_SECRET" ]; then echo "$GOOGLE_CLIENT_SECRET" > client_secret.json; fi && \
    python app.py & \
    cloudflared tunnel --no-autoupdate run --token $CF_TUNNEL_TOKEN'
