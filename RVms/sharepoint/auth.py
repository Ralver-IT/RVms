from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, Sequence

import msal
import requests

from .exceptions import GraphError, RvspConfigError


DEFAULT_GRAPH_SCOPES: tuple[str, ...] = ("https://graph.microsoft.com/.default",)
DEFAULT_GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class SPConnection:
    """
    Represents a connection to Microsoft Graph using a single app registration
    (tenant_id + client_id + client_secret).

    You can reuse one connection for multiple SharePointSite instances.
    """

    tenant_id: str
    client_id: str
    client_secret: str

    graph_scopes: Sequence[str] = field(
        default_factory=lambda: list(DEFAULT_GRAPH_SCOPES)
    )
    graph_base: str = DEFAULT_GRAPH_BASE

    # internal fields (not in __init__)
    _authority: str = field(init=False)
    _msal_app: Optional[msal.ConfidentialClientApplication] = field(
        init=False, default=None
    )
    _session: requests.Session = field(init=False)

    def __post_init__(self):
        if not self.tenant_id or not self.client_id or not self.client_secret:
            raise RvspConfigError(
                "tenant_id, client_id and client_secret are required for SPConnection"
            )

        self._authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self._session = requests.Session()

    # ---------- public properties ---------- #

    @property
    def session(self) -> requests.Session:
        return self._session

    @property
    def msal_app(self) -> msal.ConfidentialClientApplication:
        if self._msal_app is None:
            self._msal_app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=self._authority,
                client_credential=self.client_secret,
            )
        return self._msal_app

    # ---------- token + graph request ---------- #

    def get_access_token(self) -> str:
        """
        Acquire an app-only token using client credentials.
        """
        # graph_scopes is guaranteed to exist as a dataclass field
        scopes = list(self.graph_scopes)
        result = self.msal_app.acquire_token_for_client(scopes=scopes)

        if "access_token" not in result:
            raise RvspConfigError(
                f"Failed to obtain access token: {json.dumps(result, indent=2)}"
            )
        return result["access_token"]

    def graph_request(
        self,
        method: str,
        url: str,
        expected_status=(200, 201, 204),
        token: Optional[str] = None,
        **kwargs,
    ):
        """
        Generic Graph HTTP wrapper.

        - Adds Authorization and Accept headers
        - Raises GraphError on non-expected status codes
        - Parses JSON when Content-Type is application/json
        """
        if token is None:
            token = self.get_access_token()

        headers = kwargs.pop("headers", {})
        headers.setdefault("Authorization", f"Bearer {token}")
        headers.setdefault("Accept", "application/json")

        if "json" in kwargs and "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

        timeout = kwargs.pop("timeout", 15)
        resp = self._session.request(
            method,
            url,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )

        if isinstance(expected_status, int):
            expected_status = (expected_status,)

        if resp.status_code not in expected_status:
            body = resp.text
            raise GraphError(
                f"Graph {method} {url} failed", resp.status_code, body
            )

        # For 204 or non-JSON, or if caller asked for stream → return raw response
        content_type = resp.headers.get("Content-Type", "")
        if (
            resp.status_code == 204
            or kwargs.get("stream")
            or "application/json" not in content_type
        ):
            return resp

        try:
            return resp.json()
        except ValueError:
            return resp
