"""
NEXUS File Operations Tools.

Provides safe file management capabilities:
- Search files (pattern, extension, regex, depth limit)
- Create files with content
- Read files (with line limits and encoding detection)
- Edit files (overwrite, append, replace text)
- Rename files/folders
- Copy files/folders
- Move files/folders
- Create folders
- Delete files/folders with safety calculations and explicit confirmation
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
from pathlib import Path
from typing import Any

from nexus.tools.base import BaseTool, RiskLevel, TargetDevice, ToolResult
from nexus.utils.logging import get_logger

log = get_logger("tools.system.files")


def _resolve_path(raw_path: str) -> Path:
    """Safely resolve user path with home expansion."""
    return Path(raw_path.strip()).expanduser().resolve()


def _format_size(bytes_size: int | float) -> str:
    """Format byte size into human readable string."""
    size = float(bytes_size)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ---------------------------------------------------------------------------
# Search Files
# ---------------------------------------------------------------------------


class SearchFilesTool(BaseTool):
    """Search for files in a directory matching patterns or extensions."""

    @property
    def name(self) -> str:
        return "search_files"

    @property
    def description(self) -> str:
        return (
            "Search for files on the laptop by filename, glob pattern (e.g. '*.pdf', '*report*'), "
            "or extension. Specify a starting directory (defaults to user home or current dir)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Filename keyword or glob pattern to search for (e.g., 'notes.txt', '*.pdf', 'budget').",
                },
                "directory": {
                    "type": "string",
                    "description": "Base directory to search in. Defaults to user home directory.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Maximum directory depth to search (default: 4).",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 20).",
                },
            },
            "required": ["query"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        query: str = "",
        directory: str | None = None,
        max_depth: int = 4,
        max_results: int = 20,
        **kwargs: Any,
    ) -> ToolResult:
        base_dir = _resolve_path(directory) if directory else Path.home()
        if not base_dir.exists() or not base_dir.is_dir():
            return ToolResult.fail(f"Search directory '{base_dir}' does not exist.")

        pattern = query.strip()
        is_glob = any(char in pattern for char in "*?[]")
        regex = None if is_glob else re.compile(re.escape(pattern), re.IGNORECASE)

        results: list[dict[str, Any]] = []
        base_parts_len = len(base_dir.parts)

        try:
            for root, dirs, files in os.walk(base_dir):
                curr_path = Path(root)
                depth = len(curr_path.parts) - base_parts_len
                if depth > max_depth:
                    dirs.clear()  # Do not recurse deeper
                    continue

                # Skip hidden/system directories for speed
                dirs[:] = [
                    d
                    for d in dirs
                    if not d.startswith(".")
                    and d not in ("node_modules", "$Recycle.Bin", "AppData")
                ]

                for fname in files:
                    match = False
                    if is_glob:
                        if Path(fname).match(pattern):
                            match = True
                    elif regex and regex.search(fname):
                        match = True

                    if match:
                        fpath = curr_path / fname
                        try:
                            st = fpath.stat()
                            results.append(
                                {
                                    "name": fname,
                                    "path": str(fpath),
                                    "size_bytes": st.st_size,
                                    "size": _format_size(st.st_size),
                                    "is_dir": False,
                                }
                            )
                        except (OSError, PermissionError):
                            results.append({"name": fname, "path": str(fpath), "is_dir": False})

                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult.ok(
                    f"No files matching '{query}' found in '{base_dir}'.", files=[]
                )

            lines = [f"Found {len(results)} file(s) matching '{query}' in '{base_dir}':"]
            for f in results:
                lines.append(f"  • {f['name']} ({f.get('size', 'unknown')}) -> {f['path']}")

            return ToolResult.ok("\n".join(lines), files=results, count=len(results))
        except Exception as e:
            return ToolResult.fail(f"File search failed: {e}")


# ---------------------------------------------------------------------------
# Create File
# ---------------------------------------------------------------------------


class CreateFileTool(BaseTool):
    """Create a new file with specified text content."""

    @property
    def name(self) -> str:
        return "create_file"

    @property
    def description(self) -> str:
        return (
            "Create a new file with text content. Will create parent folders if they do not exist."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path where the new file should be created.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write into the file (defaults to empty).",
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "Whether to overwrite if the file already exists (default: false).",
                },
            },
            "required": ["path"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        path: str = "",
        content: str = "",
        overwrite: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        file_path = _resolve_path(path)
        if file_path.exists() and not overwrite:
            return ToolResult.fail(
                f"File '{file_path}' already exists. Set overwrite=True to replace."
            )

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return ToolResult.ok(
                f"Successfully created file '{file_path}' ({len(content)} characters written).",
                path=str(file_path),
                size_bytes=len(content.encode("utf-8")),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to create file '{path}': {e}")


# ---------------------------------------------------------------------------
# Read File
# ---------------------------------------------------------------------------


class ReadFileTool(BaseTool):
    """Read text content from a file safely."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read text content from a file on the laptop, with support for line limits and offsets."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the file to read.",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum lines to return (default: 200).",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed, default: 1).",
                },
            },
            "required": ["path"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.LOW

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        path: str = "",
        max_lines: int = 200,
        start_line: int = 1,
        **kwargs: Any,
    ) -> ToolResult:
        file_path = _resolve_path(path)
        if not file_path.exists():
            return ToolResult.fail(f"File not found: '{file_path}'")
        if file_path.is_dir():
            return ToolResult.fail(f"Target '{file_path}' is a directory, not a file.")

        try:
            # Try reading UTF-8, fall back to latin-1
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = file_path.read_text(encoding="latin-1")

            lines = text.splitlines()
            total_lines = len(lines)

            start_idx = max(0, start_line - 1)
            end_idx = min(total_lines, start_idx + max_lines)
            selected_lines = lines[start_idx:end_idx]

            output_content = "\n".join(selected_lines)
            header = f"=== File: {file_path.name} (Lines {start_idx + 1}-{end_idx} of {total_lines}) ===\n"
            return ToolResult.ok(
                f"{header}{output_content}",
                path=str(file_path),
                total_lines=total_lines,
                returned_lines=len(selected_lines),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to read file '{path}': {e}")


# ---------------------------------------------------------------------------
# Edit File
# ---------------------------------------------------------------------------


class EditFileTool(BaseTool):
    """Edit an existing file by appending, overwriting, or replacing text."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "Edit an existing file on the laptop. Supported modes: 'append' (add text to end), "
            "'overwrite' (replace entire file), or 'replace' (replace target string with new text)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the file to edit.",
                },
                "mode": {
                    "type": "string",
                    "enum": ["append", "overwrite", "replace"],
                    "description": "Edit mode: 'append', 'overwrite', or 'replace'.",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write or append (for 'append' or 'overwrite' mode), or replacement text (for 'replace' mode).",
                },
                "target_text": {
                    "type": "string",
                    "description": "The exact target text to be replaced (required if mode is 'replace').",
                },
            },
            "required": ["path", "mode"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        path: str = "",
        mode: str = "append",
        content: str = "",
        target_text: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        file_path = _resolve_path(path)
        if not file_path.exists():
            return ToolResult.fail(f"File not found: '{file_path}'")

        try:
            current_content = file_path.read_text(encoding="utf-8")

            if mode == "append":
                new_content = (
                    current_content
                    + ("\n" if current_content and not current_content.endswith("\n") else "")
                    + content
                )
                file_path.write_text(new_content, encoding="utf-8")
                return ToolResult.ok(
                    f"Successfully appended content to '{file_path}'.", path=str(file_path)
                )

            elif mode == "overwrite":
                file_path.write_text(content, encoding="utf-8")
                return ToolResult.ok(
                    f"Successfully overwrote file '{file_path}'.", path=str(file_path)
                )

            elif mode == "replace":
                if not target_text:
                    return ToolResult.fail(
                        "Parameter 'target_text' is required when mode is 'replace'."
                    )
                if target_text not in current_content:
                    return ToolResult.fail(f"Target text was not found in '{file_path}'.")
                new_content = current_content.replace(target_text, content)
                file_path.write_text(new_content, encoding="utf-8")
                return ToolResult.ok(
                    f"Successfully replaced target text in '{file_path}'.", path=str(file_path)
                )

            else:
                return ToolResult.fail(
                    f"Unknown edit mode: '{mode}'. Choose append, overwrite, or replace."
                )
        except Exception as e:
            return ToolResult.fail(f"Failed to edit file '{path}': {e}")


# ---------------------------------------------------------------------------
# Rename File / Folder
# ---------------------------------------------------------------------------


class RenameFileTool(BaseTool):
    """Rename a file or folder."""

    @property
    def name(self) -> str:
        return "rename_file"

    @property
    def description(self) -> str:
        return "Rename an existing file or directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Path to the file or directory to rename.",
                },
                "new_name": {
                    "type": "string",
                    "description": "New filename or full destination path.",
                },
            },
            "required": ["source_path", "new_name"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, source_path: str = "", new_name: str = "", **kwargs: Any) -> ToolResult:
        src = _resolve_path(source_path)
        if not src.exists():
            return ToolResult.fail(f"Source '{src}' does not exist.")

        # Determine target path
        if "/" in new_name or "\\" in new_name:
            dst = _resolve_path(new_name)
        else:
            dst = src.parent / new_name

        if dst.exists():
            return ToolResult.fail(f"Destination '{dst}' already exists.")

        try:
            src.rename(dst)
            return ToolResult.ok(
                f"Successfully renamed '{src.name}' to '{dst.name}'",
                old_path=str(src),
                new_path=str(dst),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to rename '{src}': {e}")


# ---------------------------------------------------------------------------
# Copy File / Folder
# ---------------------------------------------------------------------------


class CopyFileTool(BaseTool):
    """Copy a file or directory tree."""

    @property
    def name(self) -> str:
        return "copy_file"

    @property
    def description(self) -> str:
        return "Copy a file or directory to a new destination path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Path to the file or directory to copy.",
                },
                "destination_path": {
                    "type": "string",
                    "description": "Destination directory or new target file path.",
                },
            },
            "required": ["source_path", "destination_path"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self, source_path: str = "", destination_path: str = "", **kwargs: Any
    ) -> ToolResult:
        src = _resolve_path(source_path)
        dst = _resolve_path(destination_path)

        if not src.exists():
            return ToolResult.fail(f"Source '{src}' does not exist.")

        try:
            if src.is_dir():
                if dst.exists() and dst.is_dir():
                    dst = dst / src.name
                shutil.copytree(src, dst)
            else:
                if dst.is_dir():
                    dst = dst / src.name
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

            return ToolResult.ok(
                f"Successfully copied '{src.name}' to '{dst}'",
                source=str(src),
                destination=str(dst),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to copy '{src}': {e}")


# ---------------------------------------------------------------------------
# Move File / Folder
# ---------------------------------------------------------------------------


class MoveFileTool(BaseTool):
    """Move a file or directory."""

    @property
    def name(self) -> str:
        return "move_file"

    @property
    def description(self) -> str:
        return "Move a file or folder to a new destination path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Path to the file or directory to move.",
                },
                "destination_path": {
                    "type": "string",
                    "description": "Destination directory or new target file path.",
                },
            },
            "required": ["source_path", "destination_path"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self, source_path: str = "", destination_path: str = "", **kwargs: Any
    ) -> ToolResult:
        src = _resolve_path(source_path)
        dst = _resolve_path(destination_path)

        if not src.exists():
            return ToolResult.fail(f"Source '{src}' does not exist.")

        try:
            shutil.move(str(src), str(dst))
            return ToolResult.ok(
                f"Successfully moved '{src.name}' to '{dst}'", source=str(src), destination=str(dst)
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to move '{src}': {e}")


# ---------------------------------------------------------------------------
# Create Folder
# ---------------------------------------------------------------------------


class CreateFolderTool(BaseTool):
    """Create a new directory."""

    @property
    def name(self) -> str:
        return "create_folder"

    @property
    def description(self) -> str:
        return "Create a new folder or nested directory structure."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the folder to create.",
                },
            },
            "required": ["path"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(self, path: str = "", **kwargs: Any) -> ToolResult:
        folder_path = _resolve_path(path)
        if folder_path.exists():
            return ToolResult.ok(f"Folder '{folder_path}' already exists.", path=str(folder_path))

        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            return ToolResult.ok(
                f"Successfully created folder '{folder_path}'", path=str(folder_path)
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to create folder '{path}': {e}")


# ---------------------------------------------------------------------------
# Delete Path (HIGH RISK — REQUIRES EXPLICIT CONFIRMATION)
# ---------------------------------------------------------------------------


class DeletePathTool(BaseTool):
    """
    Delete a file or folder.

    HIGH RISK ACTION. Calculates target stats (size and child file count)
    and requires explicit confirmation.
    """

    @property
    def name(self) -> str:
        return "delete_path"

    @property
    def description(self) -> str:
        return (
            "Delete a file or folder on the laptop. HIGH RISK ACTION: Shows what will be deleted "
            "and requires explicit user confirmation before executing."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path of the file or folder to delete.",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": "Confirmation flag. If false, returns summary of target items to confirm.",
                },
            },
            "required": ["path"],
        }

    @property
    def category(self) -> str:
        return "files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.HIGH

    @property
    def requires_confirmation(self) -> bool:
        return True

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    def calculate_target_info(self, target: Path) -> dict[str, Any]:
        """Calculate statistics of what will be deleted."""
        if not target.exists():
            return {"exists": False}

        if target.parent == target or str(target).rstrip("\\/").lower() in ("c:", "c:\\", "c:/", "/", "\\") or target == Path(target.anchor):
            return {
                "exists": True,
                "is_dir": True,
                "name": str(target),
                "path": str(target),
                "is_root": True,
                "total_files": 0,
                "total_subdirs": 0,
                "total_bytes": 0,
                "formatted_size": "unknown",
                "sample_files": [],
            }

        if target.is_file():
            size = target.stat().st_size
            return {
                "exists": True,
                "is_dir": False,
                "name": target.name,
                "path": str(target),
                "total_files": 1,
                "total_bytes": size,
                "formatted_size": _format_size(size),
            }

        # Directory calculation
        total_files = 0
        total_dirs = 0
        total_bytes = 0
        preview_files: list[str] = []

        for root, dirs, files in os.walk(target):
            total_dirs += len(dirs)
            total_files += len(files)
            for f in files:
                fp = Path(root) / f
                with contextlib.suppress(OSError, PermissionError):
                    total_bytes += fp.stat().st_size
                if len(preview_files) < 5:
                    preview_files.append(f)

        return {
            "exists": True,
            "is_dir": True,
            "name": target.name,
            "path": str(target),
            "total_files": total_files,
            "total_subdirs": total_dirs,
            "total_bytes": total_bytes,
            "formatted_size": _format_size(total_bytes),
            "sample_files": preview_files,
        }

    async def execute(self, path: str = "", confirmed: bool = False, **kwargs: Any) -> ToolResult:
        target = _resolve_path(path)
        if not target.exists():
            return ToolResult.fail(f"Target '{target}' does not exist.")

        # Safety boundary: never allow deleting system root or drive root
        if target.parent == target or str(target).rstrip("\\/").lower() in ("c:", "c:\\", "c:/", "/", "\\") or target == Path(target.anchor):
            return ToolResult.fail(f"Safety violation: Refusing to delete root drive '{target}'.")

        info = self.calculate_target_info(target)

        if not confirmed:
            return ToolResult.fail(
                f"Deletion of '{target}' requires explicit confirmation (confirmed=True). "
                f"Target contains {info.get('total_files', 1)} files ({info.get('formatted_size', 'unknown')}).",
                requires_confirmation=True,
                **info,
            )

        try:
            if target.is_dir():
                shutil.rmtree(target)
                return ToolResult.ok(
                    f"Successfully deleted folder '{target.name}' ({info['total_files']} files, {info['formatted_size']}).",
                    deleted_path=str(target),
                    **info,
                )
            else:
                target.unlink()
                return ToolResult.ok(
                    f"Successfully deleted file '{target.name}' ({info['formatted_size']}).",
                    deleted_path=str(target),
                    **info,
                )
        except Exception as e:
            return ToolResult.fail(f"Failed to delete '{target}': {e}")


# ---------------------------------------------------------------------------
# Compress Files & Folders
# ---------------------------------------------------------------------------


class CompressFilesTool(BaseTool):
    """Compress files or folders into a zip or tar archive."""

    @property
    def name(self) -> str:
        return "compress_files"

    @property
    def description(self) -> str:
        return (
            "Compress one or more files/folders into an archive (e.g. .zip, .tar, .tar.gz). "
            "Specify the source paths and output destination archive path."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "sources": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of file or directory paths to compress.",
                },
                "destination_archive": {
                    "type": "string",
                    "description": "Path of the output archive file (e.g. 'C:/Users/.../backup.zip').",
                },
                "archive_format": {
                    "type": "string",
                    "enum": ["zip", "tar", "gztar", "bztar"],
                    "description": "Archive format ('zip', 'tar', 'gztar', 'bztar'). Default is 'zip'.",
                },
            },
            "required": ["sources", "destination_archive"],
        }

    @property
    def category(self) -> str:
        return "file"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        sources: list[str] | str,
        destination_archive: str = "",
        archive_format: str = "zip",
        **kwargs: Any,
    ) -> ToolResult:
        if isinstance(sources, str):
            sources = [sources]

        if not sources:
            return ToolResult.fail("At least one source file or directory must be provided.")
        if not destination_archive:
            return ToolResult.fail("Destination archive path cannot be empty.")

        dest_path = _resolve_path(destination_archive)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        added_count = 0
        total_uncompressed_bytes = 0

        try:
            if archive_format == "zip" or dest_path.suffix.lower() == ".zip":
                import zipfile

                with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for src in sources:
                        sp = _resolve_path(src)
                        if not sp.exists():
                            continue
                        if sp.is_file():
                            zf.write(sp, arcname=sp.name)
                            added_count += 1
                            total_uncompressed_bytes += sp.stat().st_size
                        elif sp.is_dir():
                            for root, _, files in os.walk(sp):
                                for f in files:
                                    file_p = Path(root) / f
                                    arcname = file_p.relative_to(sp.parent)
                                    zf.write(file_p, arcname=str(arcname))
                                    added_count += 1
                                    total_uncompressed_bytes += file_p.stat().st_size
            else:
                import tarfile

                mode = "w:gz" if (archive_format == "gztar" or str(dest_path).endswith(".tar.gz")) else "w"
                with tarfile.open(dest_path, mode) as tf:
                    for src in sources:
                        sp = _resolve_path(src)
                        if not sp.exists():
                            continue
                        tf.add(sp, arcname=sp.name)
                        added_count += 1
                        if sp.is_file():
                            total_uncompressed_bytes += sp.stat().st_size

            if added_count == 0:
                return ToolResult.fail("None of the specified source files exist to compress.")

            archive_size = dest_path.stat().st_size if dest_path.exists() else 0
            return ToolResult.ok(
                f"Successfully compressed {added_count} items into '{dest_path.name}' ({_format_size(archive_size)}).",
                archive_path=str(dest_path),
                items_compressed=added_count,
                archive_size=_format_size(archive_size),
                uncompressed_size=_format_size(total_uncompressed_bytes),
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to create archive '{dest_path}': {e}")


# ---------------------------------------------------------------------------
# Extract Archive
# ---------------------------------------------------------------------------


class ExtractArchiveTool(BaseTool):
    """Extract an archive file (.zip, .tar, .tar.gz, etc.) into a target directory."""

    @property
    def name(self) -> str:
        return "extract_archive"

    @property
    def description(self) -> str:
        return (
            "Extract files from an archive (.zip, .tar, .tar.gz, .tgz, .zip, etc.) into a destination directory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "archive_path": {
                    "type": "string",
                    "description": "Path to the archive file to extract.",
                },
                "destination_dir": {
                    "type": "string",
                    "description": "Optional destination directory. Defaults to a folder named after the archive in the same directory.",
                },
            },
            "required": ["archive_path"],
        }

    @property
    def category(self) -> str:
        return "file"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.MEDIUM

    @property
    def target_device(self) -> TargetDevice:
        return TargetDevice.LAPTOP

    async def execute(
        self,
        archive_path: str = "",
        destination_dir: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        src = _resolve_path(archive_path)
        if not src.exists():
            return ToolResult.fail(f"Archive '{src}' does not exist.")

        if not destination_dir:
            out_dir = src.parent / (src.stem if not src.name.endswith(".tar.gz") else src.name[:-7])
        else:
            out_dir = _resolve_path(destination_dir)

        out_dir.mkdir(parents=True, exist_ok=True)

        try:
            shutil.unpack_archive(str(src), str(out_dir))
            extracted_files = [f.name for f in out_dir.iterdir()][:10]
            return ToolResult.ok(
                f"Successfully extracted '{src.name}' into '{out_dir}'.",
                destination=str(out_dir),
                preview_files=extracted_files,
            )
        except Exception as e:
            return ToolResult.fail(f"Failed to extract '{src}': {e}")

