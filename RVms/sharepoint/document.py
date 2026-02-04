from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict

import requests

from .site import SharePointSite
from ..utils import LocalFile
from RVms.connection.exceptions import (
    GraphError,
    SharePointPathError,
    SharePointNotFoundError,
    SharePointPermissionError,
    translate_graph_error,
)

@dataclass
class SharepointDocument:
    """
    Graph-based implementation around a *single file* in a SharePoint site.

    You can construct it in two main ways:

    
    1) For uploading a new file:

        doc = SharepointDocument(site)
        url = doc.upload(path="invoices/2025", file_name="inv_123.pdf", file_content=b"...")

    2) For working with an existing file by serverRelativeUrl:

        doc = SharepointDocument(site, url="/sites/Finance/Documents/_document_archive/invoices/2025/inv_123.pdf")
        content = doc.download()
        doc.delete()

    Optionally you can specify a library explicitly; otherwise site's default_library is used.
    """

    site: SharePointSite
    url: Optional[str] = None          # serverRelativeUrl, e.g. /sites/Finance/Documents/...
    library: Optional[str] = None      # document library name; defaults to site's default_library

    # internal
    _drive_id: Optional[str] = field(default=None, init=False)
    _item_id: Optional[str] = field(default=None, init=False)
    _item_path: Optional[str] = field(default=None, init=False)  # path inside drive
    file: Optional[dict] = field(default=None, init=False)       # last driveItem JSON

    # ----- convenience properties -----

    @property
    def connection(self):
        return self.site.connection

    @property
    def graph_base(self) -> str:
        return self.site.graph_base

    @property
    def library_name(self) -> str:
        return self.library or self.site.default_library

    @property
    def item_id(self) -> Optional[str]:
        """
        Expose the underlying driveItem ID (if resolved).
        """
        return self._item_id

    @property
    def filename(self) -> Optional[str]:
        """
        Prefers Graph DriveItem 'name'
        """
        if self.file and isinstance(self.file, dict):
            name = self.file.get("name")
            if name:
                return name

        return None


    # ----- internal helpers -----

    def _ensure_drive_id(self) -> str:
        if not self._drive_id:
            self._drive_id = self.site.get_drive_id(self.library_name)
        return self._drive_id

    def _parse_server_relative_url(self, url: str) -> Tuple[str, str]:
        """
        /sites/Finance/Documents/_document_archive/foo/file.pdf
        → ("Documents", "_document_archive/foo/file.pdf")
        """
        url = url.strip()
        if not url.startswith("/"):
            raise SharePointPathError(f"Expected server relative URL to start with '/', got '{url}'")

        site_path = self.site.site_path.lstrip("/")
        prefix = f"/{site_path}/"
        if not url.startswith(prefix):
            raise SharePointPathError(
                f"URL '{url}' does not belong to site '{self.site.hostname}{self.site.site_path}'"
            )

        remainder = url[len(prefix):]  # e.g. "Documents/_document_archive/foo/file.pdf"
        parts = remainder.split("/", 1)
        if len(parts) < 2:
            raise SharePointPathError(f"Cannot parse library + path from URL '{url}'")

        library_name, item_path = parts[0], parts[1]
        return library_name, item_path

    def _ensure_item_from_url(self) -> None:
        """
        If the instance was created with only 'url', resolve it into
        drive item path + item ID via Graph (once).
        """
        if self._item_id:
            return

        if not self.url:
            raise SharePointPathError(
                "SharepointDocument has no 'url' set and no item loaded."
            )

        library_name, item_path = self._parse_server_relative_url(self.url)
        # If library wasn't explicitly set, adopt from URL
        if self.library is None:
            self.library = library_name

        drive_id = self._ensure_drive_id()
        token = self.connection.get_access_token()

        item = self._resolve_item_by_path(token, drive_id, item_path)
        self._item_id = item["id"]
        self._item_path = item_path
        self.file = item

    def _resolve_item_by_path(self, token: str, drive_id: str, item_path: str) -> dict:
        """
        Resolve a driveItem by its path inside the library.
        """
        item_path = item_path.strip("/")
        url = f"{self.graph_base}/drives/{drive_id}/root:/{item_path}"
        try:
            data = self.connection.graph_request("GET", url, token=token)
        except GraphError as e:
            target = f"item '{item_path}' in library '{self.library_name}'"
            translate_graph_error(target, e)
            raise
        else:
            return data

    def _ensure_folder_path(self, token: str, drive_id: str, folder_path: str) -> str:
        """
        Ensure a nested folder exists within a drive.
        Returns the normalized folder path.
        """
        folder_path = folder_path.strip("/")
        if not folder_path:
            return ""

        parts = folder_path.split("/")
        current_path = ""

        for part in parts:
            current_path = f"{current_path}/{part}".strip("/")
            url = f"{self.graph_base}/drives/{drive_id}/root:/{current_path}"

            try:
                self.connection.graph_request("GET", url, token=token)
            except GraphError as e:
                if e.status_code == 404:
                    # Need to create this folder under its parent
                    parent_path = "/".join(current_path.split("/")[:-1])
                    if parent_path:
                        parent_url = (
                            f"{self.graph_base}/drives/{drive_id}/root:/{parent_path}:/children"
                        )
                    else:
                        parent_url = f"{self.graph_base}/drives/{drive_id}/root/children"

                    body = {
                        "name": part,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "fail",
                    }

                    try:
                        self.connection.graph_request(
                            "POST",
                            parent_url,
                            token=token,
                            json=body,
                            expected_status=201,
                        )
                    except GraphError as e2:
                        target = f"folder '{current_path}'"
                        translate_graph_error(target, e2)
                else:
                    target = f"folder '{current_path}'"
                    translate_graph_error(target, e)

        return folder_path

    def _server_relative_from_path(self, item_path: str) -> str:
        """
        Build a classic-looking serverRelativeUrl:
          /sites/Finance/<LibraryName>/<item_path>
        """
        site_path = self.site.site_path.lstrip("/")
        return f"/{site_path}/{self.library_name}/{item_path.strip('/')}"

    def _upload_large_file_stream(
            self,
            drive_id: str,
            token: str,
            item_path: str,
            file: LocalFile,
            chunk_size: int = 4 * 1024 * 1024,
    ) -> dict:
        """
        Stream a large file from disk to SharePoint using a Graph upload session.
        Returns the final driveItem JSON.
        """
        file_size = file.size()

        bytes_uploaded = 0
        upload_url = None

        if upload_url is None:
            create_session_url = (
                f"{self.graph_base}/drives/{drive_id}/root:/{item_path}:/createUploadSession"
            )
            session_body = {
                "item": {
                    "@microsoft.graph.conflictBehavior": "replace",
                    "name": file.name,
                }
            }
            session = self.connection.graph_request(
                "POST",
                create_session_url,
                token=token,
                json=session_body,
                expected_status=200,
            )
            upload_url = session["uploadUrl"]
            bytes_uploaded = 0

        final_item = None

        with file.open("rb") as f:
            if bytes_uploaded > 0:
                f.seek(bytes_uploaded)

            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                chunk_len = len(chunk)
                start = bytes_uploaded
                end = bytes_uploaded + chunk_len - 1

                headers = {
                    "Content-Length": str(chunk_len),
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                }

                resp = self.connection.graph_request(
                    "PUT",
                    upload_url,
                    token=token,
                    data=chunk,
                    headers=headers,
                    expected_status=(200, 201, 202),
                )

                bytes_uploaded += chunk_len

                if isinstance(resp, dict) and "id" in resp:
                    final_item = resp

                print(
                    f"Uploaded {bytes_uploaded}/{file_size} bytes "
                    f"({bytes_uploaded * 100 / file_size:.2f}%)"
                )

        if final_item is None:
            raise RuntimeError("Upload session finished without final item response")

        return final_item

    # ----- public API -----
    def ensure_folder(self, path: str) -> str:
        """
        Ensures folder structure exists inside the library.

        NOTE:
            Business logic belongs outside — this is a pure API.
            The caller specifies *exactly* where inside the library the file goes.
        """
        drive_id = self._ensure_drive_id()
        token = self.connection.get_access_token()

        folder = (path or "").strip("/").strip()
        if not folder:
            return ""

        full_path = Path(folder)
        folder_path = "/".join(full_path.parts)

        return self._ensure_folder_path(token, drive_id, folder_path)

    def upload(
            self,
            sp_path: str,
            file: LocalFile,
            chunk_size: int = 10 * 1024 * 1024
    ) -> str:
        """
        Upload a file from disk to _document_archive/<path> in the site's document library
        without loading the whole file into memory.

        Uses a Graph upload session for large files.
        Returns a serverRelativeUrl-like string.
        """
        drive_id = self._ensure_drive_id()
        token = self.connection.get_access_token()

        # Make sure folder exists in the document library
        folder = self.ensure_folder(sp_path)
        item_path = f"{folder}/{file.name}" if folder != "" else file.name

        small_file_threshold = 4 * 1024 * 1024  # 4 MiB

        try:
            if file.size() <= small_file_threshold:

                data_bytes = file.read_bytes()

                url = f"{self.graph_base}/drives/{drive_id}/root:/{item_path}:/content"
                resp_json = self.connection.graph_request(
                    "PUT",
                    url,
                    token=token,
                    data=data_bytes,
                    expected_status=(200, 201),
                )
            else:
                resp_json = self._upload_large_file_stream(
                    drive_id=drive_id,
                    token=token,
                    item_path=item_path,
                    file=file,
                    chunk_size=chunk_size,
                )

        except GraphError as e:
            target = f"upload to '{item_path}' in library '{self.library_name}'"
            translate_graph_error(target, e)
            raise

        self.file = resp_json
        self._item_id = resp_json["id"]
        self._item_path = item_path
        self.url = self._server_relative_from_path(item_path)

        return self.url

    def download(self) -> bytes:
        """
        Downloads the file content and returns it as bytes.
        """
        drive_id = self._ensure_drive_id()
        token = self.connection.get_access_token()

        if not self._item_id:
            self._ensure_item_from_url()

        url = f"{self.graph_base}/drives/{drive_id}/items/{self._item_id}/content"

        try:
            resp = self.connection.graph_request(
                "GET",
                url,
                token=token,
                expected_status=(200, 301, 302),
                stream=False,
            )
        except GraphError as e:
            target = f"download of '{self.url or self._item_path}'"
            translate_graph_error(target, e)
            raise

        # Handle redirect (preauth link) or direct content
        if isinstance(resp, requests.Response) and resp.status_code in (301, 302):
            loc = resp.headers.get("Location")
            if not loc:
                raise SharePointNotFoundError(
                    f"No Location header when downloading {self.url or self._item_path}"
                )
            final = self.connection.session.get(loc, timeout=60)
            if final.status_code == 404:
                raise SharePointNotFoundError(
                    f"File not found at {self.url or self._item_path}"
                )
            if final.status_code in (401, 403):
                raise SharePointPermissionError(
                    f"No permission to follow preauth URL for {self.url or self._item_path}"
                )
            final.raise_for_status()
            return final.content

        if isinstance(resp, requests.Response):
            if resp.status_code == 404:
                raise SharePointNotFoundError(
                    f"File not found at {self.url or self._item_path}"
                )
            if resp.status_code in (401, 403):
                raise SharePointPermissionError(
                    f"No permission to download {self.url or self._item_path}"
                )
            resp.raise_for_status()
            return resp.content

        raise RuntimeError("Unexpected response type while downloading.")

    def delete(self) -> None:
        """
        Deletes the file from the library.
        """
        drive_id = self._ensure_drive_id()
        token = self.connection.get_access_token()

        if not self._item_id:
            self._ensure_item_from_url()

        url = f"{self.graph_base}/drives/{drive_id}/items/{self._item_id}"
        try:
            self.connection.graph_request(
                "DELETE",
                url,
                token=token,
                expected_status=204,
            )
        except GraphError as e:
            target = f"delete of '{self.url or self._item_path}'"
            translate_graph_error(target, e)

    def set_metadata(self, key: str, value: str) -> None:
        """
        Updates a metadata field on the backing list item.

        NOTE: key must correspond to an existing field in the library
        (e.g. 'Title' or a custom column's internal name).
        """
        drive_id = self._ensure_drive_id()
        token = self.connection.get_access_token()

        if not self._item_id:
            self._ensure_item_from_url()

        url = f"{self.graph_base}/drives/{drive_id}/items/{self._item_id}/listItem/fields"
        body = {key: str(value)}

        try:
            self.connection.graph_request(
                "PATCH",
                url,
                token=token,
                json=body,
                expected_status=200,
            )
        except GraphError as e:
            target = f"metadata update for '{self.url or self._item_path}'"
            translate_graph_error(target, e)

    def get_preauth_url(self) -> str:
        """
        Returns a short-lived pre-authenticated download URL.
        Uses /content redirect capturing, which works even when
        @microsoft.graph.downloadUrl is not provided.
        """
        if not self._item_id:
            raise SharePointNotFoundError(
                "File must be uploaded or loaded before calling get_preauth_url()."
            )

        token = self.site.connection.get_access_token()
        drive_id = self._ensure_drive_id()

        url = f"{self.graph_base}/drives/{drive_id}/items/{self._item_id}/content"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "*/*"
        }

        resp = requests.get(url, headers=headers, allow_redirects=False)

        # Must return redirect
        if resp.status_code not in (301, 302):
            raise SharePointNotFoundError(
                f"No redirect returned for preauth URL (status {resp.status_code})."
            )

        location = resp.headers.get("Location")
        if not location:
            raise SharePointNotFoundError(
                "No Location header found; no preauth URL available."
            )

        return location

    def get_preview_url(self) -> str:
        """
        Returns a short-lived embeddable preview URL for a DriveItem.
        Use this for showing the file in an <iframe>/<object>, not for download.
        """
        if not self._item_id:
            raise SharePointNotFoundError(
                "File must be uploaded or loaded before calling get_preview_url()."
            )

        token = self.site.connection.get_access_token()
        drive_id = self._ensure_drive_id()

        url = f"{self.graph_base}/drives/{drive_id}/items/{self._item_id}/preview"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # Body is optional; you can add viewer options if you want.
        resp = requests.post(url, headers=headers, json={})
        if resp.status_code not in (200, 201):
            raise SharePointNotFoundError(
                f"Preview endpoint failed (status {resp.status_code}): {resp.text}"
            )

        data = resp.json()
        preview_url = data.get("getUrl")
        if not preview_url:
            raise SharePointNotFoundError("No getUrl returned from preview endpoint.")

        return preview_url

    def load_by_path(self, server_relative_url: str) -> None:
        """
        Initialize this SharepointDocument instance from an existing
        server-relative URL, e.g.:

            /sites/Development/Documents/folder/file.pdf

        """
        # Set the URL and reset state
        self.url = server_relative_url
        self._item_id = None
        self._item_path = None
        self.file = None

        # Resolve _item_id and _item_path using the existing helpers
        self._ensure_item_from_url()


    @classmethod
    def from_drive_item(
            cls,
            site: SharePointSite,
            item: Dict,
            library: Optional[str] = None,
            drive_id: Optional[str] = None,
    ) -> "SharepointDocument":
        """
        Build a SharepointDocument from a DriveItem JSON dict (as returned by Graph).
        Works great with items from list_files().

        - Sets _item_id and file immediately
        - Sets _drive_id if provided (recommended)
        - Tries to derive _item_path from parentReference.path + name if possible
        - Attempts to derive server-relative url if we can parse site_path + library
        """
        doc = cls(site=site, library=library)

        doc.file = item
        doc._item_id = item["id"]

        doc._drive_id = drive_id or item.get("parentReference", {}).get("driveId")

        parent_path = item.get("parentReference", {}).get("path")  # "/drives/{id}/root:/A/B"
        name = item.get("name")

        item_path = None
        if parent_path and name:
            marker = "root:/"
            if marker in parent_path:
                rel = parent_path.split(marker, 1)[1]  # "A/B"
                rel = rel.strip("/")
                item_path = f"{rel}/{name}" if rel else name

        doc._item_path = item_path

        if item_path and doc.library_name:
            doc.url = doc._server_relative_from_path(item_path)

        return doc

