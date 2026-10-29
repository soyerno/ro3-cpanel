# Language

The panel is English by default and ships a Spanish translation. Each admin switches language from the **EN | ES**
selector on the login screen or in the panel header. The choice is stored in that browser (`localStorage`) and
applies immediately, including messages returned by the API.

## Default language

Browsers that have not picked a language start in `default_language` from `config.json`:

```json
{ "default_language": "es" }
```

Valid values are `"en"` (default) and `"es"`. Anything else falls back to `"en"`.

## How it works

- Static text and dynamic UI text use the English string as the key. `public/locales/es.json` maps each English
  string to its Spanish text. A string missing from the file is shown in English.
- The browser sends the chosen language in the `X-Panel-Lang` request header. The server translates its own error
  and status messages (and the audit-log view) for that request, using the dictionary in `server.py`.
- Player data (account, character, guild and item names) is never translated. Career and scene names come from the
  built-in tables or `names_file` ([Career and Scene Names](names.md)) and are not translated either; only their
  `Class <id>` / `Map <id>` fallbacks are.
- Audit rows are stored in English. Rows written before the panel was bilingual keep their original Spanish text.

## Adding a translation key

1. Write the English text in the code (`t('...')` in `admin.js`, `data-i18n` in `index.html`, `tr('...')` in
   `server.py`).
2. Add the Spanish text to `public/locales/es.json` (client) or `ES_MESSAGES` in `server.py` (server), keeping the
   same `{placeholders}`.
3. `python -m unittest discover -s tests` fails if a key is missing or a placeholder does not match.
