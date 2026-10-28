#!/usr/bin/env python3
"""
RO3 CPanel - White-Label Administration Control Panel for Ragnarok Online 3 (RO3Emu)
Zero-dependency, standalone server with embedded static assets and RESTful management API.
"""

import sys
import os
import json
import sqlite3
import hashlib
import secrets
import time
import urllib.request
import urllib.error
import urllib.parse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from datetime import datetime, timezone

# --- Configuration Loading ---
CONFIG_FILE = os.environ.get("RO3_CONFIG_FILE", "config.json")

DEFAULT_CONFIG = {
    "server_title": "RO3 Control Panel",
    "server_subtitle": "Ragnarok Online 3 Server Management",
    "logo_text": "RO3",
    "host": "0.0.0.0",
    "port": 8095,
    "ro3_db_path": os.environ.get("RO3_DB_PATH", os.path.join("..", "RO3Emu", "data", "ro3emu.db")),
    "ro3_status_url": os.environ.get("RO3_STATUS_URL", "http://127.0.0.1:5380/ro3emu/status"),
    "admin_users": [
        {
            "username": os.environ.get("ADMIN_USER", "admin"),
            "password": os.environ.get("ADMIN_PASSWORD", "ro3admin")
        }
    ],
    "session_ttl_hours": 24,
    "session_secret": secrets.token_hex(32)
}

def load_config():
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                config.update(user_conf)
                print(f"[Config] Loaded configuration from {CONFIG_FILE}")
        except Exception as e:
            print(f"[Config Warning] Failed reading {CONFIG_FILE}, using defaults: {e}", file=sys.stderr)
    else:
        # Check environment variables
        if os.environ.get("SERVER_TITLE"):
            config["server_title"] = os.environ["SERVER_TITLE"]
        if os.environ.get("PORT"):
            config["port"] = int(os.environ["PORT"])
        if os.environ.get("RO3_DB_PATH"):
            config["ro3_db_path"] = os.environ["RO3_DB_PATH"]
        if os.environ.get("RO3_STATUS_URL"):
            config["ro3_status_url"] = os.environ["RO3_STATUS_URL"]
    return config

CONFIG = load_config()
HOST = CONFIG.get("host", "0.0.0.0")
PORT = int(CONFIG.get("port", 8095))
DB_PATH = os.path.abspath(CONFIG.get("ro3_db_path", "ro3emu.db"))
RO3_STATUS_URL = CONFIG.get("ro3_status_url", "http://127.0.0.1:5380/ro3emu/status")
SESSION_TTL_SECONDS = int(CONFIG.get("session_ttl_hours", 24)) * 3600
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "public"))

# In-memory session store
ACTIVE_SESSIONS = {}

# RO Class & Map Dictionaries
CAREER_MAP = {
    1000: 'Novice',
    1100: 'Swordman',
    1200: 'Knight',
    1210: 'Crusader',
    1300: 'Lord Knight',
    1310: 'Paladin',
    1400: 'Rune Knight',
    1410: 'Royal Guard',
    2100: 'Magician',
    2200: 'Wizard',
    2210: 'Sage',
    2300: 'High Wizard',
    2400: 'Warlock',
    3100: 'Archer',
    3200: 'Hunter',
    3210: 'Bard',
    3211: 'Dancer',
    3300: 'Sniper',
    3400: 'Ranger',
    4100: 'Acolyte',
    4200: 'Priest',
    4210: 'Monk',
    4300: 'High Priest',
    4400: 'Archbishop',
    5100: 'Thief',
    5200: 'Assassin',
    5210: 'Rogue',
    5300: 'Assassin Cross',
    5400: 'Guillotine Cross',
    6100: 'Merchant',
    6200: 'Blacksmith',
    6300: 'Mastersmith',
    6400: 'Mechanic'
}

SCENE_MAP = {
    10100: 'Prontera',
    10101: 'Prontera North',
    10102: 'Prontera West',
    10103: 'Prontera East',
    10104: 'Prontera South',
    10200: 'Payon',
    10201: 'Payon Forest',
    10300: 'Geffen',
    10301: 'Geffen Dungeon',
    10400: 'Alberta',
    10401: 'Sunken Ship',
    10500: 'Morroc',
    10514: 'Morroc Field',
    10600: 'Izlude',
    10700: 'Al De Baran',
    10800: 'Lutie'
}

