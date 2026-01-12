from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .address import EmailAddress, emails_from_recip_list
from .attachment import Attachment
from .utils import parse_graph_datetime


class MailMessage:
    __slots__ = ("_client", "_user", "raw")

    def __init__(self, client: Any, user: str, raw: Dict[str, Any]):
        self._client = client
        self._user = user
        self.raw = raw

    @property
    def id(self) -> str:
        return self.raw.get("id", "") or ""

    @property
    def subject(self) -> str:
        return self.raw.get("subject", "") or ""

    @property
    def is_read(self) -> bool:
        return bool(self.raw.get("isRead", False))

    @property
    def has_attachments(self) -> bool:
        return bool(self.raw.get("hasAttachments", False))

    @property
    def received_at(self):
        return parse_graph_datetime(self.raw.get("receivedDateTime"))

    @property
    def from_(self) -> EmailAddress:
        d = (self.raw.get("from") or {}).get("emailAddress")
        return EmailAddress.from_graph(d)

    @property
    def to(self) -> List[EmailAddress]:
        return emails_from_recip_list(self.raw.get("toRecipients"))

    @property
    def cc(self) -> List[EmailAddress]:
        return emails_from_recip_list(self.raw.get("ccRecipients"))

    # ---- active record ops ----

    def refresh(self, *, select: Optional[Sequence[str]] = None) -> "MailMessage":
        return self._client.get_message(self._user, self.id, select=select or self._client.get_message.__defaults__[0])  # optional

    def mark_read(self, is_read: bool = True) -> "MailMessage":
        url = self._client.user_url(self._user, f"/messages/{self.id}")
        raw = self._client.request("PATCH", url, json={"isRead": is_read}, expected_status=(200,))
        return MailMessage(self._client, self._user, raw)

    def delete(self) -> None:
        url = self._client.user_url(self._user, f"/messages/{self.id}")
        self._client.request("DELETE", url, expected_status=204)

    def move_to(self, destination_folder_id: str) -> "MailMessage":
        url = self._client.user_url(self._user, f"/messages/{self.id}/move")
        raw = self._client.request("POST", url, json={"destinationId": destination_folder_id}, expected_status=201)
        return MailMessage(self._client, self._user, raw)

    # ---- attachments ----

    def list_attachments(self, *, top: int = 50) -> List[Attachment]:
        url = self._client.user_url(self._user, f"/messages/{self.id}/attachments?$top={top}")
        page = self._client.request("GET", url)
        return [Attachment(self._client, self._user, self.id, a) for a in page.get("value", [])]

    def get_attachment(self, attachment_id: str) -> Dict[str, Any]:
        url = self._client.user_url(self._user, f"/messages/{self.id}/attachments/{attachment_id}")
        return self._client.request("GET", url)
