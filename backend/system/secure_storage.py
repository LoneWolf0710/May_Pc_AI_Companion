"""Secure Storage — DPAPI-encrypted API key storage.

Per MAY_FINAL_ARCHITECTURE.md Part 5 (Immune System):
All API keys encrypted at rest using Windows hardware-backed DPAPI.
On non-Windows systems, falls back to base64-encoded storage with a warning.

DPAPI (Data Protection API) is Windows-native encryption that:
- Is bound to the user's login credentials
- Cannot be decrypted by other users or the OS installer
- Uses hardware-backed keys from the TPM when available
- Requires no password or key management from the application

Storage format: ~/.may/secure_keys/{provider}.enc
Each file contains: DPAPI-encrypted bytes of the UTF-8 encoded key string.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path

logger = logging.getLogger("may.system.secure_storage")

_SECURE_DIR = Path(os.path.expanduser("~")) / ".may" / "secure_keys"
_PLAINTEXT_FALLBACK = Path(os.path.expanduser("~")) / ".may" / ".api_keys.json"

# Try importing win32crypt for DPAPI (Windows only)
_dpapi_available = False
if platform.system() == "Windows":
    try:
        import win32crypt
        _dpapi_available = True
    except ImportError:
        logger.warning(
            "win32crypt not available — API keys will be stored in base64 (not encrypted). "
            "Install pywin32 for DPAPI encryption: pip install pywin32"
        )


def _ensure_dir():
    """Create the secure storage directory."""
    _SECURE_DIR.mkdir(parents=True, exist_ok=True)


def store_api_key(provider: str, key: str) -> None:
    """Encrypt and store an API key for a provider.

    Uses DPAPI on Windows, base64 encoding on other platforms.
    Also migrates from the legacy plaintext .api_keys.json if it exists.
    """
    _ensure_dir()
    target = _SECURE_DIR / f"{provider}.enc"

    if _dpapi_available and sys.platform == "win32":
        # DPAPI encryption — hardware-backed, user-bound
        try:
            encrypted = win32crypt.CryptProtectData(
                key.encode("utf-8"),
                f"May AI - {provider}",
                None, None, None,
                0,  # CRYPTPROTECT_LOCAL_MACHINE = 0 (user-bound)
            )
            target.write_bytes(encrypted)
            logger.info("Stored API key for '%s' (DPAPI encrypted)", provider)
        except Exception as e:
            logger.error("DPAPI encryption failed for '%s': %s", provider, e)
            # Fallback to base64
            _store_base64(provider, key, target)
    else:
        _store_base64(provider, key, target)

    # Remove from legacy plaintext store if present
    _migrate_from_plaintext(provider)


def _store_base64(provider: str, key: str, target: Path) -> None:
    """Store API key as base64 (non-Windows fallback, NOT encrypted)."""
    encoded = base64.b64encode(key.encode("utf-8")).decode("ascii")
    payload = json.dumps({"provider": provider, "key": encoded, "encoding": "base64"})
    target.write_text(payload, encoding="utf-8")
    logger.warning(
        "Stored API key for '%s' as base64 (NOT encrypted — install pywin32 for DPAPI)",
        provider,
    )


def retrieve_api_key(provider: str) -> str | None:
    """Retrieve an API key for a provider.

    Checks DPAPI-encrypted file first, then base64 fallback, then legacy plaintext.
    Returns None if no key is found.
    """
    target = _SECURE_DIR / f"{provider}.enc"

    if target.exists():
        return _read_encrypted(provider, target)

    # Check legacy plaintext store
    return _read_plaintext(provider)


def _read_encrypted(provider: str, path: Path) -> str | None:
    """Read an encrypted or base64-encoded key file."""
    try:
        raw = path.read_bytes()

        if _dpapi_available and sys.platform == "win32":
            # Try DPAPI decryption first
            try:
                _, decrypted = win32crypt.CryptUnprotectData(
                    raw, None, None, None, 0
                )
                return decrypted.decode("utf-8")
            except Exception:
                pass  # Not DPAPI format — try base64

        # Try base64 format
        try:
            payload = json.loads(raw.decode("utf-8"))
            if payload.get("encoding") == "base64":
                return base64.b64decode(payload["key"]).decode("utf-8")
        except (json.JSONDecodeError, KeyError):
            pass

        # Raw bytes (DPAPI on a different machine?) — try direct decode
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            pass

        logger.warning("Could not decrypt key for '%s'", provider)
        return None
    except Exception as e:
        logger.warning("Failed to read key for '%s': %s", provider, e)
        return None


def _read_plaintext(provider: str) -> str | None:
    """Read from legacy plaintext .api_keys.json."""
    if not _PLAINTEXT_FALLBACK.exists():
        return None
    try:
        with open(_PLAINTEXT_FALLBACK, "r") as f:
            keys = json.load(f)
        key = keys.get(provider)
        if key:
            logger.info("Read legacy plaintext key for '%s' — migrate with store_api_key()", provider)
            return key
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _migrate_from_plaintext(provider: str) -> None:
    """Remove a key from the legacy plaintext store after migrating to secure storage."""
    if not _PLAINTEXT_FALLBACK.exists():
        return
    try:
        with open(_PLAINTEXT_FALLBACK, "r") as f:
            keys = json.load(f)
        if provider in keys:
            del keys[provider]
            with open(_PLAINTEXT_FALLBACK, "w") as f:
                json.dump(keys, f, indent=2)
            logger.info("Migrated '%s' from plaintext to secure storage", provider)
    except (json.JSONDecodeError, OSError):
        pass


def delete_api_key(provider: str) -> bool:
    """Delete an API key from secure storage and legacy store."""
    target = _SECURE_DIR / f"{provider}.enc"
    deleted = False

    if target.exists():
        target.unlink()
        deleted = True
        logger.info("Deleted secure key for '%s'", provider)

    # Also remove from legacy store
    if _PLAINTEXT_FALLBACK.exists():
        try:
            with open(_PLAINTEXT_FALLBACK, "r") as f:
                keys = json.load(f)
            if provider in keys:
                del keys[provider]
                with open(_PLAINTEXT_FALLBACK, "w") as f:
                    json.dump(keys, f, indent=2)
                deleted = True
        except (json.JSONDecodeError, OSError):
            pass

    return deleted


def get_key_status() -> dict:
    """Get status of all stored keys.

    Returns dict with encryption method, stored providers, and security info.
    """
    providers = []
    if _SECURE_DIR.exists():
        for f in _SECURE_DIR.glob("*.enc"):
            providers.append(f.stem)

    # Check legacy store
    legacy_providers = []
    if _PLAINTEXT_FALLBACK.exists():
        try:
            with open(_PLAINTEXT_FALLBACK, "r") as f:
                keys = json.load(f)
            legacy_providers = list(keys.keys())
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "encryption": "dpapi" if _dpapi_available else "base64",
        "encryption_secure": _dpapi_available,
        "stored_providers": providers,
        "legacy_providers": legacy_providers,
        "storage_dir": str(_SECURE_DIR),
        "migration_needed": bool(legacy_providers),
    }


def migrate_all_from_plaintext() -> dict:
    """Migrate all keys from legacy plaintext store to secure storage.

    Returns dict with migration results.
    """
    if not _PLAINTEXT_FALLBACK.exists():
        return {"migrated": 0, "failed": 0, "providers": []}

    try:
        with open(_PLAINTEXT_FALLBACK, "r") as f:
            keys = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"migrated": 0, "failed": 0, "providers": []}

    migrated = []
    failed = []

    for provider, key in keys.items():
        if key:
            try:
                store_api_key(provider, key)
                migrated.append(provider)
            except Exception as e:
                logger.error("Failed to migrate '%s': %s", provider, e)
                failed.append(provider)

    return {
        "migrated": len(migrated),
        "failed": len(failed),
        "providers": migrated,
        "failed_providers": failed,
    }
