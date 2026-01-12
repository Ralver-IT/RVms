from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from .message import MailMessage

Json = Dict[str, Any]


def _recipients(emails: Sequence[str]) -> List[Json]:
    return [{"emailAddress": {"address": e}} for e in emails]


@dataclass
class ComposeMessage:
    """
    A local, fluent builder for a message you intend to send (or save as draft).

    This is NOT a Graph message yet until you call:
      - send()
      - save_draft()

    It is bound to a MailClient + user so it can send with zero extra args.
    """
    _client: Any
    _user: str

    _subject: str = ""
    _body_type: str = "Text"  # "Text" or "HTML"
    _body_content: str = ""

    _to: List[str] = field(default_factory=list)
    _cc: List[str] = field(default_factory=list)
    _bcc: List[str] = field(default_factory=list)

    _attachments: List[Json] = field(default_factory=list)

    def subject(self, s: str) -> "ComposeMessage":
        self._subject = s
        return self

    def text(self, content: str) -> "ComposeMessage":
        self._body_type = "Text"
        self._body_content = content
        return self

    def html(self, content: str) -> "ComposeMessage":
        self._body_type = "HTML"
        self._body_content = content
        return self

    def to(self, *emails: str) -> "ComposeMessage":
        self._to.extend(emails)
        return self

    def cc(self, *emails: str) -> "ComposeMessage":
        self._cc.extend(emails)
        return self

    def bcc(self, *emails: str) -> "ComposeMessage":
        self._bcc.extend(emails)
        return self

    def attach_bytes(self, *, filename: str, content_bytes: bytes, content_type: str = "application/octet-stream") -> "ComposeMessage":
        """
        Attach bytes as a small file attachment (best for a few MB max).
        For larger attachments you need upload sessions.
        """
        b64 = base64.b64encode(content_bytes).decode("ascii")
        self._attachments.append(
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": filename,
                "contentType": content_type,
                "contentBytes": b64,
            }
        )
        return self

    def attach_file(self, path: str, *, filename: Optional[str] = None, content_type: str = "application/octet-stream") -> "ComposeMessage":
        with open(path, "rb") as f:
            data = f.read()
        fname = filename or path.split("/")[-1]
        return self.attach_bytes(filename=fname, content_bytes=data, content_type=content_type)

    def as_graph_message(self) -> Json:
        msg: Json = {
            "subject": self._subject,
            "body": {"contentType": self._body_type, "content": self._body_content},
        }
        if self._to:
            msg["toRecipients"] = _recipients(self._to)
        if self._cc:
            msg["ccRecipients"] = _recipients(self._cc)
        if self._bcc:
            msg["bccRecipients"] = _recipients(self._bcc)
        if self._attachments:
            msg["attachments"] = list(self._attachments)
        return msg

    def send(self, *, save_to_sent_items: bool = True) -> None:
        """
        Send immediately via POST /sendMail.
        """
        url = self._client.user_url(self._user, "/sendMail")
        payload = {"message": self.as_graph_message(), "saveToSentItems": save_to_sent_items}
        self._client.request("POST", url, json=payload, expected_status=202)

    def save_draft(self) -> MailMessage:
        """
        Create a draft via POST /messages and return a MailMessage (active record).
        """
        url = self._client.user_url(self._user, "/messages")
        raw = self._client.request("POST", url, json=self.as_graph_message(), expected_status=201)

        return MailMessage(self._client, self._user, raw)
