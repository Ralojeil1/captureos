"""CaptureOS Telegram Bot — polling-based capture receiver.

Receives natural-language messages via Telegram, classifies them
through CaptureOS, and responds with the routing result.

Setup:
    export TELEGRAM_BOT_TOKEN="your_bot_token"
    export CAPTUREOS_VAULT="~/Documents/CaptureVault"  # optional
    captureos-telegram

Usage:
    In Telegram, send a message to your bot:
        "Dentist tomorrow 3pm"
    Bot replies:
        📅 [Event / Meeting] Dentist — tomorrow 15:00 (60min)

    Send multiple items:
        "Call Alex Friday 10am. Idea: build a dashboard."
    Bot splits and classifies each.

Commands in Telegram:
    /capture   — enter capture mode (all messages treated as captures)
    /normal    — exit capture mode
    /status    — show current mode
    /inbox     — show recent captures
    /help      — show usage
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from datetime import date, datetime
from typing import Optional

from captureos.classifier import classify, Basket, CaptureItem, CaptureResult
from captureos.router import RouterConfig
from captureos.state import is_capture_mode, set_capture_mode, get_state
from captureos.writer import write_to_inbox, read_inbox


# ── Configuration ────────────────────────────────────────────────────

def _load_bot_config() -> RouterConfig:
    """Load router config, optionally from CAPTUREOS_CONFIG env var."""
    config_path = os.environ.get("CAPTUREOS_CONFIG", "")
    config = RouterConfig()

    if config_path and os.path.exists(os.path.expanduser(config_path)):
        try:
            import yaml
            with open(os.path.expanduser(config_path)) as f:
                data = yaml.safe_load(f) or {}
            if "vault" in data:
                config.vault_path = data["vault"].get("path")
                config.wiki_dir = data["vault"].get("wiki_dir", "wiki")
            if "timezone" in data:
                config.timezone = data["timezone"]
            if "calendar" in data:
                config.calendar_enabled = data["calendar"].get("enabled", False)
                config.calendar_provider = data["calendar"].get("provider", "none")
        except Exception:
            pass

    # Override with env vars
    if os.environ.get("CAPTUREOS_VAULT"):
        config.vault_path = os.environ["CAPTUREOS_VAULT"]

    return config


def _format_response(result: CaptureResult, compact: bool = True) -> str:
    """Format classification results for Telegram reply."""
    if not result.items:
        return "Could not classify that input."

    lines = []
    for item in result.items:
        icon = {"Task / Reminder": "☐", "Event / Meeting": "📅", "Idea / Note": "💡"}[
            item.basket_label
        ]
        timing = ""
        if item.date:
            timing = f" — {item.date}"
            if item.time:
                timing += f" {item.time}"
                if item.duration_minutes and not compact:
                    timing += f" ({item.duration_minutes}min)"
            elif item.is_all_day:
                timing += " (all-day)"

        if compact:
            lines.append(f"{icon} {item.title}{timing}")
        else:
            lines.append(f"{icon}  [{item.basket_label}] {item.title}{timing}")
            lines.append(f"      confidence: {item.confidence:.0%}")

    return "\n".join(lines)


# ── Telegram Bot ─────────────────────────────────────────────────────

# Lazy import to avoid hard dependency when not using Telegram
TELEGRAM_AVAILABLE = False
try:
    import aiohttp
    TELEGRAM_AVAILABLE = True
except ImportError:
    pass


class TelegramCaptureBot:
    """Polling-based Telegram bot for CaptureOS.

    Uses long-polling (getUpdates) — no webhook server needed.
    Works with existing Hermes Telegram bot or standalone.
    """

    API_BASE = "https://api.telegram.org"

    def __init__(self, token: Optional[str] = None):
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "aiohttp is required for Telegram support. "
                "Install with: pip install aiohttp"
            )

        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not self.token:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN environment variable not set. "
                "Get a token from @BotFather on Telegram."
            )

        self.config = _load_bot_config()
        self._session: Optional[aiohttp.ClientSession] = None
        self._offset: int = 0
        self._running: bool = False

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _api_call(self, method: str, params: dict = None) -> dict:
        """Make a Telegram Bot API call."""
        session = await self._get_session()
        url = f"{self.API_BASE}/bot{self.token}/{method}"
        async with session.post(url, json=params or {}) as resp:
            data = await resp.json()
            if not data.get("ok"):
                print(f"Telegram API error: {data}", file=sys.stderr)
            return data

    async def send_message(self, chat_id: int, text: str) -> dict:
        """Send a message to a Telegram chat."""
        return await self._api_call("sendMessage", {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        })

    async def _process_message(self, msg: dict) -> Optional[str]:
        """Process a single Telegram message and return the response text."""
        text = msg.get("text", "").strip()
        if not text:
            return None

        chat_id = msg.get("chat", {}).get("id", 0)

        # ── Commands ──
        if text.startswith("/"):
            return await self._handle_command(text, chat_id)

        # ── Capture mode or explicit prefix ──
        in_capture = is_capture_mode()

        # Check explicit prefixes always work
        explicit_prefixes = ("task:", "reminder:", "meeting:", "event:",
                            "idea:", "note:", "call:", "capture:", "process this:")
        is_explicit = any(text.lower().startswith(p) for p in explicit_prefixes)

        if in_capture or is_explicit:
            result = classify(text, self.config)
            return _format_response(result)
        else:
            # In normal mode, only respond to captures if explicit
            return None

    async def _handle_command(self, text: str, chat_id: int) -> str:
        """Handle a Telegram bot command."""
        cmd = text.lower().split()[0].rstrip("@")

        if cmd == "/capture":
            set_capture_mode(True)
            return "✓ Capture mode ON — all messages will be classified."

        elif cmd == "/normal":
            set_capture_mode(False)
            return "✓ Capture mode OFF — back to normal."

        elif cmd == "/status":
            state = get_state()
            mode = "CAPTURE" if state.get("capture_mode") else "NORMAL"
            return f"CaptureOS: {mode}"

        elif cmd == "/inbox":
            return self._format_inbox()

        elif cmd == "/help":
            return (
                "CaptureOS — three-basket capture router\n\n"
                "Send me anything and I'll classify it:\n"
                "  📅 Event / Meeting — calls, appointments, calendar\n"
                "  ☐ Task / Reminder — todos, follow-ups, deadlines\n"
                "  💡 Idea / Note — ideas, notes, reflections\n\n"
                "Commands:\n"
                "  /capture — enter capture mode\n"
                "  /normal — exit capture mode\n"
                "  /status — show current mode\n"
                "  /inbox — recent captures\n\n"
                "Try:\n"
                "  Dentist tomorrow 3pm\n"
                "  Follow up with Sarah Friday 11am\n"
                "  Idea: build a weekly report generator"
            )

        elif cmd == "/start":
            return (
                "CaptureOS bot ready. Send me tasks, events, or ideas.\n\n"
                "Type /capture to classify all messages, or use prefixes:\n"
                "  Task: ...  Meeting: ...  Idea: ...\n"
                "Type /help for more."
            )

        # Unknown command — treat as capture if in capture mode
        if is_capture_mode():
            result = classify(text, self.config)
            return _format_response(result)

        return None

    def _format_inbox(self) -> str:
        """Format recent inbox items for display."""
        from captureos.classifier import Basket

        if not self.config.vault_path:
            return "No vault configured. Set CAPTUREOS_VAULT env var."

        baskets = {
            "Tasks": Basket.TASK_REMINDER,
            "Events": Basket.EVENT_MEETING,
            "Ideas": Basket.IDEA_NOTE,
        }

        lines = []
        for label, basket in baskets.items():
            filepath = f"{self.config.vault_path}/{self.config.wiki_dir}/capture-{label.lower()}-{'reminders' if label == 'Tasks' else 'meetings' if label == 'Events' else 'notes'}.md"
            try:
                items = read_inbox(filepath)
                if items:
                    recent = items[-5:]  # last 5
                    lines.append(f"<b>{label}</b> ({len(items)}):")
                    for item in recent:
                        lines.append(f"  {item}")
            except Exception:
                pass

        return "\n".join(lines) if lines else "No captures yet."

    async def _poll_updates(self):
        """Long-poll for updates from Telegram."""
        while self._running:
            try:
                params = {"timeout": 30, "offset": self._offset}
                if self._offset:
                    params["offset"] = self._offset

                data = await self._api_call("getUpdates", params)

                if data.get("ok") and data.get("result"):
                    for update in data["result"]:
                        self._offset = update["update_id"] + 1

                        msg = update.get("message") or update.get("channel_post")
                        if not msg:
                            continue

                        chat_id = msg.get("chat", {}).get("id", 0)
                        text = msg.get("text", "").strip()
                        if not text:
                            continue

                        response = await self._process_message(msg)
                        if response:
                            await self.send_message(chat_id, response)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Polling error: {e}", file=sys.stderr)
                await asyncio.sleep(5)

    async def start(self):
        """Start the Telegram bot (polling loop)."""
        self._running = True
        print(f"CaptureOS Telegram bot starting... (Ctrl+C to stop)")
        print(f"Mode: {'CAPTURE' if is_capture_mode() else 'NORMAL'}")

        try:
            await self._poll_updates()
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()

    async def stop(self):
        """Stop the bot and clean up."""
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
        print("CaptureOS Telegram bot stopped.")


def run_telegram_bot(token: Optional[str] = None):
    """Synchronous entry point for the Telegram bot."""
    if not TELEGRAM_AVAILABLE:
        print("aiohttp is required. Install with: pip install aiohttp", file=sys.stderr)
        sys.exit(1)

    bot = TelegramCaptureBot(token)

    # Handle graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def shutdown():
        print("\nShutting down...")
        loop.create_task(bot.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(bot.start())
    finally:
        loop.close()


# ── CLI entry point ──────────────────────────────────────────────────

def main():
    """Entry point for captureos-telegram command."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CaptureOS Telegram Bot",
    )
    parser.add_argument(
        "--token", "-t",
        help="Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)",
    )
    parser.add_argument(
        "--vault", "-v",
        help="Markdown vault path for inbox files",
    )
    args = parser.parse_args()

    if args.token:
        os.environ["TELEGRAM_BOT_TOKEN"] = args.token
    if args.vault:
        os.environ["CAPTUREOS_VAULT"] = args.vault

    run_telegram_bot()


if __name__ == "__main__":
    main()
