"""
starter.py — CLI to start or signal a WorkspaceLCWorkflow.

Required environment variables:
    TEMPORAL_ADDRESS     — e.g. <namespace>.<account-id>.tmprl.cloud:7233
    TEMPORAL_NAMESPACE   — e.g. my-namespace.abc123
    TEMPORAL_API_KEY     — Your Temporal Cloud API key

Optional:
    TASK_QUEUE           — Task queue name (default: workspace-lc-queue)

Usage:
    # Start a workflow
    python3 src/starter.py --epic EPIC-001

    # Query current phase
    python3 src/starter.py --query workspace-lc-EPIC-001

    # Inspect agent task results (before approving)
    python3 src/starter.py --agent-results workspace-lc-EPIC-001

    # Approve agent results (Phase 3b checkpoint)
    python3 src/starter.py --approve-agents workspace-lc-EPIC-001 --comment "Results look solid"

    # Send final human approval (Phase 5 checkpoint)
    python3 src/starter.py --signal workspace-lc-EPIC-001 --comment "Looks great!"

    # Discover Jira transition IDs (to set JIRA_DONE_TRANSITION_ID)
    python3 src/starter.py --jira-transitions WL-1
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy

sys.path.insert(0, os.path.dirname(__file__))
from workflow import WorkspaceLCWorkflow
import jira_client as _jira

TEMPORAL_ADDRESS   = os.environ.get("TEMPORAL_ADDRESS")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")
TEMPORAL_API_KEY   = os.environ.get("TEMPORAL_API_KEY")
TASK_QUEUE         = os.environ.get("TASK_QUEUE", "workspace-lc-queue")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
)
logger = logging.getLogger("workspace-starter")


async def _get_client() -> Client:
    address = TEMPORAL_ADDRESS or "localhost:7233"
    if TEMPORAL_API_KEY:
        return await Client.connect(
            target_host=address,
            namespace=TEMPORAL_NAMESPACE,
            tls=True,
            api_key=TEMPORAL_API_KEY,
            rpc_metadata={"temporal-namespace": TEMPORAL_NAMESPACE},
        )
    return await Client.connect(target_host=address, namespace=TEMPORAL_NAMESPACE)


async def start_workflow(client: Client, epic_id: str) -> None:
    workflow_id = f"workspace-lc-{epic_id}"
    logger.info(f"Starting workflow: {workflow_id}")

    handle = await client.start_workflow(
        WorkspaceLCWorkflow.run,
        epic_id,
        id=workflow_id,
        task_queue=TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )

    logger.info(
        f"\n{'='*60}\n"
        f"  Workflow started!\n"
        f"  Workflow ID : {workflow_id}\n"
        f"  Run ID      : {handle.result_run_id}\n"
        f"  Namespace   : {TEMPORAL_NAMESPACE}\n"
        f"  Task Queue  : {TASK_QUEUE}\n"
        f"{'='*60}\n"
        f"Next step: approve-plan {epic_id}\n"
        f"(You can always fetch full status using: query-wf {epic_id})\n"
    )


async def send_signal(client: Client, workflow_id: str, comment: str) -> None:
    logger.info(f"Sending 'human_approve' signal to: {workflow_id}")
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(WorkspaceLCWorkflow.human_approve, comment)
    logger.info(f"✅ Final approval sent. Comment: '{comment}'")


    print(f"{'='*50}")
    print(f"Next step: Workflow Finalized! ✅")
    print(f"(You can verify the final record using: query-wf {workflow_id.replace('workspace-lc-', '')})")
    print(f"{'='*50}")


async def _get_next_step_hint(client: Client, workflow_id: str) -> str:
    """Query workflow for subtask states and determine the next logical action."""
    epic_key = workflow_id.replace("workspace-lc-", "").upper()
    try:
        handle = client.get_workflow_handle(workflow_id)
        
        # 1. Get all known keys for this Epic
        all_keys = await handle.query("subtask_keys")
        
        # 2. Filter out keys that are already DONE in states
        # (This handles the case where loops haven't started yet too!)
        states = await handle.query("subtask_status") or {}
        pending = [k for k in (all_keys or []) if states.get(k) != "DONE"]

        if pending:
            next_sid = sorted(pending)[0]
            return f"approve-subtask {epic_key} {next_sid}"
        
        # If all subtasks are done, check phase
        phase = await handle.query("current_phase")
        if phase in ["FINAL_APPROVAL", "CLOSED", "DONE"] or (states and all(s == "DONE" for s in states.values())):
            return f"close-epic {epic_key}"
            
        return f"query-wf {epic_key}"
    except Exception:
        return f"query-wf {epic_key}"


async def approve_plan(client: Client, workflow_id: str) -> None:
    logger.info(f"Sending 'approve_plan' signal to: {workflow_id}")
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(WorkspaceLCWorkflow.approve_plan)
    logger.info("✅ Plan approved.")
    
    next_step = await _get_next_step_hint(client, workflow_id)
    print(f"{'='*50}")
    print(f"Next step: {next_step}")
    print(f"(You can always fetch full status using: query-wf {workflow_id.replace('workspace-lc-', '')})")
    print(f"{'='*50}")


async def approve_subtask(client: Client, workflow_id: str, subtask_id: str) -> None:
    logger.info(f"Sending 'approve_subtask' signal for {subtask_id} to: {workflow_id}")
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(WorkspaceLCWorkflow.approve_subtask, subtask_id.upper())
    logger.info(f"✅ Subtask {subtask_id} approved.")
    
    next_step = await _get_next_step_hint(client, workflow_id)
    print(f"{'='*50}")
    print(f"Next step: {next_step}")
    print(f"(You can always fetch full status using: query-wf {workflow_id.replace('workspace-lc-', '')})")
    print(f"{'='*50}")


async def terminate_workflow(client: Client, workflow_id: str) -> None:
    """Terminate any existing workflow execution for a given key."""
    handle = client.get_workflow_handle(workflow_id)
    try:
        await handle.terminate(reason="Manual reset for demo")
        logger.info(f"✅ Terminated workflow: {workflow_id}")
    except Exception as e:
        logger.warning(f"⚠️ Could not terminate {workflow_id} (it may already be closed): {e}")


async def query_subtask_status(client: Client, workflow_id: str) -> None:
    handle = client.get_workflow_handle(workflow_id)
    try:
        states = await handle.query("subtask_status")
        logger.info(f"\n{'='*50}\n  Subtask Status for {workflow_id}:\n")
        if not states:
            logger.info("  (No subtasks initialized yet)")
        for sid, status in states.items():
            # Modern icons for status
            icon = "⚪"
            if status == "DONE": icon = "✅"
            elif status == "EXECUTING": icon = "⚙️ "
            elif status == "WAITING_APPROVAL": icon = "👀"
            elif status == "PLANNING": icon = "📅"
            elif status == "APPROVED": icon = "🆗"
            
            logger.info(f"  {icon} {sid:12s} : {status}")
        logger.info(f"\n{'='*50}\n")
    except Exception as e:
        logger.error(f"Failed to query subtask status: {e}")


async def query_phase(client: Client, workflow_id: str) -> None:
    handle = client.get_workflow_handle(workflow_id)
    
    # Get overall phase, epic status, and subtask states
    phase  = await handle.query(WorkspaceLCWorkflow.current_phase)
    epic_status = "Unknown"
    try:
        epic_status = await handle.query("epic_status")
    except:
        pass

    states = {}
    try:
        states = await handle.query("subtask_status")
    except:
        pass # Older workflows might not have this query yet

    print(f"\n{'='*55}")
    print(f"  WORKSPACE DASHBOARD: {workflow_id}")
    print(f"  EPIC STATUS        : {epic_status}")
    print(f"  WORKFLOW PHASE     : {phase}")
    print(f"{'='*55}")
    
    if states:
        print("\n  Subtask Real-time Status dashboard:")
        for sid, status in states.items():
            icon = "⚪"
            if status == "DONE": icon = "✅"
            elif status == "FAILED": icon = "❌"
            elif status == "EXECUTING": icon = "⚙️ "
            elif status == "WAITING_APPROVAL": icon = "👀"
            elif status == "PLANNING": icon = "📅"
            elif status == "APPROVED": icon = "🆗"
            print(f"  {icon} {sid:12s} : {status}")
    else:
        print("\n  (No subtasks initialized yet)")
    
    print(f"\n{'='*55}\n")


async def print_jira_transitions(issue_key: str) -> None:
    """Print available Jira transitions for an issue (helps find JIRA_DONE_TRANSITION_ID)."""
    if not _jira.jira_enabled():
        logger.error("Jira credentials not set. Add JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN to .env")
        return
    transitions = await _jira.get_transitions(issue_key)
    logger.info(f"\n{'='*50}\n  Available transitions for {issue_key}:\n")
    for t in transitions:
        logger.info(f"  ID: {t['id']:5s}  Name: {t['name']}")
    logger.info(
        f"\n  Set JIRA_DONE_TRANSITION_ID=<id> in your .env\n{'='*50}\n"
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Workspace Lifecycle Workflow CLI")
    parser.add_argument("--load-epic",         default="EPIC-001", dest="load_epic", help="Jira Epic ID (default: EPIC-001)")
    parser.add_argument("--approve-plan",      metavar="WORKFLOW_ID", dest="approve_plan_wf", help="Send approve_plan signal")
    parser.add_argument("--approve-subtask",   nargs=2, metavar=("WORKFLOW_ID", "SUBTASK_ID"), dest="approve_subtask_wf", help="Send approve_subtask signal")
    parser.add_argument("--close-epic",        metavar="WORKFLOW_ID", dest="close_epic", help="Send human_approve signal (final checkpoint)")
    parser.add_argument("--comment",           default="Approved!", help="Approval comment")
    parser.add_argument("--query",             metavar="WORKFLOW_ID", help="Query current workflow phase")
    parser.add_argument("--status",            metavar="WORKFLOW_ID", help="Query detailed subtask status")
    parser.add_argument("--terminate",         metavar="WORKFLOW_ID", dest="terminate_wf", help="Terminate a stuck workflow")
    parser.add_argument("--jira-transitions",  metavar="ISSUE_KEY", dest="jira_transitions", help="List Jira transitions for an issue")
    args = parser.parse_args()

    if args.jira_transitions:
        await print_jira_transitions(args.jira_transitions)
        return

    client = await _get_client()

    if args.approve_plan_wf:
        await approve_plan(client, args.approve_plan_wf)
    elif args.approve_subtask_wf:
        await approve_subtask(client, args.approve_subtask_wf[0], args.approve_subtask_wf[1])
    elif args.close_epic:
        await send_signal(client, args.close_epic, args.comment)
    elif args.query:
        await query_phase(client, args.query)
    elif args.status:
        await query_subtask_status(client, args.status)
    elif args.terminate_wf:
        await terminate_workflow(client, args.terminate_wf)
    else:
        await start_workflow(client, args.load_epic)


if __name__ == "__main__":
    asyncio.run(main())
