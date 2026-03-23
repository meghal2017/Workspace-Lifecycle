# Multi-Agent Loop Architecture

## Concept
The "Multi-Agent Loop" is a paradigm where a single complex mission (an Epic) is broken down into parallel, independent assignments (Subtasks). Each subtask is handled by a dedicated agent instance that performs **Dynamic Planning** before executing its resolution.

---

## The Workflow Loop
For every subtask discovered in the Jira Epic, the Temporal workflow launches a concurrent `run_agent_loop`:

1.  **Dynamic Planning (`generate_subtask_plan`)**:
    - The agent analyzes the specific task summary (e.g., "UI: Build Profile Component") and the broader Epic description.
    - **Offline Support**: In Offline Mode, this activity consumes mock data from the `src/scenarios.py` registry to ensure consistent and predictable demo behavior.
    - It generates a list of realistic implementation steps (e.g., "Create React component", "Write HSL styles", "Add unit tests").
    - This plan is posted to Jira (or logged) to provide a human-readable roadmap.

2.  **Execution (`execute_agent_resolution`)**:
    - The agent simulates the actual coding and testing phase based on the generated plan.
    - Status is transitioned to "In Progress" in Jira.

3.  **Human Approval**:
    - The loop pauses using `workflow.wait_condition` until a human provides an `approve-subtask` signal.
    - Once approved, a **Human Approval Stamp** is posted to the Jira comment thread.

4.  **Finalization**:
    - The subtask is transitioned to "Done".

---

## Parallelism vs Dependencies
- **Current State**: All agents run in parallel to maximize throughput.
- **Future State**: Support for `depends_on` metadata in subtasks will allow the workflow to orchestrate sequential chains (e.g., wait for Backend API before starting UI).

---

## Learnings & Best Practices
- **Idempotency**: Activities must be idempotent because Temporal may replay workflow logic or retry activities on failure.
- **Signal-Based Control**: Using signals (`approve-plan`, `approve-subtask`) allows humans to act as the "control plane" for AI-driven execution.
- **Context Management**: Passing the full Epic description to each subtask-planning activity ensures the agent has "global" context even when working on a "local" task.
