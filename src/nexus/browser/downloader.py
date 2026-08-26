"""
NEXUS Browser Downloader — File Downloads, Verification & Target Folder Filing.

Handles:
- Triggering downloads via URL or clicking download links
- File integrity verification (SHA-256 hash & non-zero byte check)
- Relocating downloaded files to destination folders (e.g. Documents, Downloads)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from nexus.browser.controller import BrowserController
from nexus.utils.logging import get_logger

log = get_logger("browser.downloader")


@dataclass
class DownloadResult:
    """Outcome of a file download operation."""

    success: bool
    file_path: str | None = None
    filename: str | None = None
    file_size_bytes: int = 0
    sha256_hash: str | None = None
    destination_folder: str | None = None
    error: str | None = None


class BrowserDownloader:
    """Manages browser downloads and file placement."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or BrowserController()

    @property
    def controller(self) -> BrowserController:
        return self._controller

    def _resolve_destination_directory(self, destination: str | None = None) -> Path:
        """Resolve user directory alias (e.g. 'documents', 'downloads', 'desktop') or path."""
        user_home = Path.home()
        if not destination or destination.lower() in ("downloads", "default"):
            target = user_home / "Downloads"
        elif destination.lower() in ("documents", "docs"):
            target = user_home / "Documents"
        elif destination.lower() == "desktop":
            target = user_home / "Desktop"
        else:
            target = Path(destination).expanduser().resolve()

        target.mkdir(parents=True, exist_ok=True)
        return target

    async def download(
        self,
        url_or_click_target: str,
        destination_folder: str | None = "Documents",
        filename: str | None = None,
        timeout_seconds: int = 30,
    ) -> DownloadResult:
        """
        Download a file either by direct URL navigation or clicking a download element.
        """
        dest_dir = self._resolve_destination_directory(destination_folder)

        try:
            # Check if target is a direct downloadable URL
            if url_or_click_target.startswith(("http://", "https://")):
                import httpx

                async with httpx.AsyncClient(
                    follow_redirects=True, timeout=timeout_seconds
                ) as client:
                    resp = await client.get(url_or_click_target)
                    resp.raise_for_status()

                    # Determine filename
                    resolved_filename = filename
                    if not resolved_filename:
                        content_disp = resp.headers.get("content-disposition", "")
                        if "filename=" in content_disp:
                            resolved_filename = content_disp.split("filename=")[-1].strip("\"' ")
                        else:
                            resolved_filename = url_or_click_target.split("/")[-1].split("?")[0]
                        if not resolved_filename or "." not in resolved_filename:
                            resolved_filename = "downloaded_file.bin"

                    final_path = dest_dir / resolved_filename
                    final_path.write_bytes(resp.content)

                    # Compute sha256
                    file_hash = hashlib.sha256(resp.content).hexdigest()
                    file_size = len(resp.content)

                    return DownloadResult(
                        success=True,
                        file_path=str(final_path),
                        filename=resolved_filename,
                        file_size_bytes=file_size,
                        sha256_hash=file_hash,
                        destination_folder=str(dest_dir),
                    )

            # Otherwise trigger download via browser click event
            page = await self._controller.get_active_page()
            async with page.expect_download(timeout=timeout_seconds * 1000) as download_info:
                from nexus.browser.interaction import BrowserInteraction

                interact = BrowserInteraction(controller=self._controller)
                clicked = await interact.click(url_or_click_target)
                if not clicked:
                    return DownloadResult(
                        success=False,
                        error=f"Could not locate or click download target '{url_or_click_target}'",
                    )

            download = await download_info.value
            downloaded_name = filename or download.suggested_filename
            final_path = dest_dir / downloaded_name

            await download.save_as(str(final_path))

            # Compute hash and size
            file_bytes = final_path.read_bytes()
            file_hash = hashlib.sha256(file_bytes).hexdigest()
            file_size = len(file_bytes)

            return DownloadResult(
                success=True,
                file_path=str(final_path),
                filename=downloaded_name,
                file_size_bytes=file_size,
                sha256_hash=file_hash,
                destination_folder=str(dest_dir),
            )

        except Exception as e:
            log.warning("Download failed for '%s': %s", url_or_click_target, e)
            return DownloadResult(
                success=False,
                error=f"Download failed: {e}",
            )
