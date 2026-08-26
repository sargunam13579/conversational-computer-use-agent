"""
NEXUS Conversational Computer-Use Agent.

High-level autonomous visual agent that accepts natural language/voice instructions,
perceives screen state via Set-of-Marks and UI automation trees, reasons iteratively,
executes precise OS actions, and supports real-time conversational steering.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from typing import Any

from nexus.agents.computer_use.actions import ComputerActionExecutor
from nexus.agents.computer_use.grounding import VisualGroundingEngine
from nexus.agents.computer_use.protocol import (
    ActionType,
    AgentStatus,
    ComputerAction,
    ScreenObservation,
    SteeringInstruction,
    StepRecord,
)
from nexus.core.config import NexusSettings, get_settings
from nexus.core.confirmation import ConfirmationManager
from nexus.llm.providers.base import LLMMessage, ModelTier
from nexus.llm.router import ModelRouter
from nexus.utils.events import EventBus, get_event_bus
from nexus.utils.logging import get_logger

log = get_logger("agents.computer_use")

COMPUTER_USE_SYSTEM_PROMPT = """You are NEXUS Conversational Computer-Use Agent, a friendly, warm, and highly skilled AI companion that operates a Windows PC for the user.

PERSONA & CONVERSATIONAL TONE:
- Talk in a warm, cheerful, friendly, and natural conversational tone (like a close tech buddy / pair programmer).
- Avoid stiff, robotic, or overly formal corporate responses.
- When narrating what you are doing, be encouraging and friendly (e.g. "Got it! Opening Camera for you now...", "Taking photo and closing camera...", "All done! I've deleted the chats for you 🎉").
- If the user uses Tamil or Tanglish, feel free to respond in warm, natural Tanglish/English (e.g. "Done-nga! Camera open panni photo eduthu close panniten", "Kandippa, chats delete panniyachu").

TASK & CLOSED-LOOP VISION REASONING:
You are given the user's high-level goal, the current screenshot (with Set-of-Marks numerical badges on interactive UI elements), detected element coordinates, live system status, and previous action history.
Your task is to iteratively reason and output the NEXT atomic computer action using the CLOSED-LOOP PROCESS:
`Access Screen (Observe) -> Action (Sub-task) -> Access Screen (Verify) -> Next Action`

Available action types:
- open_app: {"action_type": "open_app", "app_name": "camera | notepad | calc | chrome | edge | vscode | explorer | terminal | taskmgr | settings | paint"}
- click: {"action_type": "click", "x": <px>, "y": <px>, "clicks": 1} OR by element index / badge index
- double_click: {"action_type": "double_click", "x": <px>, "y": <px>}
- right_click: {"action_type": "right_click", "x": <px>, "y": <px>}
- middle_click: {"action_type": "middle_click", "x": <px>, "y": <px>}
- type_text: {"action_type": "type_text", "text": "string to type"}
- clipboard_paste: {"action_type": "clipboard_paste", "text": "string to paste"}
- hotkey: {"action_type": "hotkey", "key": "win+a | win+e | ctrl+s | enter | space | alt+f4"}
- key_press: {"action_type": "key_press", "key": "enter | space | esc"}
- mouse_scroll: {"action_type": "mouse_scroll", "direction": "down", "amount": 3}
- mouse_drag: {"action_type": "mouse_drag", "x": <start_x>, "y": <start_y>, "end_x": <end_x>, "end_y": <end_y>}
- focus_window: {"action_type": "focus_window", "text": "window title"}
- switch_window: {"action_type": "switch_window"}
- window_minimize: {"action_type": "window_minimize"}
- window_maximize: {"action_type": "window_maximize"}
- window_close: {"action_type": "window_close", "app_name": "camera | notepad | chrome | etc"}
- wait: {"action_type": "wait", "seconds": 2.0}
- ask_user: {"action_type": "ask_user", "text": "friendly question to ask the user"}
- finish: {"action_type": "finish", "reasoning": "Friendly summary of what was completed"}

