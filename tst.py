import os
from dotenv import load_dotenv

# from RVms.sharepoint import GraphConnection, SharepointDocument, SharePointSite
# from RVms.utils import LocalFile
#
# load_dotenv()
# def run():
#     file_path = r"C:\Users\ralph.verwijmeren\Downloads\ks4all.bak"
#     conn = GraphConnection(
#         tenant_id=os.getenv("TENANT_ID"),
#         client_id=os.getenv("CLIENT_ID"),
#         client_secret=os.getenv("CLIENT_SECRET"),
#     )
#
#     st = SharePointSite(
#         connection=conn,
#         hostname=os.getenv("SHAREPOINT_HOSTNAME"),
#         site_path=os.getenv("SHAREPOINT_SITE_PATH"),
#         default_library=os.getenv("SHAREPOINT_LIBRARY"),
#     )
#
#     doc = SharepointDocument(site=st)
#     doc.upload(
#         sp_path="ralph/test",
#         file=LocalFile.from_path(file_path),
#     )
#
#
#
# run()

from RVms.connection import GraphConnection
from RVms.outlook.client import MailClient

load_dotenv()

def run2():
    conn = GraphConnection(
        tenant_id=os.getenv("TENANT_ID"),
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
    )

    mail = MailClient(conn)

    user = "info@ralver.nl"

    for msg in mail.iter_messages(user, filter="isRead eq false"):
        print(msg.subject)
        # msg = msg.mark_read()

        for att in msg.list_attachments():
            print("  -", att.name, att.size)
            full = att.fetch()
            print(full)

    msg = mail.new_message(user) \
        .to("ralphverwijmeren001@gmail.com") \
        .subject("Hello") \
        .text("Hi! This was composed locally and sent via Graph.")

    msg.send()

    # delete one
    # outlook.delete_message("allowed.user@yourdomain.com", "<message-id>")



run2()