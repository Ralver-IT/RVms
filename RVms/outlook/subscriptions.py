from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

Json = Dict[str, Any]


def qs_encode(s: str) -> str:
    return quote(s, safe="")


def to_graph_dt(dt: datetime) -> str:
    """
    Graph expects an ISO 8601 timestamp (UTC recommended).
    Example: '2026-01-14T12:34:56Z'
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


class Subscription:
    """
    Active Record wrapper around a Microsoft Graph subscription object.
    https://graph.microsoft.com/v1.0/subscriptions/{id}
    """

    __slots__ = ("_client", "raw")

    def __init__(self, client: Any, raw: Json):
        self._client = client
        self.raw = raw

    @property
    def id(self) -> str:
        return self.raw.get("id", "") or ""

    @property
    def resource(self) -> str:
        return self.raw.get("resource", "") or ""

    @property
    def change_type(self) -> str:
        return self.raw.get("changeType", "") or ""

    @property
    def notification_url(self) -> str:
        return self.raw.get("notificationUrl", "") or ""

    @property
    def lifecycle_notification_url(self) -> str:
        return self.raw.get("lifecycleNotificationUrl", "") or ""

    @property
    def expiration(self) -> Optional[str]:
        # Keep as string to avoid forcing a datetime parser.
        return self.raw.get("expirationDateTime")

    def refresh(self) -> "Subscription":
        return self._client.get_subscription(self.id)

    def delete(self) -> None:
        self._client.delete_subscription(self.id)

    def renew(self, *, expiration: datetime) -> "Subscription":
        """
        PATCH /subscriptions/{id}
        Only expirationDateTime is typically required for renewal.
        """
        return self._client.update_subscription(self.id, expiration=expiration)


@dataclass
class SubscriptionClient:
    """
    Transport + factories for Graph /subscriptions.

    Public surface area:
      - list_subscriptions(...)
      - get_subscription(...)
      - create_subscription(...)
      - update_subscription(...)  (renew)
      - delete_subscription(...)
    """

    conn: Any

    @property
    def base_url(self) -> str:
        return f"{self.conn.graph_base}/subscriptions"

    def request(self, method: str, url: str, **kwargs) -> Json:
        return self.conn.graph_request(method, url, **kwargs)

    # ---------- core CRUD ----------
    def list_subscriptions(
            self,
            *,
            next_link: Optional[str] = None,
    ) -> tuple[list[Subscription], Optional[str]]:
        url = next_link or self.base_url  # NO $top, NO $select
        page: Json = self.request("GET", url)
        subs = [Subscription(self, s) for s in page.get("value", [])]
        return subs, page.get("@odata.nextLink")

    def iter_subscriptions(self, **kwargs):
        subs, next_link = self.list_subscriptions(**kwargs)
        for s in subs:
            yield s
        while next_link:
            subs, next_link = self.list_subscriptions(next_link=next_link)
            for s in subs:
                yield s

    def get_subscription(self, subscription_id: str) -> Subscription:
        url = f"{self.base_url}/{subscription_id}"
        raw: Json = self.request("GET", url)
        return Subscription(self, raw)

    def create_subscription(
        self,
        *,
        resource: str,
        change_type: str,
        notification_url: str,
        expiration: datetime,
        client_state: Optional[str] = None,
        lifecycle_notification_url: Optional[str] = None,
        include_resource_data: Optional[bool] = None,
        encryption_certificate: Optional[str] = None,
        encryption_certificate_id: Optional[str] = None,
        latest_supported_tls_version: Optional[str] = None,
    ) -> Subscription:
        """
        POST /subscriptions

        Required (most cases):
          - changeType
          - notificationUrl
          - resource
          - expirationDateTime

        Optional:
          - clientState
          - lifecycleNotificationUrl
          - includeResourceData + encryption* (for rich notifications / resource data)
          - latestSupportedTlsVersion

        Docs: Create subscription. :contentReference[oaicite:1]{index=1}
        """
        payload: Json = {
            "changeType": change_type,
            "notificationUrl": notification_url,
            "resource": resource,
            "expirationDateTime": to_graph_dt(expiration),
        }
        if client_state is not None:
            payload["clientState"] = client_state
        if lifecycle_notification_url is not None:
            payload["lifecycleNotificationUrl"] = lifecycle_notification_url
        if include_resource_data is not None:
            payload["includeResourceData"] = include_resource_data
        if encryption_certificate is not None:
            payload["encryptionCertificate"] = encryption_certificate
        if encryption_certificate_id is not None:
            payload["encryptionCertificateId"] = encryption_certificate_id
        if latest_supported_tls_version is not None:
            payload["latestSupportedTlsVersion"] = latest_supported_tls_version

        raw: Json = self.request("POST", self.base_url, json=payload, expected_status=(201,))
        return Subscription(self, raw)

    def update_subscription(self, subscription_id: str, *, expiration: datetime) -> Subscription:
        """
        PATCH /subscriptions/{id} to renew (extend expirationDateTime).
        Docs: Update subscription. :contentReference[oaicite:2]{index=2}
        """
        url = f"{self.base_url}/{subscription_id}"
        raw: Json = self.request(
            "PATCH",
            url,
            json={"expirationDateTime": to_graph_dt(expiration)},
            expected_status=(200,),
        )
        return Subscription(self, raw)

    def delete_subscription(self, subscription_id: str) -> None:
        url = f"{self.base_url}/{subscription_id}"
        self.request("DELETE", url, expected_status=204)
