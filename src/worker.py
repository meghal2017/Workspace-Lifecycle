"""
worker.py — Temporal Worker entrypoint.

Connects to a local Temporal server by default (localhost:7233).
Set TEMPORAL_API_KEY to switch to Temporal Cloud automatically.

Environment variables:
    TEMPORAL_ADDRESS     — default: localhost:7233
    TEMPORAL_NAMESPACE   — default: default
    TASK_QUEUE           — default: workspace-lc-queue

    # Temporal Cloud only (leave unset for local):
    TEMPORAL_API_KEY     — Your Temporal Cloud API key

Usage (local):
    temporal server start-dev          # start the local dev server
    python3 src/worker.py

Usage (cloud):
    export TEMPORAL_ADDRESS="<namespace>.<account>.tmprl.cloud:7233"
    export TEMPORAL_NAMESPACE="<namespace>.<account>"
    export TEMPORAL_API_KEY="your-api-key-here"
    python3 src/worker.py
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from env_loader import load_env
load_env(override=True)  # Always override stale shell env exports

from temporalio.client import Client
from temporalio.worker import Worker

sys.path.insert(0, os.path.dirname(__file__))

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
    write_subtask_spec,
    update_epic_spec_item,
    complete_subtask_spec,
    transition_to_planning,
    transition_to_in_progress,
    transition_to_in_review,
)
from workflow import WorkspaceLCWorkflow

# ---------------------------------------------------------------------------
# Configuration — all read from environment variables
# ---------------------------------------------------------------------------
TEMPORAL_ADDRESS   = os.environ.get("TEMPORAL_ADDRESS")
TEMPORAL_NAMESPACE = os.environ.get("TEMPORAL_NAMESPACE", "default")
TEMPORAL_API_KEY   = os.environ.get("TEMPORAL_API_KEY")
TASK_QUEUE         = os.environ.get("TASK_QUEUE", "workspace-lc-queue")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("workspace-worker")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Temporal Worker for Workspace Lifecycle")
    parser.add_argument("--offline", action="store_true", help="Force run in Offline Mode (ignore Jira credentials)")
    args, _ = parser.parse_known_args()

    # Load .env file, overriding any stale bash session exports
    load_env(override=True)

    if args.offline:
        os.environ["JIRA_OFFLINE"] = "true"
    
    address = TEMPORAL_ADDRESS or "localhost:7233"
    is_cloud = bool(TEMPORAL_API_KEY)

    if is_cloud:
        logger.info(f"Connecting to Temporal Cloud at {address} (namespace={TEMPORAL_NAMESPACE}) via API Key …")
    else:
        logger.info(f"Connecting to local Temporal at {address} (namespace={TEMPORAL_NAMESPACE}) …")

    connect_kwargs: dict = dict(
        target_host=address,
        namespace=TEMPORAL_NAMESPACE,
    )

    if is_cloud:
        # Temporal Cloud with API Key: TLS is required (no client certs),
        # and the key is passed as a bearer token in RPC metadata.
        connect_kwargs["tls"] = True
        connect_kwargs["rpc_metadata"] = {"temporal-namespace": TEMPORAL_NAMESPACE}
        connect_kwargs["api_key"] = TEMPORAL_API_KEY

    client = await Client.connect(**connect_kwargs)
    logger.info("Connected. Starting worker …")

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[WorkspaceLCWorkflow],
        activities=[
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
            write_subtask_spec,
            update_epic_spec_item,
            complete_subtask_spec,
            transition_to_planning,
            transition_to_in_progress,
            transition_to_in_review,
        ],
    ):
        logger.info(
            f"✅ Worker started.\n"
            f"   Address    : {address}\n"
            f"   Namespace  : {TEMPORAL_NAMESPACE}\n"
            f"   Task Queue : {TASK_QUEUE}\n"
            f"   Auth       : {'API Key' if is_cloud else 'none (local)'}\n"
            f"\nPress Ctrl+C to stop.\n"
        )
        await asyncio.Event().wait()


if __name__ == "__main__":
    # Validate required env vars for Temporal Cloud
    if TEMPORAL_ADDRESS and ".cloud" in TEMPORAL_ADDRESS and not TEMPORAL_API_KEY:
        logger.error("TEMPORAL_ADDRESS points to Temporal Cloud but TEMPORAL_API_KEY is missing.")
        sys.exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
