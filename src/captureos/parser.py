"""CaptureOS multi-item natural-language parser.

Splits messy natural-language input into individual capture items,
detects explicit prefixes, and extracts date/time signals.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

# ── Prefix detection ─────────────────────────────────────────────────

EXPLICIT_PREFIXES = {
    "task": "task_reminder",
    "reminder": "task_reminder",
    "todo": "task_reminder",
    "follow up": "task_reminder",
    "followup": "task_reminder",
    "follow-up": "task_reminder",
    "meeting": "event_meeting",
    "event": "event_meeting",
    "call": "event_meeting",
    "appointment": "event_meeting",
    "dentist": "event_meeting",
    "doctor": "event_meeting",
    "idea": "idea_note",
    "note": "idea_note",
    "capture": None,  # generic capture — needs classification
    "process this": None,
}

# ── Date/time patterns ───────────────────────────────────────────────

DAY_NAMES = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3,
    "thurs": 3, "fri": 4, "sat": 5, "sun": 6,
}

MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10,
    "nov": 11, "dec": 12,
}

# Time pattern: "3pm", "15:00", "3:00pm", "3 pm", "3 p.m."
TIME_RE = re.compile(
    r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?',
    re.IGNORECASE
)

# Informal time words: "noon", "midnight"
INFORMAL_TIMES = {
    "noon": (12, 0),
    "midnight": (0, 0),
}

# Date patterns: ISO, slash, named
DATE_RE_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
DATE_RE_SLASH = re.compile(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?')
DATE_RE_NAMED = re.compile(
    r'(' + '|'.join(MONTH_NAMES.keys()) + r')\s+(\d{1,2})(?!\d)(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?',
    re.IGNORECASE
)
DATE_RE_NAMED_DAY_FIRST = re.compile(
    r'(\d{1,2})(?!\d)(?:st|nd|rd|th)?\s+(' + '|'.join(MONTH_NAMES.keys()) + r')(?:\s*,?\s*(\d{4}))?',
    re.IGNORECASE
)

# Relative date offsets: "in 2 days", "in 3 weeks"
OFFSET_RE = re.compile(r'\bin\s+(\d+)\s+(day|days|week|weeks|month|months)\b', re.IGNORECASE)

# Relative dates
TODAY_WORDS = {"today", "tod"}
TOMORROW_WORDS = {"tomorrow", "tmrw", "tmw"}

# ── Item splitting ───────────────────────────────────────────────────

# Split on common separators: ". ", " and ", "; ", newlines, numbered lists
ITEM_SEPARATOR_RE = re.compile(
    r'(?<=[?!])\s+(?=[A-Z0-9])|'          # sentence boundary after ? or !
    r'(?<=[^.0-9]\.)\s+(?=[A-Z0-9])|'     # sentence boundary after period (not after digit like "1.")
    r'\s+and\s+(?=[A-Za-z0-9])|'           # "and" joining sentences (any case)
    r';\s*|'                                # semicolons
    r'\n\s*(?:\d+[.)]\s*)?|'               # newlines with optional numbering
    r'\s*\.\s{2,}'                          # double space after period
)


def split_items(text: str) -> list[str]:
    """Split a multi-item input string into individual capture items."""
    if not text or not text.strip():
        return []

    text = text.strip()

    # Check for "Process this:" prefix — special handling
    process_match = re.match(r'^process\s+this\s*[:;]\s*(.+)', text, re.IGNORECASE)
    if process_match:
        text = process_match.group(1)

    # Try splitting
    parts = ITEM_SEPARATOR_RE.split(text)
    parts = [p.strip() for p in parts if p.strip()]

    # If splitting produced nothing useful, return the original as one item
    if not parts:
        return [text]

    # Merge very short fragments with neighbors
    merged = []
    for p in parts:
        if len(p.split()) <= 2 and merged:
            merged[-1] = merged[-1] + " " + p
        else:
            merged.append(p)

    return merged if merged else [text]


def detect_explicit_prefix(text: str) -> Optional[str]:
    """Detect explicit basket prefix like 'Task:', 'Meeting:', 'Idea:'."""
    text_lower = text.lower().strip()
    for prefix, basket in EXPLICIT_PREFIXES.items():
        if basket is None:
            continue
        # Match "Prefix:" or "Prefix -" at start
        pattern = rf'^{re.escape(prefix)}\s*[:;\-—]\s*(.+)'
        match = re.match(pattern, text_lower)
        if match:
            return basket
    return None


def strip_prefix(text: str) -> str:
    """Remove explicit prefix like 'Task:' from text, returning clean text."""
    for prefix in EXPLICIT_PREFIXES:
        pattern = rf'^{re.escape(prefix)}\s*[:;\-—]\s*(.+)'
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return text


def extract_date_time(text: str, reference_date: Optional[date] = None) -> dict:
    """Extract date and time from natural language text.

    Returns dict with keys: date (YYYY-MM-DD or None), time (HH:MM or None),
    is_all_day (bool), has_time (bool), has_date (bool).
    """
    if reference_date is None:
        reference_date = date.today()

    result = {
        "date": None,
        "time": None,
        "is_all_day": False,
        "has_time": False,
        "has_date": False,
    }

    text_lower = text.lower().strip()
    if not text_lower:
        return result

    # ── ISO date: 2026-04-28 ──
    iso_match = DATE_RE_ISO.search(text)
    if iso_match:
        y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
        try:
            result["date"] = date(y, m, d).isoformat()
            result["has_date"] = True
        except ValueError:
            pass

    # ── Slash date: "3/15", "3/15/2026" ──
    if not result["date"]:
        slash_match = DATE_RE_SLASH.search(text)
        if slash_match:
            g1, g2 = int(slash_match.group(1)), int(slash_match.group(2))
            # Heuristic: if first number > 12, treat as DD/MM, else MM/DD
            if g1 > 12:
                day, month = g1, g2
            else:
                month, day = g1, g2
            year_str = slash_match.group(3)
            if year_str:
                year = int(year_str)
                if year < 100:  # two-digit year
                    year += 2000 if year < 50 else 1900
            else:
                year = reference_date.year
            try:
                if 1 <= month <= 12 and 1 <= day <= 31:
                    result["date"] = date(year, month, day).isoformat()
                    result["has_date"] = True
            except ValueError:
                pass

    # ── Named date: "April 28" or "28 April" ──
    if not result["date"]:
        for pattern in [DATE_RE_NAMED, DATE_RE_NAMED_DAY_FIRST]:
            named = pattern.search(text_lower)
            if named:
                if pattern == DATE_RE_NAMED:
                    month_name, day_str, year_str = named.group(1), named.group(2), named.group(3)
                else:
                    day_str, month_name, year_str = named.group(1), named.group(2), named.group(3)

                month_num = MONTH_NAMES.get(month_name.lower())
                if month_num:
                    day = int(day_str)
                    year = int(year_str) if year_str else reference_date.year
                    try:
                        result["date"] = date(year, month_num, day).isoformat()
                        result["has_date"] = True
                    except ValueError:
                        pass
                break

    # ── Day-of-week: "Monday", "next Monday" ──
    if not result["date"]:
        next_prefix = bool(re.search(r'\bnext\b', text_lower))
        for day_name, day_num in DAY_NAMES.items():
            if day_name in text_lower:
                today_num = reference_date.weekday()
                days_ahead = (day_num - today_num) % 7
                if days_ahead == 0 and not next_prefix:
                    days_ahead = 7  # "this Monday" when today is Monday → next week
                if next_prefix and days_ahead == 0:
                    days_ahead += 7  # "next Monday" when today is Monday → 7 days out
                target = reference_date + timedelta(days=days_ahead)
                result["date"] = target.isoformat()
                result["has_date"] = True
                break

    # ── Relative: today, tomorrow ──
    if not result["date"]:
        if any(w in text_lower for w in TODAY_WORDS):
            result["date"] = reference_date.isoformat()
            result["has_date"] = True
        elif any(w in text_lower for w in TOMORROW_WORDS):
            result["date"] = (reference_date + timedelta(days=1)).isoformat()
            result["has_date"] = True

    # ── Relative offset: "in 2 days", "in 3 weeks" ──
    if not result["date"]:
        offset_match = OFFSET_RE.search(text_lower)
        if offset_match:
            count = int(offset_match.group(1))
            unit = offset_match.group(2).lower()
            try:
                if unit in ("day", "days"):
                    target = reference_date + timedelta(days=count)
                elif unit in ("week", "weeks"):
                    target = reference_date + timedelta(weeks=count)
                elif unit in ("month", "months"):
                    # Approximate: add 30 days per month
                    target = reference_date + timedelta(days=count * 30)
                else:
                    target = None
                if target:
                    result["date"] = target.isoformat()
                    result["has_date"] = True
            except (ValueError, OverflowError):
                pass

    # ── Informal time: "noon", "midnight" ──
    if not result["time"]:
        for word, (h, m) in INFORMAL_TIMES.items():
            if word in text_lower:
                result["time"] = f"{h:02d}:{m:02d}"
                result["has_time"] = True
                break

    # ── Time: "3pm", "15:00", "at 3" ──
    if not result["time"]:
        time_match = TIME_RE.search(text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)

            if period and period.lower() in ("pm", "p.m.") and hour != 12:
                hour += 12
            elif period and period.lower() in ("am", "a.m.") and hour == 12:
                hour = 0

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                result["time"] = f"{hour:02d}:{minute:02d}"
                result["has_time"] = True

    # ── All-day determination ──
    result["is_all_day"] = result["has_date"] and not result["has_time"]

    return result


def parse_capture_items(
    text: str,
    reference_date: Optional[date] = None,
    timezone: str = "UTC"
) -> list[dict]:
    """Parse text into one or more capture items with preliminary classification.

    Returns list of dicts with: raw_text, cleaned_text, explicit_basket, date_info.
    This is the preprocessing step before classification.
    """
    items = split_items(text)
    parsed = []

    for item_text in items:
        explicit = detect_explicit_prefix(item_text)
        cleaned = strip_prefix(item_text)
        dt_info = extract_date_time(cleaned, reference_date)

        parsed.append({
            "raw_text": item_text.strip(),
            "cleaned_text": cleaned,
            "explicit_basket": explicit,
            "date": dt_info["date"],
            "time": dt_info["time"],
            "is_all_day": dt_info["is_all_day"],
            "has_date": dt_info["has_date"],
            "has_time": dt_info["has_time"],
        })

    return parsed
