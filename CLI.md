# Using the Workspace Lifecycle CLI Wrapper

This guide explains how to execute the entire Workspace Lifecycle workflow step-by-step using the `bin/cli.sh` wrapper script. 

---

## 0. Initial Setup & Starting Services

Before running any commands, you must have the Temporal Server and the Worker script running in the background.

Open **Terminal 1** and start the local Temporal development server:
```bash
temporal server start-dev
```
*(The local Temporal Web UI will be available at [http://localhost:8233](http://localhost:8233). Open this in your browser to watch the workflow execute!)*

Open **Terminal 2** and start the Worker (ensure your virtual environment is active if you have one):
```bash
python3 src/worker.py
```
*To force the worker into **Offline Mode** (ignoring Jira credentials), use the `--offline` flag:*
```bash
python3 src/worker.py --offline
```

Finally, oOpen **Terminal 3** to run the CLI commands below. First, configure your terminal session with the provided shortcut script:
```bash
source setup_demo.sh
```

---

## 1. Setup Simulation (Offline)

To run fully offline (even with Jira credentials in `.env`), initialize the simulation first:
```bash
setup-demo --scenario profile --offline
```

## 2. Load the Epic

Kick off the workflow by telling it which Jira Epic to process.

```bash
load-epic EPIC-001
```

* **What happens:** The workflow starts, ingests `EPIC-001`, and generates the initial `specs/Spec.md` v1 (including the Implementation Plan). It then pauses unconditionally so you can review the generated plan.

## 2.1 Get Sample Commands (Optional)

If you're not sure which commands to run next for your epic, use the `sample-commands` helper.

```bash
sample-commands EPIC-001
```

* **What happens:** The CLI prints a list of all relevant commands with your Epic Name already filled in, making it easy to copy and paste.

## 2. Approve the Plan

Once you've reviewed the generated `specs/Spec.md` v1, you must approve the plan to unblock the parallel agent tasks.

```bash
approve-plan EPIC-001
```

* **What happens:** The workflow resumes and launches the parallel multi-agent loop. Each subtask will now perform its own dynamic planning and execution.

## 3. Query Detailed Status (Optional)

At any point, you can fetch the detailed health and status table (with icons for subtasks):

```bash
query-wf WL-1
```

## 4. Approve Subtasks (Incremental)

As each agent finishes its work, the CLI will guide you to approve them one by one.

```bash
approve-subtask WL-1 WL-1-101
```

## 5. Close Epic (Final Approval)

Give the ultimate sign-off to finalize the workspace and close the Jira issue.

```bash
close-epic WL-1 -comment "Ship it to production!"
```

* **What happens:** The workflow fetches the simulated Jira Development Summary (PRs merged, deployment status, etc.) and appends it to `Spec.md` as v3. Finally, it stamps the bottom of the Spec with your final closing comment and fully completes the Temporal run!
