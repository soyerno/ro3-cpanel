# Career and Scene Names

The panel shows each character's class (career) and location (scene) by name. The RO3Emu database stores only numeric
ids (`role.career`, `role.scene_entry`), so the panel maps them to names with two dictionaries in `server.py`:
`CAREER_MAP` and `SCENE_MAP`.

- A known id renders as its name, for example `1100` -> `Swordman`.
- An unknown id renders safely as `Class <id>` or `Map <id>` (`Clase <id>` / `Mapa <id>` when the panel is in Spanish).

## Built-in names

The built-in dictionaries cover the base careers and a set of town and field scenes, plus the story and tutorial
dungeon scenes listed in the RO3Emu server docs (`docs/systems/dungeon-inventory.md` in
[aethai/ro3emu-server](https://github.com/aethai/ro3emu-server)).

The RO3Emu config tables (`data/config/JobConfig.json`, `data/config/MapConfig.json`) do not contain display text: their
`_iName` fields are localization string ids, resolved by the client's localization data. The panel does not read the
client data. Use `names_file` to add the names your server needs.

## Verification status

Not every built-in name has an upstream source, because the names live in the game client's localization data and not
in the RO3Emu server repository.

- **From the game's own data**: the careers `1000` to `6400` that have a skill tree (job id and job name, 27 jobs) and the
  72 town, field and dungeon-entrance scenes (scene id and English name). Note that `1300` is Lord Knight and `1400`
  Rune Knight, `4300` is High Priest and `4400` Arch Bishop: the transcended second jobs end in `300`, the third jobs in
  `400`. RO3Emu's `CombatTableRulesTests.cs` calls `1400` "Lord Knight" and `4400` "High Priest" in comments, but the same
  test asserts that those jobs are job rank 5, the third job, like the Warlock `2400`.
- **From RO3Emu's tests / docs**: careers `1310` Paladin, `2400` Warlock and `6100` Merchant; scene `10101` Izlude; and
  the story/tutorial dungeon scenes listed in `docs/systems/dungeon-inventory.md`.
- **Unverified**: careers without a skill tree in the game data (`2210` Sage, `3210` Bard, `3211` Dancer, `4210` Monk,
  `5210` Rogue, `5400` Guillotine Cross). Correct anything with `names_file` if your server shows something else.
- An id that is not listed shows as `Class <id>` or `Map <id>`.

Currencies are named through the item catalog (`item_catalog_file`), because a currency id is an item id (item `1` is
Zeny): the character card lists every currency with its image and name, and currencies without an entry show as
`Currency <id>`.

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
