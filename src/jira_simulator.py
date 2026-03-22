import json
import os
import logging
from datetime import datetime

logger = logging.getLogger("jira-simulator")

SIM_DIR = os.path.join(os.path.dirname(__file__), "..", "simulated_jira")

def get_issue_dir(key: str) -> str:
    """Return the directory where an issue (and its spec) should live."""
    key = key.upper()
    parts = key.split('-')
    
    if len(parts) >= 3:
        # It's a subtask (e.g. WL-1-101)
        parent_key = "-".join(parts[:2])
        path = os.path.join(SIM_DIR, parent_key, "sub-tasks", key)
    else:
        # It's an Epic (e.g. WL-1)
        path = os.path.join(SIM_DIR, key)
    
    os.makedirs(path, exist_ok=True)
    return path

def _get_path(key: str) -> str:
    """Return the absolute path to the JSON file for a given key."""
    directory = get_issue_dir(key)
    return os.path.join(directory, f"{key.upper()}.json")

def load_sim(key: str) -> dict:
    path = _get_path(key)
    if not os.path.exists(path):
        # Fallback for old flat structure if we need to migrate or just return None
        return None
    with open(path, "r") as f:
        return json.load(f)

def save_sim(data: dict):
    key = data["key"]
    path = _get_path(key)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def get_issue(key: str) -> dict:
    """Return an issue in a format similar to Jira's REST API."""
    data = load_sim(key)
    if not data:
        return None
    
    # Return in Jira-like structure
    return {
        "id": data.get("id", f"sim-{key}"),
        "key": data["key"],
        "fields": data["fields"]
    }

def search_issues(jql: str) -> list:
    """Mock JQL search. Returns all issues found in the hierarchical sim directory."""
    results = []
    if not os.path.exists(SIM_DIR):
        return []
        
    for root, dirs, files in os.walk(SIM_DIR):
        for filename in files:
            if filename.endswith(".json"):
                key = filename[:-5]
                # Verify it's in the right place (the directory name should match the filename prefix)
                # But for simplicity, we'll just load it.
                issue = get_issue(key)
                if issue:
                    results.append(issue)
    return results

def delete_issue(key: str):
    """Delete an issue's directory (including its spec)."""
    import shutil
    directory = get_issue_dir(key)
    if os.path.exists(directory):
        shutil.rmtree(directory)
        logger.info(f"[SIM] Deleted directory {directory}")

def create_issue(fields: dict) -> dict:
    key = f"SIM-{len(search_issues('')) + 1}"
    data = {
        "key": key,
        "fields": fields,
        "children": []
    }
    save_sim(data)
    return get_issue(key)

def link_issue(inward: str, outward: str, type_name: str):
    logger.info(f"[SIM] Linked {inward} to {outward} via {type_name}")

def get_transitions(key: str) -> list:
    return [
        {"id": "planning", "name": "Planning"},
        {"id": "31", "name": "In Progress"},
        {"id": "review", "name": "In Review"},
        {"id": "done", "name": "Done"}
    ]

def get_child_issues(parent_key: str) -> list:
    """Return children associated with a parent (Epic)."""
    data = load_sim(parent_key)
    if not data or "children" not in data:
        return []
    
    # Each child is returned in a Jira-like structure
    results = []
    for child in data["children"]:
        results.append({
            "key": child["key"],
            "fields": child["fields"]
        })
    return results

def add_comment(key: str, body: str):
    """Add a comment to an issue (and persist to JSON)."""
    data = load_sim(key)
    if not data:
        # If it's a child, we might need to find which Epic it belongs to
        # For simplicity in the simulator, we assume we only comment on issues that exist
        logger.error(f"[SIM] Cannot add comment: {key} not found.")
        return

    comment = {
        "id": str(len(data["fields"].get("comments", [])) + 1),
        "body": body,
        "author": "Simulator",
        "created": datetime.now().isoformat()
    }
    
    if "comments" not in data["fields"]:
        data["fields"]["comments"] = []
    
    data["fields"]["comments"].append(comment)
    save_sim(data)
    logger.info(f"[SIM] Added comment to {key}: {body[:50]}...")

def transition_issue(key: str, status_name: str):
    """Update the status of an issue."""
    data = load_sim(key)
    if not data:
        return
    
    old_status = data["fields"].get("status", "Unknown")
    data["fields"]["status"] = status_name
    save_sim(data)
    logger.info(f"[SIM] Transitioned {key}: {old_status} -> {status_name}")

def initialize_scenario(scenario_id: str, scenario_data: dict, key: str = None):
    """Bootstrap a simulation from a scenario registry entry."""
    if not key:
        key = scenario_id.upper()
    
    # Create child stories using the Epic key as prefix
    child_stories = []
    for i, child_data in enumerate(scenario_data["children"]):
        # Children typically have incrementing IDs like WL-101, WL-102
        ckey = f"{key}-{101 + i}"
        child_stories.append({
            "key": ckey,
            "fields": {
                "summary": child_data["summary"],
                "description": child_data["desc"],
                "status": "To Do",
                "comments": []
            }
        })
    
    epic_data = {
        "id": f"sim-{key}",
        "key": key,
        "fields": {
            "summary": scenario_data["summary"],
            "description": scenario_data["description"],
            "status": "To Do",
            "comments": [],
            "labels": scenario_data.get("labels", []),
            "acceptance_criteria": scenario_data.get("acceptance_criteria", [])
        },
        "children": child_stories
    }
    
    save_sim(epic_data)
    # Also save each child as its own file so we can look them up by key directly
    for child in child_stories:
        save_sim(child)
    
    logger.info(f"[SIM] Initialized scenario '{scenario_id}' as {key}")
    return key
