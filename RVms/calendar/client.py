from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Sequence
from urllib.parse import quote

from .event import CalendarEvent

Json = Dict[str, Any]


def qs_encode(s: str) -> str:
    return quote(s, safe="")


def iso_utc(dt: datetime) -> str:
    """Ensure ISO8601 with Z/UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CalendarClient:
    """
    Transport + factories only (same pattern as MailClient).

    Public surface area:
      - list_events(...)
      - get_event(...)
      - get_next_appointment(...)

    Public transport helpers:
      - user_url(user, path)
      - request(method, url, **kwargs)
    """

    conn: Any
    default_timezone: str = "Europe/Amsterdam"

    def user_url(self, user: str, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.conn.graph_base}/users/{user}{path}"

    def request(self, method: str, url: str, **kwargs) -> Json:
        return self.conn.graph_request(method, url, **kwargs)

    # --------- events (calendarView is best for "what's next") ---------

    def list_events(
        self,
        user: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        top: int = 25,
        select: Sequence[str] = (
            "id",
            "subject",
            "start",
            "end",
            "location",
            "isAllDay",
            "isOnlineMeeting",
            "onlineMeeting",
            "webLink",
            "organizer",
            "attendees",
            "bodyPreview",
        ),
        orderby: str = "start/dateTime",
        filter: Optional[str] = None,
        next_link: Optional[str] = None,
        timezone_name: Optional[str] = None,
    ) -> tuple[list[CalendarEvent], Optional[str]]:
        """
        Returns events from /calendarView between [start, end].
        Handles recurring events correctly.
        """
        tz = timezone_name or self.default_timezone

        if next_link:
            url = next_link
            headers = {"Prefer": f'outlook.timezone="{tz}"'}
        else:
            # sensible defaults: from now to +7 days
            now = datetime.now(timezone.utc)
            start = start or now
            end = end or (now + timedelta(days=7))

            sel = ",".join(select)
            url = self.user_url(
                user,
                "/calendarView"
                f"?startDateTime={qs_encode(iso_utc(start))}"
                f"&endDateTime={qs_encode(iso_utc(end))}"
                f"&$top={top}"
                f"&$select={qs_encode(sel)}"
                f"&$orderby={qs_encode(orderby)}"
            )
            if filter:
                url += f"&$filter={qs_encode(filter)}"

            headers = {"Prefer": f'outlook.timezone="{tz}"'}

        page: Json = self.request("GET", url, headers=headers)
        events = [CalendarEvent(self, user, e) for e in page.get("value", [])]
        return events, page.get("@odata.nextLink")

    def get_event(
        self,
        user: str,
        event_id: str,
        *,
        select: Sequence[str] = (
            "id",
            "subject",
            "start",
            "end",
            "location",
            "isAllDay",
            "isOnlineMeeting",
            "onlineMeeting",
            "webLink",
            "organizer",
            "attendees",
            "bodyPreview",
            "body",
        ),
        timezone_name: Optional[str] = None,
    ) -> CalendarEvent:
        tz = timezone_name or self.default_timezone
        sel = ",".join(select)
        url = self.user_url(user, f"/events/{event_id}?$select={qs_encode(sel)}")
        raw: Json = self.request("GET", url, headers={"Prefer": f'outlook.timezone="{tz}"'})
        return CalendarEvent(self, user, raw)

    def get_next_appointment(
        self,
        user: str,
        *,
        within_days: int = 7,
        now: Optional[datetime] = None,
        timezone_name: Optional[str] = None,
    ) -> Optional[CalendarEvent]:
        """
        Returns the next upcoming event in the next N days, else None.
        """
        now = now or datetime.now(timezone.utc)
        end = now + timedelta(days=within_days)

        events, _ = self.list_events(
            user,
            start=now,
            end=end,
            top=1,
            orderby="start/dateTime",
            timezone_name=timezone_name,
        )
        return events[0] if events else None
