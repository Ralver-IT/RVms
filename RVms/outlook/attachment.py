from __future__ import annotations

from typing import Any, Dict

Json = Dict[str, Any]


class Attachment:
    __slots__ = ("_client", "_user", "_message_id", "raw")

    def __init__(self, client: Any, user: str, message_id: str, raw: Json):
        self._client = client
        self._user = user
        self._message_id = message_id
        self.raw = raw

    @property
    def id(self) -> str:
        return self.raw.get("id", "") or ""

    @property
    def name(self) -> str:
        return self.raw.get("name", "") or ""

    @property
    def content_type(self) -> str:
        return self.raw.get("contentType", "") or ""

    @property
    def size(self) -> int:
        return int(self.raw.get("size", 0) or 0)

    def fetch(self) -> Json:
        url = self._client.user_url(self._user, f"/messages/{self._message_id}/attachments/{self.id}")
        return self._client.request("GET", url)
