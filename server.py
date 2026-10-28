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
from contextlib import contextmanager
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
    10800: 'Lutie',
    # Story/tutorial dungeon scenes (DungeonConfig scene entries), ids and names as listed in
    # aethai/ro3emu-server docs/systems/dungeon-inventory.md. Entries named "Unknown Area",
    # placeholder names ("@{1}") and test scenes are left out.
    1000101: 'Job Advance Scene',
    1010101: 'Izlude',
    1011301: 'Prontera North Gate',
    1020051: 'Payon',
    1021301: 'Southern Payon',
    1021851: 'Eastern Payon',
    1022001: 'Payon Forest',
    1023001: 'Payon Instance',
    1030051: 'Geffen',
    1032101: 'Goblin Forest',
    1033051: 'Geffen East Gate',
    1033052: 'Geffen East Gate',
    1051001: 'Desert Crossroad',
    1051051: 'Desert Crossroad',
    1054001: 'Ant Hell',
    3120402: 'Culvert',
    3120702: 'Pharaoh',
    3120703: 'Pharaoh',
    3120802: 'Moonlight Flower',
    3120902: 'Baphomet',
    5000101: 'MVP Role-Playing Party',
    8100001: 'Boss Challenge',
    8100002: 'Boss Challenge',
    8100003: 'Boss Challenge',
    8100004: 'Boss Challenge',
    8100005: 'Boss Challenge',
    8100006: 'Boss Challenge',
    8100007: 'Boss Challenge'
}


def _as_int(value):
    """Return value as an int id, or None when it is not an integer id."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def career_name(career_id):
    """Display name for a career (class) id; unknown ids render as "Clase <id>"."""
    name = CAREER_MAP.get(_as_int(career_id))
    return name if name is not None else f"Clase {career_id}"


def scene_name(scene_id):
    """Display name for a scene (map) id; unknown ids render as "Mapa <id>"."""
    name = SCENE_MAP.get(_as_int(scene_id))
    return name if name is not None else f"Mapa {scene_id}"


def _parse_names_section(section_name, section):
    """Keep only integer-id keys with non-empty string names; report what was skipped."""
    parsed = {}
    if section is None:
        return parsed
    if not isinstance(section, dict):
        print(f"[Config Warning] names_file: '{section_name}' must be an object, ignored", file=sys.stderr)
        return parsed
    skipped = 0
    for key, value in section.items():
        key_id = _as_int(key)
        if key_id is None or not isinstance(value, str) or not value.strip():
            skipped += 1
            continue
        parsed[key_id] = value.strip()
    if skipped:
        print(f"[Config Warning] names_file: skipped {skipped} invalid '{section_name}' entries "
              "(keys must be integer ids, names non-empty strings)", file=sys.stderr)
    return parsed


def load_names_file(path):
    """Read a names_file ({"careers": {...}, "scenes": {...}}). Returns (careers, scenes); never raises."""
    if path is None or not str(path).strip():
        return {}, {}
    path = str(path).strip()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"[Config Warning] names_file: cannot read '{path}', using built-in names: {e}", file=sys.stderr)
        return {}, {}
    if not isinstance(data, dict):
        print(f"[Config Warning] names_file: '{path}' must contain a JSON object, using built-in names", file=sys.stderr)
        return {}, {}
    return (_parse_names_section("careers", data.get("careers")),
            _parse_names_section("scenes", data.get("scenes")))


def apply_names_file(path):
    """Merge a names_file over CAREER_MAP / SCENE_MAP in place (overrides and extends the defaults)."""
    careers, scenes = load_names_file(path)
    CAREER_MAP.update(careers)
    SCENE_MAP.update(scenes)
    if careers or scenes:
        print(f"[Config] names_file: loaded {len(careers)} career and {len(scenes)} scene names from {path}")


apply_names_file(CONFIG.get("names_file"))

@contextmanager
def get_db():
    """Open the RO3Emu database: commit on success, roll back on error, always close.

    sqlite3's own context manager never closes the connection, and an open handle
    keeps the file locked on Windows.
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"RO3 database not found at '{DB_PATH}'. Please configure 'ro3_db_path'.")
    con = sqlite3.connect(DB_PATH, timeout=10.0)
    con.row_factory = sqlite3.Row
    try:
        with con:
            yield con
    finally:
        con.close()

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

