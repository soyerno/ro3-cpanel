# Gift Codes

The **Gift Codes** tab creates, lists, disables and re-enables the redeemable codes of your RO3Emu server. Players
redeem them in the game client (Settings > Redemption Code); the panel never redeems anything and stays admin-only.

## Requirements

- An RO3Emu build with gift codes ([aethai/ro3emu-server](https://github.com/aethai/ro3emu-server), see
  `docs/systems/gift-codes.md` there). RO3Emu creates the `gift_code` and `gift_code_redemption` tables.
- If the tables do not exist (older RO3Emu), the tab shows "Update RO3Emu: this server does not support gift codes"
  and the panel never creates them.

## What the panel does

| Action | Effect |
|---|---|
| Create | Inserts one row in `gift_code`. The code is trimmed, 1 to 64 characters, unique ignoring case. |
| Disable / Enable | Sets `gift_code.disabled` to `1` / `0`. A disabled code stops working at once but keeps its history. |
| List | Reads `gift_code` and counts uses from `gift_code_redemption` (read-only). |

A code has:

- **Rewards**: one or more `item ID x count` pairs. Names are shown when `item_names_file` is configured. The panel does
  not check that an item ID exists; RO3Emu refuses a code with an unknown item when someone redeems it.
  Each reward row has an item search: type part of a name (2+ characters) or an ID (1+ digit) and pick a result,
  which shows its icon and name. Results come from `GET /api/admin/items?q=<text>&limit=<n>` (admin only; limit 1 to
  50, default 20), which searches `item_catalog_file` and `item_names_file` (names from the latter win), ranked exact
  ID, name prefix, ID prefix, then name substring. Names are shown as those files hold them (they are not
  translated). Typing a plain item ID without picking a result still works.
- **Max uses** (0 = unlimited) and **uses per account** (at least 1).
- Optional **start** and **expiry** (stored as unix seconds; the start is inclusive, the expiry exclusive).
- An optional **note**.

The status column shows `Active`, `Disabled`, `Scheduled`, `Expired` or `Exhausted`.

## Audit log

Every create, disable and enable is recorded in the audit log (`gift_code_create`, `gift_code_disable`,
`gift_code_enable`). Redemptions are written by RO3Emu into `gift_code_redemption`; the panel does not log them.

## Deleting a code

The panel does not delete codes: disable them instead, so past redemptions stay traceable.
