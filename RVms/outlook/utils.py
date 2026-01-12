from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def parse_graph_datetime(value: Optional[str]) -> Optional[datetime]:
    """
    Parse Microsoft Graph ISO8601 timestamps.

    Graph returns strings like:
      - "2025-01-05T12:34:56Z"
      - "2025-01-05T12:34:56.1234567Z"
      - "2025-01-05T12:34:56+01:00"
    """
    if not value:
        return None

    v = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        # Fallback: trim fractional seconds to microseconds.
        if "." not in v:
            raise
        head, tail = v.split(".", 1)
        tz_pos_plus = tail.find("+")
        tz_pos_minus = tail.find("-")
        tz_pos = max(tz_pos_plus, tz_pos_minus)

        if tz_pos == -1:
            frac, tz = tail, ""
        else:
            frac, tz = tail[:tz_pos], tail[tz_pos:]

        frac = (frac + "000000")[:6]
        dt = datetime.fromisoformat(f"{head}.{frac}{tz}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt
