"""
Phase 10 — NEXUS Autonomous Planning & Multi-Step Execution Agent Tests.

Validates:
1. Goal understanding & multi-step plan decomposition.
2. Sequential execution & variable interpolation across steps.
3. Dynamic tool selection & parameter resolution.
4. Progress tracking and real-time event bus notifications.
5. Safe failure recovery, exponential backoff, and fallback tool selection.
6. Clarification requests on underspecified goals.
7. Action risk assessment & ConfirmationManager integration.
8. Graceful cancellation ("Nexus stop").
9. Immediate emergency kill switch ("NEXUS STOP").
10. Result verification (artifacts, non-empty files, device deliveries).
11. Brain routing and multi-step detection.
12. FastAPI Task REST endpoints.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from nexus.api.app import create_app
from nexus.core.brain import NexusBrain
from nexus.planning.cancellation import (
    CancellationManager,
    CancellationToken,
    CancellationType,
    EmergencyStopException,
    TaskCancelledException,
)
from nexus.planning.executor import PlanExecutionEngine
from nexus.planning.manager import TaskManager
from nexus.planning.planner import TaskPlanner
from nexus.planning.progress import ProgressTracker
from nexus.planning.retry import ErrorCategory, RetrySystem
from nexus.planning.tool_selector import ToolSelector
from nexus.planning.types import (
    Plan,
    PlanStatus,
    PlanStep,
    RiskLevel,
    StepStatus,
    TaskGoal,
)
from nexus.planning.verifier import ResultVerifier

# ===========================================================================
# 1. PLANNER & GOAL DECOMPOSITION TESTS
# ===========================================================================


class TestTaskPlanner:
    """Tests for goal understanding, decomposition, risk assessment, and verification generation."""

    @pytest.mark.asyncio
    async def test_resume_workflow_decomposition(self):
        planner = TaskPlanner()
        goal = "Nexus, find my latest resume, convert it to PDF, rename it Shanmuga_Resume, and send it to my phone."
        plan = await planner.create_plan(goal)

        assert plan.total_steps >= 5
        descriptions = [s.description.lower() for s in plan.steps]

        assert any("find" in d or "resume" in d for d in descriptions)
        assert any("convert" in d or "pdf" in d for d in descriptions)
        assert any("rename" in d or "shanmuga" in d for d in descriptions)
        assert any("transfer" in d or "phone" in d for d in descriptions)
        assert any("verify" in d for d in descriptions)

        # Check step ordering
        for i, s in enumerate(plan.steps, start=1):
            assert s.order == i

    @pytest.mark.asyncio
    async def test_generic_multi_step_decomposition(self):
        planner = TaskPlanner()
        goal = "Download monthly report, generate summaries, and email the team"
        plan = await planner.create_plan(goal)

        assert len(plan.steps) >= 3
        # Final step should be automatic verification
        assert plan.steps[-1].is_verification is True

    def test_risk_assessment_destructive_actions(self):
        planner = TaskPlanner()
        risk, prompt = planner.assess_step_risk("Delete all temporary backup archives")
        assert risk == RiskLevel.HIGH
        assert prompt is not None
        assert "delete" in prompt.lower()

        risk_safe, prompt_safe = planner.assess_step_risk("Search documents folder for invoices")
        assert risk_safe == RiskLevel.LOW
        assert prompt_safe is None

    def test_clarification_detection(self):
        planner = TaskPlanner()
        needs_clarif, q = planner.check_missing_clarifications("Send to phone which phone")
        assert needs_clarif is True
        assert q is not None
        assert "phone" in q.lower()


# ===========================================================================
# 2. TOOL SELECTOR & PARAMETER RESOLUTION TESTS
# ===========================================================================


class TestToolSelector:
    """Tests for selecting registered tools and variable substitution."""

    def test_variable_interpolation(self):
        selector = ToolSelector()
        plan = Plan(goal=TaskGoal(description="Test interpolation"))
        plan.steps = [
            PlanStep(order=1, step_id="step_1", description="Find file", output="C:/docs/resume.docx"),
            PlanStep(
                order=2,
                step_id="step_2",
                description="Convert file",
                parameters={"input_file": "{{step_1.output}}", "target": "pdf"},
            ),
        ]
        plan.context_variables["dest_device"] = "phone_pixel"

        resolved = selector.resolve_parameters(plan.steps[1], plan)
        assert resolved["input_file"] == "C:/docs/resume.docx"
        assert resolved["target"] == "pdf"

    def test_nested_variable_interpolation(self):
        selector = ToolSelector()
        plan = Plan(goal=TaskGoal(description="Test nested interpolation"))
        plan.steps = [
            PlanStep(
                order=1,
                step_id="step_1",
                description="Transfer",
                output={"status": "sent", "file_info": {"path": "C:/out.pdf"}},
            ),
            PlanStep(
                order=2,
                step_id="step_2",
                description="Verify",
                parameters={"verified_path": "{{step_1.file_info.path}}"},
            ),
        ]

        resolved = selector.resolve_parameters(plan.steps[1], plan)
        assert resolved["verified_path"] == "C:/out.pdf"


# ===========================================================================
# 3. RETRY SYSTEM & RECOVERY TESTS
# ===========================================================================


class TestRetrySystem:
    """Tests for transient vs fatal failure classification and recovery."""

    def test_transient_error_classification(self):
        retry = RetrySystem(base_delay_seconds=0.1)
        step = PlanStep(order=1, description="Download file", retry_count=0, max_retries=2)

        decision = retry.evaluate_retry(step, "Connection timeout to remote server")
        assert decision.should_retry is True
        assert decision.category == ErrorCategory.TRANSIENT
        assert decision.delay_seconds > 0

    def test_fatal_error_classification(self):
        retry = RetrySystem()
        step = PlanStep(order=1, description="Format disk", retry_count=0, max_retries=2)

        decision = retry.evaluate_retry(step, "Permission denied by OS kernel")
        assert decision.should_retry is False
        assert decision.category == ErrorCategory.FATAL

    def test_tool_fallback_on_exhausted_retries(self):
        retry = RetrySystem()
        step = PlanStep(
            order=1,
            description="Convert file",
            tool_name="convert_document",
            retry_count=2,
            max_retries=2,
        )

        decision = retry.evaluate_retry(step, "Conversion filter missing")
        assert decision.should_retry is True
        assert decision.category == ErrorCategory.TOOL_FALLBACK
        assert decision.fallback_tool == "print_to_pdf"


# ===========================================================================
# 4. RESULT VERIFIER TESTS
# ===========================================================================


class TestResultVerifier:
    """Tests for verifying artifacts and task outcomes."""

    def test_file_artifact_verification(self, tmp_path: Path):
        verifier = ResultVerifier()
        sample_file = tmp_path / "Shanmuga_Resume.pdf"
        sample_file.write_bytes(b"%PDF-1.4 Mock resume content")

        step = PlanStep(description="Save PDF")
        res = verifier.verify_step_result(step, str(sample_file))

        assert res.verified is True
        assert res.target_artifact == str(sample_file)
        assert res.confidence == 1.0

    def test_empty_file_fails_verification(self, tmp_path: Path):
        verifier = ResultVerifier()
        empty_file = tmp_path / "empty.txt"
        empty_file.write_bytes(b"")

        step = PlanStep(description="Write text")
        res = verifier.verify_step_result(step, str(empty_file))

        assert res.verified is False
        assert "empty file" in res.details.lower()

    def test_structured_dict_verification(self):
        verifier = ResultVerifier()
        step = PlanStep(description="Send file")
        res = verifier.verify_step_result(step, {"success": True, "manifest": "m123"})
        assert res.verified is True


# ===========================================================================
# 5. CANCELLATION & EMERGENCY STOP TESTS
# ===========================================================================


class TestCancellationSystem:
    """Tests for graceful cancellation and hard emergency stop."""

    def test_cancellation_intent_detection(self):
        manager = CancellationManager()

        # Emergency hard stop
        assert manager.detect_cancellation_intent("NEXUS STOP") == CancellationType.EMERGENCY
        assert manager.detect_cancellation_intent("EMERGENCY STOP") == CancellationType.EMERGENCY
        assert manager.detect_cancellation_intent("STOP EVERYTHING") == CancellationType.EMERGENCY

        # Graceful soft stop
        assert manager.detect_cancellation_intent("Nexus stop") == CancellationType.GRACEFUL
        assert manager.detect_cancellation_intent("cancel the task") == CancellationType.GRACEFUL
        assert manager.detect_cancellation_intent("abort") == CancellationType.GRACEFUL

        # Normal text
        assert manager.detect_cancellation_intent("what is the weather?") == CancellationType.NONE

    def test_token_graceful_cancel(self):
        token = CancellationToken()
        token.cancel("User changed mind")
        assert token.is_cancelled is True
        assert token.is_emergency is False

        with pytest.raises(TaskCancelledException):
            token.check()

    def test_token_emergency_stop(self):
        token = CancellationToken()
        token.emergency_stop("Safety trip triggered")
        assert token.is_cancelled is True
        assert token.is_emergency is True

        with pytest.raises(EmergencyStopException):
            token.check()

    @pytest.mark.asyncio
    async def test_emergency_stop_kills_running_tasks(self):
        manager = CancellationManager()
        manager.create_token("plan_test_kill")

        async def dummy_long_task():
            await asyncio.sleep(5.0)

        t = asyncio.create_task(dummy_long_task())
        manager.register_async_task("plan_test_kill", t)

        res = manager.emergency_stop(plan_id="plan_test_kill", reason="Kill switch")
        await asyncio.sleep(0.05)
        assert res["emergency"] is True
        assert res["tasks_cancelled"] >= 1
        assert t.cancelled() or t.done()


# ===========================================================================
# 6. PROGRESS TRACKER TESTS
# ===========================================================================


class TestProgressTracker:
    """Tests for progress calculation and status formatting."""

    @pytest.mark.asyncio
    async def test_progress_lifecycle(self):
        tracker = ProgressTracker()
        plan = Plan(goal=TaskGoal(description="Test task"))
        plan.steps = [
            PlanStep(order=1, description="Step 1"),
            PlanStep(order=2, description="Step 2"),
        ]

        p_start = tracker.start_tracking(plan)
        assert p_start.total_steps == 2
        assert p_start.percent_complete == 0.0

        plan.steps[0].status = StepStatus.COMPLETED
        p_step = tracker.update_step_completed(plan, plan.steps[0])
        assert p_step.percent_complete == 50.0

        p_done = tracker.complete_tracking(plan, success=True)
        assert p_done.percent_complete == 100.0
        assert p_done.status == PlanStatus.COMPLETED


# ===========================================================================
# 7. EXECUTION ENGINE END-TO-END TESTS
# ===========================================================================


class TestPlanExecutionEngine:
    """Tests for sequential execution, variable passing, and error recovery."""

    @pytest.mark.asyncio
    async def test_successful_multi_step_execution(self):
        engine = PlanExecutionEngine()
        planner = TaskPlanner()

        goal = "Nexus, find my latest resume, convert it to PDF, rename it Shanmuga_Resume, and send it to my phone."
        plan = await planner.create_plan(goal)

        res = await engine.execute_plan(plan)
        assert res.success is True
        assert res.steps_executed == plan.total_steps
        assert plan.status == PlanStatus.COMPLETED
        assert "Shanmuga_Resume.pdf" in str(plan.context_variables.values())

    @pytest.mark.asyncio
    async def test_cancellation_during_execution(self):
        engine = PlanExecutionEngine()
        plan = Plan(goal=TaskGoal(description="Cancelled workflow"))
        plan.steps = [
            PlanStep(order=1, description="Step 1"),
            PlanStep(order=2, description="Step 2"),
        ]

        token = CancellationToken()
        token.cancel("User aborted")

        res = await engine.execute_plan(plan, token=token)
        assert res.success is False
        assert plan.status == PlanStatus.CANCELLED
        assert res.error is not None
        assert "cancelled" in res.error.lower()


# ===========================================================================
# 8. TASK MANAGER & BRAIN INTEGRATION TESTS
# ===========================================================================


class TestTaskManagerAndBrain:
    """Tests for TaskManager coordination and NexusBrain multi-step routing."""

    @pytest.mark.asyncio
    async def test_task_manager_run_goal(self):
        mgr = TaskManager()
        goal = "Find resume, convert to PDF, rename Shanmuga_Resume, send to phone"

        result = await mgr.run_goal(goal)
        assert result.success is True
        assert mgr.get_task(result.plan_id) is not None
        assert mgr.get_task_progress(result.plan_id) is not None

    @pytest.mark.asyncio
    async def test_brain_routes_multi_step_task(self):
        brain = NexusBrain()
        await brain.initialize()

        prompt = "Nexus, find my latest resume, convert it to PDF, rename it Shanmuga_Resume, and send it to my phone."
        response = await brain.process(prompt)

        assert response is not None
        assert len(brain.task_manager.list_tasks()) >= 1

    @pytest.mark.asyncio
    async def test_brain_emergency_stop_command(self):
        brain = NexusBrain()
        await brain.initialize()

        response = await brain.process("NEXUS STOP")
        assert "EMERGENCY STOP" in response


# ===========================================================================
# 9. REST API ROUTES TESTS
# ===========================================================================


class TestTasksApiRoutes:
    """Tests for /api/tasks REST endpoints."""

    @pytest.mark.asyncio
    async def test_submit_and_list_tasks(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Submit task
            submit_resp = await client.post(
                "/api/tasks",
                json={
                    "goal": "Find resume, convert to PDF, and transfer to phone",
                    "execute_now": True,
                },
            )
            assert submit_resp.status_code == 200
            data = submit_resp.json()
            assert "plan" in data
            assert "execution" in data
            task_id = data["plan"]["plan_id"]

            # List tasks
            list_resp = await client.get("/api/tasks")
            assert list_resp.status_code == 200
            list_data = list_resp.json()
            assert list_data["count"] >= 1

            # Get task details
            get_resp = await client.get(f"/api/tasks/{task_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["task"]["plan_id"] == task_id

    @pytest.mark.asyncio
    async def test_emergency_stop_api(self):
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/tasks/emergency/stop",
                json={"reason": "Manual operator kill switch"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["emergency_stop"] is True
