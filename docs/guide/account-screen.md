# Account Screen

Pressing **Manage** on a row of the **Accounts** list opens that account on its own screen (it replaces the old pop-up). The list stays where it was: its search, page and scroll position are restored when you come back.

## Layout

- **Header:** breadcrumb (Accounts > name), a **Back to accounts** button, the account name with its badges (Active or Banned with reason and end date, GM or Admin, VIP), a **VIP** checkbox, and its basics (registered, sessions). Ticking the checkbox grants the web portal VIP (permanent, or until a future end date the account already had); clearing it revokes it. Both ask for confirmation, write the portal's `account_vip` table (created with the portal's schema if it is missing) and leave a `vip_grant` / `vip_revoke` audit row. A revoked VIP stays as an `is_vip = 0` row, so the portal's login-streak reward does not grant it back. GM accounts are always VIP, so their checkbox is locked.
- **Summary** (left, sticky on wide screens): number of characters, highest level, total Zeny, and the **GM administrative notes** with **Save Notes**, the only primary button on the screen.
- **Tabs:**
  - **Characters:** one card per character with class, level, Zeny and other currencies, location, last login and stats, plus **View inventory**, **View mail** and the **GM tools** (teleport, unstuck, and, when `"quest"` is in `gm_allowed_commands`, the **Quests** debug section).
  - **Vault:** VIP status and the items in the shared account vault (read-only, paginated). See [Account Vault and Web Market](vault-market.md).
  - **Security & moderation:** **Change password**, **Suspend account** (permanent, or for a number of days) or **Remove suspension**, and, separated at the bottom, the **Danger zone** with **Delete account** (it asks you to type the account name). Admin accounts cannot be suspended or deleted from here.

Password, suspension and deletion keep using small confirmation dialogs: a dialog is the right shape for a confirmation. After each action the screen reloads the account; after a deletion you go back to the list.

## Links, history and keyboard

- Every account has its own address: `#/accounts/<name>` (and `#/accounts/<name>/vault` or `/security` for a tab). You can bookmark or share it; the browser Back and Forward buttons work.
- Tabs follow the usual pattern: Left and Right arrows, Home and End move between them.
- **Esc** returns to the list when you are not typing in a field and no dialog is open.
- If the notes have unsaved changes, leaving the screen asks for confirmation.
- On a phone the screen is a single column and the tabs scroll sideways inside their own strip; the page never scrolls sideways.
