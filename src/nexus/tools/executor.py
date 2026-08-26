"""
NEXUS Tool Executor.

Executes tools with validation, permission checks, retry logic, and audit logging.
This is the safe execution boundary between the LLM and actual system actions.
"""

from __future__ import annotations

from typing import Any

from nexus.tools.base import BaseTool, ToolResult
from nexus.tools.registry import ToolRegistry
from nexus.utils.async_utils import retry_async
from nexus.utils.events import get_event_bus
from nexus.utils.logging import get_logger, print_tool

log = get_logger("tools.executor")


class ToolExecutor:
    """
    Executes tools safely with validation, permission checks, and logging.

    The executor is the single gateway through which all tool calls pass.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        max_retries: int = 2,
        confirm_callback: Any | None = None,
    ) -> None:
        """
        Args:
            registry: The tool registry to look up tools.
            max_retries: Maximum retry attempts for failed tool executions.
            confirm_callback: Optional async callback for user confirmation.
                              Signature: async (tool_name, params, risk) -> bool
        """
        self._registry = registry
        self._max_retries = max_retries
        self._confirm_callback = confirm_callback
        self._event_bus = get_event_bus()
        self._execution_count = 0

    async def execute(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        skip_confirmation: bool = False,
    ) -> ToolResult:
        """
        Execute a tool by name with the given parameters.

        This method:
          1. Looks up the tool in the registry
          2. Validates the parameters
          3. Checks permissions / asks for confirmation if needed
          4. Executes the tool (with retry on failure)
          5. Emits events and logs the result

        Args:
            tool_name: The name of the tool to execute.
            parameters: The parameters to pass to the tool.
            skip_confirmation: If True, skip user confirmation even for high-risk tools.

        Returns:
            The ToolResult from execution.
        """
        # Step 1: Look up the tool
        tool = self._registry.get(tool_name)
        if tool is None:
            log.error("Tool '%s' not found", tool_name)
            return ToolResult.fail(f"Unknown tool: {tool_name}")

        log.info("Executing tool: %s (risk=%s)", tool_name, tool.risk_level.value)
        print_tool(tool_name, "executing")

        # Step 2: Validate parameters
        is_valid, error_msg = await tool.validate(**parameters)
        if not is_valid:
            log.warning("Validation failed for %s: %s", tool_name, error_msg)
            return ToolResult.fail(f"Validation failed: {error_msg}")

        # Step 3: Permission check
        if not skip_confirmation and tool.requires_confirmation:
            approved = await self._request_confirmation(tool, parameters)
            if not approved:
                log.info("User denied execution of %s", tool_name)
                return ToolResult.fail("Action cancelled by user")

        # Step 4: Execute with retry
        try:
            if self._max_retries > 0:
                result = await retry_async(
                    tool.execute,
                    max_retries=self._max_retries,
                    delay=0.5,
                    exceptions=(Exception,),
                    **parameters,
                )
            else:
                result = await tool.execute(**parameters)
        except Exception as e:
            log.error("Tool execution failed: %s — %s", tool_name, e)
            result = ToolResult.fail(str(e))

        # Step 5: Log and emit
        self._execution_count += 1
        status = "done" if result.success else "failed"
        print_tool(tool_name, status)

        await self._event_bus.emit(
            "tool.executed",
            {
                "tool_name": tool_name,
                "parameters": parameters,
                "success": result.success,
                "output": result.output,
                "risk_level": tool.risk_level.value,
            },
            source="tool_executor",
        )

        return result

    async def _request_confirmation(
        self,
        tool: BaseTool,
        parameters: dict[str, Any],
    ) -> bool:
        """Ask the user for confirmation before executing a high-risk tool."""
        if self._confirm_callback:
            return await self._confirm_callback(
                tool.name,
                parameters,
                tool.risk_level.value,
            )
        # Default: auto-approve (will be replaced with proper UI in Phase 6)
        log.warning(
            "Auto-approving %s (risk=%s) — no confirmation callback set",
            tool.name,
            tool.risk_level.value,
        )
        return True

    @property
    def execution_count(self) -> int:
        """Total number of tool executions so far."""
        return self._execution_count
