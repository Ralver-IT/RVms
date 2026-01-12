import os
from dotenv import load_dotenv

from RVms.sharepoint import SPConnection, SharepointDocument, SharePointSite
from RVms.utils import LocalFile

load_dotenv()
def run():
    file_path = r"C:\Users\ralph.verwijmeren\Downloads\ks4all.bak"
    conn = SPConnection(
        tenant_id=os.getenv("TENANT_ID"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
    )

    st = SharePointSite(
        connection=conn,
        hostname=os.getenv("SHAREPOINT_HOSTNAME"),
        site_path=os.getenv("SHAREPOINT_SITE_PATH"),
        default_library=os.getenv("SHAREPOINT_LIBRARY"),
    )

    doc = SharepointDocument(site=st)
    doc.upload(
        sp_path="ralph/test",
        file=LocalFile.from_path(file_path),
    )



run()