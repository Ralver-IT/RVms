from __future__ import annotations
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

Json = Dict[str, Any]


def _parse_graph_dt(s: Optional[str]) -> Optional[datetime]:
    """
    Parse Graph ISO8601-ish strings like:
      2026-02-04T10:00:00
      2026-02-04T10:00:00.0000000
      2026-02-04T10:00:00Z
      2026-02-04T10:00:00+01:00
    Returns aware datetime if possible, else naive.
    """
    if not s:
        return None

    # Graph sometimes sends 7 fractional digits; Python supports up to 6.
    if "." in s:
        head, tail = s.split(".", 1)
        frac = "".join(ch for ch in tail if ch.isdigit())
        tzpart = tail[len(frac):]  # keep Z/+hh:mm if present

        frac = (frac + "000000")[:6]
        s = f"{head}.{frac}{tzpart}"

    # Python doesn't accept 'Z' in fromisoformat
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    return datetime.fromisoformat(s)


def pretty_range(
    start_iso: str,
    end_iso: str,
    *,
    tz_name: str = "Europe/Amsterdam",
) -> str:
    tz = ZoneInfo(tz_name)

    start = _parse_graph_dt(start_iso)
    end = _parse_graph_dt(end_iso)
    if not start or not end:
        return ""

    # If Graph returned naive datetimes (common when you set Prefer timezone),
    # treat them as already in the preferred timezone.
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    else:
        start = start.astimezone(tz)

    if end.tzinfo is None:
        end = end.replace(tzinfo=tz)
    else:
        end = end.astimezone(tz)

    same_day = start.date() == end.date()

    # Tabler-ish compact: "Wed 4 Feb · 10:00–10:30"
    day = start.strftime("%a %-d %b")  # Linux/macOS; see note for Windows below
    start_t = start.strftime("%H:%M")
    end_t = end.strftime("%H:%M")

    if same_day:
        return f"{day} · {start_t}–{end_t}"

    # If crosses day boundary:
    end_part = end.strftime("%a %-d %b %H:%M")
    return f"{day} {start_t} → {end_part}"