# RO3Emu RoleStore: role.currency is "itemId:amount,..." where item 1 = Zeny.
ZENY_ITEM_ID = 1

RANKING_TYPES = ("level", "zeny", "power", "guilds")
RANKING_DEFAULT_LIMIT = 20
RANKING_MAX_LIMIT = 100


def currency_amount(curr_str, item_id):
    """Amount of one currency item in a role.currency string; malformed pairs are ignored."""
    if not curr_str:
        return 0
    for part in str(curr_str).split(","):
        key, sep, value = part.partition(":")
        if not sep:
            continue
        try:
            if int(key.strip()) == item_id:
                return int(value.strip())
        except ValueError:
            continue
    return 0


def parse_power_total(emblems_blob):
    """
    Leaderboard power of a role, mirroring RO3Emu PowerService: the role.emblems blob is the
    EmblemService.EmblemState JSON (default System.Text.Json, PascalCase) and the committed total is
    Power.CurrentNormal + Power.CurrentSeason. Returns None when the blob is missing, unparsable,
    or the power was never published.
    """
    if emblems_blob is None:
        return None
    try:
        if isinstance(emblems_blob, (bytes, bytearray, memoryview)):
            emblems_blob = bytes(emblems_blob).decode("utf-8")
        state = json.loads(emblems_blob)
        power = state.get("Power") if isinstance(state, dict) else None
        if not isinstance(power, dict):
            return None
        normal = power.get("CurrentNormal", 0)
        season = power.get("CurrentSeason", 0)
        if isinstance(normal, bool) or isinstance(season, bool):
            return None
        if not isinstance(normal, int) or not isinstance(season, int):
            return None
        return normal + season
    except (UnicodeDecodeError, ValueError, TypeError):
        return None


def parse_ranking_int(params, key, default, minimum, maximum=None):
    try:
        value = int(params.get(key, [default])[0])
    except (TypeError, ValueError):
        return default
    value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def career_label(career_id):
    return CAREER_MAP.get(career_id, f"Clase {career_id}")


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

ACCOUNTS_PAGE_SIZE_DEFAULT = 50
ACCOUNTS_PAGE_SIZE_MAX = 200

# ORDER BY clauses for the accounts list; a.name is the tie-breaker so pages are stable.
ACCOUNT_SORT_SQL = {
    'name_asc': "PY_LOWER(a.name) ASC, a.name ASC",
    'created_asc': "COALESCE(a.created_utc, '') ASC, a.name ASC",
    'chars_desc': "(SELECT COUNT(*) FROM role rc WHERE rc.account = a.name AND rc.deleted_time = 0) DESC, a.name ASC",
    'created_desc': "COALESCE(a.created_utc, '') DESC, a.name ASC",
}

def sql_py_lower(value):
    """SQLite LOWER() only folds ASCII; mirror Python str.lower() for search and sort."""
    return value.lower() if isinstance(value, str) else value

def parse_int_param(params, key, default, minimum, maximum=None):
    try:
        value = int(params.get(key, [default])[0])
    except (TypeError, ValueError):
        return default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value

