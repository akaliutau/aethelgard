import httpx
from aethelgard.core.transport import BaseClientTransport

class HttpxClientTransport(BaseClientTransport):
    """Asynchronous HTTP Client for Hospital Outbound Polling."""
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def poll_tasks(self, client_id: str) -> list:
        try:
            url = f"{self.server_url}/api/v1/client/{client_id}/poll"
            response = await self.http_client.get(url)
            response.raise_for_status()
            return response.json().get("pending_tasks", [])
        except httpx.RequestError as e:
            return []

    async def submit_insight(self, client_id: str, request_id: str, insight: str) -> None:
        url = f"{self.server_url}/api/v1/query/{request_id}/insight"
        payload = {"client_id": client_id, "sanitized_insight": insight}
        await self.http_client.post(url, json=payload)