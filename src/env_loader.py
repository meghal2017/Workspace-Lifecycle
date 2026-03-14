"""
env_loader.py — Lightweight .env file loader that does NOT rely on python-dotenv.

macOS may block python-dotenv's internal file reads on the Documents folder
(Operation not permitted) even after granting Full Disk Access to the app
due to TCC process inheritance restrictions.

This module reads the .env file using basic Python file I/O, walking up
from the script's location to find the project root .env file.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_env(override: bool = True) -> None:
    """Parse the project root .env file and inject values into os.environ.
    
    Args:
        override: if True, overwrite existing os.environ values (prevents
                  stale bash-exported variables from polluting credentials).
    """
    env_path = _find_env_file()
    if not env_path:
        return  # Silently skip if not found — caller's jira_enabled() will catch it

    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                # Skip blank lines and comments
                if not line or line.startswith("#"):
                    continue
                # Only process KEY=VALUE lines
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Strip optional surrounding quotes
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                if override or key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass  # Permission denied — credentials must be pre-set in environment


def _find_env_file() -> Path | None:
    """Walk up from this file's directory to find the project root .env.
    Uses try/except open() instead of .exists() to avoid macOS PermissionError on stat().
    """
    current = Path(__file__).resolve().parent
    for _ in range(5):  # Max 5 levels up
        candidate = current / ".env"
        try:
            # Try opening; if macOS blocks stat() this at least attempts the read
            open(candidate).close()
            return candidate
        except PermissionError:
            # macOS is blocking access — return candidate anyway so open() call in load_env
            # will also fail gracefully and be caught there
            return candidate
        except FileNotFoundError:
            pass
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None
