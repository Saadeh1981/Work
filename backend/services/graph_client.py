
"""
graph_client.py
---------------
Placeholder for Microsoft Graph client (On-Behalf-Of flow from Teams/Copilot).
Use this to fetch files from SharePoint/OneDrive and to write outputs.
"""
from typing import Optional

class GraphClient:
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token

    async def fetch_file_bytes(self, drive_id: str, item_id: str) -> bytes:
        # TODO: GET /drives/{drive-id}/items/{item-id}/content with bearer token
        raise NotImplementedError("Graph fetch not implemented yet.")

    async def upload_file_bytes(self, site_id: str, drive_id: str, folder_path: str, filename: str, data: bytes) -> str:
        # TODO: PUT /sites/{site-id}/drives/{drive-id}/root:/{folder_path}/{filename}:/content
        # Return the sharing link or the item webUrl
        raise NotImplementedError("Graph upload not implemented yet.")
