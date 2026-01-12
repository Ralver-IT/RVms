import os

from .site import SharePointSite
from .document import SharepointDocument
from ..connection import GraphConnection
from ..utils import LocalFile

import threading

HOSTNAME = os.getenv("SHAREPOINT_HOSTNAME")
SITE_PATH = os.getenv("SHAREPOINT_SITE_PATH")
LIBRARY_NAME = os.getenv("SHAREPOINT_LIBRARY")

def sp_upload_async(file_path, folder):
    """
    Fire-and-forget SharePoint upload.
    The HTTP request will NOT wait.
    """

    def _worker():
        try:
            conn = GraphConnection(
                tenant_id=os.getenv("TENANT_ID"),
                client_id=os.getenv("CLIENT_ID"),
                client_secret=os.getenv("CLIENT_SECRET"),
            )

            st = SharePointSite(
                connection=conn,
                hostname=HOSTNAME,
                site_path=SITE_PATH,
                default_library=LIBRARY_NAME,
            )

            doc = SharepointDocument(site=st, library=LIBRARY_NAME)

            doc.upload(
                sp_path=folder,
                file=LocalFile.from_path(file_path),
            )

            os.remove(file_path)
            print(f"[SP UPLOAD SUCCESS] Removed local file: {file_path}")

        except Exception as e:
            # IMPORTANT: log this somewhere
            print(f"[SP UPLOAD FAILED] {file_path}: {e}")

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

