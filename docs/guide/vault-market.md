# Account Vault and Web Market

Two read-only views of data that the **web player portal** (the Konsor `player_api`) keeps in the RO3Emu database. The panel only reads these tables. It never creates or alters them and never moves an item or any Zeny: an item must never exist twice, so every transfer stays inside the portal's own atomic code.

If a table does not exist yet (the portal creates them the first time it runs a vault or market feature), the view says so and nothing is written.

## Account vault

In **Accounts**, open an account and use the **Vault** button. It shows:

- the account's VIP status and where it comes from: **GM** (the account is in `admin_gm`, and a GM always has VIP), **VIP** (a row in `account_vip` that has not expired), **VIP (note)** (a `[VIP]` tag in the account notes) or **Not VIP**;
- every item deposited in the shared vault, newest first: item (name when `item_names_file` is set), quantity, bag, locked, who deposited it and when.

API: `GET /api/admin/accounts/<account>/vault?page=&page_size=` (default 50, max 200). `404` if the account does not exist.

The per-character inventory is the existing **Inventory** button on each character of the same account detail.

## Web market

The **Market** tab shows the player-to-player listings of the web portal (`web_market`):

- summary cards: active listings, sold listings, Zeny in active listings, and the Zeny sellers still have to claim (`web_market_claim`);
- a status filter (Active, Sold, Cancelled, All) and a search over seller, buyer, character names, item name and item id (a literal, case-insensitive substring; `%` and `_` are ordinary characters);
- a paginated table, newest first.

API: `GET /api/admin/market?status=active|sold|cancelled|all&q=&page=&page_size=`. An unknown `status` is a `400`.

## Not connected to the in-game auction

The **Auctions** tab shows RO3Emu's own auction house (dungeon loot, guild and system auctions with bids and mail delivery), which the game server owns. The web market is a separate system that moves items by writing the game database directly, so the two are deliberately not connected: two systems writing the ownership of the same items is how items get duplicated.
