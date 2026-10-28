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

## 5. GM Tools

`POST /api/admin/gm` (the **GM Tools** panel in the account detail view) relays a GM command to RO3Emu's
loopback endpoint `POST /ro3emu/gm?account=<account>`. Upstream behavior (`aethai/ro3emu-server`,
`src/Ro3Emu.Server/ServerHost.cs`): the endpoint answers only to loopback callers, runs the `!command` line
as that account's online character on the game loop, and replies `400 "not in game"` when the account has no
character online, `200 "done"` otherwise, and `503` to every POST while the game loop is not accepting.
The command's output goes to the player's in-game chat, not to the HTTP response, so `done` means
"accepted", not "succeeded" (an unknown scene, for example, only produces a usage line in chat). When
RO3Emu's `Ro3Emu:GmAccounts` list is not empty, the loopback tool only runs for the accounts on that list
(upstream `docs/guide/gm-access.md`).

Safeguards in the panel:

- **Same host only.** The target is `ro3_base_url` when set, otherwise the origin of `ro3_status_url`. The
  panel refuses to send anything unless that host is `localhost` or a loopback address (`127.0.0.0/8`,
  `::1`). A target URL with userinfo (`user:password@host` or `name@host`) is refused. Requests go out
  without environment proxies and redirects are never followed.
- **Command allowlist.** `gm_allowed_commands` (default `["warp"]`) lists the panel commands an admin may
  use. The panel builds every `!` line itself from validated integers (`warp`: `scene`, optional `x` and
  `z`); there is no free-text passthrough. `unstuck` sends `!warp <gm_unstuck_scene>` (default `10111`, the
  scene from upstream's example, with no coordinates so the player lands on the map's spawn point) and is
  enabled by `"unstuck"` or `"warp"`. Names without a panel builder are ignored.
- **Economy commands stay off.** RO3Emu also has `item`, `mail`, `zeny`, `lvl` and similar commands. The
  panel has no builder for them on purpose: exposing them would let every panel admin mint items, currency
  or levels. Do not add such commands without a separate review.
- **Audit.** Every attempt, allowed, rejected or failed, is written to `admin_audit_log` with action
  `gm_command`, the admin user, the target account, the exact command line and its outcome, and the client
  IP.
- **Errors.** `400` invalid or non-allowlisted command / non-loopback target / target with userinfo, `404`
  unknown account, `409` account not in game, `503` RO3Emu not accepting commands, `502` endpoint
  unreachable, timed out (3 s), `404` from RO3Emu, or any other unexpected answer. When RO3Emu sends an
  error status but its body stalls or breaks, the panel maps the status code alone (an unread body cannot
  match `not in game`), still answers, and still writes the audit row.

RO3Emu has no kick, ban or mute command, so the panel cannot offer them.
