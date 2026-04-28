"""CaptureOS Google Calendar Integration — create events from captures.

Writes classified Event/Meeting and Task/Reminder items to Google Calendar
using the Google Calendar API v3.

Authentication:
    1. Google Cloud OAuth (user-facing app):
       Set up a Desktop OAuth client, download client_secret.json
       Set GOOGLE_CLIENT_SECRET_PATH env var to the file path
       On first run, opens a browser for OAuth consent

    2. Service Account (server-to-server):
       Set GOOGLE_SERVICE_ACCOUNT_PATH env var to the JSON key file
       Set GOOGLE_CALENDAR_ID env var to the target calendar ID

    3. Application Default Credentials (ADC):
       gcloud auth application-default login
       The module uses the credentials automatically

Usage:
    from captureos.gcal_writer import GCalWriter
    from captureos.classifier import classify

    result = classify("Dentist tomorrow 3pm")
    writer = GCalWriter()
    for item in result.items:
        writer.write_event(item)

CLI:
    captureos "Dentist tomorrow 3pm" --gcal
"""

from __future__ import annotations

import os
import pickle
import sys
from datetime import datetime, timedelta, date as date_type
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from captureos.classifier import Basket, CaptureItem, CaptureResult

# Google Calendar API scope
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Token storage
TOKEN_DIR = os.path.expanduser("~/.captureos")
TOKEN_PATH = os.path.join(TOKEN_DIR, "gcal_token.pickle")


def _get_calendar_id() -> str:
    """Get the target calendar ID from env or default to 'primary'."""
    return os.environ.get("GOOGLE_CALENDAR_ID", "primary")


def _get_credentials() -> Credentials:
    """Get Google Calendar credentials using multiple auth strategies.

    Priority (no scary warnings):
    1. User's own OAuth token   (~/.captureos/gcal_token.pickle)
    2. Service account           (GOOGLE_SERVICE_ACCOUNT_PATH)
    3. Custom OAuth client       (GOOGLE_CLIENT_SECRET_PATH)
    4. gcloud ADC               (fallback, may show 'unverified app' warning)
    """
    # ── Strategy 0: Existing saved OAuth token (from gcal-setup wizard) ──
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, "rb") as token:
                creds = pickle.load(token)
            if creds and creds.valid:
                return creds
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                with open(TOKEN_PATH, "wb") as token:
                    pickle.dump(creds, token)
                return creds
        except Exception:
            pass  # fall through to other methods

    # ── Strategy 1: Service Account ──
    sa_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "")
    if sa_path and os.path.exists(os.path.expanduser(sa_path)):
        return service_account.Credentials.from_service_account_file(
            os.path.expanduser(sa_path),
            scopes=SCOPES,
        )

    # ── Strategy 2: Application Default Credentials ──
    try:
        import google.auth
        # First try with scopes
        creds, project = google.auth.default(scopes=SCOPES)
        if creds:
            # ADC may need refresh
            if not creds.valid:
                try:
                    from google.auth.transport.requests import Request as ADCRequest
                    creds.refresh(ADCRequest())
                except Exception:
                    pass
            if creds.valid or (hasattr(creds, 'token') and creds.token):
                return creds
        # If scoped creds failed, try without scopes (whatever ADC has)
        if not creds or (not creds.valid and not (hasattr(creds, 'token') and creds.token)):
            creds, project = google.auth.default()
            if creds and (creds.valid or (hasattr(creds, 'token') and creds.token)):
                print(
                    "Warning: ADC credentials may lack Calendar scope.\n"
                    "Run: gcloud auth application-default login \\\n"
                    "  --scopes=https://www.googleapis.com/auth/calendar.events",
                    file=sys.stderr,
                )
                return creds
    except Exception:
        pass

    # ── Strategy 3: OAuth client (user-facing) ──
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_secret_path = os.environ.get(
                "GOOGLE_CLIENT_SECRET_PATH",
                os.path.expanduser("~/.captureos/client_secret.json"),
            )

            if not os.path.exists(client_secret_path):
                raise FileNotFoundError(
                    "No Google credentials found.\n\n"
                    "Run the setup wizard:\n"
                    "  captureos-gcal-setup\n\n"
                    "Or set up manually:\n"
                    "  1. Service account: GOOGLE_SERVICE_ACCOUNT_PATH=/path/to/key.json\n"
                    "  2. OAuth client:    GOOGLE_CLIENT_SECRET_PATH=/path/to/client_secret.json\n"
                    "  3. gcloud ADC:      gcloud auth application-default login \\\n"
                    "       --scopes=https://www.googleapis.com/auth/calendar.events\n"
                    f"Put client_secret.json at: {client_secret_path}"
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save token
        os.makedirs(TOKEN_DIR, exist_ok=True)
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)

    return creds


