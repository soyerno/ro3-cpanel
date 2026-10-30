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

### Account bans

Bans require an RO3Emu with account bans. RO3Emu owns the `account_ban` table and refuses the sign-in of
an account with an active ban; the panel is the only writer of that table and never creates or alters it.

```
account_ban(account TEXT NOT NULL PRIMARY KEY, reason TEXT NOT NULL DEFAULT '',
            banned_utc INTEGER NOT NULL, until_utc INTEGER, banned_by TEXT)
```

- **Ban** (`POST /api/admin/accounts/ban`, body `{"username", "reason", "days"}`) writes the row (`banned_utc` =
  now in unix seconds, `until_utc` = now + `days` × 86400 for a temporary ban or `NULL` without `days`,
  `banned_by` = the admin user), deletes the account's `auth_token` rows and
  writes the `ban_account` audit row, all in one SQLite transaction. Banning a banned account replaces its row. The
  `reason` is text of up to 500 characters (otherwise `400`); it is stored in RO3Emu's table.
- **Unban** (`POST /api/admin/accounts/unban`, body `{"username"}`) deletes the row and writes the
  `unban_account` audit row in one transaction. With no row for that name it answers `404` "Account
  '{username}' is not suspended" and writes nothing. It also lifts the ban of a deleted account.
- **Temporary ban:** `days` is a whole number from 1 to 3650 (otherwise `400`); the form offers permanent, 1, 7
  and 30 days. RO3Emu lets the account sign in again once `until_utc` has passed; the list, the account sheet and
  the audit row show the end date.
- **Active ban:** the row exists and `until_utc` is `NULL` or later than now; a row with a past `until_utc` shows
  as not banned. The accounts list (`status=banned|active`),
  the account sheet and the dashboard count read only active rows.
- **Older RO3Emu** (no `account_ban` table): ban and unban answer `409` with "Update RO3Emu: this server does
  not support account bans", and change nothing. Reads show every account as not banned, and the accounts
  list, the account sheet and `/api/admin/stats` return `"bans_supported": false`.
- Players already in the world are not kicked by a ban; it applies from their next sign-in.
- **Deleting an account keeps its ban:** `account_ban` keeps the row, and RO3Emu refuses that name (in any
  letter case) if it is registered again, so a player cannot escape a ban by recreating the account. The
  accounts list and the counts only show bans of existing accounts.
- **Old panel bans are not migrated.** Before this change a ban was only `admin_account_meta.is_banned`, which
  RO3Emu never read. The panel no longer reads that flag (the column stays, and the table keeps the account
  notes). After updating RO3Emu, ban those accounts again. To list them:
  `SELECT name, ban_reason FROM admin_account_meta WHERE is_banned = 1;`

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

## 4. Admin Login Hardening

### Login throttling

`POST /api/admin/login` counts **failed** attempts in a sliding window, tracked separately per client IP (`ip:<address>`) and per username (`user:<name>`, case-insensitive):

| Key | Default | Meaning |
|---|---|---|
| `login_max_failures` | `5` | Failed attempts allowed inside the window before blocking. |
| `login_window_minutes` | `15` | Length of the sliding window. |

Once either key reaches the limit, every login for that IP or username (even with the correct password) is rejected with `429 Too Many Requests` and a `Retry-After` header (seconds) until enough failures leave the window. Throttled attempts are recorded as `login_throttled` in the audit log and do not extend the block. A successful login clears the counters for its IP and username. Counters live in memory and reset when the server restarts.

**Tradeoff (accepted):** the client IP is taken from `X-Real-IP` / `X-Forwarded-For` when present, and those headers can be spoofed unless a reverse proxy overwrites them. The per-username key is what stops a guessing attack that rotates IPs, but it also means anyone who knows an admin username can lock that admin out for up to `login_window_minutes`. Keep admin usernames non-obvious and, when exposed to the internet, run behind a proxy that sets `X-Real-IP` itself (see [hosting.md](hosting.md)).

