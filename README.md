# RO3 CPanel (White-Label Admin Panel)

[![License: MIT](https://img.shields.io/badge/License-MIT-gold.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-success.svg)]()

Modern, lightweight, and customizable white-label control panel (CPanel) for **Ragnarok Online 3 / Ragnarok Origin PC (`RO3Emu`)**.

Built with a dark fantasy Ragnarok theme inspired by classic RO control panels (FluxCP / CeresCP), featuring a zero-dependency Python 3 backend and a responsive vanilla JavaScript SPA.

> 📖 **Para leer la documentación en español, consulta [README.es.md](README.es.md).**

---

## ✨ Features

- **White-Label & Customizable:** Easily brand your panel by setting custom server titles, logos, subtitles, and ports in `config.json` or `.env`.
- **Zero External Dependencies:** Runs on standard Python 3 (`http.server`, `sqlite3`, `hashlib`, `secrets`) without requiring `pip install` or node modules.
- **Embedded SPA Frontend:** Self-hosts all static HTML/CSS/JS assets directly from the executable/script or proxies seamlessly behind Nginx / Cloudflare.
- **Ragnarok Dark Theme:** Sleek Nordic aesthetic with gold rune accents, job badges with custom colors, and real-time status pills.
- **Comprehensive Account Management:**
  - **Live Search & Filters:** Instant search by account name or character name, status filters (All, Active, Banned), and sorting.
  - **Player & Character Cards:** Base Lv, Job Lv, Career/Class name (`Novice`, `Swordman`, `Knight`, `Wizard`, etc.), Zeny, Diamonds, STR/AGI/VIT/INT/DEX/LUK, map coordinates, and last login.
  - **Password Management:** Compatible with RO3Emu's PBKDF2-SHA256 (100,000 iterations + 16-byte random salt). Updates revoke existing session tokens.
  - **Account Creation:** Register new player accounts directly from the panel.
  - **Ban / Suspend & Unban:** Ban accounts with custom reasons and immediate session revocation.
  - **Account Deletion:** Double-confirmation modal with safety protections for administrator accounts.
  - **GM Notes:** Private administrator notes per account.
- **Live Server Metrics:** Real-time ping to RO3Emu status endpoint for online players, database size, and automated backup counts.
- **Audit Logging:** Built-in immutable audit trail recording all administrative actions.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+ installed.
- Access to your RO3Emu SQLite database (`ro3emu.db`).

### 2. Configuration
Copy `config.example.json` to `config.json`:

```bash
cp config.example.json config.json
```

Edit `config.json` to configure your server name and administrator credentials:

```json
{
  "server_title": "MyRO3 Server Control Panel",
  "server_subtitle": "Ragnarok Online 3 Server Management",
  "logo_text": "RO3",
  "host": "0.0.0.0",
  "port": 8095,
  "ro3_db_path": "path/to/ro3emu.db",
  "ro3_status_url": "http://127.0.0.1:5380/ro3emu/status",
  "admin_users": [
    {
      "username": "admin",
      "password": "YourSuperSecretPassword!"
    }
  ]
}
```

### 3. Run

**Windows:**
```cmd
run.cmd
```
or
```cmd
python server.py
```

**Linux / macOS:**
```bash
chmod +x run.sh
./run.sh
```

**Docker:**
```bash
docker compose up -d
```

Open your browser at `http://localhost:8095` (or `/admin/` if reverse-proxied).

---

## 🌐 Nginx Reverse Proxy Example

To host under a domain or path (e.g., `https://yourserver.com/admin/`):

```nginx
# Admin Control Panel App
location /admin/ {
    proxy_pass http://127.0.0.1:8095/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
}

# Admin API
location /api/admin/ {
    proxy_pass http://127.0.0.1:8095/api/admin/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_read_timeout 60s;
}
```

---

## 🔒 Security Architecture

1. **Authentication:** Only users specified in `admin_users` (or RO3 accounts matching admin usernames with valid passwords) can log in.
2. **Session Security:** Cryptographically secure session tokens stored in `HttpOnly`, `SameSite=Lax` cookies with configurable expiration.
3. **Database Concurrency:** Fully compatible with SQLite `WAL` mode used by RO3Emu.
4. **Audit Trail:** In-database table `admin_audit_log` records every password change, ban, creation, or deletion with timestamp and admin username.

---

## 📜 License

Released under the [MIT License](LICENSE).
