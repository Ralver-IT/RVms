from datetime import datetime
from typing import Optional


def parse_graph_local(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None

    # Handle Graph's long fractional seconds
    if "." in s:
        head, tail = s.split(".", 1)
        frac = "".join(ch for ch in tail if ch.isdigit())
        frac = (frac + "000000")[:6]
        s = f"{head}.{frac}"

    return datetime.fromisoformat(s)


def pretty_range_local(start_iso: str, end_iso: str) -> str:
    start = parse_graph_local(start_iso)
    end = parse_graph_local(end_iso)
    if not start or not end:
        return ""

    same_day = start.date() == end.date()

    day = start.strftime("%a %d %b").lstrip("0").replace(" 0", " ")
    start_t = start.strftime("%H:%M")
    end_t = end.strftime("%H:%M")

    if same_day:
        return f"{day} · {start_t}–{end_t}"

    end_part = end.strftime("%a %d %b %H:%M").lstrip("0").replace(" 0", " ")
    return f"{day} {start_t} → {end_part}"
