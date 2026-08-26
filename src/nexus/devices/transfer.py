"""
NEXUS Secure Cross-Device File Transfer Bridge.

Handles file packaging, SHA-256 integrity checksum verification,
and secure transport between Laptop and Android nodes.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path

from nexus.devices.types import FileTransferManifest
from nexus.utils.logging import get_logger

log = get_logger("devices.transfer")


class SecureFileTransferBridge:
    """Orchestrates secure file transfer between connected ecosystem devices."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or Path(os.path.expanduser("~")) / ".nexus" / "transfers"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._transfers: dict[str, FileTransferManifest] = {}

    def compute_sha256(self, file_path: Path | str) -> str:
        """Compute SHA-256 hash of a file for integrity verification."""
        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return ""

        hasher = hashlib.sha256()
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def prepare_transfer(
        self,
        source_device_id: str,
        target_device_id: str,
        file_path: Path | str,
        destination_folder: str = "Documents",
    ) -> FileTransferManifest | None:
        """Create transfer manifest and calculate checksum."""
        p = Path(file_path)
        if not p.exists():
            log.error("File does not exist for transfer: %s", file_path)
            return None

        size_bytes = p.stat().st_size
        checksum = self.compute_sha256(p)
        transfer_id = f"xfer_{uuid.uuid4().hex[:12]}"

        manifest = FileTransferManifest(
            transfer_id=transfer_id,
            source_device_id=source_device_id,
            target_device_id=target_device_id,
            file_name=p.name,
            file_size_bytes=size_bytes,
            sha256_checksum=checksum,
            destination_folder=destination_folder,
            status="in_progress",
        )
        self._transfers[transfer_id] = manifest
        log.info("Prepared transfer '%s' for '%s' (%d bytes)", transfer_id, p.name, size_bytes)
        return manifest

    async def complete_transfer(
        self,
        transfer_id: str,
        received_data: bytes,
    ) -> bool:
        """Verify checksum of received data and commit file to destination."""
        manifest = self._transfers.get(transfer_id)
        if not manifest:
            log.error("Transfer ID '%s' not found.", transfer_id)
            return False

        received_checksum = hashlib.sha256(received_data).hexdigest()
        if received_checksum != manifest.sha256_checksum:
            log.error(
                "Integrity mismatch for transfer '%s'! Expected %s, got %s",
                transfer_id,
                manifest.sha256_checksum,
                received_checksum,
            )
            manifest.status = "failed"
            return False

        dest_file = self._storage_dir / manifest.file_name
        with open(dest_file, "wb") as f:
            f.write(received_data)

        manifest.status = "completed"
        log.info("Transfer '%s' completed successfully: %s", transfer_id, dest_file)
        return True

    def get_manifest(self, transfer_id: str) -> FileTransferManifest | None:
        """Retrieve manifest for a transfer."""
        return self._transfers.get(transfer_id)
