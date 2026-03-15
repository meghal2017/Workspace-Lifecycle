# Temporal Architecture — Workspace Lifecycle

## Overview
This project uses **Temporal** to orchestrate long-running, distributed processes. Temporal ensures that even if a worker crashes or a network call fails, the workspace lifecycle state is preserved and eventually recovered.

---

## Key Components

### 1. The Workflow (`src/workflow.py`)
- **Deterministic**: The workflow code must be deterministic. It uses `workflow.execute_activity` for any non-deterministic operations (like current time or API calls).
- **Signal-Driven**: The workflow blocks on `wait_condition` or signals (`approve_plan`, `approve_subtask`, `human_approve`). This allows asynchronous human interaction over hours or days.
- **State Management**: Variables like `self._phase` and `self._subtask_approvals` provide a live view of the project's progress.

### 2. Activities (`src/activities.py`)
- **Non-Deterministic**: This is where real I/O happens (Jira REST API, File System).
- **Retriable**: Activities are automatically retried based on the `RetryPolicy` defined in the workflow.
- **Isolation**: Each activity should be a discrete unit of work (e.g., "Post a Comment" or "Ingest a Ticket").

### 3. The Worker (`src/worker.py`)
- The worker is the runtime environment that executes the workflow and activity code.
- It connects to the Temporal Cluster (Local or Cloud) and listens to a specific **Task Queue**.

### 4. CLI / Starter (`src/starter.py`)
- Acts as the "Client". It starts the workflow execution and sends signals to running instances.

---

## Why Temporal?
- **Durability**: If an agent is halfway through a 10-minute task and the server restarts, Temporal ensures it resumes or retries gracefully.
- **Observability**: The Temporal Web UI provides a full history of every signal, activity result, and state transition.
- **Parallelism**: Using `asyncio.gather` within a workflow easily orchestrates complex parallel agent loops without managing threads or locks manually.
