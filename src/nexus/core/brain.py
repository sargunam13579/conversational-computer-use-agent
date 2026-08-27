"""
NEXUS AI Brain.

The central intelligence hub that wires everything together:
  - LLM Router (model selection)
  - Tool Registry + Executor (actions)
  - Context Manager (conversation memory)
  - Orchestrator (agentic loop)
  - Voice Pipeline (voice I/O — Phase 2)
  - Identity & Wake Word Manager (Phase 3)
  - Security Confirmation Manager (Phase 3)

This is the main entry point for processing user requests.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nexus.agents.laptop.agent import LaptopAgent
from nexus.core.config import NexusSettings, get_settings
from nexus.core.confirmation import ConfirmationAction, ConfirmationManager
from nexus.core.context import ContextManager
from nexus.core.identity import IdentityManager
from nexus.core.orchestrator import Orchestrator
from nexus.llm.prompts.system import build_system_prompt
from nexus.llm.providers.base import ModelTier
from nexus.llm.router import ModelRouter
from nexus.tools.executor import ToolExecutor
from nexus.tools.registry import ToolRegistry
from nexus.utils.logging import get_logger

log = get_logger("core.brain")

# Regex patterns to detect intent to change the assistant's name
_NAME_CHANGE_PATTERNS = [
    re.compile(
        r"^(?:(?:hey|ok|okay|hi|hello)\s+)?(?:(?P<cur>\w+)[,\s:]+)?(?:from\s+now\s+on\s+)?(?:your\s+name\s+is|change\s+your\s+name\s+to|call\s+yourself|set\s+your\s+name\s+to|rename\s+yourself\s+to)\s+(?P<target>[A-Za-z0-9_-]+)(?:\s+from\s+now\s+on)?[.!?]*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:(?:hey|ok|okay|hi|hello)\s+)?(?:(?P<cur>\w+)[,\s:]+)?(?:i\s+want\s+to\s+call\s+you|please\s+change\s+your\s+name\s+to)\s+(?P<target>[A-Za-z0-9_-]+)(?:\s+from\s+now\s+on)?[.!?]*$",
        re.IGNORECASE,
    ),
]


class NexusBrain:
    """
    The NEXUS AI Brain — central intelligence hub.

    Initializes all subsystems and provides a simple interface for
    processing user input.
    """

    def __init__(
        self,
        settings: NexusSettings | None = None,
        identity: IdentityManager | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._identity = identity or IdentityManager()
        self._confirmation = ConfirmationManager()

        self._router = ModelRouter(self._settings)
        self._registry = ToolRegistry()
        self._context = ContextManager(
            max_turns=self._settings.memory.working_memory_max_turns,
        )
        self._executor = ToolExecutor(
            registry=self._registry,
            max_retries=self._settings.llm.max_retries,
        )
        self._orchestrator = Orchestrator(
            router=self._router,
            registry=self._registry,
            executor=self._executor,
            context=self._context,
        )
        from nexus.accessibility.audio_feedback import AudioFeedbackManager
        from nexus.accessibility.custom_commands import CustomCommandManager
        from nexus.devices.manager import UnifiedDeviceManager
        from nexus.memory.manager import MemoryManager
        from nexus.planning.manager import TaskManager
        from nexus.reliability.connection_recovery import ConnectionRecoveryManager
        from nexus.reliability.offline import OfflineModeManager
        from nexus.security.pairing import DevicePairingManager
        from nexus.security.permissions import PermissionScopeManager

        self._memory = MemoryManager()
        self._devices = UnifiedDeviceManager()
        self._task_manager = TaskManager(
            router=self._router,
            registry=self._registry,
            tool_executor=self._executor,
            confirmation_manager=self._confirmation,
        )
        self._permissions = PermissionScopeManager()
        self._pairing = DevicePairingManager()
        self._custom_commands = CustomCommandManager()
        self._audio_feedback = AudioFeedbackManager()
        self._offline = OfflineModeManager()
        self._recovery = ConnectionRecoveryManager()

        self._initialized = False
        self._voice_pipeline: Any | None = None
        self._laptop_agent: LaptopAgent | None = None
        from nexus.agents.computer_use.agent import ConversationalComputerUseAgent

        self._computer_use_agent = ConversationalComputerUseAgent(
            router=self._router,
            confirmation=self._confirmation,
            settings=self._settings,
        )

    async def initialize(self) -> None:
        """
        Initialize all subsystems.

        Call this once at startup before processing any requests.
        """
        if self._initialized:
            return

        log.info("Initializing NEXUS Brain...")

        # Initialize LLM providers
        await self._router.initialize()

        if not self._router.has_providers:
            log.warning(
                "No LLM providers available! "
                "Set API keys in .env or start Ollama for local inference."
            )

        # Register tools
        self._register_tools()

        # Set up system prompt with assistant identity
        self._refresh_system_prompt()

        self._initialized = True
        log.info(
            "%s Brain initialized — %d tools, %d LLM providers",
            self._identity.name,
            self._registry.count,
            len(self._router.available_providers),
        )

    def _refresh_system_prompt(self) -> None:
        """Update the system prompt with current identity and available tools."""
        system_prompt = build_system_prompt(
            available_tools=self._registry.tool_names,
            user_name=self._identity.user_name,
            assistant_name=self._identity.name,
        )
        self._context.set_system_prompt(system_prompt)
        log.debug("System prompt refreshed for assistant '%s'", self._identity.name)

    def _register_tools(self) -> None:
        """Register all available tools."""
        if self._settings.laptop_agent.enabled:
            from nexus.agents.laptop.agent import LaptopAgent
            from nexus.tools.system import get_laptop_tools

            laptop_tools = get_laptop_tools()
            self._registry.register_many(laptop_tools)
            self._laptop_agent = LaptopAgent(
                settings=self._settings,
                confirmation=self._confirmation,
            )
            log.info("Registered %d laptop tools and created LaptopAgent", len(laptop_tools))
        else:
            from nexus.tools.system.basic import get_starter_tools

            starter_tools = get_starter_tools()
            self._registry.register_many(starter_tools)
            log.info("Registered %d starter tools", len(starter_tools))

    def _detect_name_change_intent(self, user_input: str) -> str | None:
        """
        Detect if the user is asking to change the assistant's name.

        Returns:
            The requested new name, or None if no name change requested.
        """
        text = user_input.strip()
        for pattern in _NAME_CHANGE_PATTERNS:
            m = pattern.match(text)
            if m:
                target = m.group("target").strip()
                if target and target.lower() != self._identity.name.lower():
                    return target
        return None

    async def process(self, user_input: str, allow_tools: bool = True) -> str:
        """
        Process a user input and return the response.

        This is the main entry point for all user interactions.

        Args:
            user_input: The user's message or command.
            allow_tools: Whether system/laptop tools are allowed for execution.

        Returns:
            NEXUS's response as a string.
        """
        if not self._initialized:
            await self.initialize()

        clean_input = user_input.strip()

        # Audio feedback on input received
        self._audio_feedback.on_wake()

        # Step 1: Check if user issued an emergency kill switch or cancellation command
        from nexus.planning.cancellation import CancellationType

        cancel_type = self._task_manager.cancellation.detect_cancellation_intent(clean_input)
        if cancel_type == CancellationType.EMERGENCY:
            self._task_manager.emergency_stop()
            self._audio_feedback.on_emergency_stop()
            return "🚨 EMERGENCY STOP: All active tasks and operations have been halted immediately."
        elif cancel_type == CancellationType.GRACEFUL and self._task_manager.active_plan:
            self._task_manager.cancel_active_task()
            return "Task cancelled. Stopped current operation."

        # Step 2: Check custom accessibility macros / command expansion
        expanded = self._custom_commands.match_and_expand(clean_input)
        if expanded:
            log.info("Expanded custom command '%s' into %d action(s)", clean_input, len(expanded))
            clean_input = expanded[0] if len(expanded) == 1 else "; ".join(expanded)

        # Step 3: Check if offline / offline-capable command
        if (self._offline.force_offline or not self._router.has_providers) and self._offline.can_handle_locally(clean_input):
            local_res = await self._offline.execute_offline_command(clean_input)
            if local_res.success:
                self._audio_feedback.on_success()
            else:
                self._audio_feedback.on_error()
            return local_res.response_text

        # Step 4: Check if there is a pending confirmation awaiting user response
        if self._confirmation.has_pending:
            status, message = await self._confirmation.handle_response(clean_input)
            return message

        # Step 5: Check if user is asking to change the assistant name
        target_name = self._detect_name_change_intent(clean_input)
        if target_name:
            self._audio_feedback.on_confirmation()
            return self.request_name_change(target_name)

        # Step 6: Inspect user input for explicit preference learning
        await self._memory.auto_learn_from_message(clean_input)

        # Step 7: Check if input is a multi-step task goal (only if tools allowed)
        if allow_tools and self._task_manager.is_multi_step_goal(clean_input):
            log.info("Detected multi-step goal, routing to TaskManager")
            task_result = await self._task_manager.run_goal(clean_input)
            if self._settings.ui.show_thinking and task_result.plan_id:
                active_p = self._task_manager.get_task(task_result.plan_id)
                if active_p:
                    self._task_manager.progress.render_progress_panel(active_p)
            if task_result.success:
                self._audio_feedback.on_success()
            else:
                self._audio_feedback.on_error()
            return task_result.final_output

        # Step 8: Single-turn request through agentic orchestrator
        tier = self._classify_tier(clean_input)

        response = await self._orchestrator.process(
            user_input=clean_input,
            tier=tier,
            show_thinking=self._settings.ui.show_thinking,
            allow_tools=allow_tools,
        )
        self._audio_feedback.on_success()
        return response

    def request_name_change(self, target_name: str) -> str:
        """
        Initiate a name change request requiring user confirmation.

        Args:
            target_name: The requested new name for the assistant.

        Returns:
            Confirmation prompt message.
        """
        current_name = self._identity.name
        prompt = f"Do you want me to change my name from {current_name} to {target_name}?"

        self._confirmation.create_confirmation(
            action=ConfirmationAction.CHANGE_NAME,
            prompt_message=prompt,
            payload={"target_name": target_name},
            on_confirm=self._apply_name_change,
        )
        return prompt

    def _apply_name_change(self, payload: dict[str, Any]) -> str:
        """Apply confirmed name change and update system prompts."""
        target_name = payload["target_name"]
        self._identity.set_name(target_name, sync_wake_word=True)
        self._refresh_system_prompt()

        # Update running voice pipeline wake words if active
        if self._voice_pipeline is not None:
            self._voice_pipeline.wake_word_detector.update_wake_words(
                primary=self._identity.wake_word,
                aliases=self._identity.aliases,
            )

        log.info("Assistant name successfully changed to %s", target_name)
        return f"My name has been changed to {target_name}."

    def _classify_tier(self, user_input: str) -> ModelTier:
        """
        Simple heuristic to select the model tier based on input.

        In Phase 4, this will be replaced by an LLM-based classifier.
        """
        input_lower = user_input.lower()

        # Use SMART model for complex requests
        complex_keywords = [
            "plan",
            "analyze",
            "explain",
            "compare",
            "summarize",
            "write",
            "create",
            "design",
            "debug",
            "help me",
            "step by step",
            "how to",
            "why",
        ]
        if any(kw in input_lower for kw in complex_keywords):
            return ModelTier.SMART

        # Use FAST model for everything else
        return ModelTier.FAST

    def reset_conversation(self) -> None:
        """Reset the conversation context for a fresh start."""
        self._orchestrator.reset()
        log.info("Conversation reset")

    # --- Voice Pipeline (Phase 2) ---

    async def start_voice(self) -> None:
        """
        Initialize and start the voice pipeline.

        Creates the VoicePipeline from settings and begins
        listening for voice input.
        """
        if not self._initialized:
            await self.initialize()

        if self._voice_pipeline is not None and self._voice_pipeline.is_running:
            log.warning("Voice pipeline is already running")
            return

        try:
            from nexus.voice.pipeline import VoicePipeline

            self._voice_pipeline = VoicePipeline.from_settings(
                brain=self,
                settings=self._settings,
            )
            await self._voice_pipeline.start()
            log.info("Voice pipeline started")
        except Exception as e:
            log.error("Failed to start voice pipeline: %s", e)
            raise

    async def stop_voice(self) -> None:
        """Stop the voice pipeline and release resources."""
        if self._voice_pipeline is not None:
            await self._voice_pipeline.stop()
            self._voice_pipeline = None
            log.info("Voice pipeline stopped")

    @property
    def identity(self) -> IdentityManager:
        """Access the assistant's IdentityManager."""
        return self._identity

    @property
    def memory_manager(self) -> Any:
        """Get the memory manager instance."""
        return self._memory

    @property
    def device_manager(self) -> Any:
        """Get the unified device manager instance."""
        return self._devices

    @property
    def confirmation(self) -> ConfirmationManager:
        """Access the ConfirmationManager."""
        return self._confirmation

    @property
    def name(self) -> str:
        """Assistant name shortcut."""
        return self._identity.name

    @property
    def voice_pipeline(self) -> Any:
        """Access the voice pipeline (None if not started)."""
        return self._voice_pipeline

    @property
    def is_voice_active(self) -> bool:
        """Whether the voice pipeline is currently running."""
        return self._voice_pipeline is not None and self._voice_pipeline.is_running

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def available_tools(self) -> list[str]:
        return self._registry.tool_names

    @property
    def laptop_agent(self) -> LaptopAgent | None:
        """Access the laptop agent instance (if enabled)."""
        return self._laptop_agent

    @property
    def task_manager(self) -> Any:
        """Access the task planning and execution manager."""
        return self._task_manager

    @property
    def memory(self) -> Any:
        """Access the MemoryManager."""
        return self._memory

    @property
    def permissions(self) -> Any:
        """Access the PermissionScopeManager."""
        return self._permissions

    @property
    def pairing(self) -> Any:
        """Access the DevicePairingManager."""
        return self._pairing

    @property
    def custom_commands(self) -> Any:
        """Access the CustomCommandManager."""
        return self._custom_commands

    @property
    def audio_feedback(self) -> Any:
        """Access the AudioFeedbackManager."""
        return self._audio_feedback

    @property
    def offline_manager(self) -> Any:
        """Access the OfflineModeManager."""
        return self._offline

    @property
    def recovery_manager(self) -> Any:
        """Access the ConnectionRecoveryManager."""
        return self._recovery

    @property
    def computer_use_agent(self) -> Any:
        """Access the Conversational Computer-Use Agent instance."""
        return self._computer_use_agent