def format_role(r, include_progress=False):
    """Formats a role row; include_progress adds exp/job_exp/bonus_points for the detail view."""
    career_id = r.get("career") or 1000
    scene_id = r.get("scene_entry") or 0
    data = {
        "id": r["id"],
        "name": r["name"],
        "sex": "M" if r.get("sex") == 1 else "F",
        "career": career_id,
        "career_name": career_name(career_id),
        "level": r.get("level", 1),
        "job_level": r.get("job_level", 1),
    }
    if include_progress:
        data["exp"] = r.get("exp", 0)
        data["job_exp"] = r.get("job_exp", 0)
    data["currency"] = parse_currency(r.get("currency"))
    data["stats"] = parse_stats(r.get("stats"))
    if include_progress:
        data["bonus_points"] = r.get("bonus_points", 0)
    data["scene_id"] = scene_id
    data["scene_name"] = scene_name(scene_id)
    data["pos"] = {
        "x": round(r.get("pos_x") or 0, 1),
        "y": round(r.get("pos_y") or 0, 1),
        "z": round(r.get("pos_z") or 0, 1)
    }
    data["last_login"] = format_timestamp(r.get("last_login_time"))
    data["created_at"] = format_timestamp(r.get("create_time"))
    return data

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

        # 8. Rankings (read-only)
        if raw_path == '/api/admin/rankings':
            return self.handle_rankings(params)

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
        page = parse_int_param(params, 'page', 1, minimum=1)
        page_size = parse_int_param(params, 'page_size', ACCOUNTS_PAGE_SIZE_DEFAULT,
                                    minimum=1, maximum=ACCOUNTS_PAGE_SIZE_MAX)

        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]

        where = []
        where_args = []
        if status_filter == 'banned':
            where.append("COALESCE(m.is_banned, 0) <> 0")
        elif status_filter == 'active':
            where.append("COALESCE(m.is_banned, 0) = 0")
        if q:
            # instr() is a literal substring test, so LIKE wildcards in q never apply.
            where.append("""(
                instr(PY_LOWER(a.name), ?) > 0
                OR EXISTS (
                    SELECT 1 FROM role r
                    WHERE r.account = a.name AND r.deleted_time = 0
                      AND instr(PY_LOWER(r.name), ?) > 0
                )
            )""")
            where_args.extend([q, q])
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        order_sql = ACCOUNT_SORT_SQL.get(sort_by, ACCOUNT_SORT_SQL['created_desc'])
        from_sql = "FROM account a LEFT JOIN admin_account_meta m ON a.name = m.name"

        with get_db() as con:
            con.create_function("PY_LOWER", 1, sql_py_lower)

            total = con.execute(f"SELECT COUNT(*) {from_sql} {where_sql}", where_args).fetchone()[0]
            pages = max(1, -(-total // page_size))
            offset = (page - 1) * page_size

            accounts = []
            if offset < total:
                accounts_query = f"""
                    SELECT a.name, a.created_utc,
                           COALESCE(m.is_banned, 0) as is_banned,
                           COALESCE(m.ban_reason, '') as ban_reason,
                           COALESCE(m.banned_at, '') as banned_at,
                           COALESCE(m.notes, '') as notes
                    {from_sql}
                    {where_sql}
                    ORDER BY {order_sql}
                    LIMIT ? OFFSET ?
                """
                accounts = [dict(r) for r in con.execute(accounts_query, where_args + [page_size, offset]).fetchall()]

            roles_by_acc = {}
            tokens_counts = {}
            page_names = [a["name"] for a in accounts]
            if page_names:
                placeholders = ",".join("?" * len(page_names))
                roles_query = f"""
                    SELECT id, account, name, sex, career, level, job_level,
                           last_login_time, create_time, currency, stats,
                           scene_entry, pos_x, pos_y, pos_z, deleted_time
                    FROM role
                    WHERE deleted_time = 0 AND account IN ({placeholders})
                """
                for r in con.execute(roles_query, page_names):
                    r = dict(r)
                    roles_by_acc.setdefault(r["account"], []).append(format_role(r))

                tokens_query = f"""
                    SELECT account, COUNT(*) as cnt FROM auth_token
                    WHERE account IN ({placeholders}) GROUP BY account
                """
                for t in con.execute(tokens_query, page_names):
                    tokens_counts[t["account"]] = t["cnt"]

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

            return self.send_json(200, {
                "accounts": accounts,
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": pages
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

            formatted_roles = [format_role(r, include_progress=True) for r in roles]

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

    def handle_rankings(self, params):
        ranking_type = params.get('type', ['level'])[0].strip().lower() or 'level'
        if ranking_type not in RANKING_TYPES:
            return self.send_json(400, {
                "error": "Tipo de ranking inválido. Valores permitidos: " + ", ".join(RANKING_TYPES)
            })

        limit = parse_ranking_int(params, 'limit', RANKING_DEFAULT_LIMIT, 1, RANKING_MAX_LIMIT)
        page = parse_ranking_int(params, 'page', 1, 1)
        offset = (page - 1) * limit

        with get_db() as con:
            if ranking_type == 'level':
                rows, total = self.rank_by_level(con, limit, offset)
            elif ranking_type == 'zeny':
                rows, total = self.rank_by_metric(con, 'currency', lambda v: currency_amount(v, ZENY_ITEM_ID), limit, offset)
            elif ranking_type == 'power':
                rows, total = self.rank_by_metric(con, 'emblems', parse_power_total, limit, offset)
            else:
                try:
                    rows, total = self.rank_guilds(con, limit, offset)
                except sqlite3.OperationalError as e:
                    if "no such table" not in str(e).lower():
                        raise
                    return self.send_json(200, {
                        "type": ranking_type, "page": page, "limit": limit,
                        "total": 0, "available": False, "rankings": []
                    })

        for index, row in enumerate(rows):
            row["rank"] = offset + index + 1

        return self.send_json(200, {
            "type": ranking_type,
            "page": page,
            "limit": limit,
            "total": total,
            "available": True,
            "rankings": rows
        })

    @staticmethod
    def character_row(r, value):
        career_id = r["career"] or 1000
        return {
            "id": r["id"],
            "name": r["name"],
            "account": r["account"],
            "career": career_id,
            "career_name": career_label(career_id),
            "level": r["level"],
            "job_level": r["job_level"],
            "value": value
        }

    def rank_by_level(self, con, limit, offset):
        total = con.execute("SELECT COUNT(*) FROM role WHERE deleted_time = 0").fetchone()[0]
        rows = con.execute("""
            SELECT id, account, name, career, level, job_level
            FROM role
            WHERE deleted_time = 0
            ORDER BY level DESC, job_level DESC, exp DESC, id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        return [self.character_row(r, r["level"]) for r in rows], total

    def rank_by_metric(self, con, column, extract, limit, offset):
        # The metric lives inside a TEXT/BLOB column, so it is decoded in Python. Only the columns
        # needed for the row are loaded (one tuple per non-deleted character) to bound memory.
        query = (
            "SELECT id, account, name, career, level, job_level, " + column + " AS metric "
            "FROM role WHERE deleted_time = 0"
        )
        scored = []
        for r in con.execute(query):
            value = extract(r["metric"])
            if value is None:
                continue
            scored.append((value, r))
        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        page = scored[offset:offset + limit]
        return [self.character_row(r, value) for value, r in page], len(scored)

    def rank_guilds(self, con, limit, offset):
        total = con.execute("SELECT COUNT(*) FROM guild").fetchone()[0]
        rows = con.execute("""
            SELECT g.id, g.name,
                   COUNT(r.id) AS member_count,
                   COALESCE(SUM(r.level), 0) AS total_level
            FROM guild g
            LEFT JOIN guild_member gm ON gm.guild_id = g.id
            LEFT JOIN role r ON r.id = gm.role_id AND r.deleted_time = 0
            GROUP BY g.id, g.name
            ORDER BY member_count DESC, total_level DESC, g.id ASC
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()
        result = [{
            "id": r["id"],
            "name": r["name"],
            "member_count": r["member_count"],
            "total_level": r["total_level"],
            "value": r["member_count"]
        } for r in rows]
        return result, total

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
