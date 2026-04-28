"""CaptureOS Writer — writes classified items to markdown inbox files.

Handles the actual file I/O for saving captures to the three basket inboxes.
"""

from __future__ import annotations

import os
from datetime import datetime, date
from typing import Optional

from captureos.classifier import Basket, CaptureItem


def _expand_path(path: str) -> str:
    """Expand ~ and environment variables in path."""
    return os.path.expanduser(os.path.expandvars(path))


def ensure_inbox_dir(filepath: str) -> None:
    """Create parent directories for a markdown inbox file if they don't exist."""
    directory = os.path.dirname(_expand_path(filepath))
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def format_capture_line(item: CaptureItem) -> str:
    """Format a capture item as a markdown list entry."""
    timing = ""
    if item.date:
        timing = f" 📅 {item.date}"
        if item.time:
            timing += f" {item.time}"
            if item.duration_minutes:
                timing += f" ({item.duration_minutes}min)"
        elif item.is_all_day or not item.time:
            timing += " (all-day)"

    return f"- [ ] {item.title}{timing}"


def write_to_inbox(
    item: CaptureItem,
    filepath: str,
    create_if_missing: bool = True,
) -> str:
    """Write a single capture item to a markdown inbox file.

    Args:
        item: The classified capture item
        filepath: Path to the markdown inbox file
        create_if_missing: Create the file with template if it doesn't exist

    Returns:
        The absolute path written to
    """
    filepath = _expand_path(filepath)
    ensure_inbox_dir(filepath)

    if not os.path.exists(filepath):
        if create_if_missing:
            _create_inbox_template(filepath, item.basket)
        else:
            raise FileNotFoundError(f"Inbox file not found: {filepath}")

    line = format_capture_line(item)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(filepath, "a") as f:
        f.write(f"\n{line}  _(captured {timestamp})_")

    return os.path.abspath(filepath)


def write_batch_to_inbox(
    items: list[CaptureItem],
    filepath: str,
    create_if_missing: bool = True,
) -> str:
    """Write multiple capture items to a markdown inbox file.

    All items should belong to the same basket.
    """
    filepath = _expand_path(filepath)
    ensure_inbox_dir(filepath)

    if not os.path.exists(filepath) and create_if_missing:
        basket = items[0].basket if items else Basket.IDEA_NOTE
        _create_inbox_template(filepath, basket)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []

    for item in items:
        line = format_capture_line(item)
        lines.append(f"{line}  _(captured {timestamp})_")

    with open(filepath, "a") as f:
        f.write("\n" + "\n".join(lines))

    return os.path.abspath(filepath)


def read_inbox(filepath: str) -> list[str]:
    """Read all capture items from a markdown inbox file.

    Returns list of capture lines (without metadata).
    """
    filepath = _expand_path(filepath)
    if not os.path.exists(filepath):
        return []

    with open(filepath, "r") as f:
        content = f.read()

    lines = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            # Remove timestamp metadata
            cleaned = stripped.split("  _(")[0] if "  _(" in stripped else stripped
            lines.append(cleaned)

    return lines


def _create_inbox_template(filepath: str, basket: Basket) -> None:
    """Create a new markdown inbox file with template header."""
    basket_labels = {
        Basket.TASK_REMINDER: "Tasks / Reminders",
        Basket.EVENT_MEETING: "Events / Meetings",
        Basket.IDEA_NOTE: "Ideas / Notes",
    }

    template = f"""# Capture: {basket_labels[basket]}

Fallback inbox for {basket_labels[basket]} captures.

## Open

_(items will appear here as they are captured)_

## Done / Archived

"""

    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with open(filepath, "w") as f:
        f.write(template)
