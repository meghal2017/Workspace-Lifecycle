# Workspace Lifecycle Worker

A Temporal-based application that orchestrates the lifecycle of a Jira Epic from ingestion to final human approval. It simulates an agentic workflow where an Epic is parsed, an implementation plan is generated, automated analysis is performed, and human checkpoints ensure quality before the Epic is finalized.

## Architecture

This project is built using [Temporal](https://temporal.io/), a durable execution framework. The core logic is defined as a deterministic workflow, while interactions with the outside world (file generation, Jira API) are handled by retriable activities.

-   **`src/workflow.py`**: The core Temporal `@workflow` definition. It defines the state machine and blocks on `@workflow.signal` methods waiting for external input. Crucially, if the worker crashes, Temporal automatically replays the state to precisely the point it crashed.
-   **`src/activities.py`**: The Temporal `@activity` definitions. These handle the actual I/O—fetching Jira epics, writing the `Spec.md` file, simulating AI planning, fetching Jira PR summaries, etc.
-   **`src/worker.py`**: The Python script that runs the Temporal Worker, connecting to the Temporal Server and listening for tasks on the queue.
-   **`src/starter.py`**: The underlying CLI script used to initiate workflows and send signals (like "start work" or "approve work") to a running workflow instance.
-   **`src/jira_client.py`**: Handles integration with the real Jira REST API (v3) for syncing comments and transitioning issues.

## Setup

1.  **Dependencies**: Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
2.  **Environment Variables**: Copy `.env.example` to `.env`.
    *   **Offline Mode (Default)**: If you leave `JIRA_API_TOKEN` unset, the worker will operate in Offline Mode. It will ingest mock data from a local scenario registry (`src/scenarios.py`) instead of calling the Jira API.
    *   **Online Mode**: To connect to a real Jira instance, fill in your Jira base URL, email, API token, and project key.
3.  **Temporal Server**: Ensure a Temporal Server is running locally.
    ```bash
    temporal server start-dev
    ```
    *The local Temporal Web UI will be available at [http://localhost:8233](http://localhost:8233).*
4.  **Worker**: Start the background Temporal Worker.
    ```bash
    python3 src/worker.py
    ```
    *To force the worker to run in **Offline Mode** (ignoring any Jira credentials in `.env`), use the `--offline` flag:*
    ```bash
    python3 src/worker.py --offline
    ```

## Usage

To get clean, top-level commands in your terminal for demoing the workflow, you can source the setup script. This maps the commands directly to your current shell session without making any permanent computer-wide changes.

```bash
source setup_demo.sh
```

> **Tip:** While running the workflow commands below, open the [Temporal Web UI (http://localhost:8233)](http://localhost:8233) to watch the execution state machine progress in real-time.

### 1. Setup Simulation (Offline)

If you are running in Offline Mode, initialize the mock data first:
```bash
setup-demo --scenario profile --offline
```

### 2. Load an Epic / Scenario

In **Online Mode**, this fetches a real Jira issue. In **Offline Mode**, this loads a mock scenario (e.g., `profile`, `auth`, `search`).

```bash
load-epic profile
```

### 2. Approve Plan

Review the generated spec in `specs/Spec.md` and approve the high-level plan. This unblocks the parallel agent loops for each child task.

```bash
approve-plan WL-123
```

### 3. Check Real-time Status

Get a dashboard view of all agents and the overall Epic phase:
```bash
query-wf WL-1
```

### 4. Approve Subtasks (Incremental)

As each agent completes its work, follow the "Next step" guide to approve them individually.
```bash
approve-subtask WL-1 WL-1-101
```

### 4. Close Epic (Final Approval)

Once all subtasks are complete and approved, provide the final human approval to finalize the workspace and close the Epic in Jira.

```bash
close-epic WL-123 -comment "Ship it to production!"
```

## Demo Mode

To see the entire lifecycle play out end-to-end with the new parallel multi-agent loop, use the `setup-demo` command to create a realistic scenario:

```bash
setup-demo --scenario profile
```
*Scenarios available: profile, auth, search.*
