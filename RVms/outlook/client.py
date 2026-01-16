from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional, Sequence
from urllib.parse import quote

from .message import MailMessage
from .compose import ComposeMessage

Json = Dict[str, Any]


def qs_encode(s: str) -> str:
    return quote(s, safe="")


@dataclass
class MailClient:
    """
    Transport + factories only.

    Public surface area:
      - get_message(...)
      - iter_messages(...)
      - list_messages(...)

    Public transport helpers intentionally exposed for Active Record models:
      - user_url(user, path)
      - request(method, url, **kwargs)

    NOTE: We do NOT expose message ops like delete/mark/move on the client.
    Those live on MailMessage.
    """

    conn: Any

    def user_url(self, user: str, path: str) -> str:
        """
        Build a Graph URL under /users/{user}/... safely.
        `path` should start with '/', e.g. '/messages/{id}'.
        """
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.conn.graph_base}/users/{user}{path}"

    def request(self, method: str, url: str, **kwargs) -> Json:
        """
        Single public transport hook used by models.
        """
        return self.conn.graph_request(method, url, **kwargs)

    # --------- folders (optional) ---------

    def list_mail_folders(self, user: str, top: int = 100) -> Json:
        url = self.user_url(user, f"/mailFolders?$top={top}")
        return self.request("GET", url)

    def get_mail_folder(self, user: str, folder_id: str) -> Json:
        url = self.user_url(user, f"/mailFolders/{folder_id}")
        return self.request("GET", url)

    # --------- messages (factories) ---------

    def list_messages(
        self,
        user: str,
        folder: str = "Inbox",
        *,
        top: int = 25,
        select: Sequence[str] = (
            "id",
            "subject",
            "from",
            "toRecipients",
            "ccRecipients",
            "receivedDateTime",
            "sentDateTime",
            "isRead",
            "bodyPreview",
            "hasAttachments",
            "importance",
            "internetMessageId",
        ),
        orderby: str = "receivedDateTime desc",
        filter: Optional[str] = None,
        search: Optional[str] = None,
        include_total_count: bool = False,
        next_link: Optional[str] = None,
    ) -> tuple[list[MailMessage], Optional[str], Optional[int]]:
        if next_link:
            url = next_link
            headers = {}
        else:
            folder_part = (
                folder
                if folder.lower()
                in {"inbox", "sentitems", "deleteditems", "drafts", "archive", "junkemail", "outbox"}
                else folder
            )

            sel = ",".join(select)
            url = self.user_url(
                user,
                f"/mailFolders/{folder_part}/messages"
                f"?$top={top}&$select={qs_encode(sel)}&$orderby={qs_encode(orderby)}",
            )

            if filter:
                url += f"&$filter={qs_encode(filter)}"
            if include_total_count:
                url += "&$count=true"

            headers = {}
            if search:
                quoted = f'"{search}"'
                url += f"&$search={qs_encode(quoted)}"
                headers["ConsistencyLevel"] = "eventual"

        page: Json = self.request("GET", url, headers=headers)
        msgs = [MailMessage(self, user, m) for m in page.get("value", [])]
        return msgs, page.get("@odata.nextLink"), (page.get("@odata.count") if include_total_count else None)

    def iter_messages(
        self,
        user: str,
        folder: str = "Inbox",
        *,
        page_size: int = 50,
        **kwargs,
    ) -> Generator[MailMessage, None, None]:
        msgs, next_link, _ = self.list_messages(user, folder, top=page_size, **kwargs)
        for m in msgs:
            yield m
        while next_link:
            msgs, next_link, _ = self.list_messages(user, folder, next_link=next_link)
            for m in msgs:
                yield m

    def get_message(
        self,
        user: str,
        message_id: str,
        *,
        select: Sequence[str] = (
            "id",
            "subject",
            "from",
            "toRecipients",
            "ccRecipients",
            "receivedDateTime",
            "sentDateTime",
            "isRead",
            "bodyPreview",
            "body",
            "hasAttachments",
            "importance",
            "internetMessageId",
        ),
    ) -> MailMessage:
        sel = ",".join(select)
        url = self.user_url(user, f"/messages/{message_id}?$select={qs_encode(sel)}")
        raw: Json = self.request("GET", url)
        return MailMessage(self, user, raw)

    def new_message(self, user: str) -> ComposeMessage:
        return ComposeMessage(self, user)