### Hashed admin passwords (`password_hash`)

Entries in `admin_users` can store a PBKDF2-HMAC-SHA256 hash instead of a plain-text `password`, using the same parameters as RO3Emu (100,000 iterations, 16-byte random salt, 32-byte key). Generate one without starting the server:

```bash
python3 server.py --hash-password
```

The command asks for the password twice and prints a single line in the format `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`. Store it in `config.json`:

```json
"admin_users": [
  { "username": "admin", "password_hash": "pbkdf2_sha256$100000$<salt_hex>$<hash_hex>" }
]
```

- When `password_hash` is present, `password` is ignored for that entry.
- Plain `password` keeps working, but the server prints a `[Security Warning]` on startup for each entry that has no `password_hash`.
- All secret comparisons use constant-time `hmac.compare_digest`.

### One password for the game, the web and the panel

The game account (the `account` table of the RO3Emu database) is the single source of truth for an admin's password:

- If an admin's username is also a game account, **only that account's password** signs in to the panel. The `password` / `password_hash` in `admin_users` is ignored for that admin, so the game, the web and the panel always share one password.
- The admin's game account is the one named **exactly** like the admin (the spelling in `admin_users` or `admin_gm`). An account that differs only by letter case (for example `Admin` next to the admin `admin`) is another person: it cannot sign in as the admin and does not lock the admin out.
- The password in `admin_users` applies only to an admin that has **no** game account (for example the first `admin` before any account exists), to an account row with no usable password hash or salt, and while there is no RO3Emu database or `account` table.
- If the database exists but cannot be read (locked, corrupt), the login is **refused** instead of falling back to the config password.
- Admins that come from the `admin_gm` table sign in with their game account password.
- Changing a password in the panel (Accounts, Update password) writes the new hash to the `account` table, which RO3Emu and the web read. It also ends the account's game sessions and its panel sessions. An admin changing their own password keeps the session they are using; their other sessions end.
- **Recovery:** because the config password no longer works for an admin that has a game account, an admin who forgets the game password cannot use the config as a back door. Another admin resets it from the panel, or it is reset directly in the database.

## 5. Audit Logging

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
character online, `200` otherwise, and `503` to every POST while the game loop is not accepting.
Newer RO3Emu builds put the command's reply in the `200` body as a JSON string (`"done"` when the command
printed nothing); the panel returns it as `reply` and shows it under the GM tools. Older builds answer a
plain `done` and the output only goes to the player's in-game chat, so `done` means "accepted", not
"succeeded" (an unknown scene, for example, only produces a usage line in chat). When
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
  `fieldexp` (off unless listed) sends RO3Emu's `!fieldexp set <min> <max> <percent> ...`, `clear` or `reset` from
  validated integers (1 to 10 rules, levels 1 to 999, percent 1 to 10000): it changes the EXP of open-field kills
  for every player until RO3Emu restarts, so enable it only for admins who may do that.
  `quest` (off unless listed) sends RO3Emu's `!quest accept|finish|done|drop <id>` for a validated quest id
  (1 to 2147483647); `repeat` sends `!quest drop <id>` then `!quest accept <id>`, stops at the first failure and
  audits each line. It changes the character's quest progress (and delivering a quest may grant its rewards), so
  it is a debug tool: enable it only on test servers or for admins who may do that.
- **Quest reads.** `GET /api/admin/quests/catalog` (cached for 60 s) and `GET /api/admin/quests?account=<account>`
  proxy RO3Emu's loopback `GET /ro3emu/quests` with the same same-host rules. They answer `403` unless `quest`
  is in `gm_allowed_commands` (the panel then hides the Quests section), `409` when the account has no character
  online, and `502` when RO3Emu is unreachable or answers an unexpected shape.
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

RO3Emu has no kick or mute command, so the panel cannot offer them. Bans go through the `account_ban`
table instead ([Account bans](#account-bans)).
