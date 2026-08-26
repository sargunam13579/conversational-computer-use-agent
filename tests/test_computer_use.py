"""
Unit & Integration Tests for NEXUS Conversational Computer-Use Agent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.agents.computer_use.actions import ComputerActionExecutor
from nexus.agents.computer_use.agent import ConversationalComputerUseAgent
from nexus.agents.computer_use.grounding import VisualGroundingEngine
from nexus.agents.computer_use.protocol import (
    ActionType,
    AgentStatus,
    ComputerAction,
    ScreenObservation,
)
from nexus.api.app import create_app
from nexus.tools.computer_use import (
    ComputerClickTool,
    ComputerHotkeyTool,
    ComputerScrollTool,
    ComputerTypeTool,
    get_computer_use_tools,
)


@pytest.mark.asyncio
async def test_action_executor_bounds_and_click():
    """Test that coordinates are clamped safely within screen bounds."""
    executor = ComputerActionExecutor(smooth_mouse=False)
    executor._screen_width = 1920
    executor._screen_height = 1080

    px, py = executor._clamp_coordinates(2500, -100)
    assert px == 1919
    assert py == 0

    action = ComputerAction(action_type=ActionType.CLICK, x=500, y=300)
    with patch("pyautogui.click", create=True):
        res = await executor.execute(action)
        assert res["success"] is True
        assert res["x"] == 500
        assert res["y"] == 300


@pytest.mark.asyncio
async def test_action_executor_typing_and_hotkey():
    """Test text typing and hotkeys execution."""
    executor = ComputerActionExecutor()

    # Type Text
    type_action = ComputerAction(action_type=ActionType.TYPE_TEXT, text="Hello NEXUS")
    with patch("pyautogui.write", create=True):
        res = await executor.execute(type_action)
        assert res["success"] is True
        assert res["length"] == 11

    # Hotkey
    hotkey_action = ComputerAction(action_type=ActionType.HOTKEY, key="ctrl+s")
    with patch("pyautogui.hotkey", create=True):
        res = await executor.execute(hotkey_action)
        assert res["success"] is True
        assert res["keys"] == ["ctrl", "s"]


@pytest.mark.asyncio
async def test_visual_grounding_coordinates():
    """Test coordinate normalization and denormalization."""
    grounding = VisualGroundingEngine()

    coord = grounding.normalize_coordinates(500, 500, 1920, 1080)
    assert coord.x == 960
    assert coord.y == 540

    norm_x, norm_y = grounding.denormalize_coordinates(960, 540, 1920, 1080)
    assert norm_x == 500
    assert norm_y == 500


@pytest.mark.asyncio
async def test_computer_use_tools():
    """Test all standalone computer use tools."""
    tools = get_computer_use_tools()
    assert len(tools) == 5

    # Click Tool
    click_tool = ComputerClickTool()
    with patch("pyautogui.click", create=True):
        res = await click_tool.execute(x=100, y=200, button="left")
        assert res.success is True

    # Type Tool
    type_tool = ComputerTypeTool()
    with patch("pyautogui.write", create=True):
        res = await type_tool.execute(text="Test input")
        assert res.success is True

    # Hotkey Tool
    hotkey_tool = ComputerHotkeyTool()
    with patch("pyautogui.hotkey", create=True):
        res = await hotkey_tool.execute(key="ctrl+alt+del")
        assert res.success is True

    # Scroll Tool
    scroll_tool = ComputerScrollTool()
    with patch("pyautogui.scroll", create=True):
        res = await scroll_tool.execute(direction="down", amount=5)
        assert res.success is True


@pytest.mark.asyncio
async def test_conversational_computer_use_agent_loop():
    """Test conversational agent reasoning loop with mocked router and vision."""
    agent = ConversationalComputerUseAgent(max_steps=2)

    mock_obs = ScreenObservation(
        screen_width=1920,
        screen_height=1080,
        detected_elements=[{"index": 1, "name": "File", "type": "menu", "center": (50, 10), "x": 40, "y": 5, "width": 20, "height": 10}],
    )

    agent._grounding.observe_screen = AsyncMock(return_value=mock_obs)
    agent._decide_next_action = AsyncMock(
        side_effect=[
            {
                "thought": "I will click the File menu",
                "narration": "Clicking File menu",
                "action": {"action_type": "click", "x": 50, "y": 10},
            },
            {
                "thought": "Task finished",
                "narration": "All done",
                "action": {"action_type": "finish"},
            },
        ]
    )

    # Test Steering
    await agent.steer("Please make sure to save first")

    # Run Goal
    with patch("pyautogui.click", create=True):
        res = await agent.run_goal("Open File menu and save")
        assert res["status"] == "completed"
        assert res["steps_executed"] >= 1
        assert len(agent.history) >= 1


@pytest.mark.asyncio
async def test_action_executor_extended_primitives():
    """Test middle click, window controls, and clipboard paste."""
    executor = ComputerActionExecutor()

    # Middle Click
    mid_action = ComputerAction(action_type=ActionType.MIDDLE_CLICK, x=300, y=400)
    with patch("pyautogui.middleClick", create=True):
        res = await executor.execute(mid_action)
        assert res["success"] is True
        assert res["action"] == "middle_click"

    # Window Minimize & Maximize
    with patch("pyautogui.hotkey", create=True):
        min_res = await executor.execute(ComputerAction(action_type=ActionType.WINDOW_MINIMIZE))
        assert min_res["success"] is True
        max_res = await executor.execute(ComputerAction(action_type=ActionType.WINDOW_MAXIMIZE))
        assert max_res["success"] is True


@pytest.mark.asyncio
async def test_grounding_find_element():
    """Test finding elements by index and text query."""
    grounding = VisualGroundingEngine()
    elements = [
        {"index": 1, "name": "File", "center": (20, 10)},
        {"index": 2, "name": "Save As", "center": (50, 80)},
    ]
    assert grounding.find_element(elements, 1) == elements[0]
    assert grounding.find_element(elements, "2") == elements[1]
    assert grounding.find_element(elements, "Save") == elements[1]
    assert grounding.find_element(elements, "Nonexistent") is None


@pytest.mark.asyncio
async def test_computer_use_api_routes():
    """Test REST API routes for Computer-Use Agent."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET status
        resp = await client.get("/api/computer-use/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data

        # GET observe
        obs_resp = await client.get("/api/computer-use/observe")
        assert obs_resp.status_code == 200
        obs_data = obs_resp.json()
        assert obs_data["status"] == "observed"

        # POST steer
        steer_resp = await client.post(
            "/api/computer-use/steer",
            json={"instruction": "Click top-right button", "interrupt": True},
        )
        assert steer_resp.status_code == 200
        assert steer_resp.json()["status"] == "steered"

        # POST stop
        stop_resp = await client.post("/api/computer-use/stop")
        assert stop_resp.status_code == 200
        assert stop_resp.json()["status"] == "stopped"

        # POST direct action
        with patch("pyautogui.click", create=True):
            act_resp = await client.post(
                "/api/computer-use/action",
                json={"action_type": "click", "x": 100, "y": 200},
            )
            assert act_resp.status_code == 200


@pytest.mark.asyncio
async def test_computer_use_open_close_loop_detection():
    """Test that open-app followed by window-close does not get stuck in a loop."""
    agent = ConversationalComputerUseAgent(max_steps=10)

    mock_obs = ScreenObservation(
        screen_width=1920,
        screen_height=1080,
        detected_elements=[],
    )

    agent._grounding.observe_screen = AsyncMock(return_value=mock_obs)
    # Simulate LLM trying to repeat: open camera -> close camera -> open camera
    agent._decide_next_action = AsyncMock(
        side_effect=[
            {
                "thought": "Opening Camera",
                "narration": "Opening Camera for you",
                "action": {"action_type": "open_app", "app_name": "camera"},
            },
            {
                "thought": "Closing Camera",
                "narration": "Closing Camera",
                "action": {"action_type": "window_close"},
            },
            {
                "thought": "Opening Camera again (loop)",
                "narration": "Opening Camera again",
                "action": {"action_type": "open_app", "app_name": "camera"},
            },
        ]
    )

    with patch("pyautogui.hotkey", create=True), patch("subprocess.Popen", create=True), patch.object(agent._executor, "_bring_window_to_foreground", return_value=True):
        res = await agent.run_goal("camera open panni close pannu")
        # Should be auto-completed by loop detection on step 3!
        assert res["status"] == "completed"
        assert res["steps_executed"] == 2
        assert len(agent.history) == 2


@pytest.mark.asyncio
async def test_outer_task_keeps_app_open():
    """Test that outer tasks (like camera photo) keep the app open and ask next steps without unintended auto-close."""
    agent = ConversationalComputerUseAgent(max_steps=5)

    mock_obs = ScreenObservation(screen_width=1920, screen_height=1080, detected_elements=[])
    agent._grounding.observe_screen = AsyncMock(return_value=mock_obs)
    agent._decide_next_action = AsyncMock(
        side_effect=[
            {
                "thought": "Opening Camera",
                "narration": "Opening Camera",
                "action": {"action_type": "open_app", "app_name": "camera"},
            },
            {
                "thought": "Taking picture with camera shutter",
                "narration": "Taking picture",
                "action": {"action_type": "key_press", "key": "space"},
            },
            {
                "thought": "Photo taken, asking what to do next",
                "narration": "Photo eduthuten-pa! Next enna pannattum? 📸",
                "action": {"action_type": "finish"},
            },
        ]
    )

    close_calls = []
    original_exec = agent._executor.execute

    async def mock_exec(action: ComputerAction):
        if action.action_type == ActionType.WINDOW_CLOSE:
            close_calls.append(action.app_name)
            return {"action": "window_close", "success": True}
        return await original_exec(action)

    with patch.object(agent._executor, "execute", side_effect=mock_exec), patch("pyautogui.press", create=True), patch("subprocess.Popen", create=True), patch.object(agent._executor, "_bring_window_to_foreground", return_value=True):
        res = await agent.run_goal("camera open panni one pic edu")
        assert res["status"] == "completed"
        # Verify that camera was NOT closed automatically (user didn't ask to close)
        assert len(close_calls) == 0


@pytest.mark.asyncio
async def test_outer_task_explicit_close():
    """Test that outer tasks with explicit 'close pannu' execute window_close."""
    agent = ConversationalComputerUseAgent(max_steps=5)

    mock_obs = ScreenObservation(screen_width=1920, screen_height=1080, detected_elements=[])
    agent._grounding.observe_screen = AsyncMock(return_value=mock_obs)
    agent._decide_next_action = AsyncMock(
        side_effect=[
            {
                "thought": "Opening Camera",
                "narration": "Opening Camera",
                "action": {"action_type": "open_app", "app_name": "camera"},
            },
            {
                "thought": "Taking photo",
                "narration": "Taking photo",
                "action": {"action_type": "key_press", "key": "space"},
            },
            {
                "thought": "Closing camera as explicitly requested",
                "narration": "Closing camera",
                "action": {"action_type": "window_close", "app_name": "camera"},
            },
            {
                "thought": "Finishing task",
                "narration": "Photo taken and camera closed! Next enna pannattum?",
                "action": {"action_type": "finish"},
            },
        ]
    )

    close_calls = []
    async def mock_exec(action: ComputerAction):
        if action.action_type == ActionType.WINDOW_CLOSE:
            close_calls.append(action.app_name)
            return {"action": "window_close", "success": True}
        return {"success": True}

    with patch.object(agent._executor, "execute", side_effect=mock_exec), patch("pyautogui.press", create=True), patch("subprocess.Popen", create=True), patch.object(agent._executor, "_bring_window_to_foreground", return_value=True):
        res = await agent.run_goal("camera open panni photo eduthutu close pannu")
        assert res["status"] == "completed"
        # Verify window_close was called because user explicitly requested close
        assert "camera" in close_calls


@pytest.mark.asyncio
async def test_inner_task_protection_and_subtasks():
    """Test that inner tasks (e.g. deleting chats in Nexus) perform subtasks and never close the window."""
    agent = ConversationalComputerUseAgent(max_steps=10)

    mock_obs = ScreenObservation(
        screen_width=1920,
        screen_height=1080,
        detected_elements=[
            {"index": 1, "name": "hello", "type": "label", "center": (100, 200)},
            {"index": 2, "name": "3-dots options menu for 'hello'", "type": "button", "center": (220, 200)},
            {"index": 3, "name": "hiii", "type": "label", "center": (100, 260)},
            {"index": 4, "name": "3-dots options menu for 'hiii'", "type": "button", "center": (220, 260)},
        ],
    )
    agent._grounding.observe_screen = AsyncMock(return_value=mock_obs)

    # Subtask execution: 1.1 click 3-dot(hello) -> 1.2 click delete -> 2.1 click 3-dot(hiii) -> 2.2 click delete -> finish
    agent._decide_next_action = AsyncMock(
        side_effect=[
            {
                "thought": "Sub-task 1.1: Click 3-dot menu for hello",
                "narration": "Clicking options for hello chat",
                "action": {"action_type": "click", "badge_index": 2},
            },
            {
                "thought": "Sub-task 1.2: Click Delete menu item",
                "narration": "Deleting hello chat",
                "action": {"action_type": "click", "x": 220, "y": 240},
            },
            {
                "thought": "Sub-task 2.1: Click 3-dot menu for hiii",
                "narration": "Clicking options for hiii chat",
                "action": {"action_type": "click", "badge_index": 4},
            },
            {
                "thought": "Sub-task 2.2: Click Delete menu item",
                "narration": "Deleting hiii chat",
                "action": {"action_type": "click", "x": 220, "y": 300},
            },
            {
                "thought": "All chats deleted. This is an inner task, so finish immediately without closing window.",
                "narration": "Deleted hello and hiii chats for you 🎉",
                "action": {"action_type": "finish"},
            },
        ]
    )

    close_calls = []
    async def mock_exec(action: ComputerAction):
        if action.action_type == ActionType.WINDOW_CLOSE:
            close_calls.append(action.app_name)
        return {"success": True, "action": str(action.action_type)}

    with patch.object(agent._executor, "execute", side_effect=mock_exec), patch("pyautogui.click", create=True):
        res = await agent.run_goal("'hello' and 'hiii' chats ah delete pannu")
        assert res["status"] == "completed"
        assert res["steps_executed"] == 4
        # Verify no window_close was executed for inner task
        assert len(close_calls) == 0


