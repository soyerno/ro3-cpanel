#!/usr/bin/env python3
"""
RO3 CPanel - White-Label Administration Control Panel for Ragnarok Online 3 (RO3Emu)
Zero-dependency, standalone server with embedded static assets and RESTful management API.
"""

import sys
import os
import ipaddress
import json
import re
import sqlite3
import hashlib
import hmac
import secrets
import threading
import time
import math
import socket
import http.client
import argparse
import getpass
import urllib.request
import urllib.error
import urllib.parse
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

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
    "session_secret": secrets.token_hex(32),
    # GM tools (POST /api/admin/gm): panel commands an admin may send through RO3Emu's loopback GM endpoint.
    "gm_allowed_commands": ["warp"],
    "gm_unstuck_scene": 10111,
    # Language of the panel when the browser has not chosen one: "en" (default) or "es".
    "default_language": "en"
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

# --- Language (English default, Spanish translation) ---
# User-facing messages are written in English and used as the translation key; ES_MESSAGES holds the
# Spanish text. The request handler sets the language for the current thread from the X-Panel-Lang header,
# falling back to config "default_language".
SUPPORTED_LANGUAGES = ("en", "es")
_LANGUAGE = threading.local()


def normalize_language(value):
    value = str(value or "").strip().lower()
    return value if value in SUPPORTED_LANGUAGES else "en"


def default_language():
    return normalize_language(CONFIG.get("default_language"))


def set_language(value):
    """Set the language for the current thread; None restores the configured default."""
    _LANGUAGE.value = None if value is None else normalize_language(value)


def current_language():
    return getattr(_LANGUAGE, "value", None) or default_language()


def tr(text, **params):
    """Translate an English message into the current language and fill its {placeholders}."""
    if current_language() == "es":
        text = ES_MESSAGES.get(text, text)
    return text.format(**params) if params else text


ES_MESSAGES = {
    # Labels
    "No bag": "Sin bolsa",
    "Items": "Objetos",
    "Equipment": "Equipo",
    "Cards": "Cartas",
    "Totems": "Tótems",
    "Emblems": "Emblemas",
    "Currencies": "Monedas",
    "Class special": "Especial de clase",
    "Character": "Personaje",
    "Guild": "Gremio",
    "System": "Sistema",
    "Escrow": "Custodia",
    "Recovery": "Recuperación",
    "Item": "Ítem",
    "Currency": "Moneda",
    "Guild resource": "Recurso de gremio",
    "Event resource": "Recurso de evento",
    "Asset": "Activo",
    "Type {kind}": "Tipo {kind}",
    "Class {id}": "Clase {id}",
    "Map {id}": "Mapa {id}",
    "Online": "En línea",
    "Offline": "Sin conexión",
    # Sign-in and generic API errors
    "Unauthorized. Sign in as an administrator.": "No autorizado. Inicie sesión como administrador.",
    "Endpoint not found": "Endpoint no encontrado",
    "Invalid request body": "Cuerpo de solicitud inválido",
    "Signed out successfully": "Sesión cerrada correctamente",
    "Enter a username and password": "Debe ingresar usuario y contraseña",
    "The username must not exceed 32 characters": "El usuario no debe superar los 32 caracteres",
    "The password must not exceed 128 characters": "La contraseña no debe superar los 128 caracteres",
    "Too many failed attempts. Try again in {seconds} seconds.":
        "Demasiados intentos fallidos. Intente nuevamente en {seconds} segundos.",
    "Too many failed attempts. Temporary ban active. Try again in {seconds} seconds.":
        "Demasiados intentos fallidos. Bloqueo temporal activo. Intente nuevamente en {seconds} segundos.",
    "Access denied: invalid administrator credentials.":
        "Acceso denegado: credenciales de administrador inválidas.",
    "Access denied: invalid administrator credentials. {remaining} attempt(s) remaining before temporary ban.":
        "Acceso denegado: credenciales de administrador inválidas. Quedan {remaining} intento(s) antes del bloqueo temporal.",
    "Access denied: invalid administrator credentials. Maximum attempts reached.":
        "Acceso denegado: credenciales de administrador inválidas. Límite de intentos alcanzado.",
    # Accounts, characters, guilds
    "Account not found": "Cuenta no encontrada",
    "Invalid character ID": "ID de personaje inválido",
    "Invalid character ID: it must be a positive integer": "ID de personaje inválido: debe ser un entero positivo",
    "Invalid request": "Solicitud inválida",
    "Type the exact character name to confirm the deletion.": "Escribí el nombre exacto del personaje para confirmar el borrado.",
    "A character of an administrator account cannot be deleted.": "No se puede eliminar un personaje de una cuenta de administrador.",
    "The account is online. Disconnect it in the game before deleting a character.": "La cuenta está en línea. Desconectala en el juego antes de eliminar un personaje.",
    "Could not verify that the account is offline, so nothing was deleted. Try again.": "No se pudo verificar que la cuenta esté desconectada, así que no se eliminó nada. Intentá de nuevo.",
    "Too many delete attempts. Try again in {seconds} seconds.": "Demasiados intentos de borrado. Intentá de nuevo en {seconds} segundos.",
    "The character changed while it was being deleted. Reload and try again.": "El personaje cambió mientras se eliminaba. Recargá e intentá de nuevo.",
    "Error deleting the character": "Error al eliminar el personaje",
    "Character '{name}' of account '{account}' was deleted.": "El personaje '{name}' de la cuenta '{account}' fue eliminado.",
    "Character not found": "Personaje no encontrado",
    "Error reading the character's inventory": "Error leyendo el inventario del personaje",
    "Guild not found": "Gremio no encontrado",
    "This character's mailbox could not be decoded.": "El buzón de este personaje no se pudo decodificar.",
    "The username must be between 3 and 32 characters":
        "El nombre de usuario debe tener entre 3 y 32 caracteres",
    "The password must be at least 6 characters": "La contraseña debe tener al menos 6 caracteres",
    "The new password must be at least 6 characters": "La nueva contraseña debe tener al menos 6 caracteres",
    "Username required": "Usuario requerido",
    "Account '{username}' already exists": "La cuenta '{username}' ya existe",
    "Account '{username}' does not exist": "La cuenta '{username}' no existe",
    "Account '{username}' is not suspended": "La cuenta '{username}' no está suspendida",
    "Account '{username}' created successfully.": "Cuenta '{username}' creada exitosamente.",
    "Password for '{username}' updated successfully. Sessions revoked.":
        "Contraseña de '{username}' actualizada exitosamente. Sesiones revocadas.",
    "An administrator account cannot be suspended.":
        "No se puede suspender una cuenta con rol de administrador.",
    "An administrator account cannot be deleted.": "No se puede eliminar una cuenta de administrador.",
    "Account '{username}' suspended and its active sessions were revoked. "
    "RO3Emu refuses its sign-in until the suspension is removed.":
        "Cuenta '{username}' suspendida y sus sesiones activas fueron revocadas. "
        "RO3Emu rechaza su inicio de sesión hasta que se quite la suspensión.",
    "Update RO3Emu: this server does not support account bans":
        "Actualice RO3Emu: este servidor no admite suspensiones de cuentas",
    "Suspension of account '{username}' removed successfully.":
        "Suspensión de la cuenta '{username}' removida exitosamente.",
    "Account '{username}' and its data were deleted successfully.":
        "Cuenta '{username}' y sus datos fueron eliminados exitosamente.",
    "Notes saved successfully.": "Notas guardadas correctamente.",
    "Invalid date. Use the format YYYY-MM-DD.": "Fecha inválida. Use el formato AAAA-MM-DD.",
    "Invalid ranking type. Allowed values: {values}": "Tipo de ranking inválido. Valores permitidos: {values}",
    # RO3Emu connection
    "The RO3Emu response exceeds the maximum allowed size.":
        "La respuesta de RO3Emu supera el tamaño máximo permitido.",
    "RO3Emu does not expose this endpoint to the panel: it only answers on loopback, "
    "so the panel must run on the same host as RO3Emu (or behind a local proxy).":
        "RO3Emu no expone este endpoint para el panel: solo responde por loopback, "
        "así que el panel debe correr en el mismo host que RO3Emu (o detrás de un proxy local).",
    "RO3Emu answered HTTP {code}.": "RO3Emu respondió HTTP {code}.",
    "RO3Emu did not answer in time.": "RO3Emu no respondió a tiempo.",
    "Could not connect to RO3Emu.": "No se pudo conectar con RO3Emu.",
    "The RO3Emu response is not valid JSON.": "La respuesta de RO3Emu no es JSON válido.",
    "The RO3Emu response has an unexpected format.": "La respuesta de RO3Emu tiene un formato inesperado.",
    "RO3Emu database unavailable.": "Base de datos de RO3Emu no disponible.",
    # GM tools
    "GM endpoint unavailable (the panel must run on the same host as RO3Emu).":
        "Endpoint GM no disponible (requiere que el panel corra en el mismo host que RO3Emu).",
    "The RO3Emu GM endpoint only accepts local connections: the panel must run on the same host "
    "as RO3Emu and 'ro3_base_url' (or 'ro3_status_url') must point to 127.0.0.1, ::1 or localhost.":
        "El endpoint GM de RO3Emu solo acepta conexiones locales: el panel debe correr en el mismo host "
        "que RO3Emu y 'ro3_base_url' (o 'ro3_status_url') debe apuntar a 127.0.0.1, ::1 o localhost.",
    "'ro3_base_url' (or 'ro3_status_url') must not include a username or password (user:pass@host).":
        "'ro3_base_url' (o 'ro3_status_url') no puede incluir usuario ni contraseña (usuario:clave@host).",
    "'{label}' must be an integer between {minimum} and {maximum}.":
        "'{label}' debe ser un número entero entre {minimum} y {maximum}.",
    "Invalid configuration: 'gm_unstuck_scene' must be a valid scene number.":
        "Configuración inválida: 'gm_unstuck_scene' debe ser un número de escena válido.",
    "GM command not supported by the panel.": "Comando GM no soportado por el panel.",
    "The command '{command}' is not enabled in 'gm_allowed_commands'.":
        "El comando '{command}' no está habilitado en 'gm_allowed_commands'.",
    "fieldexp requires 'action': set, clear or reset.":
        "fieldexp requiere 'action': set, clear o reset.",
    "fieldexp {action} takes no 'rules'.":
        "fieldexp {action} no admite 'rules'.",
    "fieldexp set requires 'rules': 1 to {max} rules.":
        "fieldexp set requiere 'rules': de 1 a {max} reglas.",
    "quest requires 'action': accept, finish, done, drop or repeat.":
        "quest requiere 'action': accept, finish, done, drop o repeat.",
    "quest requires 'id' (the quest number).":
        "quest requiere 'id' (el número de la misión).",
    "Command sent. RO3Emu's reply is shown below; it also appears in the player's in-game chat.":
        "Comando enviado. La respuesta de RO3Emu se muestra abajo; también aparece en el chat del jugador.",
    "Each rule needs exactly 'min', 'max' and 'percent'.":
        "Cada regla necesita exactamente 'min', 'max' y 'percent'.",
    "A rule's 'min' level cannot be above its 'max'.":
        "El nivel 'min' de una regla no puede ser mayor que su 'max'.",
    "Invalid account.": "Cuenta inválida.",
    "Invalid account: it contains characters that are not allowed.":
        "Cuenta inválida: contiene caracteres no permitidos.",
    "'args' must be a JSON object.": "'args' debe ser un objeto JSON.",
    "Arguments not allowed: {args}": "Argumentos no permitidos: {args}",
    "warp requires 'scene' (sceneEntry).": "warp requiere 'scene' (sceneEntry).",
    "warp requires 'x' and 'z' together, or neither.": "warp requiere 'x' y 'z' juntos, o ninguno de los dos.",
    "The account is not in the game (it has no connected character).":
        "La cuenta no está en el juego (no tiene un personaje conectado).",
    "RO3Emu is not accepting commands right now (the server is not in the Accepting phase).":
        "RO3Emu no acepta comandos en este momento (el servidor no está en fase Accepting).",
    "Unexpected RO3Emu response (HTTP {code}).": "Respuesta inesperada de RO3Emu (HTTP {code}).",
    # Stored audit-log details (see localize_audit_details)
    "Invalid credentials": "Credenciales inválidas",
    "Administrative sign-in": "Inicio de sesión administrativo",
    "Account created by admin": "Cuenta creada por admin",
    "Password changed by admin": "Contraseña modificada por admin",
    "Suspension lifted by admin": "Suspensión levantada por admin",
    "Account deleted by admin": "Cuenta eliminada por admin",
    "Rule violation / Admin action": "Violación de normas / Acción de administrador",
    "Gift code created": "Código de regalo creado",
    "Gift code disabled by admin": "Código de regalo desactivado por admin",
    "Gift code enabled by admin": "Código de regalo activado por admin",
    # Gift codes
    "Update RO3Emu: this server does not support gift codes":
        "Actualice RO3Emu: este servidor no admite códigos de regalo",
    "The code must be between 1 and 64 characters": "El código debe tener entre 1 y 64 caracteres",
    "Rewards must be a non-empty list of items with a positive item ID and count":
        "Las recompensas deben ser una lista no vacía de ítems con ID y cantidad positivos",
    "Max uses must be a whole number, 0 or more": "Los usos máximos deben ser un número entero, 0 o más",
    "Uses per account must be a whole number, 1 or more": "Los usos por cuenta deben ser un número entero, 1 o más",
    "Start and expiry must be unix timestamps in seconds":
        "El inicio y el vencimiento deben ser marcas de tiempo unix en segundos",
    "The expiry must be after the start": "El vencimiento debe ser posterior al inicio",
    "The note must be text of up to 500 characters": "La nota debe ser texto de hasta 500 caracteres",
    "The reason must be text of up to 500 characters": "El motivo debe ser texto de hasta 500 caracteres",
    "The duration must be a whole number of days from 1 to 3650":
        "La duración debe ser un número entero de días entre 1 y 3650",
    "Account '{username}' suspended until {until} and its active sessions were revoked. "
    "RO3Emu refuses its sign-in until then, or until the suspension is removed.":
        "Cuenta '{username}' suspendida hasta {until} y sus sesiones activas fueron revocadas. "
        "RO3Emu rechaza su inicio de sesión hasta entonces, o hasta que se quite la suspensión.",
    "The gift code '{code}' already exists": "El código de regalo '{code}' ya existe",
    "The gift code '{code}' does not exist": "El código de regalo '{code}' no existe",
    "Gift code required": "Código de regalo requerido",
    "The account vault is not available yet: the web player portal creates it the first time it runs":
        "La bóveda de la cuenta todavía no está disponible: el portal web de jugadores la crea la primera vez que se ejecuta",
    "The web market is not available yet: the web player portal creates it the first time it runs":
        "El mercado web todavía no está disponible: el portal web de jugadores lo crea la primera vez que se ejecuta",
    "Invalid market status. Allowed values: {values}": "Estado de mercado inválido. Valores permitidos: {values}",
    "Gift code '{code}' created successfully.": "Código de regalo '{code}' creado exitosamente.",
    "Gift code '{code}' disabled.": "Código de regalo '{code}' desactivado.",
    "Gift code '{code}' enabled.": "Código de regalo '{code}' activado.",
}


# Audit rows store English text (see log_audit calls); the audit view translates it on read.
# Rows written before the panel was bilingual stay as stored.
_AUDIT_DETAIL_PATTERNS = (
    (re.compile(r"^Reason: (.*)$", re.S), "Motivo: {0}"),
    (re.compile(r"^Retry in (\d+)s$"), "Reintentar en {0}s"),
    (re.compile(r"^(.*) -> sent \(done\)$", re.S), "{0} -> enviado (done)"),
    (re.compile(r"^(.*) -> failed: (.*)$", re.S), "{0} -> fallido: {1}"),
    (re.compile(r"^(.*) -> rejected: (.*)$", re.S), "{0} -> rechazado: {1}"),
)


def localize_audit_details(details):
    if current_language() != "es" or not isinstance(details, str) or not details:
        return details
    if details in ES_MESSAGES:
        return ES_MESSAGES[details]
    for pattern, template in _AUDIT_DETAIL_PATTERNS:
        match = pattern.match(details)
        if match:
            return template.format(*match.groups())
    return details

HOST = CONFIG.get("host", "0.0.0.0")
PORT = int(CONFIG.get("port", 8095))
DB_PATH = os.path.abspath(CONFIG.get("ro3_db_path", "ro3emu.db"))
RO3_STATUS_URL = CONFIG.get("ro3_status_url", "http://127.0.0.1:5380/ro3emu/status")
# RO3Emu diagnostics (/ro3emu/online, /ro3emu/metrics): same 2 s socket timeout as the status probe,
# plus a 2 s deadline while reading the body, and a cap on how much of the reply the panel reads.
RO3_HTTP_TIMEOUT = 2.0
RO3_MAX_RESPONSE_BYTES = 1024 * 1024
SESSION_TTL_SECONDS = int(CONFIG.get("session_ttl_hours", 24)) * 3600
# Minimum expiry gain before a DB-backed session is rewritten (limits writes to the game DB).
SESSION_SLIDE_MIN_SECONDS = 300
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "public"))

