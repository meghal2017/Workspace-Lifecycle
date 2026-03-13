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
        run_security_analysis,
        run_architecture_review,
        update_spec_v2,
        update_spec_v3,
        update_jira_comment,
        close_jira_issue,
        finalize_workspace,
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
    Workspace Lifecycle Workflow

    Orchestrates the full lifecycle of a workspace from Jira Epic ingestion to
    human-approved finalization.  All 5 phases survive a worker crash/restart.

    Phases
    ------
    1. Ingest   — Load the Jira Epic + assets.
    2. Spec v1  — Generate the initial Spec.md (t0).
    3. Agents   — Run two simulated agent tasks in parallel (t0 + m).
    4. Spec v2  — Update Spec.md with agent outputs.
    5. Checkpoint — Pause until a human sends the `human_approve` signal.
    6. Finalize — Stamp the Spec.md and return.
    """

    def __init__(self) -> None:
        # Workflow state — replayed automatically on restart
        self._approved: bool = False
        self._approver_comment: str = ""
        self._agent_approved: bool = False
        self._agent_reviewer_comment: str = ""
        self._analysis_triggered: bool = False
        self._epic: Optional[Dict[str, Any]] = None
        self._agent_results: List[str] = []
        self._phase: str = "INIT"

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    @workflow.signal
    async def start_analysis(self) -> None:
        """
        External signal sent via CLI to trigger the parallel agent tasks.
        Unblocks the AWAITING_ANALYSIS_TRIGGER checkpoint.
        """
        workflow.logger.info("[signal] start_analysis received.")
        self._analysis_triggered = True

    @workflow.signal
    async def human_approve(self, comment: str = "Approved") -> None:
        """
        External signal sent by a human reviewer (or the starter --signal CLI).
        Unblocks the wait_condition in the main run() loop.
        """
        workflow.logger.info(
            f"[signal] human_approve received. Comment: '{comment}'"
        )
        self._approver_comment = comment
        self._approved = True

    @workflow.signal
    async def approve_agent_results(self, comment: str = "Looks good") -> None:
        """
        Signal sent after reviewing Task 1 + Task 2 outputs.
        Unblocks the AWAITING_AGENT_REVIEW checkpoint and passes reviewer notes
        into Spec v2 and the Jira comment.
        """
        workflow.logger.info(
            f"[signal] approve_agent_results received. Comment: '{comment}'"
        )
        self._agent_reviewer_comment = comment
        self._agent_approved = True

    # ------------------------------------------------------------------
    # Queries (inspect workflow state without mutating it)
    # ------------------------------------------------------------------

    @workflow.query
    def current_phase(self) -> str:
        """Return the current phase name for observability."""
        return self._phase

    @workflow.query
    def is_approved(self) -> bool:
        """Return whether the final human checkpoint has been passed."""
        return self._approved

    @workflow.query
    def agent_results(self) -> List[str]:
        """Return raw agent task outputs so a reviewer can read them before approving."""
        return self._agent_results

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    @workflow.run
    async def run(self, epic_id: str) -> str:
        """
        Main workflow coroutine.  Temporal replays this from the event log on
        every worker restart — deterministic code only here.
        """
        wf_id = workflow.info().workflow_id
        workflow.logger.info(f"[WorkspaceLCWorkflow] Starting. workflow_id={wf_id}, epic_id={epic_id}")

        # ----------------------------------------------------------------
        # Phase 1: Ingest Jira Epic
        # ----------------------------------------------------------------
        self._phase = "INGEST"
        workflow.logger.info("[Phase 1] Ingesting Jira Epic …")
        self._epic = await workflow.execute_activity(
            ingest_jira_epic,
            epic_id,
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        workflow.logger.info(f"[Phase 1] Ingested epic: {self._epic.get('summary', '')}")

        # ----------------------------------------------------------------
        # Phase 2: Generate Spec.md v1
        # ----------------------------------------------------------------
        self._phase = "SPEC_V1"
        workflow.logger.info("[Phase 2] Generating Spec.md v1 …")
        spec_path_v1 = await workflow.execute_activity(
            generate_spec_v1,
            self._epic,
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        workflow.logger.info(f"[Phase 2] Spec.md v1 written → {spec_path_v1}")

        # ----------------------------------------------------------------
        # Phase 2b: AWAITING_ANALYSIS_TRIGGER
        # ----------------------------------------------------------------
        self._phase = "AWAITING_ANALYSIS_TRIGGER"
        workflow.logger.info(
            "[Phase 2b] ⏸ Pausing for analysis trigger. "
            "Send 'start_analysis' signal to continue."
        )
        await workflow.wait_condition(lambda: self._analysis_triggered)
        workflow.logger.info("[Phase 2b] ✅ Analysis triggered.")

        # ----------------------------------------------------------------
        # Phase 3: Run agent tasks in parallel (t0 + m)
        # ----------------------------------------------------------------
        self._phase = "AGENT_TASKS"
        workflow.logger.info("[Phase 3] Running agent tasks in parallel …")
        self._agent_results = list(
            await asyncio.gather(
                workflow.execute_activity(
                    run_security_analysis,
                    self._epic,
                    schedule_to_close_timeout=timedelta(minutes=5),
                    retry_policy=_DEFAULT_RETRY,
                ),
                workflow.execute_activity(
                    run_architecture_review,
                    self._epic,
                    schedule_to_close_timeout=timedelta(minutes=5),
                    retry_policy=_DEFAULT_RETRY,
                ),
            )
        )
        workflow.logger.info(f"[Phase 3] {len(self._agent_results)} agent tasks completed.")

        # ----------------------------------------------------------------
        # Phase 3b: Human Checkpoint — review agent results
        # ----------------------------------------------------------------
        self._phase = "AWAITING_AGENT_REVIEW"
        workflow.logger.info(
            "[Phase 3b] ⏸ Pausing for agent results review. "
            "Send 'approve_agent_results' signal to continue."
        )
        await workflow.wait_condition(lambda: self._agent_approved)
        workflow.logger.info(
            f"[Phase 3b] ✅ Agent results approved. Notes: '{self._agent_reviewer_comment}'"
        )

        # ----------------------------------------------------------------
        # Phase 4: Update Spec.md to v2 (includes reviewer notes)
        # ----------------------------------------------------------------
        self._phase = "SPEC_V2"
        workflow.logger.info("[Phase 4] Updating Spec.md to v2 …")
        spec_path_v2 = await workflow.execute_activity(
            update_spec_v2,
            args=[self._agent_results, self._agent_reviewer_comment],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        workflow.logger.info(f"[Phase 4] Spec.md v2 written → {spec_path_v2}")

        # ----------------------------------------------------------------
        # Phase 4b: Update Jira with a progress summary comment
        # ----------------------------------------------------------------
        self._phase = "JIRA_UPDATE"
        workflow.logger.info("[Phase 4b] Posting Jira progress comment …")
        jira_summary = (
            f"Agent analysis complete for epic `{epic_id}`.\n\n"
            f"**Security Analysis:** Task 1 findings appended to Spec.md.\n"
            f"**Architecture Review:** Task 2 findings appended to Spec.md.\n"
            f"**Reviewer notes:** {self._agent_reviewer_comment}\n\n"
            f"Spec.md updated to v2 at `{spec_path_v2}`. Awaiting final human approval."
        )
        await workflow.execute_activity(
            update_jira_comment,
            args=[epic_id, jira_summary],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        workflow.logger.info("[Phase 4b] Jira comment posted.")

        # ----------------------------------------------------------------
        # Phase 5: Human Checkpoint — final approval before finalize
        # ----------------------------------------------------------------
        self._phase = "AWAITING_HUMAN"
        workflow.logger.info(
            "[Phase 5] ⏸ Pausing at final human checkpoint. "
            "Send the 'human_approve' signal to continue."
        )
        await workflow.wait_condition(lambda: self._approved)
        workflow.logger.info(
            f"[Phase 5] ✅ Checkpoint cleared. Comment: '{self._approver_comment}'"
        )

        # ----------------------------------------------------------------
        # Phase 5b: Post final approval to Jira and close the issue
        # ----------------------------------------------------------------
        self._phase = "JIRA_CLOSE"
        workflow.logger.info("[Phase 5b] Closing Jira issue …")
        await workflow.execute_activity(
            close_jira_issue,
            args=[epic_id, self._approver_comment],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        workflow.logger.info("[Phase 5b] Jira issue closed.")

        # ----------------------------------------------------------------
        # Phase 6: Fetch Jira Development Summary (Spec v3)
        # ----------------------------------------------------------------
        self._phase = "SPEC_V3"
        workflow.logger.info("[Phase 6] Fetching Jira Development Summary for Spec v3 …")
        await workflow.execute_activity(
            update_spec_v3,
            args=[epic_id],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        workflow.logger.info("[Phase 6] Spec.md v3 updated.")

        # ----------------------------------------------------------------
        # Phase 7: Finalize
        # ----------------------------------------------------------------
        self._phase = "FINALIZE"
        workflow.logger.info("[Phase 7] Finalizing workspace …")
        summary = await workflow.execute_activity(
            finalize_workspace,
            args=[epic_id, self._approver_comment],
            schedule_to_close_timeout=timedelta(minutes=2),
            retry_policy=_DEFAULT_RETRY,
        )
        workflow.logger.info(f"[Phase 7] {summary}")

        self._phase = "DONE"
        return summary