🎯 CORE LIFECYCLE RULE 1: APP LIFECYCLE & NO UNWANTED AUTO-CLOSE (CRITICAL):
1. **NO UNWANTED AUTO-CLOSE**:
   - NEVER automatically close external applications (Camera, VS Code, Google Chrome, Folders, Notepad) upon task completion unless the user EXPLICITLY told you to close it (e.g. "close pannu", "close camera", "close chrome")!
   - NEVER touch or close unrelated background applications (such as user's open Google Chrome, VS Code, or Explorer windows).
   - Keep applications open so the user can continue their workflow seamlessly.

2. **ALWAYS ASK WHAT TO DO NEXT ("Next enna pannattum?")**:
   - Whenever you complete the user's requested task, you MUST enthusiastically confirm completion and ask what to do next in your narration:
     * e.g. "Photo எடுத்துட்டேன்-பா! Next என்ன பண்ணட்டும்-ங்க? 📸✨" / "Photo eduthuten-pa! Next enna pannattum?"
     * e.g. "VS Code open பண்ணிட்டேன்! Next என்ன பண்ணட்டும்? 💻" / "VS Code open panniten! Next enna pannattum-nga?"
     * e.g. "Desktop Java folder open பண்ணிட்டேன்-ங்க! Next என்ன பண்ணட்டும்? 📂"

3. **INNER TASKS PROTECTION (NEXUS APPLICATION)**:
   - STRICT PROHIBITION: NEVER output `window_close` or press Alt+F4 for tasks inside Nexus (like deleting chat items or settings)!

🎯 CORE LIFECYCLE RULE 2: CONVERSATIONAL DATA QUERIES VS COMPUTER ACTIONS:
1. **Direct Data Answers**:
   - If the user asks for data, questions, weather, battery percentage, system info, calculations, or chat:
   - Answer DIRECTLY in "narration" using live telemetry or knowledge!
   - STRICT PROHIBITION: NEVER open a browser, Google Chrome, or search windows unless the user explicitly requested: "Google search pannu", "search on browser", "open chrome".
2. **Perform Actions Strictly on User Need**:
   - Only open, click, type, or close what the user explicitly asked for.

🎯 CORE LIFECYCLE RULE 3: HIERARCHICAL SUB-TASK SPLITTING & CLOSED-LOOP SCREEN VERIFICATION:
When given compound or multi-item requests (e.g., `"hello" and "hiii" chats ah delete pannu`):
1. **Split into ordered sub-tasks**:
   - Task 1: Delete "hello" chat -> Sub-task 1.1: Click 3-dot options menu -> Sub-task 1.2: Click "Delete" -> Sub-task 1.3: Verify "hello" chat is deleted.
   - Task 2: Delete "hiii" chat -> Sub-task 2.1: Click 3-dot options menu -> Sub-task 2.2: Click "Delete" -> Sub-task 2.3: Verify "hiii" chat is deleted.
   - Finish: Output `finish` and ask *"Next enna pannattum-nga?"*!

2. **STRICT VERIFICATION & STEP ROLLBACK**:
   - Inspect screen after each sub-task to verify execution.
   - If a click missed or dropdown didn't appear, immediately roll back to previous sub-task and re-target coordinates accurately.

🎯 CORE LIFECYCLE RULE 3: MULTILINGUAL COMPREHENSION (TAMIL, TANGLISH, ENGLISH) & ATTRACTIVE CONVERSATIONAL REPLAY:
1. **Multilingual Understanding**:
   - Fluently understand user instructions in pure Tamil (e.g. "VS Code open பண்ணு", "Desktop-la இருக்குற Java folder open பண்ணு", "New file create பண்ணி palindrome code போடு", "Run பண்ணு"), Tanglish, or English.
2. **Fast & Attractive Spoken Narration**:
   - Deliver enthusiastic, charming, and snappy responses in natural conversational Tamil / Tanglish:
     * When opening an app: "VS Code open பண்ணிட்டேன்-பா! 💻✨" / "VS Code open panniten!"
     * When navigating folders: "Java folder-ah open பண்ணிட்டேன்-பா! 📂" / "Java folder open panniten-ga 👍"
     * When writing code & asking confirmation: Use `ask_user` with "String palindrome code type பண்ணி save பண்ணிட்டேன்! Run பண்ணட்டா? 🚀"
     * When executing code/action: "Done-nga! Code successfully run பண்ணியாச்சு! Output பாருங்க 🎉"
   - Always use enthusiastic, lively completion markers: "Done-nga!", "Mudichuten!", "Finish panniten!", "Panniten-pa!".

⚡ EFFICIENCY, SHORTEST PATH & QUICK ACTIONS RULES:
1. QUICK SETTINGS & SYSTEM TOGGLES (Energy Saver, Battery Saver, Wi-Fi, Bluetooth, Airplane Mode, Night Light, Volume, Brightness):
   - FASTEST 2-STEP METHOD:
     * Step 1: Open Windows Quick Settings using `{"action_type": "hotkey", "key": "win+a"}`.
     * Step 2: In Quick Settings popup, click the button for "Energy Saver" / "Battery Saver" / "Wi-Fi" / "Bluetooth", and output `{"action_type": "finish"}`!
   - STRICT PROHIBITION: NEVER launch full Settings app (`ms-settings:`) when Quick Settings (`win+a`) has the toggle.

2. SYSTEM STATUS QUERIES (Battery Percentage, Network Name, Date/Time, Volume):
   - Answer directly using live system status telemetry provided in the prompt. State the answer in "narration" and output `{"action_type": "finish"}` immediately in 1 step!

3. DISTINGUISHING COMPUTER ACTIONS VS CONVERSATIONAL QUESTIONS:
   - PROHIBITION: NEVER click or type into the active NexUs chat input box on screen!
   - If user asks a conversational or factual question, answer directly in "narration" and output `finish`.

Output format (strictly JSON object only):
{
  "thought": "Step-by-step reasoning explaining which sub-task is being executed and verified",
  "narration": "Friendly conversational sentence in attractive Tamil/Tanglish spoken to the user (e.g. 'Done-nga! VS Code open panniten 🎉', 'Java folder open panniten-pa! 👍')",
  "action": {
    "action_type": "open_app | click | double_click | right_click | middle_click | type_text | clipboard_paste | hotkey | key_press | mouse_scroll | mouse_drag | focus_window | switch_window | window_minimize | window_maximize | window_close | wait | ask_user | finish",
    "x": 500,
    "y": 320,
    "badge_index": 3,
    "text": "text if applicable",
    "app_name": "app name if open_app or window_close",
    "key": "shortcut if applicable",
    "reasoning": "why"
  }
}
"""


class ConversationalComputerUseAgent:
    """
    Conversational Computer-Use Agent with Vision-Action closed loop
    and live human-in-the-loop steering.
    """

    def __init__(
        self,
        router: ModelRouter | None = None,
        grounding: VisualGroundingEngine | None = None,
        executor: ComputerActionExecutor | None = None,
        confirmation: ConfirmationManager | None = None,
        event_bus: EventBus | None = None,
        settings: NexusSettings | None = None,
        max_steps: int = 25,
    ) -> None:
        self._router = router or ModelRouter()
        self._grounding = grounding or VisualGroundingEngine()
        self._executor = executor or ComputerActionExecutor()
        self._confirmation = confirmation or ConfirmationManager()
        self._event_bus = event_bus or get_event_bus()
        self._settings = settings or get_settings()
        self._max_steps = max_steps

        self._status = AgentStatus.IDLE
        self._steering_queue: asyncio.Queue[SteeringInstruction] = asyncio.Queue()
        self._history: list[StepRecord] = []
        self._stop_requested = False
        self._current_task: str = ""

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def history(self) -> list[StepRecord]:
        return list(self._history)

    def request_stop(self) -> None:
        """Immediately trigger emergency stop for computer-use loop."""
        log.warning("Computer-Use stop requested by user or system kill switch.")
        self._stop_requested = True
        self._status = AgentStatus.STOPPED

    async def steer(self, instruction: str | SteeringInstruction) -> None:
        """Inject conversational steering instruction while agent is operating."""
        if isinstance(instruction, str):
            instruction = SteeringInstruction(instruction=instruction, interrupt_current_action=True)
        log.info("Received steering instruction: %s", instruction.instruction)
        await self._steering_queue.put(instruction)

    async def observe(self, tag_elements: bool = True) -> ScreenObservation:
        """Observe and return current screen state with Set-of-Marks overlay."""
        return await self._grounding.observe_screen(tag_elements=tag_elements)

    def _action_signature(self, action: ComputerAction) -> str:
        """Compute normalized action signature for loop and cycle detection."""
        parts = [str(action.action_type.value)]
        if action.app_name:
            parts.append(f"app:{action.app_name.lower().strip()}")
        if action.key:
            parts.append(f"key:{action.key.lower().strip()}")
        if action.text:
            parts.append(f"text:{action.text.strip()[:25]}")
        if action.x is not None and action.y is not None:
            parts.append(f"pos:({round(action.x, -1)},{round(action.y, -1)})")
        return "|".join(parts)

    def _detect_loop(self, next_action: ComputerAction) -> tuple[bool, str]:
        """
        Check if executing next_action creates an infinite loop or repeats a completed cycle.

        Returns:
            (is_loop, reason_description)
        """
        curr_sig = self._action_signature(next_action)
        past_sigs = [self._action_signature(rec.action) for rec in self._history]
        all_sigs = past_sigs + [curr_sig]

        # 1. Check for 2-step ping-pong cycle: e.g. [A, B, A, B] (e.g. open_app -> close -> open_app -> close)
        if len(all_sigs) >= 4 and all_sigs[-4:-2] == all_sigs[-2:]:
            return True, f"2-step repetition cycle detected: {all_sigs[-2:]}"

        # 2. Check for 3-step cycle: e.g. [A, B, C, A, B, C]
        if len(all_sigs) >= 6 and all_sigs[-6:-3] == all_sigs[-3:]:
            return True, f"3-step repetition cycle detected: {all_sigs[-3:]}"

        # 3. Check for re-opening an app that was already opened and subsequently closed in this session
        if next_action.action_type == ActionType.OPEN_APP:
            app = (next_action.app_name or "").lower().strip()
            if app:
                opened = False
                closed_after = False
                for rec in self._history:
                    if rec.action.action_type == ActionType.OPEN_APP and (rec.action.app_name or "").lower().strip() == app:
                        opened = True
                    elif opened and rec.action.action_type in (ActionType.WINDOW_CLOSE, ActionType.CLICK):
                        closed_after = True
                if opened and closed_after:
                    return True, f"Application '{app}' was already opened and closed in this task"

        # 4. Check for 3 consecutive identical actions (excluding wait/scroll)
        if len(all_sigs) >= 3 and all_sigs[-1] == all_sigs[-2] == all_sigs[-3]:
            if next_action.action_type not in (ActionType.WAIT, ActionType.MOUSE_SCROLL):
                return True, f"Repeated identical action 3 times: {curr_sig}"

        return False, ""

    async def run_goal(self, goal: str, auto_confirm: bool = False) -> dict[str, Any]:
        """
        Execute an end-to-end conversational computer-use goal.
        """
        self._stop_requested = False
        self._current_task = goal
        self._history.clear()
        self._status = AgentStatus.OBSERVING

        await self._event_bus.emit(
            "computer_use.started",
            {"goal": goal, "max_steps": self._max_steps},
        )

        step_num = 0
        final_result: dict[str, Any] = {"status": "completed", "goal": goal, "steps_executed": 0}
        opened_external_apps: list[str] = []

        # Check if user explicitly requested to keep external windows open
        lower_goal = goal.lower()
        explicit_keep_open = any(
            kw in lower_goal
            for kw in [
                "don't close",
                "dont close",
                "close pannatha",
                "close panatha",
                "keep open",
                "keep it open",
                "open laye",
                "moodatha",
                "do not close",
            ]
        )

        try:
            while step_num < self._max_steps:
                if self._stop_requested:
                    self._status = AgentStatus.STOPPED
                    return {"status": "stopped", "reason": "User triggered emergency stop", "steps_executed": len(self._history)}

                step_num += 1
                step_start = time.perf_counter()

                # Check if user injected steering instructions
                active_steering: list[str] = []
                while not self._steering_queue.empty():
                    steer_item = self._steering_queue.get_nowait()
                    active_steering.append(steer_item.instruction)

                # 1. Observe Screen
                self._status = AgentStatus.OBSERVING
                obs = await self._grounding.observe_screen(tag_elements=True)

                # 2. Reason with Vision Multimodal LLM
                self._status = AgentStatus.THINKING
                decision = await self._decide_next_action(
                    goal=goal,
                    observation=obs,
                    step_num=step_num,
                    steering=active_steering,
                )

                thought = decision.get("thought", "")
                narration = decision.get("narration", "")
                action_data = decision.get("action", {})
                action_type_str = action_data.get("action_type", "wait")

                try:
                    action_type = ActionType(action_type_str)
                except ValueError:
                    action_type = ActionType.WAIT

                # Resolve coordinates from element badge index if provided
                badge_idx = action_data.get("badge_index") or action_data.get("element_index")
                resolved_x = action_data.get("x")
                resolved_y = action_data.get("y")
                if badge_idx and (resolved_x is None or resolved_y is None):
                    matched_el = self._grounding.find_element(obs.detected_elements, badge_idx)
                    if matched_el and "center" in matched_el:
                        resolved_x, resolved_y = matched_el["center"]

                comp_action = ComputerAction(
                    action_type=action_type,
                    x=resolved_x,
                    y=resolved_y,
                    end_x=action_data.get("end_x"),
                    end_y=action_data.get("end_y"),
                    text=action_data.get("text"),
                    app_name=action_data.get("app_name"),
                    key=action_data.get("key"),
                    keys=action_data.get("keys"),
                    direction=action_data.get("direction", "down"),
                    amount=action_data.get("amount", 3),
                    seconds=action_data.get("seconds", 1.0),
                    reasoning=thought,
                )

                # Strict User Permission Guard: NEVER close applications unless user explicitly requested 'close'
                if action_type == ActionType.WINDOW_CLOSE:
                    user_asked_close = any(kw in lower_goal for kw in ["close", "moodu", "exit", "quit", "மூடு", "கிளோஸ்"])
                    if not user_asked_close:
                        log.info("Blocked unauthorized WINDOW_CLOSE action; keeping application open.")
                        action_type = ActionType.FINISH
                        if not any(q in (narration or "").lower() for q in ["next", "என்ன", "enna", "what next", "pannattum"]):
                            narration = f"{narration} Next என்ன பண்ணட்டும்? ✨" if narration else "Task complete panniten-pa! Next என்ன பண்ணட்டும்? ✨"

                # Loop and cycle protection
                is_loop, loop_reason = self._detect_loop(comp_action)
                if is_loop and action_type != ActionType.FINISH:
                    log.warning("Cycle/Loop prevented: %s. Auto-completing task.", loop_reason)
                    action_type = ActionType.FINISH
                    narration = narration or "Task completed successfully! Next என்ன பண்ணட்டும்? 🎉"

                # Check for completion
                if action_type == ActionType.FINISH:
                    if narration and not any(q in narration.lower() for q in ["next", "என்ன", "enna", "what next", "pannattum"]):
                        narration = f"{narration} Next என்ன பண்ணட்டும்? ✨"

                    self._status = AgentStatus.COMPLETED
                    await self._event_bus.emit(
                        "computer_use.finished",
                        {"goal": goal, "narration": narration, "step": step_num},
                    )
                    final_result["status"] = "completed"
                    final_result["narration"] = narration
                    break

                if action_type == ActionType.ASK_USER:
                    self._status = AgentStatus.WAITING_USER
                    await self._event_bus.emit(
                        "computer_use.question",
                        {"question": action_data.get("text", thought), "step": step_num},
                    )
                    final_result["status"] = "waiting_user"
                    final_result["question"] = action_data.get("text", thought)
                    final_result["narration"] = narration
                    break

                # 3. Execute Action
                self._status = AgentStatus.ACTING
                await self._event_bus.emit(
                    "computer_use.action",
                    {
                        "step": step_num,
                        "action": str(action_type),
                        "thought": thought,
                        "narration": narration,
                        "coordinates": (comp_action.x, comp_action.y),
                    },
                )

                action_res = await self._executor.execute(comp_action)

                step_elapsed = time.perf_counter() - step_start
                step_record = StepRecord(
                    step_number=step_num,
                    observation=obs,
                    thought=thought,
                    action=comp_action,
                    action_result=action_res,
                    success=action_res.get("success", True),
                    elapsed_seconds=round(step_elapsed, 3),
                )
                self._history.append(step_record)

                # Snappy UI redraw delay
                await asyncio.sleep(0.01)

            final_result["steps_executed"] = len(self._history)
            final_result["history"] = [
                {
                    "step": s.step_number,
                    "thought": s.thought,
                    "action": str(s.action.action_type),
                    "coordinates": (s.action.x, s.action.y),
                    "success": s.success,
                    "elapsed_seconds": s.elapsed_seconds,
                }
                for s in self._history
            ]
            return final_result

        except Exception as e:
            log.exception("Computer-use loop encountered error: %s", e)
            self._status = AgentStatus.FAILED
            return {"status": "failed", "error": str(e), "steps_executed": len(self._history)}
        finally:
            if self._status in (AgentStatus.OBSERVING, AgentStatus.THINKING, AgentStatus.ACTING, AgentStatus.COMPLETED, AgentStatus.STOPPED):
                self._status = AgentStatus.IDLE

    async def _decide_next_action(
        self,
        goal: str,
        observation: ScreenObservation,
        step_num: int,
        steering: list[str],
    ) -> dict[str, Any]:
        """Invoke Vision LLM to determine the next computer action."""
        await self._router.initialize()

        # Build detailed history context
        history_summary = []
        for rec in self._history[-8:]:
            act_details = []
            if rec.action.app_name:
                act_details.append(f"app='{rec.action.app_name}'")
            if rec.action.text:
                act_details.append(f"text='{rec.action.text}'")
            if rec.action.key:
                act_details.append(f"key='{rec.action.key}'")
            if rec.action.x is not None and rec.action.y is not None:
                act_details.append(f"x={rec.action.x}, y={rec.action.y}")
            detail_str = f" ({', '.join(act_details)})" if act_details else ""
            res_str = rec.action_result.get("status", "ok") if isinstance(rec.action_result, dict) else "ok"
            history_summary.append(
                f"- Step {rec.step_number}: Action={rec.action.action_type.value}{detail_str} | Thought='{rec.thought}' | Result={res_str}"
            )

        steering_text = ""
        if steering:
            steering_text = "\n⚠️ USER MID-TASK GUIDANCE / INSTRUCTIONS:\n" + "\n".join(f"- {s}" for s in steering)

        # Retrieve live battery/system state if available
        system_status_line = ""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                plug_str = "Plugged In (Charging)" if battery.power_plugged else "On Battery"
                system_status_line = f"LIVE SYSTEM STATUS: Battery {battery.percent}%, {plug_str}\n"
        except Exception:
            pass

        # Task guideline hint
        task_category_hint = (
            "STRICT ACTION RULE: NEVER automatically close any application unless the user EXPLICITLY instructed 'close' in their goal. "
            "Never close background apps (like Google Chrome, VS Code, or Nexus). "
            "When completing any goal, keep apps open and enthusiastically ask 'Next enna pannattum?'"
        )

        prompt = (
            f"GOAL: {goal}\n"
            f"{task_category_hint}\n"
            f"CURRENT STEP: {step_num} / {self._max_steps}\n"
            f"SCREEN RESOLUTION: {observation.screen_width}x{observation.screen_height}\n"
            f"{system_status_line}"
            f"RECENT HISTORY:\n" + ("\n".join(history_summary) if history_summary else "None (starting task)") +
            f"{steering_text}\n\n"
            f"CLOSED-LOOP VERIFICATION INSTRUCTION:\n"
            f"- Observe the detected elements and screen state.\n"
            f"- Verify if the previous step's sub-task completed successfully.\n"
            f"- Select the next sub-action (e.g., click 3-dots, click delete, take photo, window_close, or finish).\n\n"
            f"DETECTED UI ELEMENTS ON SCREEN ({len(observation.detected_elements)} found):\n"
        )

        for el in observation.detected_elements[:50]:
            prompt += f"  [Badge #{el.get('index')}] {el.get('type')}: '{el.get('name')}' at center=({el['center'][0]}, {el['center'][1]})\n"

        prompt += "\nOutput your decision as a valid JSON object matching the schema."

        # Read screenshot image as base64 if available
        image_base64 = None
        target_img_path = observation.som_screenshot_path or observation.screenshot_path
        if target_img_path and os.path.exists(target_img_path):
            try:
                with open(target_img_path, "rb") as f:
                    image_base64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                log.debug("Could not read screenshot image: %s", e)

        messages = [
            LLMMessage(role="system", content=COMPUTER_USE_SYSTEM_PROMPT),
            LLMMessage(
                role="user",
                content=prompt,
                images=[image_base64] if image_base64 else None,
            ),
        ]

        try:
            resp = await self._router.generate(
                messages=messages,
                tier=ModelTier.VISION,
                temperature=0.1,
            )
            raw_text = resp.content or "{}"

            # Clean possible markdown formatting
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            parsed = json.loads(raw_text)
            return parsed
        except Exception as e:
            log.warning("Vision LLM decision fallback: %s", e)
            # Fallback heuristic or wait
            return {
                "thought": f"Observation complete. Analyzing screen elements ({str(e)}).",
                "narration": "Assessing application layout...",
                "action": {"action_type": "wait", "seconds": 1.0},
            }
