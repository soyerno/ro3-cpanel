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
- **Sliding Window:** Sessions expire after `session_ttl_hours` of inactivity.

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
