"""
test_workflow.py — Integration test for the full WorkspaceLCWorkflow.

Uses temporalio.testing.WorkflowEnvironment which spins up an in-process
Temporal test server — no Docker / external process needed.

Tests:
  1. Full happy-path flow with both signals → workflow returns DONE.
  2. Workflow blocks at AWAITING_AGENT_REVIEW when approve_agent_results not sent.
  3. Workflow blocks at AWAITING_HUMAN after agent approval (original checkpoint).
  4. agent_results and current_phase queries work correctly.
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from workflow import WorkspaceLCWorkflow
from src.activities import (
    close_jira_issue,
    finalize_workspace,
    generate_spec_v1,
    ingest_jira_epic,
    run_architecture_review,
    run_security_analysis,
    update_jira_comment,
    update_spec_v2,
    update_spec_v3,
)


# ---------------------------------------------------------------------------
# Helpers — mock activities so tests run fast and without real file I/O
# ---------------------------------------------------------------------------

MOCK_EPIC = {
    "id": "EPIC-001", "key": "PROJ-42",
    "summary": "Test Epic", "description": "desc",
    "status": "In Progress", "priority": "High",
    "reporter": "r@test.com", "assignee": "a@test.com",
    "labels": ["test"], "story_points": 5, "sprint": "S1",
    "assets": [], "acceptance_criteria": ["AC1"], "child_stories": [],
}


async def _mock_ingest(epic_id: str) -> dict:
    return MOCK_EPIC

async def _mock_gen_v1(epic: dict) -> str:
    return "/tmp/Spec.md"

import temporalio.activity as _ta

@_ta.defn(name="run_security_analysis")
async def _mock_run_security_analysis(epic: dict) -> str:
    return "**Security Analysis**\nEverything looks totally secure."

@_ta.defn(name="run_architecture_review")
async def _mock_run_architecture_review(epic: dict) -> str:
    return "**Architecture Review**\nScale it to the moon."

async def _mock_update_v2(results: list, reviewer_comment: str = "") -> str:
    return "/tmp/Spec.md"

async def _mock_update_v3(epic_id: str) -> str:
    return "/tmp/Spec.md"

async def _mock_jira_comment(epic_id: str, summary_comment: str) -> str:
    return f"Jira comment posted to {epic_id}"

async def _mock_jira_close(epic_id: str, final_comment: str) -> str:
    return f"Jira issue {epic_id} closed"

async def _mock_finalize(epic_id: str, comment: str) -> str:
    return f"Workspace {epic_id} FINALIZED"


MOCK_ACTIVITIES = [
    _mock_ingest, _mock_gen_v1,
    _mock_run_security_analysis, _mock_run_architecture_review,
    _mock_update_v2, _mock_update_v3, _mock_jira_comment,
    _mock_jira_close, _mock_finalize,
]

# Map real activity names → mock functions (Temporal matches by name)
import temporalio.activity as _ta
_ta.defn(_mock_ingest,                  name="ingest_jira_epic")
_ta.defn(_mock_gen_v1,                  name="generate_spec_v1")
_ta.defn(_mock_update_v2,               name="update_spec_v2")
_ta.defn(_mock_update_v3,               name="update_spec_v3")
_ta.defn(_mock_jira_comment,            name="update_jira_comment")
_ta.defn(_mock_jira_close,              name="close_jira_issue")
_ta.defn(_mock_finalize,                name="finalize_workspace")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_workflow_full_flow_with_both_signals():
    """
    Happy path: start workflow, send approve_agent_results then human_approve,
    assert workflow completes as DONE.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue",
            workflows=[WorkspaceLCWorkflow],
            activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                WorkspaceLCWorkflow.run,
                "EPIC-001",
                id="test-wf-both-signals",
                task_queue="test-queue",
            )

            # Let it run until it blocks at the analysis trigger checkpoint
            await asyncio.sleep(0.5)

            phase = await handle.query(WorkspaceLCWorkflow.current_phase)
            assert phase == "AWAITING_ANALYSIS_TRIGGER", f"Expected AWAITING_ANALYSIS_TRIGGER, got {phase}"

            # Send first signal: start analysis
            await handle.signal(WorkspaceLCWorkflow.start_analysis)
            await asyncio.sleep(0.5)

            phase = await handle.query(WorkspaceLCWorkflow.current_phase)
            assert phase == "AWAITING_AGENT_REVIEW", f"Expected AWAITING_AGENT_REVIEW, got {phase}"

            # Send second signal: approve agent results
            await handle.signal(WorkspaceLCWorkflow.approve_agent_results, "Looks solid!")

            # Let it proceed to the final checkpoint
            await asyncio.sleep(0.5)

            phase = await handle.query(WorkspaceLCWorkflow.current_phase)
            assert phase == "AWAITING_HUMAN", f"Expected AWAITING_HUMAN, got {phase}"

            # Send third signal: final human approval
            await handle.signal(WorkspaceLCWorkflow.human_approve, "Ship it!")

            result = await handle.result()
            assert "FINALIZED" in result
            assert "EPIC-001" in result