def get_db():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"RO3 database not found at '{DB_PATH}'. Please configure 'ro3_db_path'.")
    con = sqlite3.connect(DB_PATH, timeout=10.0)
    con.row_factory = sqlite3.Row
    return con

def init_tables():
    if not os.path.exists(DB_PATH):
        print(f"[Warning] Database '{DB_PATH}' does not exist yet. Tables will be initialized upon first connection.")
        return
    with get_db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS admin_account_meta (
                name TEXT PRIMARY KEY,
                is_banned INTEGER DEFAULT 0,
                ban_reason TEXT DEFAULT '',
                banned_at TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                updated_utc TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS admin_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_user TEXT NOT NULL,
                action TEXT NOT NULL,
                target TEXT DEFAULT '',
                details TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                created_utc TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        con.commit()

def log_audit(admin_user, action, target="", details="", ip_address=""):
    try:
        with get_db() as con:
            con.execute(
                "INSERT INTO admin_audit_log (admin_user, action, target, details, ip_address) VALUES (?, ?, ?, ?, ?)",
                (admin_user, action, target, details, ip_address)
            )
            con.commit()
    except Exception as e:
        print(f"[AuditLog Error] {e}", file=sys.stderr)

def hash_ro3_password(password_str, salt_bytes=None):
    if salt_bytes is None:
        salt_bytes = secrets.token_bytes(16)
    pw_bytes = password_str.encode('utf-8')
    pw_hash = hashlib.pbkdf2_hmac('sha256', pw_bytes, salt_bytes, 100000, 32)
    return pw_hash, salt_bytes

def verify_ro3_password(password_str, expected_hash, salt_bytes):
    pw_bytes = password_str.encode('utf-8')
    calc_hash = hashlib.pbkdf2_hmac('sha256', pw_bytes, salt_bytes, 100000, len(expected_hash))
    return secrets.compare_digest(calc_hash, expected_hash)

def parse_currency(curr_str):
    result = {"zeny": 0, "diamonds": 0, "raw": curr_str or ""}
    if not curr_str:
        return result
    try:
        parts = str(curr_str).split(",")
        for part in parts:
            if ":" in part:
                k, v = part.split(":", 1)
                k = k.strip()
                v = int(v.strip())
                if k == "2":
                    result["zeny"] = v
                elif k == "1":
                    result["diamonds"] = v
    except Exception:
        pass
    return result

def parse_stats(stats_str):
    result = {"str": 0, "agi": 0, "vit": 0, "int": 0, "dex": 0, "luk": 0}
    if not stats_str:
        return result
    try:
        parts = [int(p.strip()) for p in str(stats_str).split(",") if p.strip()]
        keys = ["str", "agi", "vit", "int", "dex", "luk"]
        for i in range(min(len(parts), len(keys))):
            result[keys[i]] = parts[i]
    except Exception:
        pass
    return result

def format_timestamp(ts):
    if not ts:
        return None
    try:
        ts_int = int(ts)
        if ts_int > 2000000000000:
            ts_int = ts_int // 1000
        dt = datetime.fromtimestamp(ts_int, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return str(ts)

def authenticate_admin(username, password):
    """
    Checks if username & password match any configured admin,
    OR verifies against ro3emu.db account if user is in admin list.
    """
    clean_user = username.strip().lower()
    admin_list = CONFIG.get("admin_users", [])

    for admin_entry in admin_list:
        entry_user = admin_entry.get("username", "").strip().lower()
        if clean_user == entry_user:
            # 1. Direct password check in config
            if "password" in admin_entry and admin_entry["password"]:
                if password == admin_entry["password"]:
                    return True, admin_entry.get("username", username)
            
            # 2. Check in database account table using PBKDF2
            try:
                with get_db() as con:
                    row = con.execute("SELECT name, password_hash, salt FROM account WHERE LOWER(name)=?", (clean_user,)).fetchone()
                    if row and verify_ro3_password(password, row["password_hash"], row["salt"]):
                        return True, row["name"]
            except Exception:
                pass

    return False, None

class CPanelRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Concise server log
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {self.command} {self.path} - {args[0]}")

    def send_json(self, status_code, data, extra_headers=None):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def serve_static_file(self, filename, content_type):
        path = os.path.join(STATIC_DIR, filename)
        if not os.path.exists(path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")
            return
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

    def read_json_body(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length == 0:
                return {}
            body_bytes = self.rfile.read(length)
            return json.loads(body_bytes.decode('utf-8'))
        except Exception:
            return None

    def get_session_token(self):
        cookie_header = self.headers.get('Cookie')
        if cookie_header:
            cookie = SimpleCookie()
            try:
                cookie.load(cookie_header)
                if 'ro3_admin_session' in cookie:
                    return cookie['ro3_admin_session'].value
            except Exception:
                pass
        
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:].strip()

        return None

    def check_auth(self):
        token = self.get_session_token()
        if not token or token not in ACTIVE_SESSIONS:
            return None
        session = ACTIVE_SESSIONS[token]
        if time.time() > session['expires_at']:
            del ACTIVE_SESSIONS[token]
            return None
        session['expires_at'] = time.time() + SESSION_TTL_SECONDS
        return session

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()

    def do_GET(self):
        url_parts = self.path.split('?')
        raw_path = url_parts[0].rstrip('/')
        query_str = url_parts[1] if len(url_parts) > 1 else ''
        params = urllib.parse.parse_qs(query_str)

        # 1. Static Files
        if raw_path in ['', '/admin', '/index.html', '/admin/index.html']:
            return self.serve_static_file('index.html', 'text/html; charset=utf-8')
        if raw_path in ['/admin.css', '/admin/admin.css']:
            return self.serve_static_file('admin.css', 'text/css; charset=utf-8')
        if raw_path in ['/admin.js', '/admin/admin.js']:
            return self.serve_static_file('admin.js', 'application/javascript; charset=utf-8')
        if raw_path in ['/favicon.svg', '/assets/favicon.svg', '/admin/favicon.svg']:
            return self.serve_static_file('favicon.svg', 'image/svg+xml')

        # 2. Public Config API (Branding)
        if raw_path == '/api/admin/config':
            return self.send_json(200, {
                "server_title": CONFIG.get("server_title", "RO3 Control Panel"),
                "server_subtitle": CONFIG.get("server_subtitle", "Ragnarok Online 3 Management"),
                "logo_text": CONFIG.get("logo_text", "RO3")
            })

        # 3. Session Verification
        if raw_path == '/api/admin/session':
            session = self.check_auth()
            if session:
                return self.send_json(200, {
                    "authenticated": True,
                    "user": session['user'],
                    "role": "admin"
                })
            else:
                return self.send_json(200, {"authenticated": False})

        # Protected Endpoints
        session = self.check_auth()
        if not session:
            return self.send_json(401, {"error": "No autorizado. Inicie sesión como administrador."})

        # 4. Stats
        if raw_path == '/api/admin/stats':
            return self.handle_stats()

        # 5. Accounts List
        if raw_path == '/api/admin/accounts':
            return self.handle_accounts_list(params)

        # 6. Account Detail: /api/admin/accounts/<name>
        if raw_path.startswith('/api/admin/accounts/'):
            acc_name = raw_path[len('/api/admin/accounts/'):].strip()
            return self.handle_account_detail(acc_name)

        # 7. Audit Log
        if raw_path == '/api/admin/audit-log':
            return self.handle_audit_log(params)

        self.send_json(404, {"error": "Endpoint no encontrado"})

    def do_POST(self):
        raw_path = self.path.split('?')[0].rstrip('/')
        client_ip = self.headers.get('X-Real-IP') or self.headers.get('X-Forwarded-For') or self.client_address[0]

        # 1. Login (Public)
        if raw_path == '/api/admin/login':
            return self.handle_login(client_ip)

        # 2. Logout
        if raw_path == '/api/admin/logout':
            token = self.get_session_token()
            if token and token in ACTIVE_SESSIONS:
                del ACTIVE_SESSIONS[token]
            extra_headers = {
                'Set-Cookie': 'ro3_admin_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
            }
            return self.send_json(200, {"success": True, "message": "Sesión cerrada correctamente"}, extra_headers)

        # Protected Actions
        session = self.check_auth()
        if not session:
            return self.send_json(401, {"error": "No autorizado. Inicie sesión como administrador."})

        if raw_path == '/api/admin/accounts/create':
            return self.handle_create_account(session['user'], client_ip)
        if raw_path == '/api/admin/accounts/update-password':
            return self.handle_update_password(session['user'], client_ip)
        if raw_path == '/api/admin/accounts/ban':
            return self.handle_ban_account(session['user'], client_ip)
        if raw_path == '/api/admin/accounts/unban':
            return self.handle_unban_account(session['user'], client_ip)
        if raw_path == '/api/admin/accounts/delete':
            return self.handle_delete_account(session['user'], client_ip)
        if raw_path == '/api/admin/accounts/save-notes':
            return self.handle_save_notes(session['user'], client_ip)

        self.send_json(404, {"error": "Endpoint no encontrado"})

    # --- Handlers ---

    def handle_login(self, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": "Cuerpo de solicitud inválido"})

        username = (body.get("username") or body.get("identity") or "").strip()
        password = body.get("password") or body.get("credential") or ""

        if not username or not password:
            return self.send_json(400, {"error": "Debe ingresar usuario y contraseña"})

        valid, resolved_user = authenticate_admin(username, password)
        if not valid:
            log_audit("system", "login_failed", username, "Credenciales inválidas", client_ip)
            return self.send_json(401, {"error": "Acceso denegado: credenciales de administrador inválidas."})

        token = secrets.token_urlsafe(32)
        ACTIVE_SESSIONS[token] = {
            "user": resolved_user,
            "created_at": time.time(),
            "expires_at": time.time() + SESSION_TTL_SECONDS,
            "ip": client_ip
        }

        log_audit(resolved_user, "login_success", resolved_user, "Inicio de sesión administrativo", client_ip)

        extra_headers = {
            'Set-Cookie': f'ro3_admin_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL_SECONDS}'
        }
        return self.send_json(200, {
            "success": True,
            "user": resolved_user,
            "role": "admin",
            "token": token
        }, extra_headers)

    def handle_stats(self):
        server_online = False
        online_players = 0
        try:
            req = urllib.request.Request(RO3_STATUS_URL, headers={'User-Agent': 'RO3AdminCPanel'})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                server_online = bool(data.get("online"))
                online_players = int(data.get("players", 0))
        except Exception:
            server_online = False
            online_players = 0

        with get_db() as con:
            total_accounts = con.execute("SELECT COUNT(*) FROM account").fetchone()[0]
            total_roles = con.execute("SELECT COUNT(*) FROM role WHERE deleted_time = 0").fetchone()[0]
            banned_accounts = con.execute("SELECT COUNT(*) FROM admin_account_meta WHERE is_banned = 1").fetchone()[0]
            
            db_size_mb = 0
            if os.path.exists(DB_PATH):
                db_size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)

            backups_dir = os.path.join(os.path.dirname(DB_PATH), "backups")
            backups_count = 0
            last_backup_time = None
            if os.path.isdir(backups_dir):
                files = [os.path.join(backups_dir, f) for f in os.listdir(backups_dir) if f.endswith('.db')]
                backups_count = len(files)
                if files:
                    files.sort(key=os.path.getmtime, reverse=True)
                    last_backup_time = datetime.fromtimestamp(os.path.getmtime(files[0]), tz=timezone.utc).isoformat()

        return self.send_json(200, {
            "server": {
                "online": server_online,
                "players_online": online_players,
                "status_label": "En línea" if server_online else "Sin conexión",
                "db_size_mb": db_size_mb,
                "backups_count": backups_count,
                "last_backup": last_backup_time
            },
            "counts": {
                "accounts": total_accounts,
                "characters": total_roles,
                "banned": banned_accounts
            }
        })

    def handle_accounts_list(self, params):
        q = params.get('q', [''])[0].strip().lower()
        status_filter = params.get('status', ['all'])[0].strip().lower()
        sort_by = params.get('sort', ['created_desc'])[0].strip()

        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]

        with get_db() as con:
            accounts_query = """
                SELECT a.name, a.created_utc,
                       COALESCE(m.is_banned, 0) as is_banned,
                       COALESCE(m.ban_reason, '') as ban_reason,
                       COALESCE(m.banned_at, '') as banned_at,
                       COALESCE(m.notes, '') as notes
                FROM account a
                LEFT JOIN admin_account_meta m ON a.name = m.name
            """
            accounts = [dict(r) for r in con.execute(accounts_query).fetchall()]

            roles_query = """
                SELECT id, account, name, sex, career, level, job_level,
                       last_login_time, create_time, currency, stats,
                       scene_entry, pos_x, pos_y, pos_z, deleted_time
                FROM role
                WHERE deleted_time = 0
            """
            roles = [dict(r) for r in con.execute(roles_query).fetchall()]

            roles_by_acc = {}
            for r in roles:
                acc = r["account"]
                if acc not in roles_by_acc:
                    roles_by_acc[acc] = []
                
                career_id = r.get("career") or 1000
                career_name = CAREER_MAP.get(career_id, f"Clase {career_id}")
                scene_id = r.get("scene_entry") or 0
                scene_name = SCENE_MAP.get(scene_id, f"Mapa {scene_id}")

                roles_by_acc[acc].append({
                    "id": r["id"],
                    "name": r["name"],
                    "sex": "M" if r.get("sex") == 1 else "F",
                    "career": career_id,
                    "career_name": career_name,
                    "level": r.get("level", 1),
                    "job_level": r.get("job_level", 1),
                    "currency": parse_currency(r.get("currency")),
                    "stats": parse_stats(r.get("stats")),
                    "scene_id": scene_id,
                    "scene_name": scene_name,
                    "pos": {
                        "x": round(r.get("pos_x") or 0, 1),
                        "y": round(r.get("pos_y") or 0, 1),
                        "z": round(r.get("pos_z") or 0, 1)
                    },
                    "last_login": format_timestamp(r.get("last_login_time")),
                    "created_at": format_timestamp(r.get("create_time"))
                })

            tokens_counts = {}
            for t in con.execute("SELECT account, COUNT(*) as cnt FROM auth_token GROUP BY account"):
                tokens_counts[t["account"]] = t["cnt"]

            result = []
            for a in accounts:
                name = a["name"]
                acc_roles = roles_by_acc.get(name, [])
                a["characters"] = acc_roles
                a["character_count"] = len(acc_roles)
                a["active_tokens"] = tokens_counts.get(name, 0)
                a["is_admin"] = (name.lower() in admin_usernames)
                a["is_banned"] = bool(a["is_banned"])

                latest_login = None
                for cr in acc_roles:
                    if cr["last_login"]:
                        if latest_login is None or cr["last_login"] > latest_login:
                            latest_login = cr["last_login"]
                a["last_login"] = latest_login

                if status_filter == 'banned' and not a["is_banned"]:
                    continue
                if status_filter == 'active' and a["is_banned"]:
                    continue

                if q:
                    match_acc = (q in name.lower())
                    match_char = any(q in c["name"].lower() for c in acc_roles)
                    if not (match_acc or match_char):
                        continue

                result.append(a)

            if sort_by == 'name_asc':
                result.sort(key=lambda x: x["name"].lower())
            elif sort_by == 'created_asc':
                result.sort(key=lambda x: x.get("created_utc") or "")
            elif sort_by == 'chars_desc':
                result.sort(key=lambda x: x["character_count"], reverse=True)
            else:
                result.sort(key=lambda x: x.get("created_utc") or "", reverse=True)

            return self.send_json(200, {
                "accounts": result,
                "total": len(result)
            })

    def handle_account_detail(self, account_name):
        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]
        with get_db() as con:
            acc = con.execute("SELECT name, created_utc FROM account WHERE name=?", (account_name,)).fetchone()
            if not acc:
                return self.send_json(404, {"error": "Cuenta no encontrada"})

            meta = con.execute("SELECT is_banned, ban_reason, banned_at, notes FROM admin_account_meta WHERE name=?", (account_name,)).fetchone()
            tokens = [dict(t) for t in con.execute("SELECT token, kind, expires_utc FROM auth_token WHERE account=?", (account_name,)).fetchall()]
            roles = [dict(r) for r in con.execute("SELECT * FROM role WHERE account=? AND deleted_time=0", (account_name,)).fetchall()]

            formatted_roles = []
            for r in roles:
                career_id = r.get("career") or 1000
                scene_id = r.get("scene_entry") or 0
                formatted_roles.append({
                    "id": r["id"],
                    "name": r["name"],
                    "sex": "M" if r.get("sex") == 1 else "F",
                    "career": career_id,
                    "career_name": CAREER_MAP.get(career_id, f"Clase {career_id}"),
                    "level": r.get("level", 1),
                    "job_level": r.get("job_level", 1),
                    "exp": r.get("exp", 0),
                    "job_exp": r.get("job_exp", 0),
                    "currency": parse_currency(r.get("currency")),
                    "stats": parse_stats(r.get("stats")),
                    "bonus_points": r.get("bonus_points", 0),
                    "scene_id": scene_id,
                    "scene_name": SCENE_MAP.get(scene_id, f"Mapa {scene_id}"),
                    "pos": {
                        "x": round(r.get("pos_x") or 0, 1),
                        "y": round(r.get("pos_y") or 0, 1),
                        "z": round(r.get("pos_z") or 0, 1)
                    },
                    "last_login": format_timestamp(r.get("last_login_time")),
                    "created_at": format_timestamp(r.get("create_time"))
                })

            data = {
                "name": acc["name"],
                "created_utc": acc["created_utc"],
                "is_banned": bool(meta["is_banned"]) if meta else False,
                "ban_reason": meta["ban_reason"] if meta else "",
                "banned_at": meta["banned_at"] if meta else "",
                "notes": meta["notes"] if meta else "",
                "tokens_count": len(tokens),
                "is_admin": (acc["name"].lower() in admin_usernames),
                "characters": formatted_roles
            }
            return self.send_json(200, data)

    def handle_create_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": "Cuerpo de solicitud inválido"})

        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()
        notes = (body.get("notes") or "").strip()

        if not username or len(username) < 3 or len(username) > 32:
            return self.send_json(400, {"error": "El nombre de usuario debe tener entre 3 y 32 caracteres"})

        if not password or len(password) < 6:
            return self.send_json(400, {"error": "La contraseña debe tener al menos 6 caracteres"})

        with get_db() as con:
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if existing:
                return self.send_json(400, {"error": f"La cuenta '{username}' ya existe"})

            pw_hash, salt = hash_ro3_password(password)
            now_iso = datetime.now(timezone.utc).isoformat() + "Z"

            con.execute(
                "INSERT INTO account (name, password_hash, salt, created_utc) VALUES (?, ?, ?, ?)",
                (username, pw_hash, salt, now_iso)
            )

            if notes:
                con.execute(
                    "INSERT INTO admin_account_meta (name, notes, updated_utc) VALUES (?, ?, CURRENT_TIMESTAMP) ON CONFLICT(name) DO UPDATE SET notes=excluded.notes",
                    (username, notes)
                )

            con.commit()

        log_audit(admin_user, "create_account", username, "Cuenta creada por admin", client_ip)
        return self.send_json(200, {
            "success": True,
            "message": f"Cuenta '{username}' creada exitosamente."
        })

    def handle_update_password(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": "Cuerpo de solicitud inválido"})

        username = (body.get("username") or "").strip()
        new_password = (body.get("new_password") or "").strip()

        if not username:
            return self.send_json(400, {"error": "Usuario requerido"})

        if not new_password or len(new_password) < 6:
            return self.send_json(400, {"error": "La nueva contraseña debe tener al menos 6 caracteres"})

        with get_db() as con:
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if not existing:
                return self.send_json(404, {"error": f"La cuenta '{username}' no existe"})

            pw_hash, salt = hash_ro3_password(new_password)
            con.execute("UPDATE account SET password_hash=?, salt=? WHERE name=?", (pw_hash, salt, username))
            con.execute("DELETE FROM auth_token WHERE account=?", (username,))
            con.commit()

        log_audit(admin_user, "update_password", username, "Contraseña modificada por admin", client_ip)
        return self.send_json(200, {
            "success": True,
            "message": f"Contraseña de '{username}' actualizada exitosamente. Sesiones revocadas."
        })

    def handle_ban_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": "Cuerpo de solicitud inválido"})

        username = (body.get("username") or "").strip()
        reason = (body.get("reason") or "Violación de normas / Acción de administrador").strip()

        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]
        if username.lower() in admin_usernames:
            return self.send_json(400, {"error": "No se puede suspender una cuenta con rol de administrador."})

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        with get_db() as con:
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if not existing:
                return self.send_json(404, {"error": f"La cuenta '{username}' no existe"})

            con.execute("""
                INSERT INTO admin_account_meta (name, is_banned, ban_reason, banned_at, updated_utc)
                VALUES (?, 1, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET is_banned=1, ban_reason=excluded.ban_reason, banned_at=excluded.banned_at, updated_utc=CURRENT_TIMESTAMP
            """, (username, reason, now_str))

            con.execute("DELETE FROM auth_token WHERE account=?", (username,))
            con.commit()

        log_audit(admin_user, "ban_account", username, f"Motivo: {reason}", client_ip)
        return self.send_json(200, {
            "success": True,
            "enforced": False,
            "message": (
                f"Cuenta '{username}' marcada como suspendida en el panel y sus sesiones activas fueron revocadas. "
                "RO3Emu no consulta esta suspensión al iniciar sesión: el jugador puede volver a entrar."
            )
        })

    def handle_unban_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": "Cuerpo de solicitud inválido"})

        username = (body.get("username") or "").strip()
        if not username:
            return self.send_json(400, {"error": "Usuario requerido"})

        with get_db() as con:
            con.execute("""
                UPDATE admin_account_meta
                SET is_banned = 0, ban_reason = '', updated_utc = CURRENT_TIMESTAMP
                WHERE name = ?
            """, (username,))
            con.commit()

        log_audit(admin_user, "unban_account", username, "Suspensión levantada por admin", client_ip)
        return self.send_json(200, {
            "success": True,
            "message": f"Suspensión de la cuenta '{username}' removida exitosamente."
        })

    def handle_delete_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": "Cuerpo de solicitud inválido"})

        username = (body.get("username") or "").strip()
        if not username:
            return self.send_json(400, {"error": "Usuario requerido"})

        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]
        if username.lower() in admin_usernames:
            return self.send_json(400, {"error": "No se puede eliminar una cuenta de administrador."})

        with get_db() as con:
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if not existing:
                return self.send_json(404, {"error": f"La cuenta '{username}' no existe"})

            con.execute("DELETE FROM account WHERE name=?", (username,))
            con.execute("DELETE FROM auth_token WHERE account=?", (username,))
            con.execute("DELETE FROM admin_account_meta WHERE name=?", (username,))
            con.execute("UPDATE role SET deleted_time=? WHERE account=?", (int(time.time()), username))
            con.commit()

        log_audit(admin_user, "delete_account", username, "Cuenta eliminada por admin", client_ip)
        return self.send_json(200, {
            "success": True,
            "message": f"Cuenta '{username}' y sus datos fueron eliminados exitosamente."
        })

    def handle_save_notes(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": "Cuerpo de solicitud inválido"})

        username = (body.get("username") or "").strip()
        notes = (body.get("notes") or "").strip()

        with get_db() as con:
            con.execute("""
                INSERT INTO admin_account_meta (name, notes, updated_utc)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET notes=excluded.notes, updated_utc=CURRENT_TIMESTAMP
            """, (username, notes))
            con.commit()

        return self.send_json(200, {
            "success": True,
            "message": "Notas guardadas correctamente."
        })

    def handle_audit_log(self, params):
        limit = min(int(params.get('limit', [50])[0]), 100)
        with get_db() as con:
            rows = con.execute(
                "SELECT id, admin_user, action, target, details, ip_address, created_utc FROM admin_audit_log ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            logs = [dict(r) for r in rows]
        return self.send_json(200, {"logs": logs})

def main():
    print("=" * 60)
    print(f" {CONFIG.get('server_title', 'RO3 CPanel')} - White-Label Administration")
    print("=" * 60)
    print(f" Database: {DB_PATH}")
    print(f" Status Endpoint: {RO3_STATUS_URL}")
    print(f" Static Assets: {STATIC_DIR}")
    
    init_tables()
    server_address = (HOST, PORT)
    httpd = ThreadingHTTPServer(server_address, CPanelRequestHandler)
    print(f" CPanel running on http://{HOST if HOST != '0.0.0.0' else '127.0.0.1'}:{PORT}")
    print(" Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CPanel server...")
        httpd.server_close()

if __name__ == "__main__":
    main()
