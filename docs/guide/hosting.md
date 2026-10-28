# Hosting RO3 CPanel

RO3 CPanel is lightweight and has zero external package dependencies. It can be hosted on a Windows desktop or server, on a Linux VPS, inside Docker, or behind a reverse proxy (Nginx, Caddy, Cloudflare Tunnel).

## Native Execution

### Windows
1. Clone or extract `ro3-cpanel`.
2. Make sure Python 3.10+ is installed.
3. Edit `config.json` with the path to your `ro3emu.db`.
4. Run `run.cmd` or `python server.py`.

To run on startup on Windows, you can add `run.cmd` as a Windows Scheduled Task triggered at system boot.

### Linux (systemd)
Create a systemd unit `/etc/systemd/system/ro3-cpanel.service`:

```ini
[Unit]
Description=RO3 CPanel Administration Server
After=network.target

[Service]
Type=simple
User=ro3
WorkingDirectory=/opt/ro3-cpanel
ExecStart=/usr/bin/python3 /opt/ro3-cpanel/server.py
Restart=always
RestartSec=5
Environment=PORT=8095
Environment=RO3_DB_PATH=/opt/ro3emu/data/ro3emu.db

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ro3-cpanel
```

---

## Docker Deployment

Build and run with docker-compose:

```yaml
version: '3.8'
services:
  ro3-cpanel:
    image: ro3-cpanel:latest
    build: .
    restart: unless-stopped
    ports:
      - "8095:8095"
    volumes:
      - ./config.json:/app/config.json:ro
      - /path/to/RO3Emu/data:/data:rw
    environment:
      - RO3_DB_PATH=/data/ro3emu.db
      - RO3_STATUS_URL=http://host.docker.internal:5380/ro3emu/status
```

---

## Reverse Proxy Setup

### Nginx
```nginx
server {
    listen 80;
    server_name cpanel.yourserver.com;

    location / {
        proxy_pass http://127.0.0.1:8095;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_read_timeout 60s;
    }
}
```

### Cloudflare Tunnel (cloudflared)
In your `config.yml`:

```yaml
ingress:
  - hostname: cpanel.yourserver.com
    service: http://127.0.0.1:8095
  - service: http_status:404
```