@pytest.mark.asyncio
async def test_workflow_pauses_at_agent_review():
    """
    Verify the workflow blocks at AWAITING_AGENT_REVIEW and does NOT
    proceed if approve_agent_results is not sent.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue-ar",
            workflows=[WorkspaceLCWorkflow],
            activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                WorkspaceLCWorkflow.run,
                "EPIC-001",
                id="test-wf-pause-agent",
                task_queue="test-queue-ar",
            )

            await asyncio.sleep(0.5)

            phase = await handle.query(WorkspaceLCWorkflow.current_phase)
            assert phase == "AWAITING_ANALYSIS_TRIGGER", f"Expected AWAITING_ANALYSIS_TRIGGER, got {phase}"

            # Send first signal: start analysis
            await handle.signal(WorkspaceLCWorkflow.start_analysis)
            await asyncio.sleep(0.5)

            phase = await handle.query(WorkspaceLCWorkflow.current_phase)
            assert phase == "AWAITING_AGENT_REVIEW", f"Expected AWAITING_AGENT_REVIEW, got {phase}"

            # agent_results should be populated by now
            results = await handle.query(WorkspaceLCWorkflow.agent_results)
            assert isinstance(results, list)
            assert len(results) == 2
            assert "Security Analysis" in results[0]
            assert "Architecture Review" in results[1]

            # Cleanup — send both signals
            await handle.signal(WorkspaceLCWorkflow.approve_agent_results, "cleanup")
            await asyncio.sleep(0.5)
            await handle.signal(WorkspaceLCWorkflow.human_approve, "cleanup")
            await handle.result()

@pytest.mark.asyncio
async def test_workflow_pauses_before_analysis():
    """
    Verify the workflow blocks at AWAITING_ANALYSIS_TRIGGER and does NOT
    proceed if start_analysis is not sent.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue-analysis",
            workflows=[WorkspaceLCWorkflow],
            activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                WorkspaceLCWorkflow.run,
                "EPIC-001",
                id="test-wf-pause-analysis",
                task_queue="test-queue-analysis",
            )

            await asyncio.sleep(0.5)

            phase = await handle.query(WorkspaceLCWorkflow.current_phase)
            assert phase == "AWAITING_ANALYSIS_TRIGGER", f"Expected AWAITING_ANALYSIS_TRIGGER, got {phase}"

            # Cleanup
            await handle.signal(WorkspaceLCWorkflow.start_analysis)
            await asyncio.sleep(0.5)
            await handle.signal(WorkspaceLCWorkflow.approve_agent_results, "cleanup")
            await asyncio.sleep(0.5)
            await handle.signal(WorkspaceLCWorkflow.human_approve, "cleanup")
            await handle.result()


@pytest.mark.asyncio
async def test_workflow_pauses_at_final_checkpoint():
    """
    Verify the workflow proceeds past AWAITING_AGENT_REVIEW but blocks at
    AWAITING_HUMAN when only the first signal is sent.
    """
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue-fcp",
            workflows=[WorkspaceLCWorkflow],
            activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                WorkspaceLCWorkflow.run,
                "EPIC-001",
                id="test-wf-final-checkpoint",
                task_queue="test-queue-fcp",
            )

            await asyncio.sleep(0.5)

            # Send first signal
            await handle.signal(WorkspaceLCWorkflow.start_analysis)
            await asyncio.sleep(0.5)

            # Send second signal
            await handle.signal(WorkspaceLCWorkflow.approve_agent_results, "Agent results OK")
            await asyncio.sleep(0.5)

            phase = await handle.query(WorkspaceLCWorkflow.current_phase)
            approved = await handle.query(WorkspaceLCWorkflow.is_approved)
            assert phase == "AWAITING_HUMAN", f"Expected AWAITING_HUMAN, got {phase}"
            assert approved is False

            # Cleanup
            await handle.signal(WorkspaceLCWorkflow.human_approve, "cleanup")
            await handle.result()


@pytest.mark.asyncio
async def test_workflow_queries():
    """Verify @workflow.query handlers work on a running workflow."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-queue-q",
            workflows=[WorkspaceLCWorkflow],
            activities=MOCK_ACTIVITIES,
        ):
            handle = await env.client.start_workflow(
                WorkspaceLCWorkflow.run,
                "EPIC-001",
                id="test-wf-queries",
                task_queue="test-queue-q",
            )
            await asyncio.sleep(0.5)

            phase    = await handle.query(WorkspaceLCWorkflow.current_phase)
            approved = await handle.query(WorkspaceLCWorkflow.is_approved)
            results  = await handle.query(WorkspaceLCWorkflow.agent_results)

            assert isinstance(phase, str)
            assert isinstance(approved, bool)
            assert isinstance(results, list)

            # Cleanup
            await handle.signal(WorkspaceLCWorkflow.start_analysis)
            await asyncio.sleep(0.5)
            await handle.signal(WorkspaceLCWorkflow.approve_agent_results, "done")
            await asyncio.sleep(0.5)
            await handle.signal(WorkspaceLCWorkflow.human_approve, "done")
            await handle.result()
