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

Finally, oOpen **Terminal 3** to run the CLI commands below. First, configure your terminal session with the provided shortcut script:
```bash
source setup_demo.sh
```

---

## 1. Load the Epic

Kick off the workflow by telling it which Jira Epic to process.

```bash
load-epic EPIC-001
```

* **What happens:** The workflow starts, ingests `EPIC-001`, and generates the initial `specs/Spec.md` v1 (including the Implementation Plan). It then pauses unconditionally so you can review the generated plan.

## 2. Start Work (Agent Scans)

Once you're ready to proceed, trigger the simulated AI agents.

```bash
start-work EPIC-001
```

* **What happens:** The workflow resumes and executes the Security Analysis and Architecture Review activities in parallel. Once they finish, they append their findings to `Spec.md` v2, post an update comment to Jira, and pause for human review.

## 3. Approve Work

Review the agent findings inside `specs/Spec.md`. If they look good, approve them and optionally leave a reviewer comment.

```bash
approve-work EPIC-001 -comment "Agent results look solid, ready for final human sign-off."
```

* **What happens:** The workflow records your approval comment, but pauses *one last time* at the final human checkpoint.

## 4. Close Epic (Final Approval)

Give the ultimate sign-off to finalize the workspace and close the Jira issue.

```bash
close-epic EPIC-001 -comment "Ship it to production!"
```

* **What happens:** The workflow fetches the simulated Jira Development Summary (PRs merged, deployment status, etc.) and appends it to `Spec.md` as v3. Finally, it stamps the bottom of the Spec with your final closing comment and fully completes the Temporal run!
