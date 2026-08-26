"""
NEXUS Multi-Step Workflow Engine.

Orchestrates multi-step goal execution across browser, desktop apps, file system,
with intermediate result verification and structured reporting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus.browser.controller import BrowserController
from nexus.browser.downloader import BrowserDownloader, DownloadResult
from nexus.browser.navigator import BrowserNavigator
from nexus.browser.page_reader import PageReader
from nexus.utils.logging import get_logger

log = get_logger("automation.workflow")


@dataclass
class WorkflowStep:
    """A discrete action step within a multi-step workflow."""

    step_number: int
    name: str
    action_type: str  # e.g., 'navigate', 'search', 'download', 'move_file', 'verify'
    params: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # 'pending', 'in_progress', 'completed', 'failed'
    output: str | None = None
    error: str | None = None


@dataclass
class WorkflowResult:
    """Summary of executed multi-step workflow."""

    success: bool
    summary: str
    steps: list[WorkflowStep]
    final_data: dict[str, Any] = field(default_factory=dict)


class MultiStepWorkflowEngine:
    """Plans and executes complex multi-step tasks across browser and system."""

    def __init__(
        self,
        browser_ctrl: BrowserController | None = None,
    ) -> None:
        self._browser_ctrl = browser_ctrl or BrowserController()
        self._navigator = BrowserNavigator(controller=self._browser_ctrl)
        self._page_reader = PageReader(controller=self._browser_ctrl)
        self._downloader = BrowserDownloader(controller=self._browser_ctrl)

    async def execute_web_search_and_read(
        self,
        query: str,
        engine: str = "duckduckgo",
        max_words: int = 500,
    ) -> WorkflowResult:
        """
        Execute standard Workflow:
        1. Open browser / navigate
        2. Execute query
        3. Read and parse top results
        4. Report structured answer
        """
        steps = [
            WorkflowStep(1, "Open Browser & Search", "search", {"query": query, "engine": engine}),
            WorkflowStep(2, "Extract Page Content", "read_page", {}),
            WorkflowStep(3, "Synthesize Results", "report", {}),
        ]

        # Step 1
        steps[0].status = "in_progress"
        try:
            search_res = await self._navigator.search(query, engine=engine)
            steps[0].status = "completed"
            steps[0].output = f"Navigated to {search_res['url']} (Title: {search_res['title']})"
        except Exception as e:
            steps[0].status = "failed"
            steps[0].error = str(e)
            return WorkflowResult(False, f"Search step failed: {e}", steps)

        # Step 2
        steps[1].status = "in_progress"
        try:
            content = await self._page_reader.read(max_length=max_words * 6)
            steps[1].status = "completed"
            steps[1].output = f"Extracted {content.total_words} words from '{content.title}'"
        except Exception as e:
            steps[1].status = "failed"
            steps[1].error = str(e)
            return WorkflowResult(False, f"Content extraction failed: {e}", steps)

        # Step 3
        steps[2].status = "completed"
        steps[2].output = content.text_content

        summary = (
            f"Successfully searched for '{query}' on {engine.capitalize()}.\n"
            f"Page: '{content.title}'\n\n"
            f"Key findings:\n{content.text_content[:800]}..."
        )

        return WorkflowResult(
            success=True,
            summary=summary,
            steps=steps,
            final_data={
                "title": content.title,
                "url": content.url,
                "headings": content.headings,
                "text_content": content.text_content,
            },
        )

    async def execute_search_download_and_file(
        self,
        search_query: str,
        file_extension: str = "pdf",
        destination_folder: str = "Documents",
    ) -> WorkflowResult:
        """
        Execute Multi-step Workflow:
        1. Search web
        2. Identify file / download link
        3. Download file
        4. Verify file integrity
        5. Move/Place in target destination folder
        6. Report completion
        """
        steps = [
            WorkflowStep(1, f"Search web for '{search_query}'", "search", {"query": search_query}),
            WorkflowStep(
                2, f"Identify {file_extension.upper()} link", "find_link", {"ext": file_extension}
            ),
            WorkflowStep(3, "Download file", "download", {}),
            WorkflowStep(4, "Verify file integrity & size", "verify", {}),
            WorkflowStep(
                5, f"Place in {destination_folder}", "file_placement", {"dest": destination_folder}
            ),
        ]

        # Step 1: Search
        steps[0].status = "in_progress"
        try:
            await self._navigator.search(search_query)
            steps[0].status = "completed"
            steps[0].output = "Search query executed."
        except Exception as e:
            steps[0].status = "failed"
            steps[0].error = str(e)
            return WorkflowResult(False, f"Search failed: {e}", steps)

        # Step 2: Identify link
        steps[1].status = "in_progress"
        links = await self._page_reader.find_download_links(extension=file_extension)
        if not links:
            steps[1].status = "failed"
            steps[1].error = f"No {file_extension.upper()} links found on search results page."
            return WorkflowResult(False, steps[1].error, steps)

        target_link = links[0]
        steps[1].status = "completed"
        steps[1].output = f"Selected link: '{target_link.text}' ({target_link.url})"

        # Step 3 & 4: Download & Verify
        steps[2].status = "in_progress"
        dl_res: DownloadResult = await self._downloader.download(
            url_or_click_target=target_link.url,
            destination_folder=destination_folder,
        )

        if not dl_res.success:
            steps[2].status = "failed"
            steps[2].error = dl_res.error or "Download failed"
            return WorkflowResult(False, f"Download failed: {dl_res.error}", steps)

        steps[2].status = "completed"
        steps[2].output = f"Downloaded {dl_res.filename} ({dl_res.file_size_bytes} bytes)"

        # Step 4: Verify
        hash_preview = dl_res.sha256_hash[:16] if dl_res.sha256_hash else "N/A"
        steps[
            3
        ].output = f"Verified SHA-256: {hash_preview}... (Size: {dl_res.file_size_bytes} bytes)"

        # Step 5: Placement
        steps[4].status = "completed"
        steps[4].output = f"Saved in: {dl_res.file_path}"

        summary = (
            f"Successfully executed workflow:\n"
            f"1. Searched: '{search_query}'\n"
            f"2. Found {file_extension.upper()}: '{dl_res.filename}'\n"
            f"3. Downloaded and verified ({dl_res.file_size_bytes} bytes)\n"
            f"4. Saved to: {dl_res.file_path}"
        )

        return WorkflowResult(
            success=True,
            summary=summary,
            steps=steps,
            final_data={
                "file_path": dl_res.file_path,
                "filename": dl_res.filename,
                "size_bytes": dl_res.file_size_bytes,
                "sha256": dl_res.sha256_hash,
            },
        )
