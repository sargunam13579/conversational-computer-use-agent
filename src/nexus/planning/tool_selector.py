"""
NEXUS Planning — Tool Selector & Parameter Resolver.

Selects the most suitable tools from the registry for a given plan step
and handles variable interpolation across multi-step sequences.
"""

from __future__ import annotations

import re
from typing import Any

from nexus.planning.types import Plan, PlanStep
from nexus.tools.base import BaseTool
from nexus.tools.registry import ToolRegistry
from nexus.utils.logging import get_logger

log = get_logger("planning.tool_selector")

# Regex for variable interpolation placeholders, e.g., {{step_1.output}} or {{context.file_path}}
_VAR_PATTERN = re.compile(r"\{\{([a-zA-Z0-9_\.]+)\}\}")


class ToolSelector:
    """
    Selects registered tools and resolves dynamic runtime arguments for plan steps.
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self.registry = registry or ToolRegistry()

    def select_tool_for_step(self, step: PlanStep) -> BaseTool | None:
        """
        Find the best matching tool from the registry for a plan step.
        """
        if step.tool_name:
            tool = self.registry.get(step.tool_name)
            if tool:
                return tool

        # Heuristic / semantic intent matching if tool_name is generic or not exact
        desc = step.description.lower()

        if any(k in desc for k in ["find", "search file", "locate"]):
            return self.registry.get("find_files") or self.registry.get("search_files") or self.registry.get("file_search")
        if any(k in desc for k in ["convert", "pdf"]):
            return self.registry.get("convert_document") or self.registry.get("print_to_pdf") or self.registry.get("shell_execute")
        if any(k in desc for k in ["rename", "move"]):
            return self.registry.get("rename_file") or self.registry.get("move_file")
        if any(k in desc for k in ["transfer", "send to phone", "send to device", "handoff"]):
            return self.registry.get("transfer_file") or self.registry.get("send_to_device") or self.registry.get("transfer_file_adb")
        if any(k in desc for k in ["run", "execute", "command", "powershell", "bash"]):
            return self.registry.get("shell_execute") or self.registry.get("run_command")
        if any(k in desc for k in ["memory", "remember", "store"]):
            return self.registry.get("store_memory") or self.registry.get("search_memory")

        return None

    def resolve_parameters(self, step: PlanStep, plan: Plan) -> dict[str, Any]:
        """
        Interpolate dynamic variables from context and prior step outputs into tool parameters.
        """
        resolved: dict[str, Any] = {}

        for key, value in step.parameters.items():
            resolved[key] = self._interpolate_value(value, plan)

        return resolved

    def _interpolate_value(self, value: Any, plan: Plan) -> Any:
        if isinstance(value, str):
            # Check for direct whole placeholder match, e.g. "{{step_1.output}}"
            single_match = _VAR_PATTERN.fullmatch(value.strip())
            if single_match:
                var_name = single_match.group(1)
                return self._resolve_variable_name(var_name, plan)

            # Check for multiple embedded placeholders within a string
            def replacer(match: re.Match[str]) -> str:
                v = self._resolve_variable_name(match.group(1), plan)
                return str(v) if v is not None else match.group(0)

            return _VAR_PATTERN.sub(replacer, value)

        elif isinstance(value, dict):
            return {k: self._interpolate_value(v, plan) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._interpolate_value(item, plan) for item in value]

        return value

    def _resolve_variable_name(self, var_name: str, plan: Plan) -> Any:
        """
        Resolve a variable expression like:
          - 'step_1.output'
          - 'step_2.output.file_path'
          - 'context.filename'
          - 'latest_file'
        """
        # 1. Direct match in plan.context_variables
        if var_name in plan.context_variables:
            return plan.context_variables[var_name]

        # 2. Check context.<name>
        if var_name.startswith("context."):
            ctx_key = var_name[len("context."):]
            return plan.context_variables.get(ctx_key)

        # 3. Check step reference, e.g. step_1 or step_abc.output
        parts = var_name.split(".")
        step_id_or_order = parts[0]

        target_step: PlanStep | None = None
        for s in plan.steps:
            if s.step_id == step_id_or_order or f"step_{s.order}" == step_id_or_order or str(s.order) == step_id_or_order:
                target_step = s
                break

        if target_step and target_step.output is not None:
            curr_obj = target_step.output
            for subkey in parts[1:]:
                if subkey == "output":
                    continue
                if isinstance(curr_obj, dict) and subkey in curr_obj:
                    curr_obj = curr_obj[subkey]
                elif hasattr(curr_obj, subkey):
                    curr_obj = getattr(curr_obj, subkey)
                else:
                    return None
            return curr_obj

        return None
