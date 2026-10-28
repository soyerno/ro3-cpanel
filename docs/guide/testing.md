# Testing RO3 CPanel

The test suite runs against Python's built-in `unittest` framework with zero external dependencies.

## Running Tests

From the repository root:

```bash
python -m unittest discover -s tests -v
```

## Test Structure

- `tests/test_crypto.py`: Verifies PBKDF2 hashing, salt generation, and verification parity.
- `tests/test_api.py`: Tests the HTTP server, configuration endpoints, and static asset delivery.
- `tests/test_auth.py`: Tests authentication, session creation, rejection of unauthorized users, and protected route access.
