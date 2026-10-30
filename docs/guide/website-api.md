# Website API

RO3 CPanel can feed your own website (a marketing site, a player portal) with two optional APIs. Both are
**off by default** and are completely separate from the admin API (`/api/admin/*`): different cookie,
different session table, no admin access.

| API | Paths | Login | Use |
|---|---|---|---|
| Public | `/api/public/*` | None | Server status, rankings, guilds |
| Player | `/api/player/*` | Player account | Register, sign in, "my account", change password |

Your website never connects to `ro3emu.db` itself: the panel is the only program besides RO3Emu that touches
the database, with the same PBKDF2-HMAC-SHA256 hashing (100,000 iterations, 16-byte salt) as RO3Emu.

## Configuration (`config.json`)

| Key | Default | Meaning |
|---|---|---|
| `public_api_enabled` | `false` | Turns on `/api/public/*`. |
| `public_api_cache_seconds` | `30` | How long public replies are cached in memory (and by browsers/Cloudflare). `0` disables the cache. |
| `player_api_enabled` | `false` | Turns on `/api/player/*`. |
| `player_registration_enabled` | `false` | Allows `POST /api/player/register` (needs `player_api_enabled`). |
| `player_register_per_ip_per_hour` | `3` | Registrations (plus failed captchas and taken names) allowed per IP per hour. |
| `player_session_ttl_hours` | `168` | Lifetime of a website session (sliding). |
| `api_allowed_origins` | `[]` | Website origins allowed to call the APIs from a browser, e.g. `["https://www.example.com"]`. `"*"` only applies to the public API. |
| `player_cookie_secure` | `true` | Adds `Secure` to the player cookie. Leave on: serve the API over HTTPS. |
| `player_cookie_domain` | `""` | Optional cookie `Domain`. Usually left empty. |
| `turnstile_secret_key` | `""` | When set, registration requires a valid [Cloudflare Turnstile](https://developers.cloudflare.com/turnstile/) token. |

Login throttling for players reuses `login_max_failures` and `login_window_minutes`, counted separately from
admin logins.

## Public API

All `GET`, no login, cached for `public_api_cache_seconds`. Account (sign-in) names are never returned.

- `GET /api/public/status` → `{"online", "players_online", "accounts", "characters", "guilds"}`
- `GET /api/public/rankings?type=level|zeny|power|guilds&limit=10&page=1` → `{"type", "page", "limit",
  "total", "available", "rankings": [{"rank", "id", "name", "career", "career_name", "level", "job_level", "value"}]}`
  (`limit` is capped at 50)
- `GET /api/public/guilds?page=1&page_size=20` → `{"available", "guilds": [{"id", "name", "level",
  "member_count", "total_level"}], "total", "page", "page_size", "pages"}`

## Player API

JSON bodies; the session is an `HttpOnly; SameSite=Lax` cookie (`ro3_player_session`, path `/api/player`).
From a browser, call it with `credentials: "include"`.

| Method | Path | Body | Result |
|---|---|---|---|
| `POST` | `/api/player/register` | `{"username", "password", "turnstile_token"?}` | `201`, signed in |
| `POST` | `/api/player/login` | `{"username", "password"}` | `200`, signed in |
| `POST` | `/api/player/logout` | `{}` | `200` |
| `GET` | `/api/player/session` | | `{"authenticated", "account"?}` |
| `GET` | `/api/player/me` | | Account, ban status and own characters |
| `POST` | `/api/player/change-password` | `{"current_password", "new_password"}` | `200` |

Rules:

- Usernames: 3–32 letters, digits or `_`; unique ignoring letter case; admin usernames are refused.
  Passwords: 6–128 characters. Sign-in is case-sensitive, like the game.
- A player session only reads or changes its own account. It never works on `/api/admin/*`.
- A `POST` whose `Origin` is not in `api_allowed_origins` is refused (`403`), which blocks cross-site requests.
- Changing the password deletes the account's RO3Emu `auth_token` rows, its other website sessions and its panel
  sessions; the session that made the change stays signed in. An admin password change, ban or account deletion
  ends the account's website sessions.
- Registrations and password changes are written to the audit log (`player_register`, `player_change_password`).
- Gift codes are still redeemed in the game client only.

Example (browser):

```js
const API = "https://api.example.com";
await fetch(`${API}/api/player/login`, {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ username, password }),
});
const me = await (await fetch(`${API}/api/player/me`, { credentials: "include" })).json();
```

## Deployment

Serve the panel on a hostname under the same site as your website (for example `www.example.com` and
`api.example.com`) so the `SameSite=Lax` cookie is sent. With Cloudflare Tunnel:

```yaml
ingress:
  - hostname: api.example.com
    path: ^/api/(public|player)/
    service: http://localhost:8095
  - hostname: admin.example.com
    service: http://localhost:8095   # protect with Cloudflare Access
  - service: http_status:404
```

The player API reads the visitor IP from `CF-Connecting-IP`, `X-Real-IP` or `X-Forwarded-For`. Bind the panel to
`127.0.0.1` (or firewall port 8095) so those headers cannot be forged by connecting directly.