class GCalWriter:
    """Writes classified capture items to Google Calendar."""

    def __init__(
        self,
        calendar_id: Optional[str] = None,
        credentials: Optional[Credentials] = None,
    ):
        """
        Args:
            calendar_id: Google Calendar ID (default: "primary" or GOOGLE_CALENDAR_ID env)
            credentials: Pre-authenticated Google credentials
        """
        self.calendar_id = calendar_id or _get_calendar_id()

        if credentials:
            self._creds = credentials
        else:
            try:
                self._creds = _get_credentials()
            except Exception as e:
                raise RuntimeError(
                    f"Google Calendar auth failed: {e}\n"
                    "Run: gcloud auth application-default login"
                )

        self._service = None

    @property
    def service(self):
        """Lazy-init the Calendar API service."""
        if self._service is None:
            try:
                self._service = build("calendar", "v3", credentials=self._creds)
            except Exception:
                # Fallback: direct REST access if discovery doc fails
                self._service = _DirectCalendarAPI(self._creds)
        return self._service

    def write_event(self, item: CaptureItem) -> dict:
        """Create a Google Calendar event from a capture item.

        Only creates events for Event/Meeting and Task/Reminder baskets.

        Args:
            item: Classified capture item

        Returns:
            dict with event data including the Google event ID
        """
        if item.basket == Basket.IDEA_NOTE:
            return {"skipped": True, "reason": "Idea/Note items are not calendared"}

        if not item.date:
            return {"skipped": True, "reason": "No date — cannot create calendar event"}

        # Build event body
        event_body = self._build_event(item)

        try:
            event = (
                self.service.events()
                .insert(calendarId=self.calendar_id, body=event_body)
                .execute()
            )
            return {
                "created": True,
                "event_id": event.get("id"),
                "html_link": event.get("htmlLink"),
                "summary": event.get("summary"),
                "start": event.get("start"),
                "end": event.get("end"),
            }
        except HttpError as e:
            return {"created": False, "error": str(e)}

    def _build_event(self, item: CaptureItem) -> dict:
        """Build a Google Calendar event body from a capture item."""
        from captureos.conflict import _time_to_minutes, _minutes_to_time

        summary = item.title
        description = (
            f"Captured by CaptureOS\n"
            f"Basket: {item.basket_label}\n"
            f"Confidence: {item.confidence:.0%}\n"
            f"Reasoning: {item.reasoning}"
        )

        event = {
            "summary": summary,
            "description": description,
        }

        if item.is_all_day or not item.time:
            # All-day event
            event["start"] = {"date": item.date}
            # End date is the next day for all-day events
            end_date = date_type.fromisoformat(item.date) + timedelta(days=1)
            event["end"] = {"date": end_date.isoformat()}
        else:
            # Timed event
            start_dt = f"{item.date}T{item.time}:00"
            duration = item.duration_minutes or 60
            start_minutes = _time_to_minutes(item.time)
            end_minutes = start_minutes + duration
            end_time = _minutes_to_time(end_minutes)
            end_dt = f"{item.date}T{end_time}:00"

            event["start"] = {
                "dateTime": start_dt,
                "timeZone": os.environ.get("CAPTUREOS_TIMEZONE", "UTC"),
            }
            event["end"] = {
                "dateTime": end_dt,
                "timeZone": os.environ.get("CAPTUREOS_TIMEZONE", "UTC"),
            }

            # Add reminders
            event["reminders"] = {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 1440},  # 24 hours
                    {"method": "popup", "minutes": 60},    # 1 hour
                ],
            }

        return event

    def check_conflicts(
        self, date_str: str, time_str: str, duration_minutes: int
    ) -> list[dict]:
        """Check for conflicting events on Google Calendar.

        Args:
            date_str: Date in YYYY-MM-DD format
            time_str: Time in HH:MM format
            duration_minutes: Duration of proposed event

        Returns:
            List of conflicting event summaries
        """
        if not date_str or not time_str:
            return []

        # Calculate time range
        from captureos.conflict import _time_to_minutes, _minutes_to_time
        start_minutes = _time_to_minutes(time_str)
        end_minutes = start_minutes + duration_minutes
        end_time = _minutes_to_time(end_minutes)

        time_min = f"{date_str}T{time_str}:00Z"
        time_max = f"{date_str}T{end_time}:00Z"

        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            conflicts = []
            for event in events:
                # Skip cancelled events
                if event.get("status") == "cancelled":
                    continue
                conflicts.append({
                    "summary": event.get("summary", "Untitled"),
                    "start": event.get("start", {}),
                    "end": event.get("end", {}),
                    "id": event.get("id"),
                })

            return conflicts
        except HttpError as e:
            print(f"Conflict check error: {e}", file=sys.stderr)
            return []

    def write_batch(self, items: list[CaptureItem]) -> list[dict]:
        """Write multiple classified items to Google Calendar.

        Skips Idea/Note items and items without dates.
        """
        results = []
        for item in items:
            result = self.write_event(item)
            results.append(result)
        return results


