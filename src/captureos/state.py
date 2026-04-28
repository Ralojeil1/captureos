"""CaptureOS State — persistence for capture mode toggle.

Manages a simple state file so capture mode survives session restarts.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_STATE_DIR = os.path.expanduser("~/.captureos")
DEFAULT_STATE_FILE = "state.json"


def _state_path(state_dir: Optional[str] = None) -> str:
    """Get the path to the state file."""
    directory = os.path.expanduser(state_dir or DEFAULT_STATE_DIR)
    return os.path.join(directory, DEFAULT_STATE_FILE)


def _ensure_dir(filepath: str) -> None:
    """Ensure the state directory exists."""
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def is_capture_mode(state_dir: Optional[str] = None) -> bool:
    """Check if capture mode is currently active."""
    path = _state_path(state_dir)
    if not os.path.exists(path):
        return False

    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data.get("capture_mode", False)
    except (json.JSONDecodeError, KeyError, IOError):
        return False


def set_capture_mode(
    enabled: bool,
    state_dir: Optional[str] = None,
    metadata: Optional[dict] = None
) -> None:
    """Enable or disable capture mode, persisting the state to disk.

    Args:
        enabled: True to enter capture mode, False to exit
        state_dir: Override state directory (default: ~/.captureos)
        metadata: Optional extra data to store (e.g., timezone, vault path)
    """
    path = _state_path(state_dir)
    _ensure_dir(path)

    data = {
        "capture_mode": enabled,
        "updated_at": datetime.now().isoformat(),
        "metadata": metadata or {},
    }

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def toggle_capture_mode(state_dir: Optional[str] = None) -> bool:
    """Toggle capture mode and return the new state."""
    current = is_capture_mode(state_dir)
    new_state = not current
    set_capture_mode(new_state, state_dir)
    return new_state


def get_state(state_dir: Optional[str] = None) -> dict:
    """Get the full capture state (mode + metadata)."""
    path = _state_path(state_dir)
    if not os.path.exists(path):
        return {"capture_mode": False, "metadata": {}}

    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {"capture_mode": False, "metadata": {}}


def clear_state(state_dir: Optional[str] = None) -> None:
    """Remove the state file entirely."""
    path = _state_path(state_dir)
    if os.path.exists(path):
        os.remove(path)
