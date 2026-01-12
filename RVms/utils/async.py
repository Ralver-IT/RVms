import os
import threading

from ..sharepoint import SharepointDocument, SharePointSite
from ..connection import GraphConnection
from ..utils import LocalFile

def sp_upload_async(file_path: str,
                    sp_path: str,
                    tenant_id: str = os.getenv("TENANT_ID"),
                    client_id: str = os.getenv("CLIENT_ID"),
                    client_secret: str = os.getenv("CLIENT_SECRET"),
                    sp_hostname: str = os.getenv("SHAREPOINT_HOSTNAME"),
                    sp_site_path: str = os.getenv("SHAREPOINT_SITEPATH"),
                    sp_library: str = os.getenv("SHAREPOINT_LIBRARY")):
    """
    Fire-and-forget SharePoint upload.
    The HTTP request will NOT wait.
    """

    def _worker():
        try:
            conn = GraphConnection(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
            )

            st = SharePointSite(
                connection=conn,
                hostname=sp_hostname,
                site_path=sp_site_path,
                default_library=sp_library,
            )

            doc = SharepointDocument(site=st)

            doc.upload(
                sp_path=sp_path,
                file=LocalFile.from_path(file_path),
            )

            os.remove(file_path)
            print(f"[SP UPLOAD SUCCESS] Removed local file: {file_path}")

        except Exception as e:
            print(f"[SP UPLOAD FAILED] {file_path}: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
