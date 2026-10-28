# Career and Scene Names

The panel shows each character's class (career) and location (scene) by name. The RO3Emu database stores only numeric
ids (`role.career`, `role.scene_entry`), so the panel maps them to names with two dictionaries in `server.py`:
`CAREER_MAP` and `SCENE_MAP`.

- A known id renders as its name, for example `1100` -> `Swordman`.
- An unknown id renders safely as `Clase <id>` or `Mapa <id>`.

## Built-in names

The built-in dictionaries cover the base careers and a set of town and field scenes, plus the story and tutorial
dungeon scenes listed in the RO3Emu server docs (`docs/systems/dungeon-inventory.md` in
[aethai/ro3emu-server](https://github.com/aethai/ro3emu-server)).

The RO3Emu config tables (`data/config/JobConfig.json`, `data/config/MapConfig.json`) do not contain display text: their
`_iName` fields are localization string ids, resolved by the client's localization data. The panel does not read the
client data. Use `names_file` to add the names your server needs.

## `names_file`

Set `names_file` in `config.json` to the path of a JSON file. Its entries override and extend the built-in names when
the panel starts. An empty value (`""`) or a missing key disables it.

```json
{
  "names_file": "./names.json"
}
```

A relative path is resolved from the directory the panel is started in.

### Format

```json
{
  "careers": {
    "1100": "Swordman",
    "9001": "My Custom Class"
  },
  "scenes": {
    "10111": "Starting Town",
    "424242": "Event Arena"
  }
}
```

- `careers` and `scenes` are both optional objects.
- Keys are integer ids written as strings. Keys that are not integers are skipped.
- Values are non-empty strings. Other values are skipped.
- A file entry replaces the built-in name for the same id.

### Errors

The panel never stops because of `names_file`. When the file is missing, is not valid JSON, or is not a JSON object,
the panel writes a `[Config Warning] names_file: ...` line to stderr and keeps the built-in names. Skipped entries are
counted in a warning line too.

Restart the panel after editing the file; names are loaded once at startup.
