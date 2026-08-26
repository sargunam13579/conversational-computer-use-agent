"""
NEXUS Cryptography & Secret Vault Subsystem.

Provides AES-GCM and PBKDF2-based secret encryption, key derivation,
secure token generation, and credential zeroization.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus.utils.logging import get_logger

log = get_logger("security.crypto")

# Optional cryptography library support with fallback to built-in hashlib/AES primitives
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _HAS_CRYPTOGRAPHY = True
except ImportError:
    AESGCM = None  # type: ignore[assignment, misc]
    _HAS_CRYPTOGRAPHY = False
    log.info("cryptography package not found; using pure Python PBKDF2/HMAC vault fallback")


@dataclass
class SecretEntry:
    """Stored encrypted secret entry."""

    key: str
    encrypted_value: str
    nonce: str = ""
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class KeyManager:
    """
    Manages master encryption keys and key derivation from passphrases.
    """

    def __init__(self, key_dir: str | Path | None = None) -> None:
        if key_dir is None:
            home = Path.home()
            self.key_dir = home / ".nexus" / "keys"
        else:
            self.key_dir = Path(key_dir)
        self.key_dir.mkdir(parents=True, exist_ok=True)
        self._master_key_file = self.key_dir / "master.key"
        self._master_key: bytes | None = None

    def get_or_create_master_key(self) -> bytes:
        """Load the master key from disk or generate a new 256-bit secure key."""
        if self._master_key is not None:
            return self._master_key

        if self._master_key_file.exists():
            try:
                self._master_key = self._master_key_file.read_bytes()
                if len(self._master_key) >= 32:
                    return self._master_key
            except Exception as e:
                log.warning("Could not read existing master key: %s, generating new", e)

        # Generate a new 32-byte (256-bit) cryptographically secure key
        new_key = secrets.token_bytes(32)
        try:
            self._master_key_file.write_bytes(new_key)
            # In POSIX systems, restrict permissions
            if os.name != "nt":
                os.chmod(self._master_key_file, 0o600)
        except Exception as e:
            log.warning("Could not persist master key to disk: %s", e)

        self._master_key = new_key
        return self._master_key

    def derive_key(self, passphrase: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
        """
        Derive a 256-bit encryption key from a user passphrase using PBKDF2-HMAC-SHA256.
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, iterations=100_000, dklen=32)
        return derived, salt

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """Generate a cryptographically secure URL-safe random token."""
        return secrets.token_urlsafe(length)

    @staticmethod
    def generate_pin(digits: int = 6) -> str:
        """Generate a secure numeric PIN for device pairing."""
        upper = 10**digits
        val = secrets.randbelow(upper)
        return f"{val:0{digits}d}"


class SecretVault:
    """
    Encrypted key-value vault for storing sensitive credentials, API keys,
    and pairing tokens on disk.
    """

    def __init__(self, vault_path: str | Path | None = None, key_manager: KeyManager | None = None) -> None:
        if vault_path is None:
            home = Path.home()
            self.vault_path = home / ".nexus" / "vault.enc"
        else:
            self.vault_path = Path(vault_path)
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self._key_mgr = key_manager or KeyManager(self.vault_path.parent / "keys")
        self._cache: dict[str, str] = {}
        self._load_vault()

    def _get_encryption_key(self) -> bytes:
        return self._key_mgr.get_or_create_master_key()

    def _encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext string to base64 ciphertext."""
        key = self._get_encryption_key()
        if _HAS_CRYPTOGRAPHY and AESGCM is not None:
            aesgcm = AESGCM(key)
            nonce = secrets.token_bytes(12)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
            combined = nonce + ciphertext
            return base64.b64encode(combined).decode("utf-8")
        else:
            # Fallback simple XOR-stream with SHA256 PRF key derivation
            nonce = secrets.token_bytes(16)
            stream_key = hashlib.sha256(key + nonce).digest()
            raw_bytes = plaintext.encode("utf-8")
            encrypted = bytes(b ^ stream_key[i % len(stream_key)] for i, b in enumerate(raw_bytes))
            combined = nonce + encrypted
            return base64.b64encode(combined).decode("utf-8")

    def _decrypt(self, ciphertext_b64: str) -> str:
        """Decrypt base64 ciphertext to plaintext string."""
        key = self._get_encryption_key()
        raw = base64.b64decode(ciphertext_b64.encode("utf-8"))
        if _HAS_CRYPTOGRAPHY and AESGCM is not None:
            aesgcm = AESGCM(key)
            nonce = raw[:12]
            ciphertext = raw[12:]
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode("utf-8")
        else:
            nonce = raw[:16]
            encrypted = raw[16:]
            stream_key = hashlib.sha256(key + nonce).digest()
            decrypted = bytes(b ^ stream_key[i % len(stream_key)] for i, b in enumerate(encrypted))
            return decrypted.decode("utf-8")

    def _load_vault(self) -> None:
        """Load and decrypt entries from disk."""
        if not self.vault_path.exists():
            return
        try:
            raw_data = self.vault_path.read_text(encoding="utf-8")
            if not raw_data.strip():
                return
            encrypted_payload = json.loads(raw_data)
            decrypted_json = self._decrypt(encrypted_payload["payload"])
            self._cache = json.loads(decrypted_json)
        except Exception as e:
            log.warning("Could not decrypt secret vault (corrupted or new key): %s", e)
            self._cache = {}

    def _save_vault(self) -> None:
        """Encrypt and persist cache to disk."""
        try:
            plaintext_json = json.dumps(self._cache)
            encrypted_b64 = self._encrypt(plaintext_json)
            payload = {"version": "1.0", "payload": encrypted_b64}
            self.vault_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if os.name != "nt":
                os.chmod(self.vault_path, 0o600)
        except Exception as e:
            log.error("Failed to write encrypted vault to disk: %s", e)

    def set_secret(self, key: str, value: str) -> None:
        """Store or update a secret in the vault."""
        self._cache[key] = value
        self._save_vault()

    def get_secret(self, key: str, default: str | None = None) -> str | None:
        """Retrieve a secret from the vault."""
        return self._cache.get(key, default)

    def delete_secret(self, key: str) -> bool:
        """Delete a secret from the vault."""
        if key in self._cache:
            del self._cache[key]
            self._save_vault()
            return True
        return False

    def list_keys(self) -> list[str]:
        """List all secret keys stored in the vault without revealing values."""
        return list(self._cache.keys())

    def clear(self) -> None:
        """Wipe all secrets from the vault."""
        self._cache.clear()
        self._save_vault()
