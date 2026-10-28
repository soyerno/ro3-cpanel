# Working on RO3 CPanel

Guidelines for developers and AI agents working on this repository.

## Guiding Principles

1. **Zero External Dependencies:**
   The backend must run on standard Python 3.10+ without requiring third-party libraries from PyPI (`pip`). Do not introduce dependencies unless absolutely essential and discussed.

2. **RO3Emu 1:1 Compatibility:**
   Password hashing, session handling, character schemas, career/class IDs, and database structures must remain 100% faithful to the official `ro3emu-server` specification ([aethai/ro3emu-server](https://github.com/aethai/ro3emu-server)).
   - Hashing is strictly PBKDF2-HMAC-SHA256 with 100,000 iterations and 16-byte random salt.
   - Database operations must respect SQLite WAL mode concurrency.

3. **White-Label Integrity:**
   Never hardcode server names, private URLs, personal domains, or credentials in templates or source code. All branding must flow dynamically through `config.json` and `/api/admin/config`.

4. **Before Pushing:**
   Always run the test suite:
   ```bash
   python -m unittest discover -s tests -v
   ```