def write_result_to_gcal(result: CaptureResult) -> list[dict]:
    """Convenience function: classify and write to Google Calendar.

    Args:
        result: CaptureResult from captureos.classify()

    Returns:
        List of results for each item
    """
    writer = GCalWriter()
    return writer.write_batch(result.items)


# ── CLI hook ─────────────────────────────────────────────────────────


class _DirectCalendarAPI:
    """Direct REST fallback for Google Calendar when discovery doc fails.

    Uses raw HTTP requests instead of the googleapiclient discovery mechanism.
    Works without the discovery document cache.
    """

    BASE = "https://www.googleapis.com/calendar/v3"

    def __init__(self, credentials):
        self._creds = credentials
        self._session = None

    def _get_session(self):
        import requests
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _headers(self):
        if not self._creds.valid:
            from google.auth.transport.requests import Request as R
            self._creds.refresh(R())
        return {"Authorization": f"Bearer {self._creds.token}"}

    def events(self):
        return _EventsResource(self)

    def calendarList(self):
        return _CalendarListResource(self)


class _EventsResource:
    def __init__(self, api):
        self._api = api

    def insert(self, calendarId, body):
        return _InsertRequest(self._api, calendarId, body)

    def list(self, calendarId, timeMin=None, timeMax=None,
             singleEvents=None, orderBy=None):
        return _ListRequest(self._api, calendarId, timeMin, timeMax,
                           singleEvents, orderBy)


class _CalendarListResource:
    def __init__(self, api):
        self._api = api

    def list(self, maxResults=None):
        return _ListCalendarsRequest(self._api, maxResults)


class _InsertRequest:
    def __init__(self, api, calendar_id, body):
        self._api = api
        self._calendar_id = calendar_id
        self._body = body

    def execute(self):
        import requests as req
        url = f"{self._api.BASE}/calendars/{self._calendar_id}/events"
        r = self._api._get_session().post(
            url, headers=self._api._headers(), json=self._body
        )
        if r.status_code not in (200, 201):
            raise HttpError(
                resp=type('obj', (object,), {'status': r.status_code, 'reason': r.text})(),
                content=r.content
            )
        return r.json()


class _ListRequest:
    def __init__(self, api, calendar_id, time_min, time_max, single_events, order_by):
        self._api = api
        self._calendar_id = calendar_id
        self._params = {}
        if time_min:
            self._params["timeMin"] = time_min
        if time_max:
            self._params["timeMax"] = time_max
        if single_events:
            self._params["singleEvents"] = "true"
        if order_by:
            self._params["orderBy"] = order_by

    def execute(self):
        url = f"{self._api.BASE}/calendars/{self._calendar_id}/events"
        r = self._api._get_session().get(
            url, headers=self._api._headers(), params=self._params
        )
        if r.status_code != 200:
            raise HttpError(
                resp=type('obj', (object,), {'status': r.status_code, 'reason': r.text})(),
                content=r.content
            )
        return r.json()


class _ListCalendarsRequest:
    def __init__(self, api, max_results):
        self._api = api
        self._params = {}
        if max_results:
            self._params["maxResults"] = max_results

    def execute(self):
        url = f"{self._api.BASE}/users/me/calendarList"
        r = self._api._get_session().get(
            url, headers=self._api._headers(), params=self._params
        )
        if r.status_code != 200:
            raise HttpError(
                resp=type('obj', (object,), {'status': r.status_code, 'reason': r.text})(),
                content=r.content
            )
        return r.json()

def add_gcal_args(parser):
    """Add Google Calendar arguments to an argparse parser."""
    parser.add_argument(
        "--gcal", action="store_true",
        help="Write events to Google Calendar (requires auth)"
    )
    parser.add_argument(
        "--calendar-id",
        help="Google Calendar ID (default: primary or GOOGLE_CALENDAR_ID env)"
    )
    parser.add_argument(
        "--check-conflicts", action="store_true",
        help="Check for conflicts before creating events"
    )
