# Panel URLs

Each panel tab has its own address, so a section can be bookmarked, shared, reloaded and reached with the browser's back and forward buttons.

| Tab | Standalone (`server.py`) | Under `/admin/` |
| --- | --- | --- |
| Dashboard | `/dashboard` | `/admin/dashboard` |
| Accounts | `/accounts` | `/admin/accounts` |
| Rankings | `/rankings` | `/admin/rankings` |
| Guilds | `/guilds` | `/admin/guilds` |
| Economy | `/economy` | `/admin/economy` |
| Auctions | `/auctions` | `/admin/auctions` |
| Gift codes | `/giftcodes` | `/admin/giftcodes` |
| Market | `/market` | `/admin/market` |
| Audit log | `/audit` | `/admin/audit` |

- An open account keeps its hash route on the Accounts path: `/accounts#/accounts/<name>`, `/accounts#/accounts/<name>/vault`. An account hash on any other path opens the Accounts tab and moves the URL to `/accounts`.
- An empty or unknown path opens Accounts and the address bar is corrected to `/accounts`.

## Serving deep links

`server.py` answers every tab path, with or without the `/admin` prefix, with the panel page (`index.html`). A trailing slash (`/market/`) redirects to `/market` so the page's relative assets (`admin.js`, `admin.css`) still load. `/api/...` paths, unknown paths and files with an extension keep their usual JSON errors.

Behind a reverse proxy that forwards every path to `server.py` (see [Hosting](hosting.md)) nothing else is needed. A host that serves `public/` itself must answer each tab path with `index.html`, for example in nginx:

```nginx
location ^~ /admin {
    try_files $uri $uri/ /admin/index.html =404;
}
```

The panel finds its base from the address it was opened at: the part before a known tab slug or a file name (`/admin/market` and `/admin/index.html` both give `/admin/`).

## Extending routes: `window.CPANEL_ROUTES`

`admin.js` exposes a small hook for pages that embed the panel and add their own tabs or translated URLs. Call it before the session check finishes, for example from a script that runs right after `admin.js`. Every method that changes routes returns the hook, so calls can be chained.

| Method | Effect |
| --- | --- |
| `registerRoute(slug, tabId, onShow)` | `<base><slug>` opens tab `tabId`. `onShow(tabId)`, when given, runs every time that tab is shown: click, back/forward, deep link. |
| `setPreferredSlug(tabId, slug)` | The slug written to the address bar for that tab. The slug is also accepted on load; the tab id keeps working and is corrected to the preferred slug. |
| `setBase(path)` | Use this base (`'/admin/'`) instead of detecting it. |
| `tabForSlug(slug)` | The tab a slug opens, or `null`. |
| `slugForTab(tabId)` | The slug written for a tab. |
| `base()` | The base in use. |
| `refresh()` | Re-read the address bar and open its tab (after changing slugs once the panel is already showing). |

A tab is any sidebar button `<button class="tab-btn" data-tab="<id>">`; its id is already a valid slug. A view added as `<section id="tab-view-<id>">` is shown only on its own tab and hidden on every other one.

```js
window.CPANEL_ROUTES
  .registerRoute('funciones', 'features', showFeatures)
  .setPreferredSlug('features', 'funciones')
  .setPreferredSlug('accounts', 'cuentas')
  .setPreferredSlug('market', 'mercado')
  .setPreferredSlug('audit', 'auditoria');
```

With that, `/admin/mercado` opens Market, a click on Market writes `/admin/mercado`, and an old `/admin/market` link still works.
