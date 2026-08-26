"""
NEXUS Context & Reference Resolution Engine.

Resolves anaphoric pronouns ("this", "it", "that", "the file", "the link") and
domain aliases ("my Java project", "my work folder") into concrete parameters.
"""

from __future__ import annotations

import re
from typing import Any

from nexus.memory.storage import MemoryStorage
from nexus.memory.types import ContextState, MemoryCategory
from nexus.utils.logging import get_logger

log = get_logger("memory.context_resolver")

# Patterns matching pronouns and deictic references
_PRONOUN_PATTERNS = re.compile(
    r"\b(this|it|that|the\s+file|the\s+pdf|the\s+download|the\s+link|the\s+page)\b",
    re.IGNORECASE,
)

# Patterns for user project references
_PROJECT_PATTERNS = re.compile(
    r"my\s+(?P<lang>[a-zA-Z0-9_+]+)?\s*(?:project|workspace|repo|codebase|folder|directory)",
    re.IGNORECASE,
)


class ContextResolver:
    """Resolves conversational and task references using dynamic context & stored memory."""

    def __init__(self, storage: MemoryStorage | None = None) -> None:
        self._storage = storage or MemoryStorage()
        self._state = ContextState()

    @property
    def state(self) -> ContextState:
        return self._state

    def update_state(
        self,
        active_app: str | None = None,
        active_window_title: str | None = None,
        last_mentioned_path: str | None = None,
        last_mentioned_url: str | None = None,
        last_search_query: str | None = None,
        last_downloaded_file: str | None = None,
        last_copied_text: str | None = None,
        active_task_description: str | None = None,
        recent_entity_key: str | None = None,
        recent_entity_val: str | None = None,
    ) -> None:
        """Update the active dynamic context state."""
        if active_app is not None:
            self._state.active_app = active_app
        if active_window_title is not None:
            self._state.active_window_title = active_window_title
        if last_mentioned_path is not None:
            self._state.last_mentioned_path = last_mentioned_path
        if last_mentioned_url is not None:
            self._state.last_mentioned_url = last_mentioned_url
        if last_search_query is not None:
            self._state.last_search_query = last_search_query
        if last_downloaded_file is not None:
            self._state.last_downloaded_file = last_downloaded_file
        if last_copied_text is not None:
            self._state.last_copied_text = last_copied_text
        if active_task_description is not None:
            self._state.active_task_description = active_task_description
        if recent_entity_key and recent_entity_val:
            self._state.recent_entities[recent_entity_key.lower()] = recent_entity_val

    async def resolve_reference(
        self,
        user_input: str,
        recent_dialog_turns: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze user input for references and resolve them to concrete entities.

        Returns dictionary of resolved keys and their values.
        """
        resolved: dict[str, Any] = {}
        text_lower = user_input.lower()

        # 1. Resolve Project/Folder references (e.g. "my Java project", "my projects folder")
        project_match = _PROJECT_PATTERNS.search(text_lower)
        if project_match:
            lang = project_match.group("lang") or ""
            lang_clean = lang.strip().lower()

            # Search in USER_PREFERENCE memory
            candidates = [
                f"{lang_clean}_projects_dir",
                f"{lang_clean}_projects",
                f"{lang_clean}_project_dir",
                f"{lang_clean}_project_path",
                "projects_dir",
                "projects_path",
                "workspace_path",
            ]
            for cand in candidates:
                rec = await self._storage.find_by_key(cand, category=MemoryCategory.USER_PREFERENCE)
                if rec:
                    resolved["target_path"] = str(rec.value)
                    resolved["reference_type"] = "project_directory"
                    break

            if "target_path" not in resolved and self._state.last_mentioned_path:
                resolved["target_path"] = self._state.last_mentioned_path

        # 2. Resolve Pronouns ("this", "it", "that", "the file", "the link")
        if _PRONOUN_PATTERNS.search(text_lower):
            # Check for file references
            if any(term in text_lower for term in ["file", "pdf", "download"]):
                if self._state.last_downloaded_file:
                    resolved["target_file"] = self._state.last_downloaded_file
                elif self._state.last_mentioned_path:
                    resolved["target_file"] = self._state.last_mentioned_path

            # Check for search/browser references ("search this", "open this")
            if "search" in text_lower:
                if self._state.last_copied_text:
                    resolved["search_query"] = self._state.last_copied_text
                elif self._state.last_search_query:
                    resolved["search_query"] = self._state.last_search_query
                elif recent_dialog_turns:
                    # Pick most recent non-empty turn snippet
                    for turn in reversed(recent_dialog_turns):
                        clean_turn = turn.strip()
                        if clean_turn and not clean_turn.lower().startswith(("search", "open")):
                            resolved["search_query"] = clean_turn
                            break

            # Check for link/URL references
            if ("link" in text_lower or "url" in text_lower) and self._state.last_mentioned_url:
                resolved["target_url"] = self._state.last_mentioned_url

        return resolved

    async def build_context_prompt(self, max_items: int = 5) -> str:
        """Build structured memory context block for injection into LLM prompts."""
        lines = []

        # 1. User Preferences
        pref_records = await self._storage.list_by_category(MemoryCategory.USER_PREFERENCE)
        if pref_records:
            lines.append("## Stored User Preferences:")
            for r in pref_records[:max_items]:
                lines.append(f"- {r.key}: {r.value}")

        # 2. User Defined Info
        info_records = await self._storage.list_by_category(MemoryCategory.USER_DEFINED_INFO)
        if info_records:
            lines.append("\n## Important User Knowledge:")
            for r in info_records[:max_items]:
                lines.append(f"- {r.key}: {r.value}")

        # 3. Active Task / Dynamic Context
        if self._state.active_task_description:
            lines.append(f"\n## Active Task: {self._state.active_task_description}")
        if self._state.active_app:
            lines.append(f"## Active Application: {self._state.active_app}")
        if self._state.last_mentioned_path:
            lines.append(f"## Recent Path: {self._state.last_mentioned_path}")

        return "\n".join(lines)
