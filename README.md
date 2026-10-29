<p align="center">
  <img src="docs/assets/hero.svg" alt="RO3 CPanel: Web Administration Control Panel for RO3Emu" width="100%">
</p>

<p align="center">
  <a href="#start-in-three-steps"><img src="docs/assets/button-quickstart.svg" alt="Quick Start" height="44"></a>
  &nbsp;
  <a href="#why-ro3-cpanel"><img src="docs/assets/button-features.svg" alt="Features" height="44"></a>
  &nbsp;
  <a href="https://github.com/aethai/ro3emu-server"><img src="docs/assets/button-ro3emu.svg" alt="RO3Emu Server" height="44"></a>
</p>

<p align="center">
  <a href="https://github.com/soyerno/ro3-cpanel/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/soyerno/ro3-cpanel/ci.yml?branch=main&label=tests&color=d8b46a&labelColor=1b2740" alt="Tests"></a>
  <img src="https://img.shields.io/badge/python-3.10+-3fb950?labelColor=1b2740" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/dependencies-0-3fb950?labelColor=1b2740" alt="Zero Dependencies">
  <a href="https://github.com/aethai/ro3emu-server"><img src="https://img.shields.io/badge/companion-RO3Emu-d8b46a?labelColor=1b2740" alt="Companion for RO3Emu"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-8b949e?labelColor=1b2740" alt="MIT License"></a>
</p>

