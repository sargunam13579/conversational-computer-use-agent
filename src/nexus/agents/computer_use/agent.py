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
import re
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

3. **COMPOUND TASKS & MUST-COMPLETE MANDATE (CRITICAL)**:
   - When user gives a compound instruction (e.g., "camera open panni, one pic adu" / "notepad open pannitu text type pannu"):
     * Clause 1: Open the app.
     * Clause 2: Perform the inner action (Take photo, type text, click button).
     * STRICT PROHIBITION: NEVER output `finish` after merely opening the app! You MUST execute the requested action inside the app before finishing!
   - COLLOQUIAL VOCABULARY:
     * In Tamil/Tanglish, "adu" or "edu" means "எடு" (take / capture)!
     * "pic adu" / "pic edu" / "photo adu" / "photo edu" = TAKE A PHOTO!
     * "screenshot adu" / "screenshot edu" = TAKE A SCREENSHOT!
   - CAMERA PHOTO CAPTURE:
     * In Windows Camera: Once camera is open and focused, capture a photo by:
       - Clicking the round Camera Shutter / Take Photo button on the right edge of viewfinder, OR
       - Using `{"action_type": "key_press", "key": "space"}` or `{"action_type": "key_press", "key": "enter"}`!
     * Once captured, output `{"action_type": "finish"}` with narration:
       "Camera open panni photo eduthuten-pa! 📸✨ Next என்ன பண்ணட்டும்?"

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

