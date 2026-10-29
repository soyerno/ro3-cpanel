# Account Screen

Pressing **Manage** on a row of the **Accounts** list opens that account on its own screen (it replaces the old pop-up). The list stays where it was: its search, page and scroll position are restored when you come back.

## Layout

- **Header:** breadcrumb (Accounts > name), a **Back to accounts** button, the account name with its badges (Active or Banned with reason and end date, GM or Admin, VIP) and its basics (registered, sessions).
- **Summary** (left, sticky on wide screens): number of characters, highest level, total Zeny, and the **GM administrative notes** with **Save Notes**, the only primary button on the screen.
- **Tabs:**
  - **Characters:** one card per character with class, level, Zeny and other currencies, location, last login and stats, plus **View inventory**, **View mail** and the **GM tools** (teleport, unstuck).
  - **Vault:** VIP status and the items in the shared account vault (read-only, paginated). See [Account Vault and Web Market](vault-market.md).
  - **Security & moderation:** **Change password**, **Suspend account** (permanent, or for a number of days) or **Remove suspension**, and, separated at the bottom, the **Danger zone** with **Delete account** (it asks you to type the account name). Admin accounts cannot be suspended or deleted from here.

Password, suspension and deletion keep using small confirmation dialogs: a dialog is the right shape for a confirmation. After each action the screen reloads the account; after a deletion you go back to the list.

## Links, history and keyboard

- Every account has its own address: `#/accounts/<name>` (and `#/accounts/<name>/vault` or `/security` for a tab). You can bookmark or share it; the browser Back and Forward buttons work.
- Tabs follow the usual pattern: Left and Right arrows, Home and End move between them.
- **Esc** returns to the list when you are not typing in a field and no dialog is open.
- If the notes have unsaved changes, leaving the screen asks for confirmation.
- On a phone the screen is a single column and the tabs scroll sideways inside their own strip; the page never scrolls sideways.
