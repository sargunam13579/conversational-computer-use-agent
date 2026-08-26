"""
NEXUS Browser Interaction — Click, Type, Scroll, Select, and Form Fill.

Provides DOM-level actions with intelligent selector discovery and text fallback.
"""

from __future__ import annotations

from nexus.browser.controller import BrowserController
from nexus.utils.logging import get_logger

log = get_logger("browser.interaction")


class BrowserInteraction:
    """Performs actions on DOM elements: clicking, typing, scrolling, form filling."""

    def __init__(self, controller: BrowserController | None = None) -> None:
        self._controller = controller or BrowserController()

    @property
    def controller(self) -> BrowserController:
        return self._controller

    async def click(self, target: str, timeout_ms: int = 8000) -> bool:
        """
        Click an element by CSS selector, XPath, text content, or role.
        """
        page = await self._controller.get_active_page()
        target = target.strip()

        # Strategy 1: Direct CSS/XPath selector
        try:
            await page.click(target, timeout=timeout_ms)
            return True
        except Exception:
            pass

        # Strategy 2: Text matching (button, link, label)
        try:
            locator = page.get_by_text(target, exact=False).first
            if await locator.is_visible():
                await locator.click(timeout=timeout_ms)
                return True
        except Exception:
            pass

        # Strategy 3: Role based (button, link)
        try:
            for role in ["button", "link", "menuitem", "tab", "checkbox"]:
                loc = page.get_by_role(role, name=target).first
                if await loc.is_visible():
                    await loc.click(timeout=timeout_ms)
                    return True
        except Exception:
            pass

        # Strategy 4: Fallback fuzzy XPath text contains
        try:
            xpath = (
                "//*[contains(translate(text(), "
                "'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), "
                f"'{target.lower()}')]"
            )
            await page.locator(xpath).first.click(timeout=timeout_ms)
            return True
        except Exception as e:
            log.warning("Click failed for target '%s': %s", target, e)
            return False

    async def type_text(
        self,
        target: str | None,
        text: str,
        press_enter: bool = False,
        clear_first: bool = True,
        timeout_ms: int = 8000,
    ) -> bool:
        """
        Type text into input field or active element.
        """
        page = await self._controller.get_active_page()

        if target:
            target = target.strip()
            locator = None

            # Strategy 1: Direct selector
            try:
                loc = page.locator(target).first
                if await loc.is_visible():
                    locator = loc
            except Exception:
                pass

            # Strategy 2: Placeholder or label text
            if not locator:
                try:
                    loc = page.get_by_placeholder(target).first
                    if await loc.is_visible():
                        locator = loc
                except Exception:
                    pass

            if not locator:
                try:
                    loc = page.get_by_label(target).first
                    if await loc.is_visible():
                        locator = loc
                except Exception:
                    pass

            if locator:
                try:
                    if clear_first:
                        await locator.fill("")
                    await locator.type(text, delay=15)
                    if press_enter:
                        await locator.press("Enter")
                    return True
                except Exception as e:
                    log.warning("Typing into locator failed: %s", e)

        # Fallback to focused element typing
        try:
            await page.keyboard.type(text, delay=15)
            if press_enter:
                await page.keyboard.press("Enter")
            return True
        except Exception as e:
            log.warning("Keyboard typing failed: %s", e)
            return False

    async def scroll(
        self,
        direction: str = "down",
        amount: int = 500,
        target_selector: str | None = None,
    ) -> bool:
        """
        Scroll page or specific element.
        """
        page = await self._controller.get_active_page()

        if target_selector:
            try:
                loc = page.locator(target_selector).first
                await loc.scroll_into_view_if_needed(timeout=5000)
                return True
            except Exception as e:
                log.warning("Scroll to target '%s' failed: %s", target_selector, e)

        # Global page scroll
        delta_y = amount if direction.lower() in ("down", "bottom") else -amount
        if direction.lower() == "bottom":
            delta_y = 10000
        elif direction.lower() == "top":
            delta_y = -10000

        try:
            await page.evaluate(f"window.scrollBy({{top: {delta_y}, behavior: 'smooth'}})")
            return True
        except Exception as e:
            log.warning("Page scroll failed: %s", e)
            return False

    async def fill_form(self, fields: dict[str, str]) -> dict[str, bool]:
        """
        Autofill a dictionary of field identifiers and their corresponding values.
        """
        results: dict[str, bool] = {}
        for field_name, value in fields.items():
            success = await self.type_text(target=field_name, text=value, press_enter=False)
            results[field_name] = success
        return results

    async def upload_file(self, target_selector: str, file_path: str) -> bool:
        """Upload a file to a file input element."""
        page = await self._controller.get_active_page()
        try:
            await page.set_input_files(target_selector, file_path)
            return True
        except Exception as e:
            log.warning("File upload failed: %s", e)
            return False
