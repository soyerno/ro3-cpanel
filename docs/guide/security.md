# Security Architecture

RO3 CPanel is designed to operate safely directly on the game server host or over reverse proxies.

## 1. Password Hashing (RO3Emu Parity)

RO3Emu stores passwords in its `account` SQLite table using `PBKDF2-HMAC-SHA256`:

- **Algorithm:** PBKDF2 with HMAC-SHA256
- **Iterations:** 100,000
- **Salt:** 16 cryptographically random bytes (`os.urandom(16)`)
- **Key Length:** 32 bytes (256 bits)

When changing a user's password or creating a new account from RO3 CPanel, the password is derived using this exact function:

```python
hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, 32)
```

This guarantees 100% interoperability with RO3Emu (`Ro3Emu.Server.exe`) game logins.

## 2. Token Invalidation

Whenever a password is changed or an account is banned/suspended:
- All active records in `auth_token` for that account are deleted, which revokes its existing login tokens.

> **Known limitation:** a ban is stored only in the panel's `admin_account_meta` table. RO3Emu's login
> (`/sdk/login`) does not read it, so a banned player can sign in again and get fresh tokens until RO3Emu
> enforces account bans. Tracked in [#1](https://github.com/soyerno/ro3-cpanel/issues/1).

## 3. Session Security

- **Session Tokens:** 256-bit cryptographically secure random tokens (`secrets.token_urlsafe(32)`).
- **Cookies:** Marked `HttpOnly` and `SameSite=Lax` to prevent XSS exfiltration and CSRF.
- **Revocation by config:** a stored session is accepted only while its user is still listed in `admin_users`; removing an admin from the config ends their sessions on the next request.
- **Sliding Window:** Sessions expire after `session_ttl_hours` of inactivity. To avoid a write to the live RO3Emu database on every request, the stored expiry is only renewed once it would move by at least 5 minutes, so the effective idle timeout can be up to 5 minutes shorter.
- **Persistence:** Sessions are stored in the panel-owned `admin_session` table of the RO3Emu database, so
  a restart does not log admins out. A session stays valid until its TTL runs out.
- **Hashed at rest:** Only the SHA-256 hash of the token is stored. The raw token is never written to the
  database or to logs.
- **Cleanup:** Logout and expiry delete the row. Expired rows are also purged at startup and on every login.
- **Fallback:** If the database file is missing, sessions are kept in memory (`ACTIVE_SESSIONS`, also keyed
  by token hash) so the panel still works; those sessions are lost on restart.

```sql
CREATE TABLE IF NOT EXISTS admin_session (
    token_hash TEXT PRIMARY KEY,   -- sha256 hex of the session token
    admin_user TEXT NOT NULL,
    ip_address TEXT DEFAULT '',
    created_utc INTEGER NOT NULL,  -- unix seconds
    expires_utc INTEGER NOT NULL   -- unix seconds, slides with activity (at most one write per 5 minutes)
);
```

## 4. Audit Logging

Every state-modifying action is permanently recorded in the `admin_audit_log` table:

```sql
CREATE TABLE IF NOT EXISTS admin_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_user TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT DEFAULT '',
    details TEXT DEFAULT '',
    ip_address TEXT DEFAULT '',
    created_utc DEFAULT CURRENT_TIMESTAMP
);
```

The audit trail cannot be modified or cleared from the web interface.
