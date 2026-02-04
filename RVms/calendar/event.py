from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .helpers import pretty_range_local

Json = Dict[str, Any]


@dataclass
class CalendarEvent:
    """
    Active Record-ish wrapper for a Graph event JSON.
    Keep it lightweight; add helpers for UI/serialization.
    """

    client: Any
    user: str
    raw: Json

    @property
    def id(self) -> str:
        return self.raw.get("id", "")

    @property
    def subject(self) -> str:
        return self.raw.get("subject") or "(No title)"

    @property
    def web_link(self) -> Optional[str]:
        return self.raw.get("webLink")

    @property
    def join_url(self) -> Optional[str]:
        # Present for Teams meetings etc.
        online = self.raw.get("onlineMeeting") or {}
        return online.get("joinUrl")

    @property
    def start(self) -> Optional[str]:
        # returns ISO-ish string as provided by Graph (already in preferred timezone)
        s = self.raw.get("start") or {}
        return s.get("dateTime")

    @property
    def end(self) -> Optional[str]:
        e = self.raw.get("end") or {}
        return e.get("dateTime")

    @property
    def location_name(self) -> str:
        loc = self.raw.get("location") or {}
        return loc.get("displayName") or ""

    def to_widget_dict(self) -> Json:
        start_iso = self.start
        end_iso = self.end

        return {
            "id": self.id,
            "title": self.subject,
            "start": start_iso,
            "end": end_iso,
            "range_pretty": pretty_range_local(start_iso, end_iso)
            if start_iso and end_iso else "",
            "location": self.location_name,
            "join_url": self.join_url,
            "web_link": self.web_link,
            "is_online": bool(self.join_url),
        }