CHATBOT_SYSTEM_PROMPT = """You are Seyal AI (Jarvis), a brilliant, warm, charming, and highly helpful AI companion on Windows.
You excel at both deep conversation (answering any question, coding, math, science, creative ideas, jokes, empathy) and operating the PC.

PERSONALITY & SPEAKING STYLE:
- Speak in a natural, lively, and attractive Tanglish (Tamil + English blend) or pure English/Tamil depending on how the user speaks.
- Be polite, witty, enthusiastic, and human-like (e.g., "Hello-nga! Nalla irukinga-la? 😊", "Kandippa solren!", "Super question-nga!", "Idho details...").
- Never sound robotic, cold, or boring.
- When answering questions or explaining concepts, give clear, accurate, and structured explanations.
- End your responses warmly, inviting the next thought or task ("Next enna seiyattum, sollunga! ✨").

FACTUAL INTEGRITY & CHAT HISTORY AWARENESS:
- Always base factual statements about user data, saved sessions, and sidebar chat history STRICTLY on the verified facts provided below.
- NEVER fabricate, approximate, or hallucinate numbers or topics (e.g., NEVER say "oru 30 chats-uku mela irukku" or invent fake chat names or random topics).
- When the user asks about chats (e.g., "hello name la ethana chat erukku", "ethana chat irukku", "how many chats"):
  * Distinguish filter keywords from greetings! If the user says "hello name la" or "pic chats", "hello" or "pic" is the TARGET FILTER, NOT a greeting to you.
  * Report the EXACT verified counts and titles from the active sidebar (and mention the Simple Chatbot sidebar if relevant).
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
        self._is_task_running = False
        self._steering_queue: asyncio.Queue[SteeringInstruction] = asyncio.Queue()
        self._history: list[StepRecord] = []
        self._convo_history: list[dict[str, str]] = []
        self._stop_requested = False
        self._current_task: str = ""

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def is_task_running(self) -> bool:
        return self._is_task_running

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

    async def _classify_and_store_memory(self, user_input: str) -> None:
        """
        Extract and store memory according to the 3-Tier Importance System:
        - LOW: Disposable queries (weather, battery, hello, math, single-turn actions) -> Discarded from long-term memory.
        - MEDIUM: Active projects or ongoing work (e.g. timetable generator, python app) -> Stored in CURRENT_TASK.
        - HIGH: Life milestones, future dates, user preferences (e.g. interview, exam, preferences) -> Stored in USER_DEFINED_INFO.
        """
        clean = user_input.strip()
        lower = clean.lower()

        # 1. LOW: Immediate discards
        disposable_triggers = (
            "weather", "climate", "battery", "time", "hello", "hi", "hey",
            "open ", "close ", "click ", "type ", "screenshot", "stop", "cancel"
        )
        if any(dt in lower for dt in disposable_triggers) and not any(
            kw in lower for kw in ["interview", "exam", "building", "project", "prefer", "my name"]
        ):
            return  # LOW -> Do not store in permanent memory

        # 2. HIGH: Life milestones, events, preferences
        high_patterns = (
            "interview", "exam", "presentation", "meeting", "deadline", "appointment",
            "tomorrow i have", "today i have", "my name is", "i prefer", "prefer short",
            "enakku pidikkum", "naan oru"
        )
        if any(hp in lower for hp in high_patterns):
            try:
                import datetime
                from nexus.memory.manager import MemoryManager
                from nexus.memory.types import MemoryCategory
                manager = MemoryManager()
                now = datetime.datetime.now()
                target_date = now.date()
                if "tomorrow" in lower or "naalaiki" in lower:
                    target_date = (now + datetime.timedelta(days=1)).date()
                elif "yesterday" in lower or "nethu" in lower:
                    target_date = (now - datetime.timedelta(days=1)).date()

                payload = {
                    "text": clean,
                    "created_at": now.isoformat(),
                    "event_date": target_date.isoformat(),
                }
                await manager.storage.store(
                    key="latest_user_milestone",
                    value=payload,
                    category=MemoryCategory.USER_DEFINED_INFO,
                    tags=["importance:high", "milestone"],
                    metadata=payload,
                )
                log.info("Saved HIGH-importance milestone with event_date=%s: '%s'", target_date, clean)
            except Exception as e:
                log.debug("Memory store notice: %s", e)
            return

        # 3. MEDIUM: Ongoing projects and dev tasks
        medium_patterns = (
            "building", "developing", "creating a", "working on", "timetable",
            "project", "app create", "generator", "making a"
        )
        if any(mp in lower for mp in medium_patterns):
            try:
                import datetime
                from nexus.memory.manager import MemoryManager
                from nexus.memory.types import MemoryCategory
                manager = MemoryManager()
                now = datetime.datetime.now()
                payload = {
                    "text": clean,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
                await manager.storage.store(
                    key="active_project_context",
                    value=payload,
                    category=MemoryCategory.CURRENT_TASK,
                    tags=["importance:medium", "project"],
                    metadata=payload,
                )
                log.info("Saved MEDIUM-importance project context: '%s'", clean)
            except Exception as e:
                log.debug("Memory store notice: %s", e)

    async def generate_welcome_greeting(self, user_name: str = "Friend") -> str:
        """
        Generate a dynamic, human-like, context-aware welcome greeting based on:
        - Time of day (Morning, Afternoon, Evening)
        - HIGH-importance memories with temporal decay (today vs yesterday vs expired)
        - MEDIUM-importance memories (active project within 7 days)
        - Natural Tanglish / Tamil persona
        """
        import datetime
        now = datetime.datetime.now()
        today = now.date()
        hour = now.hour

        if 5 <= hour < 12:
            time_greeting = "Good morning"
        elif 12 <= hour < 17:
            time_greeting = "Good afternoon"
        elif 17 <= hour < 22:
            time_greeting = "Good evening"
        else:
            time_greeting = "Hey"

        # Check for High & Medium memories
        milestone_data = None
        project_data = None
        try:
            from nexus.memory.manager import MemoryManager
            manager = MemoryManager()
            rec_high = await manager.storage.find_by_key("latest_user_milestone")
            if rec_high and rec_high.value:
                milestone_data = rec_high.value if isinstance(rec_high.value, dict) else {"text": str(rec_high.value)}

            rec_med = await manager.storage.find_by_key("active_project_context")
            if rec_med and rec_med.value:
                project_data = rec_med.value if isinstance(rec_med.value, dict) else {"text": str(rec_med.value)}
        except Exception as e:
            log.debug("Memory check notice for greeting: %s", e)

        # 1. Temporal reasoning for HIGH-priority milestones (Interview, Exam, Presentation)
        if milestone_data and "text" in milestone_data:
            text = milestone_data["text"]
            lower_text = text.lower()
            event_date_str = milestone_data.get("event_date")
            days_diff = None
            if event_date_str:
                try:
                    event_date = datetime.date.fromisoformat(event_date_str)
                    days_diff = (today - event_date).days
                except Exception:
                    days_diff = None

            # Only follow up if the event is today or was yesterday (within 2 days)
            if days_diff is not None and days_diff in (0, 1):
                if "interview" in lower_text:
                    if days_diff == 0:
                        return f"Hey {user_name}, {time_greeting}-nga! Innaiki unga interview irukku-la? All the best-nga! Confidence-ah pannunga! 🌟"
                    else:
                        return f"Hey {user_name}, {time_greeting}-nga! Nethu unga interview eppadi pochu? Nalla pannengala? Today enna plan, sollunga! 😊✨"
                elif "exam" in lower_text:
                    if days_diff == 0:
                        return f"Hey {user_name}, {time_greeting}-nga! Innaiki unga exam irukku-la? All the very best! Nalla ezhudhunga! 🎓✨"
                    else:
                        return f"Hey {user_name}, {time_greeting}-nga! Nethu exam eppadi pochu? Nalla ezhudhineengala? Today enna seiyalam, sollunga! 🎓✨"
                elif "presentation" in lower_text or "meeting" in lower_text:
                    return f"{time_greeting} {user_name}-nga! Unga presentation / meeting nalla mudinjadha? Next enna task pannattum, sollunga! 🚀"

        # 2. Check for MEDIUM-priority active projects within 7 days
        if project_data and "text" in project_data:
            proj_text = project_data["text"]
            lower_p = proj_text.lower()
            created_str = project_data.get("created_at")
            is_recent = True
            if created_str:
                try:
                    created_dt = datetime.datetime.fromisoformat(created_str)
                    if (now - created_dt).days > 7:
                        is_recent = False
                except Exception:
                    pass

            if is_recent:
                if "timetable" in lower_p:
                    return f"Vanakkam {user_name}-nga! Ungaloda timetable generator project work eppadi pogudhu? Innaiki adhai continue pannalama, illa vera task edhavadhu seiyalama? 📅✨"
                else:
                    short_p = proj_text[:30]
                    return f"{time_greeting} {user_name}-nga! Ungaloda '{short_p}' work eppadi pogudhu? Innaiki enna task seiyalam, sollunga! 💻✨"

        # 3. Default Fresh Time-of-Day Personal Greeting (if no active milestones or projects)
        return f"{time_greeting} {user_name}-nga! Nalla irukinga-la? Innaiki enna interesting-ana task seiyalam, sollunga! 😊✨"

    async def _classify_intent(self, goal: str) -> str:
        """
        Classify user message into 'CONVERSATION', 'CONVERSATION_GREETING', 'SYSTEM_WEATHER', 'SYSTEM_BATTERY', or 'TASK'.
        """
        lower_goal = goal.lower().strip()
        lower_clean = re.sub(r"[^\w\s]", "", lower_goal).strip()

        # 1. Quick Emergency Stop
        if lower_clean in ("stop", "cancel", "pause", "halt", "stop it", "niruthu"):
            return "STOP"

        # 2. Weather Triggers
        weather_triggers = [
            "weather", "climate", "rain", "temperature", "வானிலை", "வெதர்", "மழை", "mazhai",
            "appadi erukku", "eppadi irukku", "epdi irukku", "how is the weather"
        ]
        if any(w in lower_clean for w in weather_triggers) and not any(
            action_kw in lower_clean for action_kw in ["open", "click", "type", "run", "launch", "write", "delete", "create", "calc"]
        ):
            return "SYSTEM_WEATHER"

        # 3. Battery / System Triggers
        battery_triggers = ["battery", "charge", "percentage", "battery status", "charging", "battery level"]
        if any(b in lower_clean for b in battery_triggers) and not any(
            action_kw in lower_clean for action_kw in ["open", "click", "type", "run", "launch", "delete"]
        ):
            return "SYSTEM_BATTERY"

        # 4. Obvious "No Task" / Casual chit-chat indicators (< 0.1ms)
        no_task_triggers = [
            "task athum illa", "task ethum illa", "task illa", "no task", "not a task",
            "task onnum illa", "onnum illa", "ethuvum illa", "summa", "summa thaan",
            "summa pesuren", "just chat", "just chatting", "just talking", "nothing",
            "bore adikuthu", "bore"
        ]
        if any(nt in lower_clean for nt in no_task_triggers) and not any(
            action_kw in lower_clean for action_kw in ["open", "click", "type", "run", "launch", "write", "delete", "create"]
        ):
            return "CONVERSATION"

        # 5. Obvious Computer-Use Task Triggers (< 0.2ms)
        task_action_prefixes = (
            "open ", "launch ", "start ", "close ", "kill ", "click ", "double click ",
            "right click ", "type ", "press ", "scroll ", "screenshot ", "take photo ",
            "photo edu ", "screenshot edu ", "window-va moodu", "close pannu", "open pannu"
        )
        task_action_suffixes = (
            "open pannu", "open panu", "open pannunga", "close pannu", "close panu",
            "moodu", "play pannu", "type pannu", "click pannu", "delete pannu", "run pannu"
        )
        known_apps = (
            "notepad", "calculator", "calc", "chrome", "google chrome", "edge",
            "browser", "camera", "vscode", "vs code", "explorer", "spotify",
            "paint", "terminal", "powershell", "cmd", "taskmgr", "task manager"
        )
        has_app = any(app in lower_clean for app in known_apps)
        has_action = (
            any(lower_clean.startswith(p) for p in task_action_prefixes)
            or any(lower_clean.endswith(s) for s in task_action_suffixes)
            or any(s in lower_clean for s in task_action_suffixes)
        )
        if has_app and has_action:
            return "TASK"

        # 6. Obvious Chatbot Q&A Triggers (< 0.2ms)
        convo_triggers = (
            "what is", "who is", "who are", "why is", "why does", "how does", "how to",
            "explain", "tell me", "can you tell", "describe", "write a poem", "write a code",
            "write python", "kavithai", "joke", "comedy", "kadhai", "story", "solren",
            "enna solra", "meaning", "define", "translate", "advise", "advice"
        )
        if any(ct in lower_clean for ct in convo_triggers) and not (has_app and has_action):
            return "CONVERSATION"

        # 7. Fast Semantic Classification via ModelTier.FAST (< 200ms) for edge cases
        try:
            await self._router.initialize()
            classify_prompt = (
                "You are an intent classification system for an AI companion on Windows.\n"
                "Classify the following user input into either 'CONVERSATION' or 'TASK':\n"
                "- 'CONVERSATION': The user is chatting, asking questions, seeking explanations, requesting code, math, jokes, advice, feelings, opinions, or general chit-chat. (NO direct desktop OS action required).\n"
                "- 'TASK': The user wants the agent to directly operate the computer OS right now (e.g. open an application, click somewhere on screen, type text into an app, close a window, take a photo with camera, take a screenshot, manage files).\n\n"
                f"User Input: \"{goal}\"\n\n"
                "Output strictly ONE word: CONVERSATION or TASK"
            )
            res = await self._router.generate(
                messages=[LLMMessage(role="user", content=classify_prompt)],
                tier=ModelTier.FAST,
                temperature=0.0,
            )
            raw = (res.content or "").strip().upper()
            if "TASK" in raw:
                return "TASK"
            return "CONVERSATION"
        except Exception as e:
            log.warning("Intent classification LLM notice: %s. Using heuristic.", e)
            task_verbs = ["open", "launch", "close", "click", "type", "press", "scroll", "maximize", "minimize", "kill", "shut"]
            if any(tv in lower_clean.split() for tv in task_verbs):
                return "TASK"
            return "CONVERSATION"

    def _analyze_chat_history_query(
        self,
        goal: str,
        agent_titles: list[str],
        simple_titles: list[str],
    ) -> str | None:
        """Analyze if user is querying for chat count, history, or specific chat names."""
        goal_lower = goal.lower().strip()
        chat_keywords = ["chat", "chats", "சேட்", "session", "sessions", "sidebar", "history"]
        if not any(kw in goal_lower for kw in chat_keywords):
            return None

        query_intent_keywords = [
            "ethana", "athana", "ethanai", "athanai", "எத்தனை", "how many", "count",
            "total", "list", "show", "irukku", "erukku", "இருக்", "solren", "sollu"
        ]
        if not any(q in goal_lower for q in query_intent_keywords):
            return None

        target_filter = None
        quoted_match = re.search(r'["\']([^"\']+)["\']', goal)
        cand_stop = {
            "all", "motha", "total", "intha", "antha", "oru", "the", "my", "enga", "unga",
            "ethana", "athana", "ethanai", "athanai", "how", "many", "recent", "new", "old",
            "side", "sidebar", "sila", "some", "nalla", "enna", "irukura", "erukura", "la"
        }

        if quoted_match:
            target_filter = quoted_match.group(1).strip()
        else:
            name_match = re.search(
                r'(\b[\w\u0B80-\u0BFF\-]+)\s+(?:name(?:\s*la|-la)?|title(?:\s*la|-la)?|nu|endru|endra|peyiril)\b',
                goal,
                re.IGNORECASE,
            )
            if name_match:
                cand = name_match.group(1).strip()
                if cand.lower() not in cand_stop:
                    target_filter = cand
            else:
                chat_kw_match = re.search(
                    r'(\b[\w\u0B80-\u0BFF\-]+)\s+(?:chats?|சேட்)\b',
                    goal,
                    re.IGNORECASE,
                )
                if chat_kw_match:
                    cand = chat_kw_match.group(1).strip()
                    if cand.lower() not in cand_stop:
                        target_filter = cand

        if target_filter:
            tf_lower = target_filter.lower()
            matching_agent = [t for t in agent_titles if tf_lower in t.lower()]
            matching_simple = [t for t in simple_titles if tf_lower in t.lower()]

            return (
                f"[DETERMINISTIC VERIFIED CHAT QUERY RESULT FOR USER QUESTION]:\n"
                f"- User Query Target Name: '{target_filter}'\n"
                f"- CRITICAL NOTE: '{target_filter}' in the user query is a TITLE SEARCH FILTER, NOT a greeting to the assistant!\n"
                f"- In Current Active Sidebar (Conversational Computer-Use Agent):\n"
                f"  * Total matching chats: {len(matching_agent)}\n"
                f"  * Matching titles: {json.dumps(matching_agent, ensure_ascii=False)}\n"
                f"- In Alternate Sidebar (Simple Chatbot):\n"
                f"  * Total matching chats: {len(matching_simple)}\n"
                f"  * Matching titles: {json.dumps(matching_simple, ensure_ascii=False)}\n\n"
                f"STRICT RESPONSE INSTRUCTIONS:\n"
                f"1. Clearly state the exact count of chats matching '{target_filter}' in the active Conversational Computer-Use Agent sidebar ({len(matching_agent)} chats).\n"
                f"2. Also mention how many match in the Simple Chatbot sidebar ({len(matching_simple)} chats) so the user gets complete clarity across both modes.\n"
                f"3. List the matching chat names.\n"
                f"4. NEVER fabricate numbers or invent random topics (like 'pal pal'). Use ONLY the exact numbers and titles provided above."
            )
        else:
            return (
                f"[DETERMINISTIC VERIFIED CHAT QUERY RESULT FOR USER QUESTION]:\n"
                f"- Current Active Sidebar (Conversational Computer-Use Agent) Total: {len(agent_titles)} chats\n"
                f"- Alternate Sidebar (Simple Chatbot) Total: {len(simple_titles)} chats\n"
                f"- Recent Active Sidebar Titles: {json.dumps(agent_titles[:15], ensure_ascii=False)}\n\n"
                f"STRICT RESPONSE INSTRUCTIONS:\n"
                f"1. State that the active Conversational Computer-Use Agent sidebar currently has exactly {len(agent_titles)} chats.\n"
                f"2. Mention that the Simple Chatbot sidebar has {len(simple_titles)} chats.\n"
                f"3. Do NOT approximate with vague numbers (like '30-ku mela') or fabricate chat topics. State the exact numbers directly."
            )

    async def _handle_conversational_query(self, goal: str) -> dict[str, Any]:
        """Process conversational chit-chat, Q&A, and discussion using the Full Chatbot Engine."""
        self._status = AgentStatus.THINKING
        await self._router.initialize()

        # Build dynamic system prompt including recent saved sessions from sidebar if available
        system_content = CHATBOT_SYSTEM_PROMPT
        query_fact: str | None = None
        try:
            from nexus.database.engine import get_session
            from nexus.database.repositories.conversation import ConversationRepository
            async with get_session() as db_session:
                repo = ConversationRepository(db_session)
                all_convs, _ = await repo.list_conversations(offset=0, limit=200)
                if all_convs:
                    agent_convs = [c for c in all_convs if (c.summary or "").startswith("[Computer-Use]")]
                    simple_convs = [c for c in all_convs if not (c.summary or "").startswith("[Computer-Use]")]

                    agent_titles = [c.summary.replace("[Computer-Use]", "").strip() for c in agent_convs if c.summary]
                    simple_titles = [c.summary.strip() for c in simple_convs if c.summary]

                    query_fact = self._analyze_chat_history_query(goal, agent_titles, simple_titles)

                    session_info = (
                        f"\n\nCURRENT SAVED SESSIONS IN USER'S NEXUS SIDEBAR:\n"
                        f"- Active Mode: Conversational Computer-Use Agent ({len(agent_titles)} total chats)\n"
                        f"  Recent titles: {json.dumps(agent_titles[:25], ensure_ascii=False)}\n"
                        f"- Other Mode: Simple Chatbot ({len(simple_titles)} total chats)\n"
                        f"  Recent titles: {json.dumps(simple_titles[:15], ensure_ascii=False)}"
                    )
                    if query_fact:
                        session_info += f"\n\n{query_fact}"
                    system_content += session_info
        except Exception as db_err:
            log.debug("Session list retrieval notice: %s", db_err)

        messages = [LLMMessage(role="system", content=system_content)]
        for msg in self._convo_history[-10:]:
            messages.append(LLMMessage(role=msg["role"], content=msg["content"]))
        messages.append(LLMMessage(role="user", content=goal))

        try:
            generation_temp = 0.15 if query_fact else 0.7
            resp = await self._router.generate(
                messages=messages,
                tier=ModelTier.FAST,
                temperature=generation_temp,
            )
            reply_text = (resp.content or "").strip()
        except Exception as e:
            log.warning("Chatbot generation notice: %s", e)
            reply_text = "Romba interesting-ana vishayam-nga! Enna task seiyattum sollunga! 😊✨"

        if not reply_text:
            reply_text = "Sollunga! Enna help pannattum? 😊✨"

        # Update persistent conversational working memory
        self._convo_history.append({"role": "user", "content": goal})
        self._convo_history.append({"role": "assistant", "content": reply_text})
        if len(self._convo_history) > 20:
            self._convo_history = self._convo_history[-20:]

        self._status = AgentStatus.IDLE
        self._is_task_running = False
        await self._event_bus.emit(
            "computer_use.finished",
            {"goal": goal, "narration": reply_text, "step": 0},
        )
        return {
            "status": "completed",
            "intent": "CONVERSATION",
            "is_task": False,
            "goal": goal,
            "narration": reply_text,
            "steps_executed": 0,
            "history": [],
        }

    async def _extract_weather_location(self, goal: str) -> str | None:
        """Extract and standardize city/town name from weather query dynamically without hardcoded city defaults."""
        candidate: str | None = None
        # Heuristic regex:
        m = re.search(r"\b([a-zA-Z\u0B80-\u0BFF]{3,})\b\s*(?:-|\s)?(?:la|le|il|ula|lo)\s+(?:weather|climate|rain|mazhai|வெதர்|வானிலை)", goal, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
        else:
            m2 = re.search(r"(?:weather|climate|rain|mazhai)\s+(?:in|at|for|of)\s+([a-zA-Z\u0B80-\u0BFF\s]{3,})", goal, re.IGNORECASE)
            if m2:
                candidate = re.sub(r"\b(today|now|tomorrow|appadi|eppadi|irukku|erukku|please|nga)\b.*", "", m2.group(1), flags=re.IGNORECASE).strip()

        # Fast LLM normalization (normalizes typos/Tanglish e.g. "truttani" -> "Tiruttani", "kovai" -> "Coimbatore", detects "NONE")
        try:
            await self._router.initialize()
            prompt = (
                "Extract and standardize the city/town/location name from the user weather query.\n"
                f'User query: "{goal}"\n'
                "Rules:\n"
                "- If a city/town/location is mentioned (even with colloquial spelling, e.g. 'truttani' -> 'Tiruttani', 'kovai' -> 'Coimbatore', 'chennai' -> 'Chennai'), output ONLY the standardized official English city name.\n"
                "- If NO city or location is mentioned in the query at all (e.g. 'weather appadi erukku?'), output strictly 'NONE'.\n"
                "Output ONLY the location name or NONE, nothing else."
            )
            res = await self._router.generate(
                messages=[LLMMessage(role="user", content=prompt)],
                tier=ModelTier.FAST,
                temperature=0.0,
            )
            val = (res.content or "").strip().replace("'", "").replace('"', "")
            if val and val.upper() != "NONE" and len(val) < 40:
                return val
        except Exception as e:
            log.warning("Location extraction via LLM notice: %s", e)
            if candidate and len(candidate) < 30:
                return candidate.title()

        return candidate.title() if (candidate and len(candidate) < 30) else None

    async def _handle_weather_query(self, goal: str) -> dict[str, Any]:
        """Fetch live weather or forecast dynamically for any city/town without defaulting to Chennai."""
        target_city = await self._extract_weather_location(goal)
        lower_clean = goal.lower()
        is_tomorrow = any(
            w in lower_clean
            for w in ["tomorrow", "naalaiki", "naalaiku", "nalaiku", "naalai", "repu"]
        )

        if not target_city:
            narration = "Endha ooru-ku (city-ku) weather paakanum-nga? (e.g. Tiruttani, Avadi, Chennai, Coimbatore) Sollunga, paathu solren! 🌦️"
        else:
            try:
                from nexus.tools.system.basic import GetWeatherTool
                weather_tool = GetWeatherTool()
                target_day = "tomorrow" if is_tomorrow else "current"
                w_res = await weather_tool.execute(location=target_city, target_day=target_day)
                if hasattr(w_res, "success") and not w_res.success:
                    narration = f"Mannikavum, {target_city}-ku weather details edukka mudiyala-nga. Ooru name correct-ah nu check pannunga! 🌦️"
                else:
                    weather_summary = w_res.output if hasattr(w_res, "output") else str(w_res)
                    if is_tomorrow:
                        narration = f"{target_city}-la naalaiki (tomorrow) weather: {weather_summary} ⛅ Next enna pannattum, sollunga! ✨"
                    else:
                        narration = f"{target_city}-la ippo weather: {weather_summary} 🌦️ Next enna pannattum, sollunga! ✨"
            except Exception as w_err:
                log.warning("Weather lookup notice for %s: %s", target_city, w_err)
                narration = f"Mannikavum, {target_city}-ku weather details edukka mudiyala-nga. Ooru name correct-ah nu check pannunga! 🌦️"

        self._convo_history.append({"role": "user", "content": goal})
        self._convo_history.append({"role": "assistant", "content": narration})

        self._status = AgentStatus.IDLE
        self._is_task_running = False
        await self._event_bus.emit(
            "computer_use.finished",
            {"goal": goal, "narration": narration, "step": 0},
        )
        return {
            "status": "completed",
            "intent": "CONVERSATION",
            "is_task": False,
            "goal": goal,
            "narration": narration,
            "steps_executed": 0,
            "history": [],
        }

    async def _handle_battery_query(self, goal: str) -> dict[str, Any]:
        """Fetch system battery status and respond conversationally."""
        try:
            import psutil
            battery = psutil.sensors_battery()
            if battery:
                plugged = "charger connected-la irukku" if battery.power_plugged else "battery mode-la run aagudhu"
                narration = f"Ungaloda laptop battery ippo {round(battery.percent)}%-la irukku-nga! ({plugged}) 🔋✨ Next enna seiyattum, sollunga!"
            else:
                narration = "Laptop battery status details ippo retrieve panna mudiyala-nga! Desktop PC-la run aagudha nu check pannunga. 😊✨"
        except Exception as b_err:
            log.warning("Battery status notice: %s", b_err)
            narration = "Battery status check panna mudiyala-nga. Vera enna help seiyattum sollunga! 😊"

        self._convo_history.append({"role": "user", "content": goal})
        self._convo_history.append({"role": "assistant", "content": narration})

        self._status = AgentStatus.IDLE
        self._is_task_running = False
        await self._event_bus.emit(
            "computer_use.finished",
            {"goal": goal, "narration": narration, "step": 0},
        )
        return {
            "status": "completed",
            "intent": "CONVERSATION",
            "is_task": False,
            "goal": goal,
            "narration": narration,
            "steps_executed": 0,
            "history": [],
        }

    async def run_goal(self, goal: str, auto_confirm: bool = False) -> dict[str, Any]:
        """
        Execute an end-to-end goal as a Unified Dual-Engine (Chatbot + Computer-Use Agent).
        """
        self._stop_requested = False
        self._current_task = goal
        self._history.clear()
        self._is_task_running = False
        self._status = AgentStatus.IDLE

        # Background 3-Tier memory learning (LOW discarded, MEDIUM/HIGH stored)
        asyncio.create_task(self._classify_and_store_memory(goal))

        # 1. First classify intent: Conversation vs Task vs System
        intent = await self._classify_intent(goal)
        log.info("Classified goal intent: '%s' for input: '%s'", intent, goal)

        if intent == "STOP":
            self._status = AgentStatus.STOPPED
            self._is_task_running = False
            return {"status": "stopped", "intent": "STOP", "is_task": False, "reason": "User requested stop", "steps_executed": 0}

        if intent in ("CONVERSATION", "CONVERSATION_GREETING"):
            return await self._handle_conversational_query(goal)

        if intent == "SYSTEM_WEATHER":
            return await self._handle_weather_query(goal)

        if intent == "SYSTEM_BATTERY":
            return await self._handle_battery_query(goal)

        # 2. TASK INTENT: Computer-Use Execution Engine
        self._is_task_running = True
        self._status = AgentStatus.OBSERVING
        await self._event_bus.emit(
            "computer_use.started",
            {"goal": goal, "max_steps": self._max_steps},
        )

        # Emit immediate verbal acknowledgment so user hears voice confirmation in < 800ms
        clean_name = goal[:35].strip()
        ack_narration = f"Kandippa-nga, ippo {clean_name} task-ah start panren! 🚀"
        await self._event_bus.emit(
            "computer_use.narrate",
            {"narration": ack_narration, "step": 0},
        )

        step_num = 0
        final_result: dict[str, Any] = {"status": "completed", "intent": "TASK", "is_task": True, "goal": goal, "steps_executed": 0}
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
                    # Guard for camera photo task: if user asked for a photo and no shutter was fired yet, auto-trigger space shutter!
                    if "camera" in lower_goal and any(kw in lower_goal for kw in ["pic", "photo", "adu", "edu", "picture", "snap", "take"]):
                        photo_taken = any(
                            (r.action.action_type == ActionType.KEY_PRESS and r.action.key in ("space", "enter"))
                            or (r.action.action_type == ActionType.CLICK and "shutter" in (r.thought or "").lower())
                            for r in self._history
                        )
                        if not photo_taken:
                            log.info("Camera photo task guard: photo not taken yet. Auto-triggering Spacebar shutter.")
                            comp_action = ComputerAction(action_type=ActionType.KEY_PRESS, key="space", reasoning="Press Spacebar to capture photo in Windows Camera")
                            narration = "Camera-la photo capture panniten-pa! 📸"
                            action_res = await self._executor.execute(comp_action)
                            self._history.append(StepRecord(
                                step_number=step_num,
                                observation=obs,
                                thought="Pressed Spacebar to capture photo in Windows Camera",
                                action=comp_action,
                                action_result=action_res,
                                success=True,
                                elapsed_seconds=0.1,
                            ))

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
            self._is_task_running = False
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
        lower_goal = goal.lower().strip()
        task_category_hint = (
            "STRICT ACTION RULE: NEVER automatically close any application unless the user EXPLICITLY instructed 'close' in their goal. "
            "Never close background apps (like Google Chrome, VS Code, or Nexus). "
            "When completing any goal, keep apps open and enthusiastically ask 'Next enna pannattum?'"
        )

        if "camera" in lower_goal and any(kw in lower_goal for kw in ["pic", "photo", "adu", "edu", "picture", "snap", "take"]):
            task_category_hint += (
                "\n📸 CAMERA COMPOUND TASK MANDATE:\n"
                "- The user requested to OPEN CAMERA and TAKE A PHOTO ('pic adu' / 'photo edu' = take a photo in Tamil/Tanglish)!\n"
                "- If Camera app is in the background or not focused: Focus it using switch_window or focus_window.\n"
                "- If Camera app is open on screen: Take the photo by clicking the Camera shutter button OR using key_press 'space' or 'enter'!\n"
                "- DO NOT output 'finish' after merely opening the camera. You MUST take the photo first!"
            )
        elif any(kw in lower_goal for kw in ["panni", "pannitu", "and then", "and"]):
            task_category_hint += (
                "\n⚠️ COMPOUND GOAL MANDATE:\n"
                "- The user has given a multi-step task ('... panni ...').\n"
                "- Complete ALL requested steps before finishing. Never finish after only opening an app when a follow-up action was requested!"
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
