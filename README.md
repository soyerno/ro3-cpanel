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
    <td width="50%" valign="top"><b>Complete account management</b><br>Real-time search, player character sheets (Base/Job Lv, stats, Zeny, Diamonds, coordinates), account creation, password resets, suspension, and audit logs.</td>
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
| **2** | **Copy and edit your configuration:**<br><code>cp config.example.json config.json</code><br>Point <code>ro3_db_path</code> to your <code>ro3emu.db</code> and set your admin username and password. |
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
    └── Live Status Ping  ──► [RO3Emu Server (Port 5380)]
```

---

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

---

## Documentation Guides

- [Hosting & Deployment Guide](docs/guide/hosting.md) (Windows Scheduled Tasks, Linux systemd, Docker, Nginx, Cloudflare)
- [White-Label Customization Guide](docs/guide/white-label.md) (Theming, server branding, logo customization)
- [Career and Scene Names](docs/guide/names.md) (Class and map names, custom `names_file`)
- [Security Architecture](docs/guide/security.md) (PBKDF2 hashing, session tokens, audit trail)
- [Testing Guide](docs/guide/testing.md) (Running the automated unit test suite)

---

## Contributing

Contributions are welcome! Please read [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for code conventions, zero-dependency requirements, and pull request guidelines.

---

## License

Released under the [MIT License](LICENSE).
