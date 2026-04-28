#!/usr/bin/env python3
"""CaptureOS CLI — standalone capture router.

Usage:
    captureos "Dentist tomorrow 3pm"
    captureos --multi "Call Alex Friday 10am. Idea: build a report generator."
    captureos --capture    # Enter capture mode (persistent)
    captureos --normal     # Exit capture mode
    captureos --status     # Show current mode
    captureos --classify "Follow up with Sarah Monday 11am"
    captureos --inbox tasks   # Read tasks inbox
    captureos --config ~/my-capture-config.yaml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from typing import Optional

import yaml  # optional, graceful fallback

from captureos.parser import parse_capture_items, split_items, strip_prefix
from captureos.classifier import Basket, CaptureItem, CaptureResult
from captureos.router import RouterConfig
from captureos.writer import write_to_inbox, read_inbox, write_batch_to_inbox
from captureos.state import is_capture_mode, set_capture_mode, get_state
from captureos.conflict import ConflictDetector


def _load_config(config_path: Optional[str] = None) -> RouterConfig:
    """Load router configuration from YAML file or defaults."""
    config = RouterConfig()

    if config_path:
        config_path = os.path.expanduser(config_path)
    else:
        # Try default locations
        candidates = [
            os.path.expanduser("~/.captureos/config.yaml"),
            os.path.expanduser("~/.hermes/captureos/config.yaml"),
            "config/captureos.config.yaml",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                config_path = candidate
                break

    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f) or {}

            if "user" in data:
                config.user_name = data["user"].get("name", "")
            if "timezone" in data:
                config.timezone = data["timezone"]
            if "vault" in data:
                config.vault_path = data["vault"].get("path")
                config.wiki_dir = data["vault"].get("wiki_dir", "wiki")
            if "calendar" in data:
                config.calendar_enabled = data["calendar"].get("enabled", False)
                config.calendar_provider = data["calendar"].get("provider", "none")
                config.default_reminders = data["calendar"].get(
                    "default_reminders_minutes", [1440, 60]
                )
            if "durations_minutes" in data:
                config.duration_meeting_call = data["durations_minutes"].get(
                    "meeting_call", 60
                )
                config.duration_event_appointment = data["durations_minutes"].get(
                    "ordinary_event_appointment", 60
                )
                config.duration_large_event = data["durations_minutes"].get(
                    "large_event_when_obvious", 120
                )
                config.duration_timed_task = data["durations_minutes"].get(
                    "timed_task_reminder", 60
                )
            if "baskets" in data:
                config.basket_files = {
                    Basket.TASK_REMINDER: data["baskets"].get(
                        "task_reminder", "capture-tasks-reminders.md"
                    ),
                    Basket.EVENT_MEETING: data["baskets"].get(
                        "event_meeting", "capture-events-meetings.md"
                    ),
                    Basket.IDEA_NOTE: data["baskets"].get(
                        "idea_note", "capture-ideas-notes.md"
                    ),
                }
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}", file=sys.stderr)
    elif config_path:
        print(f"Warning: Config file not found: {config_path}", file=sys.stderr)

    return config


def _classify_item(parsed: dict, config: RouterConfig) -> CaptureItem:
    """Classify a single parsed item into a basket using heuristics."""
    raw = parsed["raw_text"]
    cleaned = parsed["cleaned_text"]
    explicit = parsed["explicit_basket"]
    has_date = parsed["has_date"]
    has_time = parsed["has_time"]

    # ── 1. Explicit prefix wins ──
    if explicit:
        basket = Basket(explicit)
        return CaptureItem(
            basket=basket,
            title=cleaned,
            date=parsed["date"],
            time=parsed["time"],
            duration_minutes=_default_duration(basket, cleaned, config),
            is_all_day=parsed["is_all_day"],
            confidence=1.0,
            reasoning=f"Explicit prefix: {explicit}",
        )

    # ── 2. Date+time present → event/meeting or task/reminder ──
    if has_date and has_time:
        # Meeting keywords → event
        meeting_kw = {"meeting", "call", "sync", "standup", "appointment",
                      "dentist", "doctor", "lunch", "dinner", "coffee"}
        if any(kw in cleaned.lower() for kw in meeting_kw):
            return CaptureItem(
                basket=Basket.EVENT_MEETING,
                title=cleaned,
                date=parsed["date"],
                time=parsed["time"],
                duration_minutes=config.duration_meeting_call,
                is_all_day=False,
                confidence=0.9,
                reasoning="Meeting/event keyword with specific time",
            )

        # Follow-up / task keywords → task
        task_kw = {"follow up", "follow-up", "remind", "remember", "submit",
                   "send", "finish", "complete", "review", "check"}
        if any(kw in cleaned.lower() for kw in task_kw):
            return CaptureItem(
                basket=Basket.TASK_REMINDER,
                title=cleaned,
                date=parsed["date"],
                time=parsed["time"],
                duration_minutes=config.duration_timed_task,
                is_all_day=False,
                confidence=0.85,
                reasoning="Task keyword with specific date/time",
            )

        # Default: event if timed
        return CaptureItem(
            basket=Basket.EVENT_MEETING,
            title=cleaned,
            date=parsed["date"],
            time=parsed["time"],
            duration_minutes=config.duration_event_appointment,
            is_all_day=False,
            confidence=0.7,
            reasoning="Timed item, defaulting to event",
        )

    # ── 3. Date only (no time) → could be task or event ──
    if has_date and not has_time:
        # Meeting keywords → event (all-day)
        event_kw = {"meeting", "call", "dentist", "doctor", "appointment",
                    "lunch", "dinner", "party", "conference"}
        if any(kw in cleaned.lower() for kw in event_kw):
            return CaptureItem(
                basket=Basket.EVENT_MEETING,
                title=cleaned,
                date=parsed["date"],
                time=None,
                duration_minutes=0,
                is_all_day=True,
                confidence=0.8,
                reasoning="Event keyword with date only, all-day",
            )

        # Task keywords → task
        task_kw = {"follow up", "remind", "remember", "submit", "send",
                   "finish", "complete", "task", "todo", "deadline"}
        if any(kw in cleaned.lower() for kw in task_kw):
            return CaptureItem(
                basket=Basket.TASK_REMINDER,
                title=cleaned,
                date=parsed["date"],
                time=None,
                duration_minutes=0,
                is_all_day=True,
                confidence=0.85,
                reasoning="Task keyword with date, all-day task",
            )

        # Default date-only → task (all-day reminder)
        return CaptureItem(
            basket=Basket.TASK_REMINDER,
            title=cleaned,
            date=parsed["date"],
            time=None,
            duration_minutes=0,
            is_all_day=True,
            confidence=0.65,
            reasoning="Date-only item, defaulting to all-day task",
        )

    # ── 4. No date → idea/note or undated task ──
    idea_kw = {"idea", "note", "think", "maybe", "someday", "consider",
               "reflect", "journal", "learn", "explore", "research"}
    if any(kw in cleaned.lower() for kw in idea_kw):
        return CaptureItem(
            basket=Basket.IDEA_NOTE,
            title=cleaned,
            confidence=0.9,
            reasoning="Idea/note keyword detected",
        )

    task_kw = {"follow up", "remind", "remember", "task", "todo"}
    if any(kw in cleaned.lower() for kw in task_kw):
        return CaptureItem(
            basket=Basket.TASK_REMINDER,
            title=cleaned,
            confidence=0.7,
            reasoning="Task keyword, no date specified",
        )

    # Default: idea/note (safest basket for ambiguous input)
    return CaptureItem(
        basket=Basket.IDEA_NOTE,
        title=cleaned,
        confidence=0.5,
        reasoning="No clear signal, defaulting to idea/note",
    )


def _default_duration(basket: Basket, title: str, config: RouterConfig) -> int:
    """Get default duration for a basket and title."""
    if basket == Basket.EVENT_MEETING:
        large_kw = {"dinner", "party", "conference", "workshop"}
        if any(kw in title.lower() for kw in large_kw):
            return config.duration_large_event
        return config.duration_event_appointment
    elif basket == Basket.TASK_REMINDER:
        return config.duration_timed_task
    return 0


def classify(text: str, config: Optional[RouterConfig] = None) -> CaptureResult:
    """Classify a single natural-language input into capture items.

    Delegates to captureos.classifier.classify() which has the canonical
    classification logic including proper duration handling for large events.
    """
    from captureos.classifier import classify as _classifier_classify

    if config is None:
        config = _load_config()

    return _classifier_classify(text, config)


def _format_output(result: CaptureResult, json_mode: bool = False) -> str:
    """Format classification result for display."""
    if json_mode:
        return result.to_json()

    lines = ["", "═" * 50]
    for item in result.items:
        icon = {"Task / Reminder": "☐", "Event / Meeting": "📅", "Idea / Note": "💡"}[item.basket_label]
        timing = ""
        if item.date:
            timing = f" {item.date}"
            if item.time:
                timing += f" {item.time} ({item.duration_minutes}min)"
            elif item.is_all_day:
                timing += " (all-day)"

        lines.append(f"  {icon}  [{item.basket_label}] {item.title}{timing}")
        lines.append(f"      confidence: {item.confidence:.0%} | {item.reasoning}")
        lines.append("")

    lines.append("═" * 50)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        prog="captureos",
        description="Three-basket universal capture router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  captureos "Dentist tomorrow 3pm"
  captureos --multi "Call Alex Friday. Idea: build a dashboard."
  captureos --capture       # Enter capture mode
  captureos --normal        # Exit capture mode
  captureos --status        # Show current mode
  captureos --json "Meeting with Sarah Monday 10am"
  captureos --inbox tasks   # Read tasks inbox
  captureos --write "Idea: build a weekly report" --vault ~/Documents/Vault
  captureos "Dentist tomorrow 3pm" --gcal              # Write to Google Calendar
  captureos --telegram                                 # Start Telegram bot
        """,
    )

    parser.add_argument(
        "text", nargs="*",
        help="Natural-language text to classify and capture"
    )
    parser.add_argument(
        "--multi", "-m", action="store_true",
        help="Treat input as potentially containing multiple items"
    )
    parser.add_argument(
        "--json", "-j", action="store_true",
        help="Output in JSON format"
    )
    parser.add_argument(
        "--capture", action="store_true",
        help="Enter capture mode (persistent)"
    )
    parser.add_argument(
        "--normal", action="store_true",
        help="Exit capture mode"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show current capture mode state"
    )
    parser.add_argument(
        "--config", "-c", type=str,
        help="Path to config YAML file"
    )
    parser.add_argument(
        "--vault", "-v", type=str,
        help="Path to markdown vault for writing inbox files"
    )
    parser.add_argument(
        "--write", "-w", action="store_true",
        help="Write classified items to markdown inbox files"
    )
    parser.add_argument(
        "--inbox", type=str, choices=["tasks", "events", "ideas"],
        help="Read items from a specific inbox"
    )
    parser.add_argument(
        "--version", action="store_true",
        help="Show version"
    )
    # Google Calendar
    parser.add_argument(
        "--gcal", action="store_true",
        help="Write classified events to Google Calendar (requires auth)"
    )
    parser.add_argument(
        "--calendar-id", type=str,
        help="Google Calendar ID (default: primary)"
    )
    parser.add_argument(
        "--check-conflicts", action="store_true",
        help="Check for calendar conflicts before creating events"
    )
    # Telegram
    parser.add_argument(
        "--telegram", action="store_true",
        help="Start Telegram bot (requires TELEGRAM_BOT_TOKEN env var)"
    )
    parser.add_argument(
        "--tg-token", type=str,
        help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)"
    )

    args = parser.parse_args()

    # Telegram mode
    if args.telegram:
        try:
            from captureos.telegram_bot import run_telegram_bot
            token = args.tg_token or None
            run_telegram_bot(token)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("Install: pip install captureos[telegram]", file=sys.stderr)
            sys.exit(1)
        return

    # Version
    if args.version:
        from captureos import __version__
        print(f"CaptureOS v{__version__}")
        return

    # Mode commands
    if args.capture:
        set_capture_mode(True)
        print("✓ Capture mode ENABLED (persistent)")
        return

    if args.normal:
        set_capture_mode(False)
        print("✓ Capture mode DISABLED — normal assistant mode")
        return

    if args.status:
        state = get_state()
        mode = "CAPTURE" if state.get("capture_mode") else "NORMAL"
        print(f"CaptureOS state: {mode}")
        if state.get("metadata"):
            print(f"Metadata: {json.dumps(state['metadata'], indent=2)}")
        return

    # Inbox reading
    if args.inbox:
        config = _load_config(args.config)
        if args.vault:
            config.vault_path = args.vault
        basket_map = {
            "tasks": Basket.TASK_REMINDER,
            "events": Basket.EVENT_MEETING,
            "ideas": Basket.IDEA_NOTE,
        }
        basket = basket_map[args.inbox]
        filepath = _inbox_path(basket, config)
        items = read_inbox(filepath)
        if items:
            print(f"\n{basket.name.replace('_', ' ').title()} Inbox ({len(items)} items):\n")
            for item in items:
                print(f"  {item}")
        else:
            print(f"No items in {basket.name} inbox yet.")
        return

    # Classification
    text = " ".join(args.text) if args.text else ""
    if not text:
        # Read from stdin if no text provided and not a command
        if sys.stdin.isatty():
            parser.print_help()
            return
        text = sys.stdin.read().strip()

    if not text:
        print("Error: No text provided for classification.", file=sys.stderr)
        sys.exit(1)

    config = _load_config(args.config)
    result = classify(text, config)

    # Output
    print(_format_output(result, args.json))

    # Optional: write to Google Calendar
    if args.gcal:
        try:
            from captureos.gcal_writer import GCalWriter
            writer = GCalWriter(calendar_id=args.calendar_id or None)

            for item in result.items:
                if item.basket != Basket.IDEA_NOTE and item.date:
                    # Check conflicts if requested
                    if args.check_conflicts and item.time:
                        conflicts = writer.check_conflicts(
                            item.date, item.time, item.duration_minutes
                        )
                        if conflicts:
                            print(f"  ⚠ Conflicts for '{item.title}':")
                            for c in conflicts:
                                print(f"    - {c['summary']} ({c['start'].get('dateTime', c['start'].get('date'))})")
                            continue  # skip conflicting events

                    event_result = writer.write_event(item)
                    if event_result.get("created"):
                        print(f"  ✓ Calendar: {item.title} → {event_result.get('html_link', '')}")
                    elif event_result.get("skipped"):
                        print(f"  ⊘ {event_result['reason']}: {item.title}")
                    else:
                        print(f"  ✗ Failed: {event_result.get('error', 'unknown')}")
        except ImportError as e:
            print(f"Error: Google Calendar support requires additional packages: {e}", file=sys.stderr)
            print("Install: pip install google-auth google-auth-oauthlib google-api-python-client", file=sys.stderr)
        except Exception as e:
            print(f"Google Calendar error: {e}", file=sys.stderr)

    # Optional: write to inbox
    if args.write:
        vault_path = args.vault or config.vault_path
        if not vault_path:
            print("Warning: No vault path configured. Use --vault or set in config.", file=sys.stderr)
            return

        config.vault_path = vault_path
        for item in result.items:
            filepath = _inbox_path(item.basket, config)
            write_to_inbox(item, filepath)
            print(f"  ✓ Written to {os.path.basename(filepath)}")


def _inbox_path(basket: Basket, config: RouterConfig) -> str:
    """Build the markdown inbox file path for a basket."""
    if not config.vault_path:
        return f"{config.wiki_dir}/{config.basket_files.get(basket, 'capture-inbox.md')}"
    return f"{config.vault_path}/{config.wiki_dir}/{config.basket_files.get(basket, 'capture-inbox.md')}"


if __name__ == "__main__":
    main()
