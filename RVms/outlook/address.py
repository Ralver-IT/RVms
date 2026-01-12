from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

Json = Dict[str, Any]


@dataclass(frozen=True)
class EmailAddress:
    name: str = ""
    address: str = ""

    @staticmethod
    def from_graph(d: Optional[Json]) -> "EmailAddress":
        if not d:
            return EmailAddress()
        return EmailAddress(name=d.get("name", "") or "", address=d.get("address", "") or "")

    def display(self) -> str:
        if self.name and self.address:
            return f"{self.name} <{self.address}>"
        return self.address or self.name or ""


def emails_from_recip_list(items: Optional[list[Json]]) -> list[EmailAddress]:
    """
    Graph recipient list shape:
      [{"emailAddress": {"name": "...", "address": "..."}}]
    """
    out: list[EmailAddress] = []
    for item in items or []:
        out.append(EmailAddress.from_graph((item or {}).get("emailAddress")))
    return out
