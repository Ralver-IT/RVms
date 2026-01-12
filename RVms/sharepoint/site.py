from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict

from ..connection import GraphConnection
from ..connection.exceptions import (
    GraphError,
    SharePointNotFoundError,
    translate_graph_error,
)

@dataclass
class SharePointSite:
    """
    Represents a single SharePoint site (hostname + path) tied to a specificSPConnection.

    Example:
        connection = GraphConnection(...)
        site = SharePointSite(
            connection=connection,
            hostname="domain.sharepoint.com",
            site_path="/sites/Finance",
            default_library="Documents"
        )
    """
    connection: GraphConnection
    hostname: str
    site_path: str
    default_library: str = "Documents"

    _site_id: Optional[str] = field(default=None, init=False)
    _drive_cache: Dict[str, str] = field(default_factory=dict, init=False)

    @property
    def graph_base(self) -> str:
        return self.connection.graph_base

    def normalize_site_path(self) -> str:
        sp = self.site_path or ""
        if not sp.startswith("/"):
            sp = "/" + sp
        return sp

    def _ensure_site_id(self):
        """
        Resolve and cache the Graph site ID for this hostname + site_path.
        """
        if self._site_id:
            return self._site_id

        token = self.connection.get_access_token()
        url = f"{self.graph_base}/sites/{self.hostname}:{self.normalize_site_path()}"
        try:
            data = self.connection.graph_request("GET", url, token=token)
        except GraphError as e:
            target = f"site {self.hostname}{self.normalize_site_path()}"
            return translate_graph_error(target, e)
        else:
            self._site_id = data["id"]
            return self._site_id

    def get_drive_id(self, library_name: Optional[str] = None):
        """
        Returns the drive (document library) ID for the given library name.
        Results are cached per site.
        """
        lib = library_name or self.default_library
        if lib in self._drive_cache:
            return self._drive_cache[lib]

        site_id = self._ensure_site_id()
        token = self.connection.get_access_token()
        url = f"{self.graph_base}/sites/{site_id}/drives?$select=id,name"
        try:
            data = self.connection.graph_request("GET", url, token=token)
        except GraphError as e:
            target = f"drives on site {self.hostname}{self.normalize_site_path()}"
            return translate_graph_error(target, e)
        else:
            for d in data.get("value", []):
                if d.get("name") == lib:
                    self._drive_cache[lib] = d["id"]
                    return d["id"]

            available = ", ".join(d.get("name") for d in data.get("value", []))
            raise SharePointNotFoundError(
                f"Drive '{lib}' not found on site {self.hostname}{self.normalize_site_path()}. "
                f"Available drives: {available}"
            )
