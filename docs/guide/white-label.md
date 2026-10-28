# White-Label Customization Guide

RO3 CPanel is fully white-label ready. You can rebrand the panel for your own Ragnarok Online 3 private server without modifying any HTML or JavaScript files.

## Configuration Keys

The server exposes `GET /api/admin/config`, which the frontend automatically queries upon page load.

In `config.json` (or `.env`):

| Key | Description | Default |
|---|---|---|
| `server_title` | The main title of your server/panel | `"RO3 Control Panel"` |
| `server_subtitle` | The subtitle displayed below the title | `"Ragnarok Online 3 Server Management"` |
| `logo_text` | Text or acronym displayed in the logo square | `"RO3"` |
| `admin_users` | List of admin accounts allowed to log in | `[{"username": "admin", "password": "..."}]` |
| `session_ttl_hours` | How long a login session remains valid | `24` |

### Example Rebranding for "Midgard RO3"

```json
{
  "server_title": "Midgard RO3 - Staff Panel",
  "server_subtitle": "Servidor Privado Ragnarok Origin PC",
  "logo_text": "MRO3",
  "host": "0.0.0.0",
  "port": 8095,
  "ro3_db_path": "D:/RO3Emu/data/ro3emu.db",
  "admin_users": [
    {
      "username": "gm_midgard",
      "password": "MidgardSuperSecret2026!"
    }
  ]
}
```

The frontend immediately renders "Midgard RO3 - Staff Panel", "MRO3", and applies the title to the browser tab, header, and login screen.

## Styling & Theme Customization

Colors and theme properties are defined as CSS custom variables in `public/admin.css`:

```css
:root {
  --bg-dark: #0a0e17;       /* Main page background */
  --bg-card: #121824;       /* Card background */
  --border-color: #26344d;  /* Outline border */
  --gold: #e5c07b;          /* Accent gold */
  --gold-glow: rgba(229, 192, 123, 0.25);
  --danger: #e06c75;        /* Ban / Delete button red */
  --success: #98c379;       /* Active badge green */
  --info: #61afef;          /* Informational badge blue */
}
```

You can change `--gold` to any color matching your server's brand identity.