# Fallback session store, used only while the RO3Emu database file is missing or
# unusable. Sessions normally live in the `admin_session` table so they survive a
# restart. Keyed by the SHA-256 hash of the token, never by the raw token.
ACTIVE_SESSIONS = {}


class LoginThrottle:
    """
    Thread-safe sliding-window limiter for FAILED login attempts.

    Each key (e.g. "ip:1.2.3.4" or "user:admin") keeps the timestamps of its
    recent failures. A key is blocked while it holds `max_failures` or more
    failures inside the last `window_seconds`.
    """

    # Above this many tracked keys, expired keys are swept on every new failure.
    _SWEEP_THRESHOLD = 10000

    def __init__(self, max_failures=5, window_seconds=900, clock=time.monotonic):
        self.max_failures = max(1, int(max_failures))
        self.window_seconds = max(1, int(window_seconds))
        self._clock = clock
        self._failures = {}
        self._lock = threading.Lock()

    def _prune(self, key, now):
        timestamps = self._failures.get(key)
        if not timestamps:
            self._failures.pop(key, None)
            return []
        cutoff = now - self.window_seconds
        recent = [ts for ts in timestamps if ts > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            del self._failures[key]
        return recent

    def _retry_after_locked(self, keys, now):
        wait = 0.0
        for key in keys:
            recent = self._prune(key, now)
            if len(recent) >= self.max_failures:
                # Allowed again once enough failures leave the window.
                unblock_at = recent[-self.max_failures] + self.window_seconds
                wait = max(wait, unblock_at - now)
        return max(1, math.ceil(wait)) if wait > 0 else 0

    def _record_locked(self, keys, now):
        if len(self._failures) > self._SWEEP_THRESHOLD:
            for stale_key in list(self._failures):
                self._prune(stale_key, now)
        for key in keys:
            self._prune(key, now)
            self._failures.setdefault(key, []).append(now)

    def retry_after(self, *keys):
        """Seconds until every key is allowed again; 0 when allowed now."""
        with self._lock:
            return self._retry_after_locked(keys, self._clock())

    def record_failure(self, *keys):
        with self._lock:
            self._record_locked(keys, self._clock())

    def reserve(self, *keys):
        """
        Atomically admit one attempt: returns the wait in seconds if blocked
        (nothing recorded), else records the attempt as a failure up front and
        returns 0. Call reset() when the attempt succeeds. Checking and
        recording in separate steps would let a parallel burst exceed the limit.
        """
        with self._lock:
            now = self._clock()
            wait = self._retry_after_locked(keys, now)
            if wait == 0:
                self._record_locked(keys, now)
            return wait

    def reset(self, *keys):
        with self._lock:
            for key in keys:
                self._failures.pop(key, None)

    def failure_count(self, key):
        with self._lock:
            return len(self._prune(key, self._clock()))


def _positive_int_config(key, default):
    try:
        value = int(CONFIG.get(key, default))
    except (TypeError, ValueError):
        print(f"[Config Warning] Invalid '{key}', using default {default}", file=sys.stderr)
        return default
    return value if value > 0 else default


LOGIN_MAX_FAILURES = _positive_int_config("login_max_failures", 5)
LOGIN_WINDOW_SECONDS = _positive_int_config("login_window_minutes", 15) * 60
LOGIN_THROTTLE = LoginThrottle(max_failures=LOGIN_MAX_FAILURES, window_seconds=LOGIN_WINDOW_SECONDS)

# Deleting a character is destructive: attempts (valid or not) are capped per admin so a stolen session
# cannot wipe characters in bulk or guess confirmation names.
CHARACTER_DELETE_MAX_PER_MINUTE = _positive_int_config("character_delete_max_per_minute", 10)
CHARACTER_DELETE_THROTTLE = LoginThrottle(max_failures=CHARACTER_DELETE_MAX_PER_MINUTE, window_seconds=60)

# RO Class & Map Dictionaries
# Careers 1000-6400 and the town/field scenes come from the game's own data: job_id -> job_name of the skill trees
# (konsor-ro3 data/ro3base/skill_trees.json) and id -> name_en of the scene list (data/ro3base/maps.json). Careers
# 2210, 3210, 3211, 4210, 5210 and 5400 have no skill tree there and stay UNVERIFIED, as does anything else that is
# not listed. aethai/ro3emu-server tests/Ro3Emu.Tests CombatTableRulesTests.cs (cited for 1310, 2400 and 6100) calls
# 1400 "Lord Knight" and 4400 "High Priest" in comments, but the same test asserts that every resonance job (1400, 4400,
# 2400) is job rank 5, the third job, which is the game data's Rune Knight (1400) and Arch Bishop (4400); the
# transcended second jobs Lord Knight and High Priest are 1300 and 4300.
# Operators can correct or extend any of them with `names_file` (docs/guide/names.md).
CAREER_MAP = {
    1000: 'Novice',
    1100: 'Swordman',
    1200: 'Knight',
    1210: 'Crusader',
    1310: 'Paladin',
    1300: 'Lord Knight',     # skill_trees.json: Swordsman, Trans 2-1
    1400: 'Rune Knight',     # skill_trees.json: Swordsman, 3rd Job (3-1); CombatTableRulesTests.cs:36 asserts job rank 5
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
    4300: 'High Priest',     # skill_trees.json: Acolyte, Trans 2-1
    4400: 'Arch Bishop',     # skill_trees.json: Acolyte, 3rd Job (3-1); CombatTableRulesTests.cs:41 asserts job rank 5
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
    # Town, field and dungeon-entrance scenes: id -> name_en of the game's scene list (konsor-ro3 data/ro3base/maps.json).
    101: 'Garden of Time',
    10001: 'Tritura Academy',
    10100: 'Prontera',
    10101: 'Izlude',  # tests/Ro3Emu.Tests/DungeonTests.Return.cs:534
    10102: 'Byalan Island',
    10103: 'Inn',
    10104: 'Library',
    10105: 'Grand Cathedral',
    10106: 'Royal Palace',
    10107: 'Tavern',
    10110: 'Prontera East Gate',
    10111: 'Prontera South Gate',
    10112: 'Prontera West Gate',
    10113: 'Prontera North Gate',
    10141: 'Undersea Tunnel 1F',
    10150: 'Culvert 1F',
    10200: 'Payon',
    10201: 'Archer Village',
    10213: 'Southern Payon',
    10214: 'Poring Island',
    10217: 'Southeast Payon',
    10218: 'Eastern Payon',
    10219: 'Deep Forest',
    10220: 'Payon Forest',
    10240: 'Payon Cave',
    10241: 'Abandoned Village',
    10300: 'Geffen',
    10310: 'Orc Village',
    10312: 'Kordt Forest',
    10314: 'Geffen North Gate',
    10315: 'Geffen Outskirts',
    10317: 'Geffen West Gate',
    10318: 'Geffen Field',
    10321: 'Goblin Forest',
    10330: 'Geffen East Gate',
    10340: 'Orc Cave',
    10350: 'Geffen Tower 1F',
    10414: 'Mjolnir Garden',
    10415: 'Mt. Mjolnir',
    10420: 'Larva Canyon',
    10440: 'Hidden Forest',
    10450: 'Abandoned Mine',
    10500: 'Morroc',
    10510: 'Desert Crossroad',
    10512: 'Bridge of Desert',
    10514: 'Sograt Desert',
    10522: 'South Morroc',
    10527: 'Southern Sograt',
    10529: 'Western Morroc',
    10531: 'Papuchicha Forest',
    10537: 'Pharos Lighthouse',
    10540: 'Ant Hell',
    10550: 'Pyramid 1F',
    10560: 'Sphinx Dungeon 1F',
    10600: 'Alberta',
    10601: 'Amatsu',
    10602: 'Gonryun',
    10603: 'Luoyang',
    10604: 'Ayothaya',
    10605: 'Dewata Village',
    10606: 'Port Malaya',
    10610: 'Sunken Ship',
    10641: 'Shipwreck Labyrinth 1F',
    10700: 'Glast Heim the Ancient City',
    10740: 'Glast Heim Monastery',
    10742: 'Glast Heim Aboveground 1F',
    10751: 'Glast Heim Culvert 1F',
    10761: 'Glast Heim Chivalry 1F',
    10771: 'Glast Heim Underground Cave 1F',
    10781: 'Glast Heim Underground Cemetery',
    10791: 'Glast Heim Underground Prison 1F',
    30399: "Producer's Lair",
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

# RO3Emu PackType values stored in item.pack (aethai/ro3emu-server
# src/Ro3Emu.Server/Protos/romsg/MG_Pack.proto, enum PackType).
PACK_NAMES = {
    0: 'No bag',
    1: 'Items',
    2: 'Equipment',
    3: 'Cards',
    4: 'Totems',
    5: 'Emblems',
    20: 'Currencies',
    100: 'Class special'
}

# Max value of a signed 64-bit SQLite INTEGER.
MAX_SQLITE_INT = 2 ** 63 - 1

# Cache of the optional item names file ({"<entry>": "<name>"}).
# "key" is (absolute path, mtime); "warned" holds paths already reported on stderr.
ITEM_NAMES_STATE = {"key": None, "names": None, "warned": set()}

def _load_item_names_file():
    """Returns the {entry: name} mapping from config 'item_names_file', or None when unavailable."""
    path = str(CONFIG.get("item_names_file") or "").strip()
    if not path:
        return None
    abs_path = os.path.abspath(path)
    try:
        key = (abs_path, os.path.getmtime(abs_path))
        if ITEM_NAMES_STATE["key"] == key:
            return ITEM_NAMES_STATE["names"]
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object {\"<entry>\": \"<name>\"}")
        names = {str(k): v for k, v in data.items() if isinstance(v, str)}
        ITEM_NAMES_STATE["key"] = key
        ITEM_NAMES_STATE["names"] = names
        return names
    except (OSError, ValueError) as e:
        if abs_path not in ITEM_NAMES_STATE["warned"]:
            ITEM_NAMES_STATE["warned"].add(abs_path)
            print(f"[Config Warning] Could not load item_names_file '{abs_path}', item names disabled: {e}", file=sys.stderr)
        return None


# Optional item catalog ('item_catalog_file'): a JSON list of {"id", "n" (name), "ic" (icon file), "q" (quality)}
# rows, the shape Konsor's items-catalog.json has. Every field is validated here, so what reaches the page is
# a plain name, an icon FILE NAME that passes a strict pattern, or one of five quality words.
ITEM_CATALOG_STATE = {"key": None, "catalog": None, "warned": set()}
ITEM_CATALOG_MAX_BYTES = 32 * 1024 * 1024
ITEM_NAME_MAX_LENGTH = 120
ITEM_ICON_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,100}\.(?:png|webp|jpg)\Z")
ITEM_QUALITIES = ("common", "fine", "rare", "legendary", "mythic")
ITEM_ICONS_URL_PATTERN = re.compile(r"^/?(?:[A-Za-z0-9._~-]+/?)+\Z")


def _catalog_row(row):
    """One catalog row as (id text, {"name", "icon", "quality"}), or None when it is unusable."""
    if not isinstance(row, dict):
        return None
    raw_id, name = row.get("id"), row.get("n")
    if isinstance(raw_id, bool):
        return None
    if isinstance(raw_id, str) and raw_id.isascii() and raw_id.isdigit():
        raw_id = int(raw_id)
    if not isinstance(raw_id, int) or not (0 < raw_id <= MAX_SQLITE_INT):
        return None
    if not isinstance(name, str) or not name.strip():
        return None
    icon = row.get("ic")
    quality = row.get("q")
    quality = quality.strip().lower() if isinstance(quality, str) else None
    return str(raw_id), {
        "name": name.strip()[:ITEM_NAME_MAX_LENGTH],
        "icon": icon if isinstance(icon, str) and ITEM_ICON_NAME.match(icon) else None,
        "quality": quality if quality in ITEM_QUALITIES else None,
    }


def load_item_catalog():
    """Returns {entry text: {"name", "icon", "quality"}} from config 'item_catalog_file', or None when unavailable."""
    path = str(CONFIG.get("item_catalog_file") or "").strip()
    if not path:
        return None
    abs_path = os.path.abspath(path)
    try:
        stat = os.stat(abs_path)
        key = (abs_path, stat.st_mtime, stat.st_size)
        if ITEM_CATALOG_STATE["key"] == key:
            return ITEM_CATALOG_STATE["catalog"]
        if stat.st_size > ITEM_CATALOG_MAX_BYTES:
            raise ValueError(f"larger than {ITEM_CATALOG_MAX_BYTES} bytes")
        with open(abs_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("expected a JSON list of {\"id\", \"n\", \"ic\", \"q\"} rows")
        catalog = {}
        for row in data:
            parsed = _catalog_row(row)
            if parsed:
                catalog.setdefault(*parsed)
        ITEM_CATALOG_STATE["key"] = key
        ITEM_CATALOG_STATE["catalog"] = catalog
        return catalog
    except (OSError, ValueError, RecursionError) as e:
        if abs_path not in ITEM_CATALOG_STATE["warned"]:
            ITEM_CATALOG_STATE["warned"].add(abs_path)
            print(f"[Config Warning] Could not load item_catalog_file '{abs_path}', item icons disabled: {e}", file=sys.stderr)
        return None


def load_item_names():
    """The {entry: name} mapping: 'item_names_file' names, then catalog names for the ids it lacks; None when neither exists."""
    names = _load_item_names_file()
    catalog = load_item_catalog()
    if not catalog:
        return names
    merged = {entry: info["name"] for entry, info in catalog.items()}
    if names:
        merged.update(names)
    return merged


NO_ITEM_INFO = {"name": None, "icon": None, "quality": None}


def item_resolver(names=None):
    """A lookup function entry -> {"name", "icon", "quality"} that loads the sources once (one call per request)."""
    names = load_item_names() or {} if names is None else names
    catalog = load_item_catalog() or {}

    def resolve(entry):
        if isinstance(entry, int) and not isinstance(entry, bool):
            key = str(entry)
        elif isinstance(entry, str):
            key = entry.strip()
        else:
            return dict(NO_ITEM_INFO)
        found = catalog.get(key) or NO_ITEM_INFO
        return {"name": names.get(key), "icon": found["icon"], "quality": found["quality"]}

    return resolve


def item_info(entry):
    return item_resolver()(entry)


def normalized_item_icons_url(value):
    """'item_icons_url' as a same-site path with a trailing slash, or '' when it is unset or could leave the site."""
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if not value or len(value) > 200 or not ITEM_ICONS_URL_PATTERN.match(value):
        return ""
    if any(part in (".", "..") for part in value.split("/")):
        return ""
    return value if value.endswith("/") else value + "/"


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
    """Display name for a career (class) id; unknown ids render as "Class <id>"."""
    name = CAREER_MAP.get(_as_int(career_id))
    return name if name is not None else tr("Class {id}", id=career_id)


def scene_name(scene_id):
    """Display name for a scene (map) id; unknown ids render as "Map <id>"."""
    name = SCENE_MAP.get(_as_int(scene_id))
    return name if name is not None else tr("Map {id}", id=scene_id)


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
        con.execute(ADMIN_SESSION_TABLE_SQL)
        con.commit()
    # Startup: drop sessions that expired while the panel was down.
    purge_expired_sessions()

# --- Admin Sessions ---
# Panel sessions live in `admin_session` so a restart does not log every admin out.
# Only the SHA-256 hash of the token is stored; the raw token never reaches the DB or logs.
ADMIN_SESSION_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS admin_session (
        token_hash TEXT PRIMARY KEY,
        admin_user TEXT NOT NULL,
        ip_address TEXT DEFAULT '',
        created_utc INTEGER NOT NULL,
        expires_utc INTEGER NOT NULL
    );
"""

def hash_session_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

@contextmanager
def session_db():
    """get_db() plus the session table, which may be missing if the DB appeared after startup.

    Raises FileNotFoundError when the DB file is missing; callers fall back to ACTIVE_SESSIONS.
    """
    with get_db() as con:
        con.execute(ADMIN_SESSION_TABLE_SQL)
        yield con

def purge_expired_sessions(now=None):
    now = int(time.time()) if now is None else now
    # Snapshot first: request threads may mutate the dict concurrently.
    for key in [k for k, s in list(ACTIVE_SESSIONS.items()) if now > s["expires_at"]]:
        ACTIVE_SESSIONS.pop(key, None)
    try:
        with session_db() as con:
            con.execute("DELETE FROM admin_session WHERE expires_utc < ?", (now,))
    except (FileNotFoundError, sqlite3.Error) as e:
        if not isinstance(e, FileNotFoundError):
            print(f"[Session Warning] Could not purge expired sessions: {e}", file=sys.stderr)

def create_session(token, user, ip_address):
    now = int(time.time())
    expires = now + SESSION_TTL_SECONDS
    token_hash = hash_session_token(token)
    purge_expired_sessions(now)
    try:
        with session_db() as con:
            con.execute(
                "INSERT INTO admin_session (token_hash, admin_user, ip_address, created_utc, expires_utc) VALUES (?, ?, ?, ?, ?)",
                (token_hash, user, ip_address or "", now, expires)
            )
        return
    except FileNotFoundError:
        pass
    except sqlite3.Error as e:
        print(f"[Session Warning] Database unavailable, keeping session in memory: {e}", file=sys.stderr)
    ACTIVE_SESSIONS[token_hash] = {"user": user, "created_at": now, "expires_at": expires, "ip": ip_address}

def is_configured_admin(username):
    """True while `username` is still listed in admin_users (case-insensitive)."""
    wanted = str(username or "").strip().lower()
    return any(str(a.get("username", "")).strip().lower() == wanted for a in CONFIG.get("admin_users", []))

def get_session(token):
    """Return the live session for `token` and slide its expiry, or None.

    Expired sessions are deleted. A database error fails closed for DB-backed sessions.
    """
    if not token:
        return None
    now = int(time.time())
    token_hash = hash_session_token(token)

    session = ACTIVE_SESSIONS.get(token_hash)
    if session is not None:
        if now > session["expires_at"] or not is_configured_admin(session["user"]):
            ACTIVE_SESSIONS.pop(token_hash, None)
            return None
        session["expires_at"] = now + SESSION_TTL_SECONDS
        return session

    try:
        with session_db() as con:
            row = con.execute(
                "SELECT admin_user, ip_address, created_utc, expires_utc FROM admin_session WHERE token_hash = ?",
                (token_hash,)
            ).fetchone()
            if row is None:
                return None
            # A session dies when it expires or when its admin is removed from admin_users.
            if now > row["expires_utc"] or not is_configured_admin(row["admin_user"]):
                con.execute("DELETE FROM admin_session WHERE token_hash = ?", (token_hash,))
                return None
            expires = now + SESSION_TTL_SECONDS
            # The session table lives in the live RO3Emu database: skip the write unless
            # the expiry would move by at least SESSION_SLIDE_MIN_SECONDS.
            if expires - row["expires_utc"] >= SESSION_SLIDE_MIN_SECONDS:
                con.execute("UPDATE admin_session SET expires_utc = ? WHERE token_hash = ?", (expires, token_hash))
            else:
                expires = row["expires_utc"]
            return {"user": row["admin_user"], "created_at": row["created_utc"], "expires_at": expires, "ip": row["ip_address"]}
    except FileNotFoundError:
        return None
    except sqlite3.Error as e:
        print(f"[Session Warning] Could not read session: {e}", file=sys.stderr)
        return None

def delete_session(token):
    if not token:
        return
    token_hash = hash_session_token(token)
    ACTIVE_SESSIONS.pop(token_hash, None)
    try:
        with session_db() as con:
            con.execute("DELETE FROM admin_session WHERE token_hash = ?", (token_hash,))
    except FileNotFoundError:
        pass
    except sqlite3.Error as e:
        print(f"[Session Warning] Could not delete session: {e}", file=sys.stderr)

def revoke_admin_sessions(con, user, keep_token_hash=None):
    """Ends every panel session of `user` (letter case ignored) except the one whose hash is `keep_token_hash`.

    Runs on the caller's connection so it commits or rolls back with the password change.
    """
    wanted = str(user).strip().lower()
    for key in [k for k, s in list(ACTIVE_SESSIONS.items()) if str(s.get("user", "")).lower() == wanted and k != keep_token_hash]:
        ACTIVE_SESSIONS.pop(key, None)
    con.execute(ADMIN_SESSION_TABLE_SQL)
    con.execute(
        "DELETE FROM admin_session WHERE LOWER(admin_user) = ? AND token_hash IS NOT ?",
        (wanted, keep_token_hash),
    )

def insert_audit(con, admin_user, action, target="", details="", ip_address=""):
    """Writes an audit row on an open connection, inside the caller's transaction."""
    con.execute(
        "INSERT INTO admin_audit_log (admin_user, action, target, details, ip_address) VALUES (?, ?, ?, ?, ?)",
        (admin_user, action, target, details, ip_address)
    )

def log_audit(admin_user, action, target="", details="", ip_address=""):
    try:
        with get_db() as con:
            insert_audit(con, admin_user, action, target, details, ip_address)
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

# role.currency holds "<ItemConfig id>:<amount>" pairs; RO3Emu defines id 1 as Zeny
# (Accounts/RoleStore.cs, Game/CharacterService.cs ZenyId). Other ids have no verified
# name, so they are reported by id.
ZENY_CURRENCY_ITEM_ID = 1

def parse_currency(curr_str):
    result = {"zeny": 0, "others": [], "raw": curr_str or ""}
    if not curr_str:
        return result
    for part in str(curr_str).split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        try:
            currency_id, amount = int(key.strip()), int(value.strip())
        except ValueError:
            continue
        if currency_id == ZENY_CURRENCY_ITEM_ID:
            result["zeny"] = amount
        else:
            result["others"].append({"id": currency_id, "amount": amount})
    result["others"].sort(key=lambda c: c["id"])
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
    return CAREER_MAP.get(career_id, tr("Class {id}", id=career_id))


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

MAIL_PAGE_SIZE_DEFAULT = 20
MAIL_PAGE_SIZE_MAX = 100
CHARACTER_MAIL_PATH = re.compile(r'^/api/admin/characters/([^/]+)/mail$')
POSITIVE_INT = re.compile(r'^[0-9]+$')

class MailboxDecodeError(ValueError):
    """role.mailbox does not hold a MailService.Mailbox JSON document."""

def _json_str(obj, key, default=""):
    value = obj.get(key)
    return value if isinstance(value, str) else default

def _json_int(obj, key, default=0):
    value = obj.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default

def _json_bool(obj, key):
    return obj.get(key) is True

def _json_objects(obj, key):
    value = obj.get(key)
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []

def _reject_json_constant(name):
    raise MailboxDecodeError(f"non-standard JSON constant {name}")

def decode_mailbox(raw):
    """Decodes role.mailbox: RO3Emu MailService.Mailbox serialized by System.Text.Json with
    default options (PascalCase names, UTF-8). NULL or empty means an empty mailbox.
    Raises MailboxDecodeError when the stored value is not such a document."""
    if raw is None or len(raw) == 0:
        return []
    try:
        text = raw if isinstance(raw, str) else bytes(raw).decode('utf-8-sig')
        doc = json.loads(text, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise MailboxDecodeError(str(exc)) from None
    if not isinstance(doc, dict):
        raise MailboxDecodeError("mailbox is not a JSON object")
    letters = doc.get("Letters")
    if letters is None:
        return []
    if not isinstance(letters, list) or not all(isinstance(m, dict) for m in letters):
        raise MailboxDecodeError("Letters is not a list of objects")
    return letters

def format_mail(letter, resolve=None):
    """Projects one MailService.Letter onto display fields; internal keys and the
    protobuf ContentParams are never exposed. `resolve` is an item_resolver() shared by a whole page of mail."""
    resolve = resolve or item_resolver()
    attachments = [{"entry": _json_int(a, "Entry"), "count": _json_int(a, "Count"), "bind": _json_int(a, "Bind"),
                    **resolve(_json_int(a, "Entry"))}
                   for a in _json_objects(letter, "Attachments")]
    items = [{"guid": _json_int(i, "Guid"), "entry": _json_int(i, "Entry"), "stack": _json_int(i, "Stack"),
              **resolve(_json_int(i, "Entry"))}
             for i in _json_objects(letter, "Items")]
    currency = []
    raw_currency = letter.get("Currency")
    if isinstance(raw_currency, dict):
        for key, amount in raw_currency.items():
            if POSITIVE_INT.match(str(key)) and isinstance(amount, int) and not isinstance(amount, bool):
                currency.append({"entry": int(key), "amount": amount, **resolve(int(key))})
        currency.sort(key=lambda c: c["entry"])
    created = _json_int(letter, "CreatedTime")
    remove = _json_int(letter, "RemoveTime")
    return {
        "id": _json_str(letter, "Id"),
        "category": _json_int(letter, "Category", 1),
        "title": _json_str(letter, "Title"),
        "abstract": _json_str(letter, "Abstract"),
        "content": _json_str(letter, "Content"),
        "sender": _json_str(letter, "Sender", "RO3"),
        "sender_id": _json_str(letter, "SenderId", "0"),
        "template_id": _json_int(letter, "TemplateId"),
        "important_type": _json_int(letter, "ImportantType"),
        "created_at": format_timestamp(created),
        "remove_at": format_timestamp(remove),
        "read": _json_bool(letter, "Read"),
        "claimed": _json_bool(letter, "Claimed"),
        "attachments": attachments,
        "items": items,
        "currency": currency,
        "attachment_count": len(attachments) + len(items) + len(currency),
    }

def format_role(r, include_progress=False):
    """Formats a role row; include_progress adds exp/job_exp/bonus_points for the detail view, and the name, image
    and quality of every currency (currency ids are item ids, item 1 is Zeny)."""
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
    if include_progress:
        resolve = item_resolver()
        data["currency"]["zeny_item"] = resolve(ZENY_CURRENCY_ITEM_ID)
        for entry in data["currency"]["others"]:
            entry.update(resolve(entry["id"]))
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

# --- Economy Log (read-only view over RO3Emu economy_entry / operation_receipt) ---
# Enum values mirror upstream ro3emu-server src/Ro3Emu.Server/Economy/EconomyContracts.cs
# (EconomyOwnerKind, EconomyAssetKind). Role owners store the role id as invariant text in owner_id.
ECONOMY_DEFAULT_PAGE_SIZE = 50
ECONOMY_MAX_PAGE_SIZE = 200
ECONOMY_OWNER_KIND_ROLE = 1
ECONOMY_OWNER_KIND_LABELS = {
    1: 'Character',
    2: 'Guild',
    3: 'System',
    4: 'Escrow',
    5: 'Recovery'
}
ECONOMY_ASSET_KIND_CURRENCY = 2
ECONOMY_ASSET_KIND_LABELS = {
    1: 'Item',
    2: 'Currency',
    3: 'Guild resource',
    4: 'Event resource'
}
# Upstream RoleStore.cs: currencies are ItemConfig ids and "1 = Zeny".
ZENY_CURRENCY_ID = 1
DAY_MS = 24 * 3600 * 1000
ISO_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')

def parse_int_value(raw, default, minimum, maximum):
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value

def parse_iso_date_ms(raw):
    """Returns UTC midnight of a YYYY-MM-DD date in epoch milliseconds, None if empty; raises ValueError."""
    value = (raw or '').strip()
    if not value:
        return None
    if not ISO_DATE_RE.match(value):
        raise ValueError("invalid date")
    day = datetime.strptime(value, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    return int(day.timestamp()) * 1000

def format_utc_ms(ms):
    if ms is None:
        return None
    try:
        ms = int(ms)
        dt = datetime.fromtimestamp(ms // 1000, tz=timezone.utc) + timedelta(milliseconds=ms % 1000)
        return dt.isoformat(timespec='milliseconds')
    except (TypeError, ValueError, OverflowError, OSError):
        return None

def query_economy(account, character, from_ms, to_ms, page, page_size):
    """Strictly read-only query over the economy ledger. Every filter value is bound as a parameter."""
    result = {
        "available": False,
        "entries": [],
        "total": 0,
        "page": page,
        "page_size": page_size,
        "pages": 1
    }
    with get_db() as con:
        con.execute("PRAGMA query_only = ON")
        tables = {row[0] for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('economy_entry', 'operation_receipt', 'role')"
        )}
        if 'economy_entry' not in tables or 'operation_receipt' not in tables:
            return result
        has_role = 'role' in tables

        where = []
        args = []
        if account:
            where.append("LOWER(r.actor_account) = LOWER(?)")
            args.append(account)
        if character:
            if has_role:
                where.append(
                    "(r.actor_role IN (SELECT id FROM role WHERE LOWER(name) = LOWER(?))"
                    " OR (e.owner_kind = ? AND e.owner_id IN"
                    " (SELECT CAST(id AS TEXT) FROM role WHERE LOWER(name) = LOWER(?))))"
                )
                args.extend([character, ECONOMY_OWNER_KIND_ROLE, character])
            else:
                where.append("0")
        if from_ms is not None:
            where.append("e.recorded_utc_ms >= ?")
            args.append(from_ms)
        if to_ms is not None:
            where.append("e.recorded_utc_ms < ?")
            args.append(to_ms + DAY_MS)

        base_sql = " FROM economy_entry e JOIN operation_receipt r ON r.operation_id = e.operation_id"
        if where:
            base_sql += " WHERE " + " AND ".join(where)

        total = con.execute("SELECT COUNT(*)" + base_sql, args).fetchone()[0]
        offset = (page - 1) * page_size
        rows = []
        if offset < total:
            rows = con.execute(
                "SELECT e.entry_id, e.recorded_utc_ms, e.operation_id, r.command_kind, r.actor_account,"
                " r.actor_role, e.owner_kind, e.owner_id, e.asset_kind, e.asset_id, e.delta, e.reason_code"
                + base_sql + " ORDER BY e.entry_id DESC LIMIT ? OFFSET ?",
                args + [page_size, offset]
            ).fetchall()

        role_ids = set()
        for row in rows:
            if row["actor_role"] is not None:
                role_ids.add(int(row["actor_role"]))
            owner_id = str(row["owner_id"] or "")
            if row["owner_kind"] == ECONOMY_OWNER_KIND_ROLE and owner_id.isdigit():
                role_ids.add(int(owner_id))
        role_names = {}
        role_accounts = {}
        if has_role and role_ids:
            ids = sorted(role_ids)
            placeholders = ",".join("?" for _ in ids)
            for role_row in con.execute("SELECT id, name, account FROM role WHERE id IN (" + placeholders + ")", ids):
                role_names[role_row["id"]] = role_row["name"]
                role_accounts[role_row["id"]] = role_row["account"]

        entries = []
        for row in rows:
            owner_id = str(row["owner_id"] or "")
            owner_name = None
            owner_account = None
            if row["owner_kind"] == ECONOMY_OWNER_KIND_ROLE and owner_id.isdigit():
                owner_name = role_names.get(int(owner_id))
                owner_account = role_accounts.get(int(owner_id))
            asset_kind = row["asset_kind"]
            if asset_kind == ECONOMY_ASSET_KIND_CURRENCY and row["asset_id"] == ZENY_CURRENCY_ID:
                asset_label = "Zeny"
            else:
                asset_label = f"{tr(ECONOMY_ASSET_KIND_LABELS.get(asset_kind, 'Asset'))} #{row['asset_id']}"
            actor_role = row["actor_role"]
            entries.append({
                "entry_id": row["entry_id"],
                "recorded_utc": format_utc_ms(row["recorded_utc_ms"]),
                "operation_id": row["operation_id"],
                "command_kind": row["command_kind"],
                "actor_account": row["actor_account"],
                "actor_role": actor_role,
                "actor_role_name": role_names.get(int(actor_role)) if actor_role is not None else None,
                "owner_kind": row["owner_kind"],
                "owner_kind_label": tr(ECONOMY_OWNER_KIND_LABELS[row["owner_kind"]]) if row["owner_kind"] in ECONOMY_OWNER_KIND_LABELS else tr("Type {kind}", kind=row["owner_kind"]),
                "owner_id": owner_id,
                "owner_name": owner_name,
                "owner_account": owner_account,
                "asset_kind": asset_kind,
                "asset_id": row["asset_id"],
                "asset_label": asset_label,
                "delta": row["delta"],
                "reason_code": row["reason_code"]
            })

    result.update({
        "available": True,
        "entries": entries,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size)
    })
    return result


RO3_STATUS_SUFFIX = "/ro3emu/status"


class Ro3EmuUnavailable(Exception):
    """RO3Emu could not serve a diagnostics request; the message is shown to the admin."""


def ro3_base_url():
    """RO3Emu HTTP root: config 'ro3_base_url' if set, else RO3_STATUS_URL without '/ro3emu/status'."""
    explicit = str(CONFIG.get("ro3_base_url") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    status_url = RO3_STATUS_URL.rstrip("/")
    if status_url.endswith(RO3_STATUS_SUFFIX):
        return status_url[:-len(RO3_STATUS_SUFFIX)]
    parts = urllib.parse.urlsplit(status_url)
    return f"{parts.scheme}://{parts.netloc}"


def fetch_ro3_json(path):
    """GET a RO3Emu JSON endpoint within RO3_HTTP_TIMEOUT and RO3_MAX_RESPONSE_BYTES.

    Raises Ro3EmuUnavailable with a translated reason on any failure.
    """
    deadline = time.monotonic() + RO3_HTTP_TIMEOUT
    req = urllib.request.Request(ro3_base_url() + path, headers={'User-Agent': 'RO3AdminCPanel'})
    try:
        with urllib.request.urlopen(req, timeout=RO3_HTTP_TIMEOUT) as resp:
            declared = resp.headers.get('Content-Length')
            if declared and declared.isdigit() and int(declared) > RO3_MAX_RESPONSE_BYTES:
                raise Ro3EmuUnavailable(tr("The RO3Emu response exceeds the maximum allowed size."))
            body = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise TimeoutError()
                chunk = resp.read(65536)
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > RO3_MAX_RESPONSE_BYTES:
                    raise Ro3EmuUnavailable(tr("The RO3Emu response exceeds the maximum allowed size."))
    except Ro3EmuUnavailable:
        raise
    except urllib.error.HTTPError as e:
        e.close()
        if e.code == 404:
            raise Ro3EmuUnavailable(tr(
                "RO3Emu does not expose this endpoint to the panel: it only answers on loopback, "
                "so the panel must run on the same host as RO3Emu (or behind a local proxy)."
            ))
        raise Ro3EmuUnavailable(tr("RO3Emu answered HTTP {code}.", code=e.code))
    except (TimeoutError, socket.timeout):
        raise Ro3EmuUnavailable(tr("RO3Emu did not answer in time."))
    except urllib.error.URLError as e:
        if isinstance(e.reason, (TimeoutError, socket.timeout)):
            raise Ro3EmuUnavailable(tr("RO3Emu did not answer in time."))
        raise Ro3EmuUnavailable(tr("Could not connect to RO3Emu."))
    except (OSError, ValueError, http.client.HTTPException):
        raise Ro3EmuUnavailable(tr("Could not connect to RO3Emu."))
    try:
        return json.loads(bytes(body).decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        raise Ro3EmuUnavailable(tr("The RO3Emu response is not valid JSON."))


def unexpected_format():
    return tr("The RO3Emu response has an unexpected format.")


def _number(value):
    """Finite numbers pass through; anything else (bool, str, NaN, None, missing) becomes None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _section(data, key):
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def summarize_metrics(snapshot):
    """Selected fields of RO3Emu's ServerMetrics.Snapshot(); missing values become None."""
    if not isinstance(snapshot, dict):
        raise Ro3EmuUnavailable(unexpected_format())
    wire = _section(snapshot, "wire")
    sessions = _section(snapshot, "sessions")
    database = _section(snapshot, "database")
    runtime = _section(snapshot, "runtime")
    errors = _section(snapshot, "errors")

    # byMap has one entry per map instance (line/room); the dashboard shows players per map.
    per_map = {}
    by_map = sessions.get("byMap")
    for entry in by_map if isinstance(by_map, list) else []:
        if not isinstance(entry, dict):
            continue
        map_id = _number(entry.get("map"))
        count = _number(entry.get("count"))
        if map_id is None or count is None:
            continue
        per_map[map_id] = per_map.get(map_id, 0) + count

    captured = snapshot.get("capturedUtc")
    return {
        "captured_utc": captured if isinstance(captured, str) else None,
        "uptime_seconds": _number(snapshot.get("elapsedSeconds")),
        "connections": _number(wire.get("connections")),
        "sessions": {
            "login": _number(sessions.get("login")),
            "loading": _number(sessions.get("loading")),
            "in_world": _number(sessions.get("inWorld")),
            "by_map": [
                {"map": map_id, "scene_name": scene_name(map_id), "count": count}
                for map_id, count in per_map.items()
            ],
        },
        "database": {
            "statements": _number(database.get("statements")),
            "commits": _number(database.get("commits")),
        },
        "runtime": {"working_set_bytes": _number(runtime.get("workingSetBytes"))},
        "errors": {
            "exceptions": _number(errors.get("exceptions")),
            "error_logs": _number(errors.get("errorLogs")),
        },
    }


def account_is_online(account_name):
    """True when RO3Emu lists the account as connected. Raises when that answer cannot be trusted:
    callers that delete must fail closed instead of assuming the account is offline."""
    entries = fetch_ro3_json("/ro3emu/online")
    if not isinstance(entries, list):
        raise Ro3EmuUnavailable(unexpected_format())
    target = str(account_name or "").strip().lower()
    return any(
        isinstance(entry, dict) and str(entry.get("account") or "").strip().lower() == target
        for entry in entries
    )


def summarize_online(entries, show_ips):
    """RO3Emu /ro3emu/online rows -> panel rows; 'remote' (player IP) only when show_ips."""
    if not isinstance(entries, list):
        raise Ro3EmuUnavailable(unexpected_format())
    players = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        scene = _number(entry.get("scene"))
        x = _number(entry.get("x"))
        z = _number(entry.get("z"))
        role = entry.get("role")
        player = {
            "account": str(entry.get("account") or ""),
            "character": role if isinstance(role, str) else None,
            "scene_id": scene,
            "scene_name": scene_name(scene) if scene is not None else None,
            "x": round(x, 1) if x is not None else None,
            "z": round(z, 1) if z is not None else None,
        }
        if show_ips:
            remote = entry.get("remote")
            player["remote"] = str(remote) if remote is not None else None
        players.append(player)
    return players


# --- Read-only guild and auction views (issue #9) ---
# Schemas follow aethai/ro3emu-server: guild/guild_member in Accounts/Persistence/GuildStorePlans.cs,
# auction_item/auction_prebuy in Accounts/Persistence/CoreSchemaPlans.cs (AuctionSchemaPlan), and the
# auction_item columns AuctionItemColumns.Migrate adds. Everything else lives in JSON state blobs.

LIST_PAGE_SIZE_DEFAULT = 50
LIST_PAGE_SIZE_MAX = 200
AUDIT_PAGE_SIZE_DEFAULT = 50
AUDIT_PAGE_SIZE_MAX = 100

# Verified relational columns per auction view; columns added by later RO3Emu migrations read as NULL when absent.
AUCTION_VIEWS = {
    'lots': {
        'table': 'auction_item',
        'columns': ['id', 'source_key', 'settled', 'auction_type', 'run_id', 'end_time'],
        'booleans': ['settled'],
    },
    'prebuy': {
        'table': 'auction_prebuy',
        'columns': ['id', 'role_id', 'auction_type', 'src_type', 'item_id', 'quantity',
                    'unit_price', 'currency', 'processed', 'paused'],
        'booleans': ['processed', 'paused'],
    },
}

def open_read_only(con):
    """Makes the connection refuse writes; used by the read-only views."""
    con.execute("PRAGMA query_only = ON")

def table_exists(con, table):
    return con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)).fetchone() is not None

def table_columns(con, table):
    # PRAGMA cannot take a bound parameter; table always comes from AUCTION_VIEWS, never from the request.
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}

# --- Account bans ---
# RO3Emu owns `account_ban` (account, reason, banned_utc, until_utc, banned_by) and reads it at login.
# The panel is its only writer and never creates or alters it: an older RO3Emu has no such table and
# cannot enforce a ban. A ban is active while its row exists and until_utc is NULL or still in the
# future (unix seconds). `admin_account_meta.is_banned` is no longer read: those old panel-only bans
# were never enforced and are not migrated.
ACTIVE_BAN_SQL = "(b.until_utc IS NULL OR b.until_utc > ?)"

def bans_supported(con):
    return table_exists(con, "account_ban")

def bans_unsupported_error():
    return tr("Update RO3Emu: this server does not support account bans")

def ban_time_label(banned_utc):
    if banned_utc is None:
        return ""
    return datetime.fromtimestamp(int(banned_utc), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def active_ban(con, account, now):
    """The account's active ban row (reason, banned_utc, until_utc), or None; also None when bans are unsupported."""
    if not bans_supported(con):
        return None
    return con.execute(
        f"SELECT reason, banned_utc, until_utc FROM account_ban b WHERE b.account = ? AND {ACTIVE_BAN_SQL}", (account, now)
    ).fetchone()

def count_active_bans(con, now):
    if not bans_supported(con):
        return 0
    return con.execute(
        f"SELECT COUNT(*) FROM account_ban b JOIN account a ON a.name = b.account WHERE {ACTIVE_BAN_SQL}", (now,)
    ).fetchone()[0]

def account_ban_sql(con, now):
    """SQL pieces for the accounts list: (join, join args, ban columns, condition that means banned)."""
    if not bans_supported(con):
        return "", [], "0 AS is_banned, '' AS ban_reason, NULL AS banned_utc, NULL AS ban_until_utc", "0"
    return (
        f" LEFT JOIN account_ban b ON b.account = a.name AND {ACTIVE_BAN_SQL}",
        [now],
        "b.account IS NOT NULL AS is_banned, COALESCE(b.reason, '') AS ban_reason, b.banned_utc AS banned_utc,"
        " b.until_utc AS ban_until_utc",
        "b.account IS NOT NULL",
    )

def paging(total, page, page_size):
    return {"total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}

def guild_state_level(state_blob):
    """GuildStore.State.Level from the System.Text.Json blob (default options, PascalCase); None if unreadable."""
    try:
        level = json.loads(state_blob).get("Level")
    except (TypeError, ValueError, AttributeError):
        return None
    return level if isinstance(level, int) and not isinstance(level, bool) else None

# Guild row plus live (non-deleted) member count and summed level.
GUILD_SUMMARY_SQL = """
    SELECT g.id, g.name, g.state,
           COUNT(r.id) AS member_count,
           COALESCE(SUM(r.level), 0) AS total_level
    FROM guild g
    LEFT JOIN guild_member m ON m.guild_id = g.id
    LEFT JOIN role r ON r.id = m.role_id AND r.deleted_time = 0
"""

def format_guild_summary(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "level": guild_state_level(row["state"]),
        "member_count": row["member_count"],
        "total_level": row["total_level"],
    }

ADMIN_HASH_SCHEME = "pbkdf2_sha256"
ADMIN_HASH_ITERATIONS = 100000


def make_admin_password_hash(password, iterations=ADMIN_HASH_ITERATIONS, salt=None):
    """
    Encodes a password for the `password_hash` field of an `admin_users` entry:
    pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex> (PBKDF2-HMAC-SHA256, 32-byte key,
    16-byte random salt by default; same parameters as RO3Emu).
    """
    if salt is None:
        salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(iterations), 32)
    return f"{ADMIN_HASH_SCHEME}${int(iterations)}${salt.hex()}${derived.hex()}"


def verify_admin_password_hash(password, encoded):
    """Returns True only if `password` matches `encoded`; malformed input returns False."""
    if not isinstance(password, str) or not isinstance(encoded, str):
        return False
    parts = encoded.split("$")
    if len(parts) != 4 or parts[0] != ADMIN_HASH_SCHEME:
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except ValueError:
        return False
    if iterations <= 0 or not salt or not expected:
        return False
    derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations, len(expected))
    return hmac.compare_digest(derived, expected)


def _usable_credential(value):
    return isinstance(value, (bytes, bytearray)) and len(value) > 0


def lookup_game_account(clean_user, identity_names):
    """Returns (game account row or None, database_ok).

    The account of an admin is the one named exactly like the admin (`identity_names`: the spelling in
    admin_users or admin_gm). Accounts that differ only by letter case are other people, so they are
    ignored. A row without a usable password hash or salt counts as no account.
    database_ok is False when the read failed for a reason other than "no database / no account
    table", so the caller can refuse instead of falling back to a stale config password.
    """
    try:
        with get_db() as con:
            rows = con.execute(
                "SELECT name, password_hash, salt FROM account WHERE LOWER(name)=?", (clean_user,)
            ).fetchall()
    except FileNotFoundError:
        return None, True
    except sqlite3.OperationalError as e:
        return None, "no such table" in str(e).lower()
    except Exception:
        return None, False
    for row in rows:
        if row["name"] in identity_names and _usable_credential(row["password_hash"]) and _usable_credential(row["salt"]):
            return row, True
    return None, True


def authenticate_admin(username, password=None, password_hash=None):
    """
    Checks whether `username` is an admin (listed in admin_users or in the admin_gm table) and
    whether the credential is right.

    The game account is the single source of truth: when `username` is also an account in the RO3Emu
    database (named exactly like the admin), only that account's password signs in to the panel (the
    game, the web and the panel then share one password, and changing it from the panel replaces it
    everywhere). The `password` / `password_hash` of an admin_users entry only applies to an admin that
    has no game account, or while there is no RO3Emu database or `account` table. If the database
    cannot be read for any other reason (locked, corrupt), the login is refused.

    A config entry may hold `password_hash` (preferred, see make_admin_password_hash) or a plain
    `password`; when `password_hash` is present, `password` is ignored. `password_hash` passed to this
    function is the client-side derived PBKDF2 key, compared with account.password_hash.
    """
    clean_user = username.strip().lower()
    admin_list = CONFIG.get("admin_users", [])

    identity_names = {
        a.get("username", "").strip() for a in admin_list if a.get("username", "").strip().lower() == clean_user
    }
    if not identity_names:
        try:
            with get_db() as con:
                if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin_gm'").fetchone():
                    identity_names = {
                        r["account"] for r in con.execute("SELECT account FROM admin_gm WHERE LOWER(account)=?", (clean_user,))
                    }
        except Exception:
            pass
    if not identity_names:
        return False, None

    account, db_ok = lookup_game_account(clean_user, identity_names)
    if not db_ok:
        return False, None
    if account is not None:
        try:
            expected_hash = account["password_hash"]
            if password_hash:
                try:
                    client_hash = bytes.fromhex(password_hash)
                    if len(client_hash) == len(expected_hash) and secrets.compare_digest(client_hash, expected_hash):
                        return True, account["name"]
                except ValueError:
                    pass
            if password and verify_ro3_password(password, expected_hash, account["salt"]):
                return True, account["name"]
        except (TypeError, ValueError):
            pass
        return False, None

    # No game account (or no database): the credential configured for this admin.
    for admin_entry in admin_list:
        entry_user = admin_entry.get("username", "").strip().lower()
        if clean_user == entry_user:
            if admin_entry.get("password_hash") and password:
                if verify_admin_password_hash(password, admin_entry["password_hash"]):
                    return True, admin_entry.get("username", username)
            elif "password" in admin_entry and admin_entry["password"] and password:
                stored = admin_entry["password"]
                if (
                    isinstance(password, str)
                    and isinstance(stored, str)
                    and hmac.compare_digest(password.encode('utf-8'), stored.encode('utf-8'))
                ):
                    return True, admin_entry.get("username", username)

    return False, None

# --- GM tools: RO3Emu's loopback GM endpoint ---
# Upstream (aethai/ro3emu-server, src/Ro3Emu.Server/ServerHost.cs, MapPost("/ro3emu/gm")): answers only to
# loopback callers (404 otherwise), reads the account from the `account` query parameter and one `!command`
# line from the body, runs it as that account's online character, and answers 400 "not in game" when the
# account has no character online, 200 "done" otherwise. Every POST gets 503 while the game loop is not
# Accepting. Newer RO3Emu builds answer 200 with a JSON string holding the command's reply ("done" when the
# command printed nothing); older builds answer the plain "done". The panel shows whichever it gets.

GM_TIMEOUT_SECONDS = 3.0
GM_DEFAULT_ALLOWED_COMMANDS = ["warp"]
GM_DEFAULT_UNSTUCK_SCENE = 10111  # the scene in upstream docs/guide/gm-access.md's example (`!warp 10111 150 190`)
GM_SCENE_MAX = 10 ** 9
GM_COORD_LIMIT = 100000
GM_ACCOUNT_MAX_LEN = 64
def gm_unavailable():
    return tr("GM endpoint unavailable (the panel must run on the same host as RO3Emu).")


class GmRequestError(Exception):
    """A GM request refused before anything was sent to RO3Emu."""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def is_loopback_host(host):
    """True only for localhost or a loopback IP literal (127.0.0.0/8, ::1)."""
    if not host or not isinstance(host, str):
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def gm_endpoint_base():
    """scheme://host:port of RO3Emu: `ro3_base_url` when set, else the origin of the status URL."""
    source = CONFIG.get("ro3_base_url") or RO3_STATUS_URL
    try:
        parts = urllib.parse.urlsplit(str(source))
        host = parts.hostname
        parts.port  # raises ValueError on a malformed port
    except ValueError:
        host, parts = None, None
    if parts is None or parts.scheme not in ("http", "https") or not is_loopback_host(host):
        raise GmRequestError(400, tr(
            "The RO3Emu GM endpoint only accepts local connections: the panel must run on the same host "
            "as RO3Emu and 'ro3_base_url' (or 'ro3_status_url') must point to 127.0.0.1, ::1 or localhost."
        ))
    # urlsplit's hostname drops userinfo but netloc keeps it; never send a URL that carries credentials.
    if "@" in parts.netloc:
        raise GmRequestError(400, tr(
            "'ro3_base_url' (or 'ro3_status_url') must not include a username or password (user:pass@host)."
        ))
    return f"{parts.scheme}://{parts.netloc}"


def gm_allowed_commands():
    allowed = CONFIG.get("gm_allowed_commands", GM_DEFAULT_ALLOWED_COMMANDS)
    if not isinstance(allowed, list):
        return set()
    return {c for c in allowed if isinstance(c, str)}


def _gm_int(value, minimum, maximum, label):
    # bool is an int subclass; JSON true/false must not pass as 1/0.
    if type(value) is not int or not (minimum <= value <= maximum):
        raise GmRequestError(400, tr("'{label}' must be an integer between {minimum} and {maximum}.", label=label, minimum=minimum, maximum=maximum))
    return value


def _gm_args(args, allowed_keys):
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise GmRequestError(400, tr("'args' must be a JSON object."))
    extra = set(args) - set(allowed_keys)
    if extra:
        raise GmRequestError(400, tr("Arguments not allowed: {args}", args=", ".join(sorted(repr(k) for k in extra))))
    return args


def _build_warp(args):
    args = _gm_args(args, ("scene", "x", "z"))
    if "scene" not in args:
        raise GmRequestError(400, tr("warp requires 'scene' (sceneEntry)."))
    scene = _gm_int(args["scene"], 1, GM_SCENE_MAX, "scene")
    has_x, has_z = "x" in args, "z" in args
    if has_x != has_z:
        raise GmRequestError(400, tr("warp requires 'x' and 'z' together, or neither."))
    if not has_x:
        return f"!warp {scene}"
    x = _gm_int(args["x"], -GM_COORD_LIMIT, GM_COORD_LIMIT, "x")
    z = _gm_int(args["z"], -GM_COORD_LIMIT, GM_COORD_LIMIT, "z")
    return f"!warp {scene} {x} {z}"


def _build_unstuck(args):
    _gm_args(args, ())
    try:
        scene = _gm_int(CONFIG.get("gm_unstuck_scene", GM_DEFAULT_UNSTUCK_SCENE), 1, GM_SCENE_MAX, "gm_unstuck_scene")
    except GmRequestError:
        raise GmRequestError(400, tr("Invalid configuration: 'gm_unstuck_scene' must be a valid scene number."))
    return f"!warp {scene}"


GM_FIELDEXP_MAX_RULES = 10
GM_FIELDEXP_LEVEL_MAX = 999
GM_FIELDEXP_PERCENT_MAX = 10000  # upstream FieldExpRates.MaxPercent


def _build_fieldexp(args):
    # Upstream `!fieldexp` (src/Ro3Emu.Server/Game/GmCommands.cs): the field EXP rates, in memory until the next start.
    # "set" replaces the rules (groups of minLevel maxLevel percent), "clear" leaves none, "reset" brings back the
    # configured ones. The bare `!fieldexp` (show) is not offered: its answer goes to the in-game chat, not here.
    args = _gm_args(args, ("action", "rules"))
    action = args.get("action")
    if action not in ("set", "clear", "reset"):
        raise GmRequestError(400, tr("fieldexp requires 'action': set, clear or reset."))
    if action != "set":
        if "rules" in args:
            raise GmRequestError(400, tr("fieldexp {action} takes no 'rules'.", action=action))
        return f"!fieldexp {action}"
    rules = args.get("rules")
    if not isinstance(rules, list) or not 1 <= len(rules) <= GM_FIELDEXP_MAX_RULES:
        raise GmRequestError(400, tr("fieldexp set requires 'rules': 1 to {max} rules.", max=GM_FIELDEXP_MAX_RULES))
    numbers = []
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) != {"min", "max", "percent"}:
            raise GmRequestError(400, tr("Each rule needs exactly 'min', 'max' and 'percent'."))
        low = _gm_int(rule["min"], 1, GM_FIELDEXP_LEVEL_MAX, "min")
        high = _gm_int(rule["max"], 1, GM_FIELDEXP_LEVEL_MAX, "max")
        percent = _gm_int(rule["percent"], 1, GM_FIELDEXP_PERCENT_MAX, "percent")
        if low > high:
            raise GmRequestError(400, tr("A rule's 'min' level cannot be above its 'max'."))
        numbers += [low, high, percent]
    return "!fieldexp set " + " ".join(str(n) for n in numbers)


GM_QUEST_ID_MAX = 2 ** 31 - 1
GM_QUEST_ACTIONS = ("accept", "finish", "done", "drop", "repeat")


def _build_quest(args):
    # Upstream `!quest accept|finish|done|drop <taskId>` (src/Ro3Emu.Server/Game/TaskService.cs). "repeat" is a
    # panel shortcut: drop then accept, so a quest can be taken again even after it was delivered.
    args = _gm_args(args, ("action", "id"))
    action = args.get("action")
    if action not in GM_QUEST_ACTIONS:
        raise GmRequestError(400, tr("quest requires 'action': accept, finish, done, drop or repeat."))
    if "id" not in args:
        raise GmRequestError(400, tr("quest requires 'id' (the quest number)."))
    quest_id = _gm_int(args["id"], 1, GM_QUEST_ID_MAX, "id")
    if action == "repeat":
        return [f"!quest drop {quest_id}", f"!quest accept {quest_id}"]
    return f"!quest {action} {quest_id}"


# Panel command -> (allowlist names that enable it, builder). The panel builds every `!` line itself from
# validated arguments; there is no free-text passthrough. "unstuck" sends a warp, so allowing "warp" allows it.
# A builder returns one line, or a list of lines sent in order (stopping at the first failure).
GM_COMMANDS = {
    "warp": (("warp",), _build_warp),
    "unstuck": (("unstuck", "warp"), _build_unstuck),
    "fieldexp": (("fieldexp",), _build_fieldexp),
    "quest": (("quest",), _build_quest),
}


def gm_command_enabled(command):
    return command in GM_COMMANDS and bool(gm_allowed_commands().intersection(GM_COMMANDS[command][0]))


def build_gm_lines(command, args):
    """Validates a panel GM command and returns the exact `!` lines to send, or raises GmRequestError."""
    if not isinstance(command, str) or command not in GM_COMMANDS:
        raise GmRequestError(400, tr("GM command not supported by the panel."))
    if not gm_command_enabled(command):
        raise GmRequestError(400, tr("The command '{command}' is not enabled in 'gm_allowed_commands'.", command=command))
    lines = GM_COMMANDS[command][1](args)
    return lines if isinstance(lines, list) else [lines]


def validate_gm_account(account):
    if not isinstance(account, str) or not account or len(account) > GM_ACCOUNT_MAX_LEN:
        raise GmRequestError(400, tr("Invalid account."))
    if any(c.isspace() or not c.isprintable() or c in "!&=?#%" for c in account):
        raise GmRequestError(400, tr("Invalid account: it contains characters that are not allowed."))
    return account


def resolve_gm_account(account):
    """Validates an account and returns its stored name (case-insensitive lookup), or raises GmRequestError."""
    account = validate_gm_account(account)
    try:
        with get_db() as con:
            con.create_function("PY_LOWER", 1, sql_py_lower)
            rows = con.execute(
                "SELECT name FROM account WHERE PY_LOWER(name) = ? ORDER BY name = ? DESC, name LIMIT 1",
                (account.lower(), account),
            ).fetchall()
    except (sqlite3.Error, OSError):
        raise GmRequestError(503, tr("RO3Emu database unavailable."))
    if not rows:
        raise GmRequestError(404, tr("Account '{username}' does not exist", username=account))
    return rows[0]["name"]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # a redirect becomes an HTTPError; never follow it off the loopback target


# No proxies: a loopback call must never be routed through an HTTP(S)_PROXY from the environment.
_GM_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


GM_REPLY_MAX_BYTES = 64 * 1024
GM_REPLY_MAX_CHARS = 4000


def _gm_reply_text(raw):
    """RO3Emu's reply: a JSON string from newer builds, plain text from older ones."""
    text = raw.decode("utf-8", "replace")
    try:
        value = json.loads(text)
    except ValueError:
        value = text
    if not isinstance(value, str):
        value = text
    return value.strip()[:GM_REPLY_MAX_CHARS]


def send_gm_line(base_url, account, line):
    """POSTs one `!` line to RO3Emu. Returns (http_status, panel_message, outcome_for_audit, reply_text)."""
    url = f"{base_url}/ro3emu/gm?" + urllib.parse.urlencode({"account": account})
    req = urllib.request.Request(
        url,
        data=line.encode("utf-8"),
        method="POST",
        headers={"Content-Type": "text/plain; charset=utf-8", "User-Agent": "RO3AdminCPanel"},
    )
    try:
        with _GM_OPENER.open(req, timeout=GM_TIMEOUT_SECONDS) as resp:
            reply = _gm_reply_text(resp.read(GM_REPLY_MAX_BYTES))
            message = tr("Command sent. RO3Emu's reply is shown below; it also appears in the player's in-game chat.")
            return 200, message, "sent (done)", reply
    except urllib.error.HTTPError as e:
        # The status line already arrived; a body that stalls or resets must not drop the reply or the audit row.
        with e:
            try:
                body = e.read(4096).decode("utf-8", "replace")
            except Exception:
                body = ""
        if e.code == 400 and "not in game" in body:
            return 409, tr("The account is not in the game (it has no connected character)."), "failed: not in game", ""
        if e.code == 503:
            return 503, tr("RO3Emu is not accepting commands right now (the server is not in the Accepting phase)."), "failed: HTTP 503", ""
        if e.code == 404:
            return 502, gm_unavailable(), "failed: HTTP 404", ""
        return 502, tr("Unexpected RO3Emu response (HTTP {code}).", code=e.code), f"failed: HTTP {e.code}", ""
    except Exception as e:  # URLError, timeout, connection reset: never a 500 from the panel
        return 502, gm_unavailable(), f"failed: {type(e).__name__}", ""


# --- Quest debug tools: RO3Emu's loopback /ro3emu/quests ---
# GET /ro3emu/quests -> [{"id", "name"}]; GET /ro3emu/quests?account=<acct> -> {"account", "role", "quests":
# [{"id", "name", "status", "progress": [{"done", "need"}], "completed"}]}, 400 "not in game" when offline.

QUEST_CATALOG_TTL_SECONDS = 60.0
_QUEST_CATALOG_CACHE = {"key": None, "expires": 0.0, "quests": None}


def fetch_ro3_quests(base_url, account=None):
    """GET RO3Emu's /ro3emu/quests (the catalog, or one account's quests). Raises GmRequestError."""
    url = f"{base_url}/ro3emu/quests"
    if account is not None:
        url += "?" + urllib.parse.urlencode({"account": account})
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "RO3AdminCPanel"})
    try:
        with _GM_OPENER.open(req, timeout=GM_TIMEOUT_SECONDS) as resp:
            raw = resp.read(RO3_MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as e:
        with e:
            try:
                body = e.read(4096).decode("utf-8", "replace")
            except Exception:
                body = ""
        if e.code == 400 and "not in game" in body:
            raise GmRequestError(409, tr("The account is not in the game (it has no connected character)."))
        if e.code == 503:
            raise GmRequestError(503, tr("RO3Emu is not accepting commands right now (the server is not in the Accepting phase)."))
        if e.code == 404:
            raise GmRequestError(502, gm_unavailable())
        raise GmRequestError(502, tr("Unexpected RO3Emu response (HTTP {code}).", code=e.code))
    except Exception:  # URLError, timeout, connection reset: never a 500 from the panel
        raise GmRequestError(502, gm_unavailable())
    if len(raw) > RO3_MAX_RESPONSE_BYTES:
        raise GmRequestError(502, tr("The RO3Emu response exceeds the maximum allowed size."))
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise GmRequestError(502, tr("The RO3Emu response is not valid JSON."))


def _quest_int(value):
    if type(value) is not int:
        raise ValueError("expected an integer")
    return value


def normalize_quest_catalog(payload):
    """Only the known fields, with their types checked; raises ValueError/KeyError/TypeError otherwise."""
    if not isinstance(payload, list):
        raise ValueError("the quest catalog is not a list")
    return [{"id": _quest_int(q["id"]), "name": str(q.get("name") or "")} for q in payload]


def normalize_character_quests(payload):
    """Only the known fields, with their types checked; raises ValueError/KeyError/TypeError otherwise."""
    if not isinstance(payload, dict) or not isinstance(payload.get("quests"), list):
        raise ValueError("the quest state has no quest list")
    quests = []
    for q in payload["quests"]:
        progress = q.get("progress") or []
        if not isinstance(progress, list):
            raise ValueError("progress is not a list")
        quests.append({
            "id": _quest_int(q["id"]),
            "name": str(q.get("name") or ""),
            "status": str(q.get("status") or ""),
            "progress": [{"done": _quest_int(p.get("done", 0)), "need": _quest_int(p.get("need", 0))} for p in progress],
            "completed": _quest_int(q.get("completed", 0)),
        })
    return {"account": str(payload.get("account") or ""), "role": str(payload.get("role") or ""), "quests": quests}


def _audit_text(value, limit=200):
    """Untrusted text for the audit log: control characters escaped, length capped."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return "".join(c if c.isprintable() else repr(c)[1:-1] for c in text)[:limit]

# --- Gift codes (RO3Emu gift_code table) ---
# Contract: aethai/ro3emu-server docs/systems/gift-codes.md. The server creates gift_code and
# gift_code_redemption; the panel only writes gift_code (never creates or alters either table) and
# only reads the redemption table to count uses.
GIFT_CODE_MAX_LEN = 64
GIFT_NOTE_MAX_LEN = 500
# account_ban.reason is RO3Emu's column; the panel caps it like the other free-text fields it writes.
BAN_REASON_MAX_LEN = 500
# A temporary ban lasts 1 to 3650 days (issue #40); without days it is permanent (until_utc NULL).
BAN_MAX_DAYS = 3650


def gift_codes_unsupported():
    return tr("Update RO3Emu: this server does not support gift codes")


def _table_exists(con, name):
    row = con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return row is not None


def _is_whole_number(value):
    # bool is an int subclass; values beyond SQLite's signed 64-bit INTEGER would raise OverflowError on insert.
    return isinstance(value, int) and not isinstance(value, bool) and -(2 ** 63) <= value < 2 ** 63


def _optional_int(value):
    return value if _is_whole_number(value) else None


def parse_gift_items(raw):
    """Rewards of a stored code as [{"entry", "count", "name"}]; a malformed row yields no rewards."""
    try:
        pairs = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(pairs, list):
        return []
    resolve = item_resolver()
    items = []
    for pair in pairs:
        if isinstance(pair, list) and len(pair) == 2 and _is_whole_number(pair[0]) and _is_whole_number(pair[1]):
            items.append({"entry": pair[0], "count": pair[1], **resolve(pair[0])})
    return items


def gift_code_status(disabled, starts_utc, expires_utc, max_uses, uses, now):
    if disabled:
        return "disabled"
    if expires_utc is not None and now >= expires_utc:
        return "expired"
    if starts_utc is not None and now < starts_utc:
        return "scheduled"
    if max_uses and max_uses > 0 and uses >= max_uses:
        return "exhausted"
    return "active"


def validate_gift_code_body(body):
    """Returns (fields, None) for a valid create request or (None, error message)."""
    code = body.get("code")
    if not isinstance(code, str) or not (1 <= len(code.strip()) <= GIFT_CODE_MAX_LEN) or not code.strip().isprintable():
        return None, tr("The code must be between 1 and 64 characters")
    code = code.strip()

    raw_items = body.get("items")
    items_error = tr("Rewards must be a non-empty list of items with a positive item ID and count")
    if not isinstance(raw_items, list) or not raw_items:
        return None, items_error
    pairs = []
    for item in raw_items:
        if not isinstance(item, dict):
            return None, items_error
        entry, count = item.get("entry"), item.get("count")
        if not _is_whole_number(entry) or not _is_whole_number(count) or entry < 1 or count < 1:
            return None, items_error
        pairs.append([entry, count])

    max_uses = body.get("max_uses", 0)
    if not _is_whole_number(max_uses) or max_uses < 0:
        return None, tr("Max uses must be a whole number, 0 or more")
    per_account = body.get("per_account", 1)
    if not _is_whole_number(per_account) or per_account < 1:
        return None, tr("Uses per account must be a whole number, 1 or more")

    starts_utc, expires_utc = body.get("starts_utc"), body.get("expires_utc")
    for stamp in (starts_utc, expires_utc):
        if stamp is not None and (not _is_whole_number(stamp) or stamp < 0):
            return None, tr("Start and expiry must be unix timestamps in seconds")
    if starts_utc is not None and expires_utc is not None and expires_utc <= starts_utc:
        return None, tr("The expiry must be after the start")

    note = body.get("note")
    if note is not None:
        if not isinstance(note, str) or len(note.strip()) > GIFT_NOTE_MAX_LEN:
            return None, tr("The note must be text of up to 500 characters")
        note = note.strip() or None

    return {
        "code": code, "items": json.dumps(pairs, separators=(",", ":")), "max_uses": max_uses,
        "per_account": per_account, "starts_utc": starts_utc, "expires_utc": expires_utc, "note": note,
    }, None


# --- Web player portal data: account vault and web market (read-only) ---
# The web player portal (konsor-ro3 windows/player_api.py) owns account_vip, account_vault, web_market and
# web_market_claim. The panel only reads them, never creates or alters them and never moves an item: an item
# must never exist twice, and every transfer belongs to the portal's atomic code.
ACCOUNT_VAULT_PATH = re.compile(r'^/api/admin/accounts/([^/]+)/vault$')
MARKET_STATUSES = ("active", "sold", "cancelled", "all")
MARKET_SUMMARY_KEYS = ("active", "sold", "cancelled", "active_zeny", "sold_zeny", "pending_claims", "pending_zeny")


def vault_unavailable_reason():
    return tr("The account vault is not available yet: the web player portal creates it the first time it runs")


def market_unavailable_reason():
    return tr("The web market is not available yet: the web player portal creates it the first time it runs")


def account_vip_status(con, account):
    """VIP status as the web portal computes it: a GM always, else an account_vip row, else a [VIP] note."""
    none = {"is_vip": False, "vip_until": None, "source": "none"}
    if table_exists(con, "admin_gm") and con.execute(
        "SELECT 1 FROM admin_gm WHERE account = ? COLLATE NOCASE", (account,)
    ).fetchone():
        return {"is_vip": True, "vip_until": None, "source": "gm"}
    if table_exists(con, "account_vip"):
        row = con.execute(
            "SELECT is_vip, vip_until FROM account_vip WHERE account = ? COLLATE NOCASE", (account,)
        ).fetchone()
        if row and row["is_vip"]:
            until = row["vip_until"]
            if until:
                try:
                    expires = datetime.fromisoformat(str(until).replace("Z", "+00:00"))
                    if expires.tzinfo is None:
                        expires = expires.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) > expires:
                        expires = None
                except ValueError:
                    expires = True  # an unreadable date keeps the VIP, like the portal does
                if expires is None:
                    pass
                else:
                    return {"is_vip": True, "vip_until": until, "source": "vip"}
            else:
                return {"is_vip": True, "vip_until": None, "source": "vip"}
    if table_exists(con, "admin_account_meta"):
        row = con.execute("SELECT notes FROM admin_account_meta WHERE name = ?", (account,)).fetchone()
        if row and row["notes"] and "[VIP]" in str(row["notes"]).upper():
            return {"is_vip": True, "vip_until": None, "source": "note"}
    return none


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
            # The app shell must be revalidated so a deploy shows up on the next load;
            # only static images keep a one-hour cache.
            if filename in ('index.html', 'admin.js', 'admin.css', os.path.join('locales', 'es.json')):
                self.send_header('Cache-Control', 'no-cache')
            else:
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
        return get_session(self.get_session_token())

    def apply_request_language(self):
        """Language of this request: the X-Panel-Lang header, else the configured default."""
        header = self.headers.get('X-Panel-Lang')
        set_language(header if header and header.strip().lower() in SUPPORTED_LANGUAGES else None)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Panel-Lang')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()

    def do_GET(self):
        self.apply_request_language()
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
        if raw_path == '/locales/es.json':
            return self.serve_static_file(os.path.join('locales', 'es.json'), 'application/json; charset=utf-8')

        # 2. Public Config API (Branding)
        if raw_path == '/api/admin/config':
            return self.send_json(200, {
                "server_title": CONFIG.get("server_title", "RO3 Control Panel"),
                "server_subtitle": CONFIG.get("server_subtitle", "Ragnarok Online 3 Management"),
                "logo_text": CONFIG.get("logo_text", "RO3"),
                "logo_image_url": CONFIG.get("logo_image_url", ""),
                "item_icons_url": normalized_item_icons_url(CONFIG.get("item_icons_url")),
                "default_language": default_language()
            })

        # 3. Public Auth Salt Endpoint (Zero-plaintext client PBKDF2)
        if raw_path == '/api/admin/auth/salt':
            return self.handle_auth_salt(params)

        # 4. Session Verification
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
            return self.send_json(401, {"error": tr("Unauthorized. Sign in as an administrator.")})

        # 4. Stats
        if raw_path == '/api/admin/stats':
            return self.handle_stats()

        # 5. Accounts List
        if raw_path == '/api/admin/accounts':
            return self.handle_accounts_list(params)

        # 5b. Account vault (read-only): /api/admin/accounts/<name>/vault
        vault_match = ACCOUNT_VAULT_PATH.match(raw_path)
        if vault_match:
            return self.handle_account_vault(urllib.parse.unquote(vault_match.group(1)), params)

        # 5c. Web market (read-only)
        if raw_path == '/api/admin/market':
            return self.handle_market(params)

        # 6. Account Detail: /api/admin/accounts/<name>
        if raw_path.startswith('/api/admin/accounts/'):
            acc_name = raw_path[len('/api/admin/accounts/'):].strip()
            return self.handle_account_detail(acc_name)

        # 7. Character Inventory: /api/admin/characters/<role_id>/items
        if raw_path.startswith('/api/admin/characters/') and raw_path.endswith('/items'):
            role_id_str = raw_path[len('/api/admin/characters/'):-len('/items')]
            return self.handle_character_items(role_id_str)

        # 8. Audit Log
        if raw_path == '/api/admin/audit-log':
            return self.handle_audit_log(params)

        # 9. Character Mailbox (read-only): /api/admin/characters/<role_id>/mail
        mail_match = CHARACTER_MAIL_PATH.match(raw_path)
        if mail_match:
            return self.handle_character_mail(mail_match.group(1), params)

        # 10. Economy Log (read-only)
        if raw_path == '/api/admin/economy':
            return self.handle_economy(params)

        # 10b. Gift codes (RO3Emu's gift_code table; the panel creates and toggles codes)
        if raw_path == '/api/admin/gift-codes':
            return self.handle_gift_codes_list()

        # 11. Rankings (read-only)
        if raw_path == '/api/admin/rankings':
            return self.handle_rankings(params)

        # 11. Who is online (RO3Emu /ro3emu/online, loopback only)
        if raw_path == '/api/admin/online':
            return self.handle_online()

        # 11b. Quest debug tools (RO3Emu /ro3emu/quests, loopback only; needs "quest" in gm_allowed_commands)
        if raw_path == '/api/admin/quests/catalog':
            return self.handle_quests(params, catalog=True)
        if raw_path == '/api/admin/quests':
            return self.handle_quests(params, catalog=False)

        # 12. Server metrics (RO3Emu /ro3emu/metrics, loopback only)
        if raw_path == '/api/admin/metrics':
            return self.handle_metrics()

        # 13. Guilds (read-only): list and /api/admin/guilds/<id>
        if raw_path == '/api/admin/guilds':
            return self.handle_guilds_list(params)
        if raw_path.startswith('/api/admin/guilds/'):
            return self.handle_guild_detail(raw_path[len('/api/admin/guilds/'):].strip())

        # 14. Auctions (read-only)
        if raw_path == '/api/admin/auctions':
            return self.handle_auctions_list(params)

        self.send_json(404, {"error": tr("Endpoint not found")})

    def do_POST(self):
        self.apply_request_language()
        raw_path = self.path.split('?')[0].rstrip('/')
        client_ip = self.headers.get('X-Real-IP') or self.headers.get('X-Forwarded-For') or self.client_address[0]

        # 1. Login (Public)
        if raw_path == '/api/admin/login':
            return self.handle_login(client_ip)

        # 2. Logout
        if raw_path == '/api/admin/logout':
            delete_session(self.get_session_token())
            extra_headers = {
                'Set-Cookie': 'ro3_admin_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'
            }
            return self.send_json(200, {"success": True, "message": tr("Signed out successfully")}, extra_headers)

        # Protected Actions
        session = self.check_auth()
        if not session:
            return self.send_json(401, {"error": tr("Unauthorized. Sign in as an administrator.")})

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
        if raw_path == '/api/admin/characters/delete':
            return self.handle_delete_character(session['user'], client_ip)
        if raw_path == '/api/admin/accounts/save-notes':
            return self.handle_save_notes(session['user'], client_ip)
        if raw_path == '/api/admin/gm':
            return self.handle_gm(session['user'], client_ip)
        if raw_path == '/api/admin/gift-codes':
            return self.handle_gift_code_create(session['user'], client_ip)
        if raw_path == '/api/admin/gift-codes/disable':
            return self.handle_gift_code_toggle(session['user'], client_ip, disabled=True)
        if raw_path == '/api/admin/gift-codes/enable':
            return self.handle_gift_code_toggle(session['user'], client_ip, disabled=False)

        self.send_json(404, {"error": tr("Endpoint not found")})

    # --- Handlers ---

    def handle_auth_salt(self, params):
        username = (params.get('username', [''])[0] or '').strip().lower()
        salt_bytes = None
        if username:
            try:
                with get_db() as con:
                    row = con.execute("SELECT salt FROM account WHERE LOWER(name)=?", (username,)).fetchone()
                    if row and row["salt"]:
                        salt_bytes = row["salt"]
            except Exception:
                pass
        if not salt_bytes:
            # Deterministic dummy salt so nonexistent users don't reveal timing/existence differences
            salt_bytes = hashlib.sha256(f"dummy_salt:{username}".encode('utf-8')).digest()[:16]
        return self.send_json(200, {
            "ok": True,
            "salt": salt_bytes.hex(),
            "iterations": 100000
        })

    def handle_login(self, client_ip):
        throttle_ip = "ip:" + client_ip
        retry_after = LOGIN_THROTTLE.retry_after(throttle_ip)
        if retry_after > 0:
            log_audit("system", "login_throttled", "flood", f"Retry in {retry_after}s", client_ip)
            return self.send_json(
                429,
                {
                    "error": tr("Too many failed attempts. Temporary ban active. Try again in {seconds} seconds.", seconds=retry_after),
                    "retry_after": retry_after,
                    "temporary_ban": True
                },
                {"Retry-After": str(retry_after)}
            )

        body = self.read_json_body()
        if not body:
            LOGIN_THROTTLE.record_failure(throttle_ip)
            return self.send_json(400, {"error": tr("Invalid request body")})

        username = (body.get("username") or body.get("identity") or "").strip()
        password = body.get("password") or body.get("credential") or ""
        password_hash = (body.get("password_hash") or "").strip()

        if not username or (not password and not password_hash):
            LOGIN_THROTTLE.record_failure(throttle_ip)
            post_wait = LOGIN_THROTTLE.retry_after(throttle_ip)
            if post_wait > 0:
                return self.send_json(
                    429,
                    {
                        "error": tr("Too many failed attempts. Temporary ban active. Try again in {seconds} seconds.", seconds=post_wait),
                        "retry_after": post_wait,
                        "temporary_ban": True
                    },
                    {"Retry-After": str(post_wait)}
                )
            return self.send_json(400, {"error": tr("Enter a username and password")})

        if len(username) > 32:
            LOGIN_THROTTLE.record_failure(throttle_ip)
            post_wait = LOGIN_THROTTLE.retry_after(throttle_ip)
            if post_wait > 0:
                return self.send_json(
                    429,
                    {
                        "error": tr("Too many failed attempts. Temporary ban active. Try again in {seconds} seconds.", seconds=post_wait),
                        "retry_after": post_wait,
                        "temporary_ban": True
                    },
                    {"Retry-After": str(post_wait)}
                )
            return self.send_json(400, {"error": tr("The username must not exceed 32 characters")})

        if len(password) > 128 or len(password_hash) > 128:
            LOGIN_THROTTLE.record_failure(throttle_ip)
            post_wait = LOGIN_THROTTLE.retry_after(throttle_ip)
            if post_wait > 0:
                return self.send_json(
                    429,
                    {
                        "error": tr("Too many failed attempts. Temporary ban active. Try again in {seconds} seconds.", seconds=post_wait),
                        "retry_after": post_wait,
                        "temporary_ban": True
                    },
                    {"Retry-After": str(post_wait)}
                )
            return self.send_json(400, {"error": tr("The password must not exceed 128 characters")})

        # Failures are tracked per IP and per username. X-Forwarded-For can be spoofed to
        # rotate the IP key, so the username key is what stops a distributed guess on one
        # admin. Tradeoff (accepted): anyone can lock an admin out for the window.
        throttle_keys = (throttle_ip, "user:" + username.lower())
        # reserve() counts this attempt as a failure up front; success resets it below.
        retry_after = LOGIN_THROTTLE.reserve(*throttle_keys)
        if retry_after > 0:
            log_audit("system", "login_throttled", username, f"Retry in {retry_after}s", client_ip)
            return self.send_json(
                429,
                {
                    "error": tr("Too many failed attempts. Temporary ban active. Try again in {seconds} seconds.", seconds=retry_after),
                    "retry_after": retry_after,
                    "temporary_ban": True
                },
                {"Retry-After": str(retry_after)}
            )

        valid, resolved_user = authenticate_admin(username, password=password, password_hash=password_hash)
        if not valid:
            log_audit("system", "login_failed", username, "Invalid credentials", client_ip)
            failures = max(
                LOGIN_THROTTLE.failure_count("ip:" + client_ip),
                LOGIN_THROTTLE.failure_count("user:" + username.lower())
            )
            remaining = max(0, LOGIN_THROTTLE.max_failures - failures)
            if remaining > 0:
                err_text = tr("Access denied: invalid administrator credentials. {remaining} attempt(s) remaining before temporary ban.", remaining=remaining)
            else:
                err_text = tr("Access denied: invalid administrator credentials. Maximum attempts reached.")
            return self.send_json(401, {"error": err_text, "remaining_attempts": remaining})

        LOGIN_THROTTLE.reset(*throttle_keys)

        token = secrets.token_urlsafe(32)
        create_session(token, resolved_user, client_ip)

        log_audit(resolved_user, "login_success", resolved_user, "Administrative sign-in", client_ip)

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
            bans_ok = bans_supported(con)
            banned_accounts = count_active_bans(con, int(time.time()))
            
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
                "status_label": tr("Online") if server_online else tr("Offline"),
                "db_size_mb": db_size_mb,
                "backups_count": backups_count,
                "last_backup": last_backup_time
            },
            "counts": {
                "accounts": total_accounts,
                "characters": total_roles,
                "banned": banned_accounts
            },
            "bans_supported": bans_ok
        })

    # RO3Emu diagnostics are optional: any failure answers 200 {available: false, reason}.
    def handle_online(self):
        show_ips = CONFIG.get("show_player_ips") is True
        try:
            players = summarize_online(fetch_ro3_json("/ro3emu/online"), show_ips)
        except Ro3EmuUnavailable as e:
            return self.send_json(200, {"available": False, "reason": str(e)})
        except Exception:
            return self.send_json(200, {"available": False, "reason": unexpected_format()})
        return self.send_json(200, {
            "available": True,
            "show_ips": show_ips,
            "count": len(players),
            "players": players
        })

    def handle_metrics(self):
        try:
            metrics = summarize_metrics(fetch_ro3_json("/ro3emu/metrics"))
        except Ro3EmuUnavailable as e:
            return self.send_json(200, {"available": False, "reason": str(e)})
        except Exception:
            return self.send_json(200, {"available": False, "reason": unexpected_format()})
        return self.send_json(200, {"available": True, "metrics": metrics})

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
        order_sql = ACCOUNT_SORT_SQL.get(sort_by, ACCOUNT_SORT_SQL['created_desc'])

        with get_db() as con:
            con.create_function("PY_LOWER", 1, sql_py_lower)
            bans_ok = bans_supported(con)
            ban_join, ban_args, ban_cols, banned_sql = account_ban_sql(con, int(time.time()))
            if status_filter == 'banned':
                where.insert(0, banned_sql)
            elif status_filter == 'active':
                where.insert(0, f"NOT ({banned_sql})")
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            from_sql = "FROM account a LEFT JOIN admin_account_meta m ON a.name = m.name" + ban_join
            where_args = ban_args + where_args

            total = con.execute(f"SELECT COUNT(*) {from_sql} {where_sql}", where_args).fetchone()[0]
            pages = max(1, -(-total // page_size))
            offset = (page - 1) * page_size

            accounts = []
            if offset < total:
                accounts_query = f"""
                    SELECT a.name, a.created_utc, {ban_cols},
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
                a["banned_at"] = ban_time_label(a.pop("banned_utc"))
                a["banned_until"] = ban_time_label(a.pop("ban_until_utc"))

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
                "pages": pages,
                "bans_supported": bans_ok
            })

    def handle_account_detail(self, account_name):
        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]
        with get_db() as con:
            acc = con.execute("SELECT name, created_utc FROM account WHERE name=?", (account_name,)).fetchone()
            if not acc:
                return self.send_json(404, {"error": tr("Account not found")})

            meta = con.execute("SELECT notes FROM admin_account_meta WHERE name=?", (account_name,)).fetchone()
            ban = active_ban(con, account_name, int(time.time()))
            tokens = [dict(t) for t in con.execute("SELECT token, kind, expires_utc FROM auth_token WHERE account=?", (account_name,)).fetchall()]
            roles = [dict(r) for r in con.execute("SELECT * FROM role WHERE account=? AND deleted_time=0", (account_name,)).fetchall()]

            formatted_roles = [format_role(r, include_progress=True) for r in roles]

            data = {
                "name": acc["name"],
                "created_utc": acc["created_utc"],
                "is_banned": ban is not None,
                "ban_reason": ban["reason"] if ban else "",
                "banned_at": ban_time_label(ban["banned_utc"]) if ban else "",
                "banned_until": ban_time_label(ban["until_utc"]) if ban else "",
                "bans_supported": bans_supported(con),
                "notes": meta["notes"] if meta else "",
                "tokens_count": len(tokens),
                "is_admin": (acc["name"].lower() in admin_usernames),
                "characters": formatted_roles
            }
            return self.send_json(200, data)

    def handle_character_mail(self, raw_role_id, params):
        """Read-only, paginated view of one live character's role.mailbox."""
        role_id = int(raw_role_id) if POSITIVE_INT.match(raw_role_id) else 0
        if role_id <= 0 or role_id > 2 ** 63 - 1:
            return self.send_json(400, {"error": tr("Invalid character ID")})
        page = parse_int_param(params, 'page', 1, minimum=1)
        page_size = parse_int_param(params, 'page_size', MAIL_PAGE_SIZE_DEFAULT,
                                    minimum=1, maximum=MAIL_PAGE_SIZE_MAX)

        with get_db() as con:
            con.execute("PRAGMA query_only = ON")
            role = con.execute(
                "SELECT id, name, account, mailbox FROM role WHERE id = ? AND deleted_time = 0",
                (role_id,)
            ).fetchone()
        if not role:
            return self.send_json(404, {"error": tr("Character not found")})

        data = {
            "role_id": role["id"],
            "role_name": role["name"],
            "account": role["account"],
            "decodable": True,
            "page": page,
            "page_size": page_size,
        }
        try:
            letters = decode_mailbox(role["mailbox"])
        except MailboxDecodeError:
            data.update({"decodable": False, "total": 0, "pages": 1, "mails": [],
                         "message": tr("This character's mailbox could not be decoded.")})
            return self.send_json(200, data)

        resolve = item_resolver()
        # Same order RO3Emu lists mail in: newest CreatedTime first, then Id descending.
        letters = sorted(letters,
                         key=lambda m: (_json_int(m, "CreatedTime"), _json_str(m, "Id")),
                         reverse=True)
        total = len(letters)
        offset = (page - 1) * page_size
        data.update({
            "total": total,
            "pages": max(1, -(-total // page_size)),
            "mails": [format_mail(m, resolve) for m in letters[offset:offset + page_size]],
        })
        return self.send_json(200, data)

    def handle_character_items(self, role_id_str):
        """Read-only inventory of one character (SELECT only)."""
        if not (role_id_str.isascii() and role_id_str.isdigit()) or not (0 < int(role_id_str) <= MAX_SQLITE_INT):
            return self.send_json(400, {"error": tr("Invalid character ID: it must be a positive integer")})
        role_id = int(role_id_str)

        try:
            with get_db() as con:
                role = con.execute(
                    "SELECT id, name, account, deleted_time FROM role WHERE id=?", (role_id,)
                ).fetchone()
                if not role or (role["deleted_time"] or 0) != 0:
                    return self.send_json(404, {"error": tr("Character not found")})
                character = {"id": role["id"], "name": role["name"], "account": role["account"]}

                has_item_table = con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='item'"
                ).fetchone()
                if not has_item_table:
                    return self.send_json(200, {"character": character, "items": [], "total": 0, "available": False})

                rows = [dict(r) for r in con.execute(
                    "SELECT * FROM item WHERE role_id=? ORDER BY pack, sort, guid", (role_id,)
                ).fetchall()]
        except sqlite3.Error as e:
            print(f"[Inventory Error] {e}", file=sys.stderr)
            return self.send_json(500, {"error": tr("Error reading the character's inventory")})

        resolve = item_resolver()
        items = []
        for r in rows:
            entry = r.get("entry")
            pack = r.get("pack")
            items.append({
                "guid": r.get("guid"),
                "entry": entry,
                **resolve(entry),
                "stack": r.get("stack"),
                "pack": pack,
                "pack_name": tr(PACK_NAMES[pack]) if pack in PACK_NAMES else None,
                "equipped": bool(r.get("grid") or 0),
                "locked": bool(r.get("is_locked") or 0),
                "bind_type": r.get("bind_type") or 0
            })

        return self.send_json(200, {
            "character": character,
            "items": items,
            "total": len(items),
            "available": True
        })

    def handle_guilds_list(self, params):
        q = params.get('q', [''])[0].strip().lower()
        page = parse_int_param(params, 'page', 1, minimum=1)
        page_size = parse_int_param(params, 'page_size', LIST_PAGE_SIZE_DEFAULT,
                                    minimum=1, maximum=LIST_PAGE_SIZE_MAX)

        with get_db() as con:
            open_read_only(con)
            if not (table_exists(con, 'guild') and table_exists(con, 'guild_member')):
                return self.send_json(200, {"available": False, "guilds": [], **paging(0, page, page_size)})
            con.create_function("PY_LOWER", 1, sql_py_lower)

            where_sql, where_args = "", []
            if q:
                # instr() is a literal substring test, so LIKE wildcards in q never apply.
                where_sql, where_args = "WHERE instr(PY_LOWER(g.name), ?) > 0", [q]

            total = con.execute(f"SELECT COUNT(*) FROM guild g {where_sql}", where_args).fetchone()[0]
            offset = (page - 1) * page_size
            guilds = []
            if offset < total:
                rows = con.execute(
                    f"{GUILD_SUMMARY_SQL} {where_sql} GROUP BY g.id ORDER BY g.id ASC LIMIT ? OFFSET ?",
                    where_args + [page_size, offset],
                ).fetchall()
                guilds = [format_guild_summary(r) for r in rows]

        return self.send_json(200, {"available": True, "guilds": guilds, **paging(total, page, page_size)})

    def handle_guild_detail(self, raw_id):
        # ASCII digits only, within SQLite's signed 64-bit range; anything else cannot be a guild id.
        guild_id = None
        if raw_id.isascii() and raw_id.isdigit() and len(raw_id) <= 18:
            guild_id = int(raw_id)

        with get_db() as con:
            open_read_only(con)
            if not (table_exists(con, 'guild') and table_exists(con, 'guild_member')):
                return self.send_json(200, {"available": False, "guild": None, "members": []})

            row = None
            if guild_id is not None:
                row = con.execute(f"{GUILD_SUMMARY_SQL} WHERE g.id = ? GROUP BY g.id", (guild_id,)).fetchone()
            if not row:
                return self.send_json(404, {"error": tr("Guild not found")})

            members = []
            for r in con.execute(
                """
                SELECT r.id, r.name, r.account, r.career, r.level
                FROM guild_member m
                JOIN role r ON r.id = m.role_id AND r.deleted_time = 0
                WHERE m.guild_id = ?
                ORDER BY r.level DESC, r.id ASC
                """,
                (guild_id,),
            ):
                career_id = r["career"] or 1000
                members.append({
                    "role_id": r["id"],
                    "name": r["name"],
                    "account": r["account"],
                    "career": career_id,
                    "career_name": career_name(career_id),
                    "level": r["level"],
                })

        return self.send_json(200, {"available": True, "guild": format_guild_summary(row), "members": members})

    def handle_auctions_list(self, params):
        view = params.get('view', ['lots'])[0].strip().lower()
        if view not in AUCTION_VIEWS:
            view = 'lots'
        spec = AUCTION_VIEWS[view]
        table = spec['table']
        page = parse_int_param(params, 'page', 1, minimum=1)
        page_size = parse_int_param(params, 'page_size', LIST_PAGE_SIZE_DEFAULT,
                                    minimum=1, maximum=LIST_PAGE_SIZE_MAX)

        with get_db() as con:
            open_read_only(con)
            if not table_exists(con, table):
                return self.send_json(200, {"available": False, "view": view, "rows": [],
                                            **paging(0, page, page_size)})

            present = table_columns(con, table)
            select_sql = ", ".join(f"t.{c}" if c in present else f"NULL AS {c}" for c in spec['columns'])
            join_sql = ""
            if view == 'prebuy':
                select_sql += ", r.name AS role_name, r.account AS role_account"
                join_sql = "LEFT JOIN role r ON r.id = t.role_id"

            total = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            offset = (page - 1) * page_size
            rows = []
            if offset < total:
                for r in con.execute(
                    f"SELECT {select_sql} FROM {table} t {join_sql} ORDER BY t.id DESC LIMIT ? OFFSET ?",
                    (page_size, offset),
                ):
                    item = dict(r)
                    for col in spec['booleans']:
                        if item[col] is not None:
                            item[col] = bool(item[col])
                    rows.append(item)

        return self.send_json(200, {"available": True, "view": view, "rows": rows,
                                    **paging(total, page, page_size)})

    def handle_create_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": tr("Invalid request body")})

        username = (body.get("username") or "").strip()
        password = (body.get("password") or "").strip()
        notes = (body.get("notes") or "").strip()

        if not username or len(username) < 3 or len(username) > 32:
            return self.send_json(400, {"error": tr("The username must be between 3 and 32 characters")})

        if not password or len(password) < 6:
            return self.send_json(400, {"error": tr("The password must be at least 6 characters")})

        with get_db() as con:
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if existing:
                return self.send_json(400, {"error": tr("Account '{username}' already exists", username=username)})

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

        log_audit(admin_user, "create_account", username, "Account created by admin", client_ip)
        return self.send_json(200, {
            "success": True,
            "message": tr("Account '{username}' created successfully.", username=username)
        })

    def handle_update_password(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": tr("Invalid request body")})

        username = (body.get("username") or "").strip()
        new_password = (body.get("new_password") or "").strip()

        if not username:
            return self.send_json(400, {"error": tr("Username required")})

        if not new_password or len(new_password) < 6:
            return self.send_json(400, {"error": tr("The new password must be at least 6 characters")})

        with get_db() as con:
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if not existing:
                return self.send_json(404, {"error": tr("Account '{username}' does not exist", username=username)})

            pw_hash, salt = hash_ro3_password(new_password)
            con.execute("UPDATE account SET password_hash=?, salt=? WHERE name=?", (pw_hash, salt, username))
            con.execute("DELETE FROM auth_token WHERE account=?", (username,))
            # The same account signs in to the panel, so its panel sessions end too; an admin changing
            # their own password keeps the session they are using.
            current = self.get_session_token() if username.lower() == str(admin_user).lower() else None
            revoke_admin_sessions(con, username, hash_session_token(current) if current else None)
            con.commit()

        log_audit(admin_user, "update_password", username, "Password changed by admin", client_ip)
        return self.send_json(200, {
            "success": True,
            "message": tr("Password for '{username}' updated successfully. Sessions revoked.", username=username)
        })

    def handle_ban_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": tr("Invalid request body")})

        username = (body.get("username") or "").strip()
        reason = body.get("reason") or "Rule violation / Admin action"
        if not isinstance(reason, str) or len(reason.strip()) > BAN_REASON_MAX_LEN:
            return self.send_json(400, {"error": tr("The reason must be text of up to 500 characters")})
        reason = reason.strip()
        days = body.get("days")
        # bool is an int in Python: refuse it explicitly.
        if days is not None and (isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= BAN_MAX_DAYS):
            return self.send_json(400, {"error": tr("The duration must be a whole number of days from 1 to 3650")})

        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]
        if username.lower() in admin_usernames:
            return self.send_json(400, {"error": tr("An administrator account cannot be suspended.")})

        with get_db() as con:
            if not bans_supported(con):
                return self.send_json(409, {"error": bans_unsupported_error()})
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if not existing:
                return self.send_json(404, {"error": tr("Account '{username}' does not exist", username=username)})

            now = int(time.time())
            until_utc = now + days * 86400 if days is not None else None
            details = f"Reason: {reason}" + (f"; until {ban_time_label(until_utc)}" if until_utc else "")
            # One transaction: the ban row RO3Emu reads at login, the token revocation and the audit row.
            con.execute(
                "INSERT OR REPLACE INTO account_ban (account, reason, banned_utc, until_utc, banned_by)"
                " VALUES (?, ?, ?, ?, ?)",
                (username, reason, now, until_utc, admin_user),
            )
            con.execute("DELETE FROM auth_token WHERE account=?", (username,))
            insert_audit(con, admin_user, "ban_account", username, details, client_ip)
            con.commit()

        if until_utc:
            message = tr(
                "Account '{username}' suspended until {until} and its active sessions were revoked. "
                "RO3Emu refuses its sign-in until then, or until the suspension is removed.",
                username=username, until=ban_time_label(until_utc),
            )
        else:
            message = tr(
                "Account '{username}' suspended and its active sessions were revoked. "
                "RO3Emu refuses its sign-in until the suspension is removed.",
                username=username,
            )
        return self.send_json(200, {"success": True, "enforced": True, "until_utc": until_utc, "message": message})

    def handle_unban_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": tr("Invalid request body")})

        username = (body.get("username") or "").strip()
        if not username:
            return self.send_json(400, {"error": tr("Username required")})

        with get_db() as con:
            if not bans_supported(con):
                return self.send_json(409, {"error": bans_unsupported_error()})
            # No row: nothing to lift, so no audit row either (issue #39). An expired row is still removed.
            if con.execute("DELETE FROM account_ban WHERE account=?", (username,)).rowcount == 0:
                return self.send_json(404, {"error": tr("Account '{username}' is not suspended", username=username)})
            insert_audit(con, admin_user, "unban_account", username, "Suspension lifted by admin", client_ip)
            con.commit()

        return self.send_json(200, {
            "success": True,
            "message": tr("Suspension of account '{username}' removed successfully.", username=username)
        })

    def handle_delete_account(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": tr("Invalid request body")})

        username = (body.get("username") or "").strip()
        if not username:
            return self.send_json(400, {"error": tr("Username required")})

        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]
        if username.lower() in admin_usernames:
            return self.send_json(400, {"error": tr("An administrator account cannot be deleted.")})

        with get_db() as con:
            existing = con.execute("SELECT name FROM account WHERE name=?", (username,)).fetchone()
            if not existing:
                return self.send_json(404, {"error": tr("Account '{username}' does not exist", username=username)})

            con.execute("DELETE FROM account WHERE name=?", (username,))
            con.execute("DELETE FROM auth_token WHERE account=?", (username,))
            con.execute("DELETE FROM admin_account_meta WHERE name=?", (username,))
            con.execute("UPDATE role SET deleted_time=? WHERE account=?", (int(time.time()), username))
            con.commit()

        log_audit(admin_user, "delete_account", username, "Account deleted by admin", client_ip)
        return self.send_json(200, {
            "success": True,
            "message": tr("Account '{username}' and its data were deleted successfully.", username=username)
        })

    def handle_delete_character(self, admin_user, client_ip):
        """Logical delete of one character (role.deleted_time), the same delete the account delete uses.

        Guards, in order: JSON-only (a cross-site form cannot send it), per-admin rate limit, strict input,
        the character's exact name as confirmation, no characters of admin accounts, the account must be
        offline (and that must be verifiable), then one transaction that deletes and audits together."""
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            return self.send_json(415, {"error": tr("Invalid request")})

        wait = CHARACTER_DELETE_THROTTLE.reserve("admin:" + str(admin_user).lower())
        if wait:
            return self.send_json(
                429,
                {"error": tr("Too many delete attempts. Try again in {seconds} seconds.", seconds=wait), "retry_after": wait},
                {"Retry-After": str(wait)},
            )

        body = self.read_json_body()
        if not isinstance(body, dict):
            return self.send_json(400, {"error": tr("Invalid request body")})
        role_id = body.get("role_id")
        if isinstance(role_id, bool) or not isinstance(role_id, int) or not (0 < role_id <= MAX_SQLITE_INT):
            return self.send_json(400, {"error": tr("Invalid character ID")})
        typed_name = body.get("confirm_name")

        try:
            with get_db() as con:
                role = con.execute(
                    "SELECT id, name, account, deleted_time FROM role WHERE id = ?", (role_id,)
                ).fetchone()
        except sqlite3.Error as e:
            print(f"[Character Delete Error] {e}", file=sys.stderr)
            return self.send_json(500, {"error": tr("Error deleting the character")})
        if not role or (role["deleted_time"] or 0) != 0:
            return self.send_json(404, {"error": tr("Character not found")})

        if not isinstance(typed_name, str) or typed_name != role["name"]:
            return self.send_json(400, {"error": tr("Type the exact character name to confirm the deletion.")})

        account = role["account"] or ""
        admin_usernames = [a.get("username", "").strip().lower() for a in CONFIG.get("admin_users", [])]
        if account.strip().lower() in admin_usernames:
            return self.send_json(400, {"error": tr("A character of an administrator account cannot be deleted.")})

        try:
            online = account_is_online(account)
        except Exception:
            return self.send_json(503, {"error": tr("Could not verify that the account is offline, so nothing was deleted. Try again.")})
        if online:
            return self.send_json(409, {"error": tr("The account is online. Disconnect it in the game before deleting a character.")})

        try:
            with get_db() as con:
                con.execute("BEGIN IMMEDIATE")
                # name and deleted_time are part of the match: the row must still be the one that was confirmed.
                changed = con.execute(
                    "UPDATE role SET deleted_time = ? WHERE id = ? AND name = ? AND deleted_time = 0",
                    (max(1, int(time.time())), role["id"], role["name"]),
                ).rowcount
                if changed != 1:
                    return self.send_json(409, {"error": tr("The character changed while it was being deleted. Reload and try again.")})
                # Same transaction: there is no delete without its audit row.
                insert_audit(
                    con, admin_user, "delete_character", f"{role['name']} (#{role['id']})",
                    f"Character of account {account} logically deleted by admin", client_ip,
                )
        except sqlite3.Error as e:
            print(f"[Character Delete Error] {e}", file=sys.stderr)
            return self.send_json(500, {"error": tr("Error deleting the character")})

        return self.send_json(200, {
            "success": True,
            "role_id": role["id"],
            "message": tr("Character '{name}' of account '{account}' was deleted.", name=role["name"], account=account),
        })

    def handle_save_notes(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body:
            return self.send_json(400, {"error": tr("Invalid request body")})

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
            "message": tr("Notes saved successfully.")
        })

    def handle_gm(self, admin_user, client_ip):
        """Relays one allowlisted, panel-built GM command to RO3Emu's loopback endpoint. Every attempt is audited."""
        body = self.read_json_body()
        raw_account = body.get("account") if isinstance(body, dict) else None
        raw_command = body.get("command") if isinstance(body, dict) else None
        lines = None
        try:
            if not isinstance(body, dict):
                raise GmRequestError(400, tr("Invalid request body"))
            lines = build_gm_lines(raw_command, body.get("args"))
            validate_gm_account(raw_account)
            base_url = gm_endpoint_base()
            account = resolve_gm_account(raw_account)
        except GmRequestError as e:
            details = f"{_audit_text(' ; '.join(lines) if lines else raw_command)} -> rejected: {e.message}"
            log_audit(admin_user, "gm_command", _audit_text(raw_account, 80), details, client_ip)
            return self.send_json(e.status, {"error": e.message})

        # Lines go out in order with one audit row each; the first failure stops the rest.
        replies = []
        message = ""
        for line in lines:
            status, message, outcome, reply = send_gm_line(base_url, account, line)
            log_audit(admin_user, "gm_command", account, f"{line} -> {outcome}", client_ip)
            if status != 200:
                return self.send_json(status, {"error": message, "sent": line, "replies": replies})
            replies.append({"sent": line, "reply": reply})
        return self.send_json(200, {
            "success": True,
            "sent": "\n".join(r["sent"] for r in replies),
            "reply": "\n".join(r["reply"] for r in replies),
            "replies": replies,
            "message": message,
        })

    def handle_quests(self, params, catalog):
        """Quest debug tools (read side): RO3Emu's quest catalog, or one online account's quests."""
        try:
            if not gm_command_enabled("quest"):
                raise GmRequestError(403, tr("The command '{command}' is not enabled in 'gm_allowed_commands'.", command="quest"))
            if not catalog:
                validate_gm_account(params.get("account", [""])[0])
            base_url = gm_endpoint_base()
            if catalog:
                cache = _QUEST_CATALOG_CACHE
                if cache["key"] != base_url or cache["expires"] < time.monotonic():
                    quests = normalize_quest_catalog(fetch_ro3_quests(base_url))
                    cache.update(key=base_url, expires=time.monotonic() + QUEST_CATALOG_TTL_SECONDS, quests=quests)
                return self.send_json(200, {"quests": cache["quests"]})
            account = resolve_gm_account(params.get("account", [""])[0])
            return self.send_json(200, normalize_character_quests(fetch_ro3_quests(base_url, account)))
        except GmRequestError as e:
            return self.send_json(e.status, {"error": e.message})
        except (ValueError, KeyError, TypeError, AttributeError):
            return self.send_json(502, {"error": unexpected_format()})

    def handle_audit_log(self, params):
        # `limit` is the original name of `page_size` and still works.
        size_key = 'page_size' if 'page_size' in params else 'limit'
        page_size = parse_int_param(params, size_key, AUDIT_PAGE_SIZE_DEFAULT, minimum=1, maximum=AUDIT_PAGE_SIZE_MAX)
        page = parse_int_param(params, 'page', 1, minimum=1)
        with get_db() as con:
            total = con.execute("SELECT COUNT(*) FROM admin_audit_log").fetchone()[0]
            offset = (page - 1) * page_size
            logs = []
            if offset < total:
                rows = con.execute(
                    "SELECT id, admin_user, action, target, details, ip_address, created_utc"
                    " FROM admin_audit_log ORDER BY id DESC LIMIT ? OFFSET ?",
                    (page_size, offset)
                ).fetchall()
                logs = [dict(r) for r in rows]
        for entry in logs:
            entry["details"] = localize_audit_details(entry.get("details"))
        return self.send_json(200, {"logs": logs, **paging(total, page, page_size)})

    def handle_gift_codes_list(self):
        with get_db() as con:
            if not _table_exists(con, "gift_code"):
                return self.send_json(200, {"available": False, "reason": gift_codes_unsupported()})
            rows = con.execute(
                "SELECT code, items, max_uses, per_account, starts_utc, expires_utc, disabled, created_by,"
                " created_utc, note FROM gift_code ORDER BY created_utc DESC, code"
            ).fetchall()
            uses = {}
            if _table_exists(con, "gift_code_redemption"):
                for r in con.execute("SELECT code, COUNT(*) AS n FROM gift_code_redemption GROUP BY code"):
                    key = str(r["code"]).lower()
                    uses[key] = uses.get(key, 0) + r["n"]
        now = int(time.time())
        codes = []
        for r in rows:
            used = uses.get(str(r["code"]).lower(), 0)
            max_uses = _optional_int(r["max_uses"]) or 0
            starts_utc, expires_utc = _optional_int(r["starts_utc"]), _optional_int(r["expires_utc"])
            disabled = bool(r["disabled"])
            codes.append({
                "code": r["code"],
                "items": parse_gift_items(r["items"]),
                "max_uses": max_uses,
                "per_account": _optional_int(r["per_account"]) or 1,
                "starts_utc": starts_utc,
                "expires_utc": expires_utc,
                "disabled": disabled,
                "status": gift_code_status(disabled, starts_utc, expires_utc, max_uses, used, now),
                "uses": used,
                "created_by": r["created_by"],
                "created_utc": _optional_int(r["created_utc"]),
                "note": r["note"],
            })
        return self.send_json(200, {"available": True, "codes": codes})

    def handle_gift_code_create(self, admin_user, client_ip):
        body = self.read_json_body()
        if not body or not isinstance(body, dict):
            return self.send_json(400, {"error": tr("Invalid request body")})
        fields, error = validate_gift_code_body(body)
        if error:
            return self.send_json(400, {"error": error})
        code = fields["code"]
        with get_db() as con:
            if not _table_exists(con, "gift_code"):
                return self.send_json(503, {"error": gift_codes_unsupported()})
            try:
                con.execute(
                    "INSERT INTO gift_code (code, items, max_uses, per_account, starts_utc, expires_utc, disabled,"
                    " created_by, created_utc, note) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)",
                    (code, fields["items"], fields["max_uses"], fields["per_account"], fields["starts_utc"],
                     fields["expires_utc"], admin_user, int(time.time()), fields["note"]),
                )
            except sqlite3.IntegrityError:
                return self.send_json(409, {"error": tr("The gift code '{code}' already exists", code=code)})
        log_audit(admin_user, "gift_code_create", code, "Gift code created", client_ip)
        return self.send_json(200, {
            "success": True,
            "code": code,
            "message": tr("Gift code '{code}' created successfully.", code=code),
        })

    def handle_gift_code_toggle(self, admin_user, client_ip, disabled):
        body = self.read_json_body()
        if not body or not isinstance(body, dict):
            return self.send_json(400, {"error": tr("Invalid request body")})
        code = body.get("code")
        if not isinstance(code, str) or not code.strip():
            return self.send_json(400, {"error": tr("Gift code required")})
        code = code.strip()
        with get_db() as con:
            if not _table_exists(con, "gift_code"):
                return self.send_json(503, {"error": gift_codes_unsupported()})
            row = con.execute("SELECT code FROM gift_code WHERE code = ?", (code,)).fetchone()
            if not row:
                return self.send_json(404, {"error": tr("The gift code '{code}' does not exist", code=code)})
            stored = row["code"]
            con.execute("UPDATE gift_code SET disabled = ? WHERE code = ?", (1 if disabled else 0, stored))
        if disabled:
            log_audit(admin_user, "gift_code_disable", stored, "Gift code disabled by admin", client_ip)
            message = tr("Gift code '{code}' disabled.", code=stored)
        else:
            log_audit(admin_user, "gift_code_enable", stored, "Gift code enabled by admin", client_ip)
            message = tr("Gift code '{code}' enabled.", code=stored)
        return self.send_json(200, {"success": True, "code": stored, "message": message})

    def handle_account_vault(self, account_name, params):
        page = parse_int_param(params, 'page', 1, minimum=1)
        page_size = parse_int_param(params, 'page_size', LIST_PAGE_SIZE_DEFAULT, minimum=1, maximum=LIST_PAGE_SIZE_MAX)
        with get_db() as con:
            open_read_only(con)
            acc = con.execute("SELECT name FROM account WHERE name = ?", (account_name,)).fetchone()
            if not acc:
                return self.send_json(404, {"error": tr("Account not found")})
            name = acc["name"]
            vip = account_vip_status(con, name)
            if not table_exists(con, "account_vault"):
                return self.send_json(200, {
                    "available": False, "reason": vault_unavailable_reason(), "account": name, "vip": vip,
                    "items": [], **paging(0, page, page_size),
                })
            total = con.execute("SELECT COUNT(*) FROM account_vault WHERE account = ? COLLATE NOCASE", (name,)).fetchone()[0]
            rows = []
            offset = (page - 1) * page_size
            if offset < total:
                rows = con.execute(
                    "SELECT id, entry, stack, pack, is_locked, bind_type, bind_expire, deposited_by_role_id,"
                    " deposited_by_name, deposited_utc FROM account_vault WHERE account = ? COLLATE NOCASE"
                    " ORDER BY id DESC LIMIT ? OFFSET ?",
                    (name, page_size, offset),
                ).fetchall()
        resolve = item_resolver()
        items = [{
            "id": r["id"],
            "entry": r["entry"],
            **resolve(r["entry"]),
            "stack": r["stack"],
            "pack": r["pack"],
            "pack_name": tr(PACK_NAMES[r["pack"]]) if r["pack"] in PACK_NAMES else None,
            "locked": bool(r["is_locked"]),
            "bind_type": r["bind_type"] or 0,
            "bind_expire": r["bind_expire"] or 0,
            "deposited_by_name": r["deposited_by_name"],
            "deposited_by_role_id": r["deposited_by_role_id"],
            "deposited_utc": r["deposited_utc"],
        } for r in rows]
        return self.send_json(200, {
            "available": True, "account": name, "vip": vip, "items": items, **paging(total, page, page_size),
        })

    def handle_market(self, params):
        status = (params.get('status', ['active'])[0] or 'active').strip().lower()
        if status not in MARKET_STATUSES:
            return self.send_json(400, {"error": tr("Invalid market status. Allowed values: {values}", values=", ".join(MARKET_STATUSES))})
        q = params.get('q', [''])[0].strip().lower()
        page = parse_int_param(params, 'page', 1, minimum=1)
        page_size = parse_int_param(params, 'page_size', LIST_PAGE_SIZE_DEFAULT, minimum=1, maximum=LIST_PAGE_SIZE_MAX)
        empty_summary = {key: 0 for key in MARKET_SUMMARY_KEYS}
        names = load_item_names() or {}
        with get_db() as con:
            open_read_only(con)
            if not table_exists(con, "web_market"):
                return self.send_json(200, {
                    "available": False, "reason": market_unavailable_reason(), "summary": empty_summary,
                    "status": status, "listings": [], **paging(0, page, page_size),
                })
            con.create_function("PY_LOWER", 1, sql_py_lower)
            counts = {r["status"]: (r["n"], r["zeny"]) for r in con.execute(
                "SELECT status, COUNT(*) AS n, COALESCE(SUM(price_zeny), 0) AS zeny FROM web_market GROUP BY status"
            )}
            summary = dict(empty_summary)
            summary["active"], summary["active_zeny"] = counts.get("active", (0, 0))
            summary["sold"], summary["sold_zeny"] = counts.get("sold", (0, 0))
            summary["cancelled"] = counts.get("cancelled", (0, 0))[0]
            if table_exists(con, "web_market_claim"):
                pending = con.execute(
                    "SELECT COUNT(*), COALESCE(SUM(amount_zeny), 0) FROM web_market_claim WHERE is_claimed = 0"
                ).fetchone()
                summary["pending_claims"], summary["pending_zeny"] = pending[0], pending[1]

            where, args = [], []
            if status != "all":
                where.append("status = ?")
                args.append(status)
            if q:
                # instr() is a literal substring test, so LIKE wildcards in q never apply.
                clauses = [
                    "instr(PY_LOWER(seller_account), ?) > 0", "instr(PY_LOWER(seller_role_name), ?) > 0",
                    "instr(PY_LOWER(COALESCE(buyer_account, '')), ?) > 0", "instr(PY_LOWER(COALESCE(buyer_role_name, '')), ?) > 0",
                ]
                clause_args = [q, q, q, q]
                if q.isascii() and q.isdigit() and int(q) <= MAX_SQLITE_INT:
                    clauses.append("entry = ?")
                    clause_args.append(int(q))
                matching_entries = sorted(int(k) for k, v in names.items() if k.isdigit() and q in v.lower())[:500]
                if matching_entries:
                    clauses.append("entry IN (%s)" % ",".join("?" * len(matching_entries)))
                    clause_args.extend(matching_entries)
                where.append("(" + " OR ".join(clauses) + ")")
                args.extend(clause_args)
            where_sql = ("WHERE " + " AND ".join(where)) if where else ""
            total = con.execute(f"SELECT COUNT(*) FROM web_market {where_sql}", args).fetchone()[0]
            rows = []
            offset = (page - 1) * page_size
            if offset < total:
                rows = con.execute(
                    "SELECT id, seller_account, seller_role_id, seller_role_name, entry, stack, pack, price_zeny, is_locked,"
                    f" status, buyer_account, buyer_role_name, created_utc, updated_utc FROM web_market {where_sql}"
                    " ORDER BY id DESC LIMIT ? OFFSET ?",
                    args + [page_size, offset],
                ).fetchall()
        resolve = item_resolver(names)
        listings = [{
            "id": r["id"],
            "seller_account": r["seller_account"],
            "seller_role_id": r["seller_role_id"],
            "seller_role_name": r["seller_role_name"],
            "entry": r["entry"],
            **resolve(r["entry"]),
            "stack": r["stack"],
            "pack": r["pack"],
            "pack_name": tr(PACK_NAMES[r["pack"]]) if r["pack"] in PACK_NAMES else None,
            "price_zeny": r["price_zeny"],
            "locked": bool(r["is_locked"]),
            "status": r["status"],
            "buyer_account": r["buyer_account"],
            "buyer_role_name": r["buyer_role_name"],
            "created_utc": r["created_utc"],
            "updated_utc": r["updated_utc"],
        } for r in rows]
        return self.send_json(200, {
            "available": True, "summary": summary, "status": status, "listings": listings, **paging(total, page, page_size),
        })

    def handle_economy(self, params):
        account = params.get('account', [''])[0].strip()
        character = params.get('character', [''])[0].strip()
        page = parse_int_value(params.get('page', [''])[0], 1, 1, None)
        page_size = parse_int_value(params.get('page_size', [''])[0], ECONOMY_DEFAULT_PAGE_SIZE, 1, ECONOMY_MAX_PAGE_SIZE)

        try:
            from_ms = parse_iso_date_ms(params.get('from', [''])[0])
            to_ms = parse_iso_date_ms(params.get('to', [''])[0])
        except ValueError:
            return self.send_json(400, {"error": tr("Invalid date. Use the format YYYY-MM-DD.")})

        result = query_economy(account, character, from_ms, to_ms, page, page_size)
        return self.send_json(200, result)

    def handle_rankings(self, params):
        ranking_type = params.get('type', ['level'])[0].strip().lower() or 'level'
        if ranking_type not in RANKING_TYPES:
            return self.send_json(400, {
                "error": tr("Invalid ranking type. Allowed values: {values}", values=", ".join(RANKING_TYPES))
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


def warn_plaintext_admin_passwords(admin_users, stream=None):
    """Writes a warning for each admin entry that relies on a plain `password`. Returns their usernames."""
    stream = stream if stream is not None else sys.stderr
    warned = []
    for entry in admin_users or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("password") and not entry.get("password_hash"):
            name = entry.get("username", "")
            warned.append(name)
            print(
                f"[Security Warning] Admin user '{name}' uses a plain-text 'password' in the config. "
                "Generate a 'password_hash' with: python server.py --hash-password",
                file=stream
            )
    return warned


def prompt_admin_password_hash():
    """Interactive helper behind --hash-password. Returns a process exit code."""
    password = getpass.getpass("New admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password:
        print("Error: password must not be empty.", file=sys.stderr)
        return 1
    if password != confirm:
        print("Error: passwords do not match.", file=sys.stderr)
        return 1
    print(make_admin_password_hash(password))
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="RO3 CPanel administration server.")
    parser.add_argument(
        "--hash-password",
        action="store_true",
        help="Prompt for a password, print a 'password_hash' value for admin_users and exit."
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.hash_password:
        return prompt_admin_password_hash()

    print("=" * 60)
    print(f" {CONFIG.get('server_title', 'RO3 CPanel')} - White-Label Administration")
    print("=" * 60)
    print(f" Database: {DB_PATH}")
    print(f" Status Endpoint: {RO3_STATUS_URL}")
    print(f" Static Assets: {STATIC_DIR}")
    warn_plaintext_admin_passwords(CONFIG.get("admin_users", []))

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
    sys.exit(main())