Modern, lightweight, and customizable white-label web administration control panel (CPanel) for **Ragnarok Online 3 / Ragnarok Origin PC (`RO3Emu`)** servers ([aethai/ro3emu-server](https://github.com/aethai/ro3emu-server)).

Inspired by classic Ragnarok Online control panels (FluxCP / CeresCP), built with a dark fantasy Nordic aesthetic, zero external Python dependencies, and a responsive single-page client.

> 📖 **Para leer la documentación completa en español, consulta [README.es.md](README.es.md).**

---

## Why RO3 CPanel

<table>
  <tr>
    <td width="50%" valign="top"><b>White-label out of the box</b><br>Rebrand your entire panel for your private server in seconds. Server title, subtitle, logo, and footer are dynamically populated from <code>config.json</code> without touching frontend code.</td>
    <td width="50%" valign="top"><b>Zero external dependencies</b><br>Runs on standard Python 3.10+ (<code>http.server</code>, <code>sqlite3</code>, <code>hashlib</code>). No <code>pip install</code>, no Node.js build step, no npm packages to audit.</td>
  </tr>
  <tr>
    <td width="50%" valign="top"><b>1:1 RO3Emu compatibility</b><br>Password hashing matches RO3Emu's PBKDF2-SHA256 (100,000 iterations + 16-byte random salt) exactly. Sessions and tokens are cleanly revoked upon password updates or bans.</td>
    <td width="50%" valign="top"><b>Complete account management</b><br>Real-time search, player character sheets (Base/Job Lv, stats, Zeny and other currencies, coordinates, read-only inventory), account creation, password resets, suspension, and audit logs.</td>
  </tr>
  <tr>
    <td colspan="2" valign="top"><b>Economy log viewer</b><br>Read-only, paginated view of RO3Emu's <code>economy_entry</code> ledger joined with <code>operation_receipt</code> (the FluxCP zeny/pick log equivalent) to audit dupes and disputes. Filter by account, character, and UTC date range (<code>GET /api/admin/economy?account=&amp;character=&amp;from=YYYY-MM-DD&amp;to=YYYY-MM-DD&amp;page=&amp;page_size=</code>). Queries are parameterized and run on a <code>query_only</code> connection; databases without the economy tables report <code>"available": false</code>.</td>
  </tr>
</table>

---

## Start in three steps

| Step | Action |
|:---:|---|
| **1** | **Clone the repository:**<br><code>git clone https://github.com/soyerno/ro3-cpanel.git</code><br><code>cd ro3-cpanel</code> |
| **2** | **Copy and edit your configuration:**<br><code>cp config.example.json config.json</code><br>Point <code>ro3_db_path</code> to your <code>ro3emu.db</code> and set your admin username and password.<br>Recommended: run <code>python3 server.py --hash-password</code> and store the printed value as <code>password_hash</code> instead of a plain <code>password</code>. Login throttling is tuned with <code>login_max_failures</code> (default 5) and <code>login_window_minutes</code> (default 15). See the <a href="docs/guide/security.md">Security guide</a>. |
| **3** | **Launch the server:**<br>Windows: <code>run.cmd</code> &nbsp;·&nbsp; Linux: <code>./run.sh</code> &nbsp;·&nbsp; Docker: <code>docker compose up -d</code><br>Open your browser at <a href="http://localhost:8095">http://localhost:8095</a>. |

---

## Architecture & Integration

RO3 CPanel operates as an autonomous daemon connecting to your `RO3Emu` database:

```
[Browser]
    │  (HTTP / HTTPS)
    ▼
[Nginx / Reverse Proxy] (Optional)
    │  (Port 8095)
    ▼
[RO3 CPanel (server.py)]
    ├── Serves Embedded SPA (public/index.html, admin.css, admin.js)
    ├── REST API (/api/admin/*)
    ├── SQLite Concurrency ──► [ro3emu.db (WAL Mode)]
    ├── Live Status Ping  ──► [RO3Emu Server (Port 5380)] /ro3emu/status
    └── Diagnostics       ──► [RO3Emu Server (Port 5380)] /ro3emu/online, /ro3emu/metrics (loopback only)

    ├── Live Status Ping  ──► [RO3Emu Server (Port 5380)]
    └── GM Tools (loopback) ──► [RO3Emu POST /ro3emu/gm]
```

### Online players and server metrics

The dashboard shows RO3Emu's uptime, connections, players in the world, memory, database statements and error counts, plus an **En línea** table (account, character, map, position). The panel reads them from RO3Emu's `/ro3emu/metrics` and `/ro3emu/online`, through `GET /api/admin/metrics` and `GET /api/admin/online`.

- **Loopback only:** RO3Emu answers those two endpoints only to requests from `127.0.0.1` / `::1`. Run the panel on the same host as RO3Emu (or proxy to its loopback). Otherwise the dashboard shows "No disponible" and the rest of the panel keeps working.
- **Base URL:** the panel derives the RO3Emu address from `ro3_status_url` (it removes `/ro3emu/status`). Set `ro3_base_url` (for example `http://127.0.0.1:5380`) to override it.
- **Player IPs:** RO3Emu reports each session's remote address. The panel hides it unless `show_player_ips` is the JSON boolean `true` (default `false`).
- **Uptime** is the time since RO3Emu's metrics epoch started (process start, or the last `/ro3emu/metrics/reset`).
- Each request keeps the 2 s timeout and has a 1 MB response cap; any failure answers `200 {"available": false, "reason": "..."}`.

### Read-only character mail

In the account sheet, **Ver correo** on a character card shows that character's mailbox, 10 letters per page.
The panel never writes it. The endpoint is `GET /api/admin/characters/<role_id>/mail?page=1&page_size=20`
(admin session required; `page_size` is 1–100, default 20).

- RO3Emu has no mail table: each character's mail lives in the `role.mailbox` BLOB, a `MailService.Mailbox`
  JSON document (`NextId`, `Letters`). The panel loads only that column, with `PRAGMA query_only = ON`, and decodes it in Python.
- Letters are sorted newest first (`CreatedTime`, then `Id`, descending), as the game lists them.
- Each mail returns `id`, `category`, `title`, `abstract`, `content`, `sender`, `sender_id`, `template_id`,
  `important_type`, `created_at` / `remove_at` (ISO 8601 UTC; `remove_at` is `null` when the letter never expires),
  `read`, `claimed`, `attachments` (`entry`, `count`, `bind`), `items` (`guid`, `entry`, `stack`), `currency` (`entry`, `amount`) and `attachment_count`.
  Internal keys (`DeliveryKey`, `ContentParams`) and the raw blob are never returned.
- Expired letters that the game has not purged yet are still listed; compare `remove_at` with the current time.
- A missing or empty mailbox is an empty list. A blob that is not valid UTF-8 JSON in this shape returns `200` with
  `"decodable": false` and no mails. A non-numeric or zero id returns `400`; an unknown or deleted character returns `404`.

### GM tools

The account detail view has a **GM Tools** panel (warp and unstuck) that relays commands to RO3Emu's
loopback GM endpoint (`POST /ro3emu/gm?account=<account>`). RO3Emu only answers that endpoint on loopback,
so it **only works when the panel runs on the same host as RO3Emu** (not from a separate machine or a
bridged Docker container). Only commands listed in `gm_allowed_commands` (default `["warp"]`) are sent, the
panel builds every `!` line itself from validated numbers, and every attempt is written to the audit log.
See [Security Architecture](docs/guide/security.md#5-gm-tools).

### Account bans

Suspending an account requires an RO3Emu with account bans. The panel writes the ban to RO3Emu's
`account_ban` table, and RO3Emu refuses that account's sign-in until the suspension is removed. The
account's game sessions are revoked at once. With an older RO3Emu (no `account_ban` table) the panel
refuses to ban and asks you to update RO3Emu; it never creates the table.

Accounts suspended by an older panel were only flagged in the panel and are not carried over: after
updating RO3Emu, suspend them again. See [Security Architecture](docs/guide/security.md#account-bans).

---

## Character Inventory

Each character card in the account sheet has a **Ver inventario** button that lists the character's items, grouped by bag (`pack`: Items, Equipment, Cards, Totems, Emblems, Currency, Career special). The view is read-only: the panel only runs `SELECT` queries against the `item` table.

- API: `GET /api/admin/characters/<role_id>/items` (requires an admin session). Returns `{character, items, total, available}`; each item has `guid`, `entry`, `name`, `stack`, `pack`, `pack_name`, `equipped`, `locked`, `bind_type`. `available` is `false` when the database has no `item` table yet.
- Item names are not stored in SQLite (they live in the server's config tables). To show names, point `item_names_file` in `config.json` to a JSON object that maps item config ids (`entry`) to names:

  ```json
  { "100001": "Red Potion", "200002": "Sword" }
  ```

  Leave it empty (`""`, the default) to disable names. When the file is missing or invalid, a warning is printed once to stderr and items are shown as `#<entry>`.

## Rankings

The **🏆 Rankings** tab shows read-only, paginated leaderboards. Deleted characters (`deleted_time != 0`) are always excluded.

```
GET /api/admin/rankings?type=level|zeny|power|guilds&limit=20&page=1
```

| `type` | Ordering | `value` |
|---|---|---|
| `level` (default) | Base level, then job level, then base EXP | Base level |
| `zeny` | Zeny held (currency item `1` in `role.currency`) | Zeny amount |
| `power` | Leaderboard power stored by RO3Emu in `role.emblems` (`Power.CurrentNormal + Power.CurrentSeason`) | Power total |
| `guilds` | Active members, then summed member base level | Member count |

- `limit` defaults to `20` and is clamped to `1..100`; `page` starts at `1`. Each row carries its global `rank`.
- Character rows include `id`, `name`, `account`, `career`, `career_name`, `level` and `job_level`; guild rows include `id`, `name`, `member_count` and `total_level`.
- `power` lists only characters whose power has been published by the game server at least once; blobs that cannot be parsed are skipped.
- `zeny` and `power` are decoded in Python from a single pass over the non-deleted characters (only the needed columns are loaded), so their cost grows with the number of characters.
- On databases without the `guild` / `guild_member` tables, `type=guilds` returns an empty list with `"available": false` instead of an error.
- An unknown `type` returns `400`. The endpoint requires an authenticated admin session, like every other `/api/admin/*` read.

## Read-only guild and auction views

The **🛡️ Gremios** and **💰 Subastas** tabs show RO3Emu data without ever writing it: every query runs on a connection with `PRAGMA query_only = ON`, and all values are bound parameters. Lists are paginated (`page`, `page_size`; default 50, max 200). If the database has no such tables, the endpoints answer `200` with `"available": false`.

| Endpoint | Returns |
| --- | --- |
| `GET /api/admin/guilds?q=&page=&page_size=` | Guilds by id: `id`, `name`, `level`, `member_count`, `total_level`. `q` is a case-insensitive literal substring of the name. |
| `GET /api/admin/guilds/<id>` | The guild plus its members: `role_id`, `name`, `account`, `career`, `career_name`, `level`. `404` if the guild does not exist. |
| `GET /api/admin/auctions?view=lots\|prebuy&page=&page_size=` | Newest first. `lots` (`auction_item`): `id`, `source_key`, `settled`, `auction_type`, `run_id`, `end_time`. `prebuy` (`auction_prebuy`): `id`, `role_id`, `role_name`, `auction_type`, `src_type`, `item_id`, `quantity`, `unit_price`, `currency`, `processed`, `paused`. |

Only relational columns are read, as defined in `ro3emu-server` (`Accounts/Persistence/GuildStorePlans.cs`, `CoreSchemaPlans.cs`, `AuctionItemColumns.cs`). The one exception is the guild `level`, read from the `Level` field of the `guild.state` JSON (`GuildStore.State`); it is `null` when the blob cannot be read. Member counts and level totals include only characters that are not deleted. `auction_item` columns added by later RO3Emu migrations read as `null` on databases that predate them; values such as `auction_type` and `end_time` are shown as stored.

---

## Documentation Guides

- [Hosting & Deployment Guide](docs/guide/hosting.md) (Windows Scheduled Tasks, Linux systemd, Docker, Nginx, Cloudflare)
- [White-Label Customization Guide](docs/guide/white-label.md) (Theming, server branding, logo customization)
- [Gift Codes](docs/guide/gift-codes.md) (Create and manage redeemable codes from the panel)
- [Language](docs/guide/language.md) (English by default, Spanish translation, switching from the panel)
- [Career and Scene Names](docs/guide/names.md) (Class and map names, custom `names_file`)
- [Security Architecture](docs/guide/security.md) (PBKDF2 hashing, session tokens, audit trail)
- [Testing Guide](docs/guide/testing.md) (Running the automated unit test suite)

---

## Contributing

Contributions are welcome! Please read [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for code conventions, zero-dependency requirements, and pull request guidelines.

---

## License

Released under the [MIT License](LICENSE).
