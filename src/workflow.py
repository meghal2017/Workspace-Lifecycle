"""
workflow.py — The core Temporal @workflow definition for the Workspace Lifecycle Worker.

Temporal workflows are deterministic functions that are replayed on restart.
All state (instance variables) is automatically reconstructed from event history,
giving crash-resilience for free. Real I/O (file writes, network calls) goes
in activities — never directly inside a workflow.

Key Temporal concepts demonstrated here:
  - @workflow.signal    : Human-in-the-loop approval gate
  - workflow.wait_condition : Blocks until a signal arrives (no polling, no resources consumed)
  - asyncio.gather      : Parallel activity execution
  - retry_policy        : Automatic activity retries on failure
  - schedule_to_close_timeout : Overall deadline for each activity
"""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities via a deferred import block (required by Temporal's sandbox)
with workflow.unsafe.imports_passed_through():
    from activities import (
        ingest_jira_epic,
        generate_spec_v1,
        execute_agent_resolution,
        update_spec_v2,
        update_jira_comment,
        close_jira_issue,
        finalize_workspace,
        post_implementation_plan,
        post_spec_artifact,
        generate_subtask_plan,
    )

# ---------------------------------------------------------------------------
# Shared retry policy — applies to all activities unless overridden
# ---------------------------------------------------------------------------
_DEFAULT_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=5,
)


@workflow.defn
class WorkspaceLCWorkflow:
    """
    Workspace Lifecycle Workflow (Multi-Agent Loop POC)

    Orchestrates:
    1. Plan Approval — Initial spec approval.
    2. Parallel Subtasks — Each child task runs its own agent -> approval loop.
    3. Finalization — Final approval to close the Epic.
    """

    def __init__(self) -> None:
        self._phase: str = "INIT"
        self._epic: Optional[Dict[str, Any]] = None
        
        # Signals
        self._plan_approved: bool = False
        self._subtask_approvals: Dict[str, bool] = {}
        self._final_approved: bool = False
        self._final_comment: str = ""

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    @workflow.signal
    async def approve_plan(self) -> None:
        """Signal to approve the initial implementation plan/spec."""
        workflow.logger.info("[signal] approve_plan received.")
        self._plan_approved = True

    @workflow.signal
    async def approve_subtask(self, subtask_id: str) -> None:
        """Signal to approve a specific agent's work on a subtask."""
        workflow.logger.info(f"[signal] approve_subtask received for {subtask_id}")
        self._subtask_approvals[subtask_id] = True

    @workflow.signal
    async def human_approve(self, comment: str = "Approved") -> None:
        """Final signal to ship the fix and close the Epic."""
        workflow.logger.info(f"[signal] human_approve received. Comment: '{comment}'")
        self._final_comment = comment
        self._final_approved = True

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @workflow.query
    def current_phase(self) -> str:
        return self._phase

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    @workflow.run
    async def run(self, epic_id: str) -> str:
        wf_id = workflow.info().workflow_id
        workflow.logger.info(f"[WorkspaceLCWorkflow] Starting POC. epic_id={epic_id}")

        # Phase 1: Ingest
        self._phase = "INGEST"
        self._epic = await workflow.execute_activity(
            ingest_jira_epic,
            epic_id,
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )

        # Phase 2: Spec v1 & Plan Approval
        self._phase = "PLAN_APPROVAL"
        spec_path = await workflow.execute_activity(
            generate_spec_v1,
            self._epic,
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )

        # NEW: Feedback Loop - post plan and full spec artifact to Jira
        await asyncio.gather(
            workflow.execute_activity(
                post_implementation_plan,
                args=[epic_id, spec_path],
                schedule_to_close_timeout=timedelta(minutes=1),
                retry_policy=_DEFAULT_RETRY,
            ),
            workflow.execute_activity(
                post_spec_artifact,
                args=[epic_id, spec_path],
                schedule_to_close_timeout=timedelta(minutes=1),
                retry_policy=_DEFAULT_RETRY,
            ),
        )
        workflow.logger.info("[Phase 2] Waiting for 'approve_plan' signal...")
        await workflow.wait_condition(lambda: self._plan_approved)

        # Phase 3: Parallel Agent Tasks
        self._phase = "PARALLEL_AGENTS"
        child_stories = self._epic.get("child_stories", [])
        workflow.logger.info(f"[Phase 3] Launching {len(child_stories)} parallel agent loops.")

        # Logic for each parallel agent task
        async def run_agent_loop(story: Dict[str, Any]) -> str:
            sid = story["key"]
            sumry = story["summary"]
            epic_desc = self._epic.get("description", "")
            
            # 1. NEW: Generate local plan dynamically
            plan_steps = await workflow.execute_activity(
                generate_subtask_plan,
                args=[sid, sumry, epic_desc],
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=_DEFAULT_RETRY,
            )

            # 2. Post local plan to subtask
            plan_comment = "📅 **Implementation Approach**\n" + "\n".join([f"- {s}" for s in plan_steps])
            await workflow.execute_activity(
                update_jira_comment,
                args=[sid, plan_comment],
                schedule_to_close_timeout=timedelta(minutes=1),
                retry_policy=_DEFAULT_RETRY,
            )

            # 3. Execute Resolution
            res = await workflow.execute_activity(
                execute_agent_resolution,
                args=[sid, sumry, plan_steps],
                schedule_to_close_timeout=timedelta(minutes=5),
                retry_policy=_DEFAULT_RETRY,
            )
            
            # 2. Notify Jira that agent is done and waiting for approval
            await workflow.execute_activity(
                update_jira_comment,
                args=[sid, f"Agent has completed the resolution for `{sid}`. Please review the findings and approve."],
                schedule_to_close_timeout=timedelta(minutes=1),
                retry_policy=_DEFAULT_RETRY,
            )
            
            # 3. Wait for individual approval
            workflow.logger.info(f"Agent loop {sid} waiting for 'approve_subtask'...")
            await workflow.wait_condition(lambda: self._subtask_approvals.get(sid, False))

            # NEW: Post approval stamp to the subtask
            await workflow.execute_activity(
                update_jira_comment,
                args=[sid, "✅ **Human Approval Stamp**: Resolution reviewed and approved by workspace manager."],
                schedule_to_close_timeout=timedelta(minutes=1),
                retry_policy=_DEFAULT_RETRY,
            )

            # 4. Final Transition to "Done"
            await workflow.execute_activity(
                close_jira_issue,
                args=[sid, "Agent resolution approved by human."],
                schedule_to_close_timeout=timedelta(minutes=2),
                retry_policy=_DEFAULT_RETRY,
            )
            
            return res

        # Gather all parallel tasks
        agent_results = await asyncio.gather(*(run_agent_loop(s) for s in child_stories))

        # Phase 4: Summarize in Spec v2
        self._phase = "SUMMARY"
        await workflow.execute_activity(
            update_spec_v2,
            args=[agent_results],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )

        # Phase 5: Final Epic Approval
        self._phase = "FINAL_APPROVAL"
        workflow.logger.info("[Phase 5] Waiting for final 'human_approve' to close Epic...")
        await workflow.wait_condition(lambda: self._final_approved)

        # Phase 6: Close Epic
        self._phase = "CLOSE_EPIC"
        await workflow.execute_activity(
            close_jira_issue,
            args=[epic_id, self._final_comment],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        
        await workflow.execute_activity(
            finalize_workspace,
            args=[epic_id, self._final_comment],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )

        self._phase = "DONE"
        return f"Workflow complete for {epic_id}"
