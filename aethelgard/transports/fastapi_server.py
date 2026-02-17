import uuid
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from aethelgard.core.transport import BaseServerTransport
from aethelgard.core.broker import BaseTaskBroker

class ClinicalQuery(BaseModel):
    query_text: str
    query_vector: list[float]
    target_clients: list[str]

class InsightSubmission(BaseModel):
    client_id: str
    sanitized_insight: str

class FastAPITransport(BaseServerTransport):
    """HTTP REST API implementation using FastAPI."""
    def __init__(self, broker: BaseTaskBroker):
        super().__init__(broker)
        self.app = FastAPI(title="Aethelgard SuperLink")
        self._setup_routes()

    def _setup_routes(self):
        @self.app.post("/api/v1/query/broadcast")
        async def broadcast_query(query: ClinicalQuery):
            request_id = str(uuid.uuid4())
            for client in query.target_clients:
                await self.broker.enqueue_query(client, request_id, query.query_vector)
            return {"message": "Query broadcast initiated", "request_id": request_id}

        @self.app.get("/api/v1/client/{client_id}/poll")
        async def poll_tasks(client_id: str):
            tasks = await self.broker.dequeue_queries(client_id)
            return {"pending_tasks": tasks}

        @self.app.post("/api/v1/query/{request_id}/insight")
        async def submit_insight(request_id: str, submission: InsightSubmission):
            await self.broker.save_insight(request_id, submission.client_id, submission.sanitized_insight)
            return {"status": "success"}

        @self.app.get("/api/v1/query/{request_id}/consensus")
        async def get_consensus(request_id: str):
            insights = await self.broker.get_consensus(request_id)
            return {"request_id": request_id, "consensus_data": insights}

    async def start(self, host: str, port: int):
        config = uvicorn.Config(self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()