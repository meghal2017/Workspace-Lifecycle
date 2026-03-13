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
    )

    logger.info(
        f"\n{'='*60}\n"
        f"  Workflow started!\n"
        f"  Workflow ID : {workflow_id}\n"
        f"  Run ID      : {handle.result_run_id}\n"
        f"  Namespace   : {TEMPORAL_NAMESPACE}\n"
        f"  Task Queue  : {TASK_QUEUE}\n"
        f"{'='*60}\n"
    )


async def send_signal(client: Client, workflow_id: str, comment: str) -> None:
    logger.info(f"Sending 'human_approve' signal to: {workflow_id}")
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(WorkspaceLCWorkflow.human_approve, comment)
    logger.info(f"✅ Signal sent. Comment: '{comment}'")


async def trigger_analysis(client: Client, workflow_id: str) -> None:
    logger.info(f"Sending 'start_analysis' signal to: {workflow_id}")
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(WorkspaceLCWorkflow.start_analysis)
    logger.info("✅ Analysis triggered.")


async def query_phase(client: Client, workflow_id: str) -> None:
    handle = client.get_workflow_handle(workflow_id)
    phase    = await handle.query(WorkspaceLCWorkflow.current_phase)
    approved = await handle.query(WorkspaceLCWorkflow.is_approved)
    logger.info(
        f"\n{'='*40}\n"
        f"  Workflow : {workflow_id}\n"
        f"  Phase    : {phase}\n"
        f"  Approved : {approved}\n"
        f"{'='*40}\n"
    )


async def approve_agents(client: Client, workflow_id: str, comment: str) -> None:
    logger.info(f"Sending 'approve_agent_results' signal to: {workflow_id}")
    handle = client.get_workflow_handle(workflow_id)
    await handle.signal(WorkspaceLCWorkflow.approve_agent_results, comment)
    logger.info(f"✅ Agent results approved. Comment: '{comment}'")


async def print_agent_results(client: Client, workflow_id: str) -> None:
    handle = client.get_workflow_handle(workflow_id)
    results = await handle.query(WorkspaceLCWorkflow.agent_results)
    if not results:
        logger.info("Agent results not available yet (workflow still in AGENT_TASKS phase).")
        return
    logger.info(f"\n{'='*60}")
    for i, r in enumerate(results, start=1):
        logger.info(f"\n--- Agent Task {i} ---\n{r}")
    logger.info(f"{'='*60}\n")


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
    parser.add_argument("--close-epic",        metavar="WORKFLOW_ID", dest="close_epic", help="Send human_approve signal (final checkpoint)")
    parser.add_argument("--approve-work",      metavar="WORKFLOW_ID", dest="approve_work", help="Send approve_agent_results signal")
    parser.add_argument("--start-work",        metavar="WORKFLOW_ID", dest="start_work", help="Send start_analysis signal to trigger agent scans")
    parser.add_argument("--agent-results",     metavar="WORKFLOW_ID", dest="agent_results_wf", help="Query and print raw agent task outputs")
    parser.add_argument("--comment",           default="Approved — looks good!", help="Approval comment")
    parser.add_argument("--query",             metavar="WORKFLOW_ID", help="Query current workflow phase")
    parser.add_argument("--jira-transitions",  metavar="ISSUE_KEY", dest="jira_transitions", help="List Jira transitions for an issue (e.g. WL-1)")
    args = parser.parse_args()

    if args.jira_transitions:
        await print_jira_transitions(args.jira_transitions)
        return

    client = await _get_client()

    if args.close_epic:
        await send_signal(client, args.close_epic, args.comment)
    elif args.approve_work:
        await approve_agents(client, args.approve_work, args.comment)
    elif args.start_work:
        await trigger_analysis(client, args.start_work)
    elif args.agent_results_wf:
        await print_agent_results(client, args.agent_results_wf)
    elif args.query:
        await query_phase(client, args.query)
    else:
        await start_workflow(client, args.load_epic)


if __name__ == "__main__":
    asyncio.run(main())
