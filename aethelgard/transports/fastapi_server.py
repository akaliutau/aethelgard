import uuid
from typing import List

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, Field

from aethelgard.core.broker import BaseTaskBroker
from aethelgard.core.config import get_logger

# Configure module-level logger
logger = get_logger(__name__)


# ==========================================
# 1. Pydantic Data Models
# ==========================================
class ClinicalQuery(BaseModel):
    query_text: str = Field(..., description="Human-readable text of the query")
    query_vector: List[float] = Field(..., description="Fused embedding vector (e.g., text + image)")
    target_clients: List[str] = Field(..., description="List of hospital client IDs to poll this query")


class InsightSubmission(BaseModel):
    client_id: str
    sanitized_insight: str = Field(..., description="The JSON string sanitized by the local Semantic Firewall")


class AckSubmission(BaseModel):
    client_id: str = Field(..., description="The ID of the node acknowledging the task")


# ==========================================
# 2. Unified FastAPI Orchestrator Server
# ==========================================
class FastAPIServer:
    """
    Unified Orchestrator and REST API transport.
    Replaces both BaseServerTransport and FedRagOrchestrator.
    """

    def __init__(self, broker: BaseTaskBroker):
        self.broker = broker
        self.app = FastAPI(
            title="Aethelgard SuperLink Orchestrator",
            version="0.2.0",
            description="Federated RAG centralized routing and consensus API."
        )
        self._setup_routes()

    def _setup_routes(self):
        """Maps HTTP endpoints to the underlying Broker logic."""

        @self.app.post("/api/v1/query/broadcast", status_code=202)
        async def broadcast_query(query: ClinicalQuery):
            """1. Drops a new query into the target clients' queues."""
            request_id = str(uuid.uuid4())
            logger.info(f"Broadcasting query {request_id} to {len(query.target_clients)} clients.")

            for client in query.target_clients:
                await self.broker.enqueue_query(client, request_id, query.query_vector)

            return {"message": "Query broadcast initiated", "request_id": request_id}

        @self.app.get("/api/v1/client/{client_id}/poll")
        async def poll_tasks(client_id: str):
            """2. Client nodes poll this endpoint to pull pending tasks."""
            tasks = await self.broker.dequeue_queries(client_id)
            if tasks:
                logger.info(f"Client {client_id} pulled {len(tasks)} tasks.")
            return {"pending_tasks": tasks}

        @self.app.post("/api/v1/query/{request_id}/insight")
        async def submit_insight(request_id: str, submission: InsightSubmission):
            """3. Client nodes push successfully sanitized insights here[cite: 157]."""
            logger.info(f"Received insight for {request_id} from {submission.client_id}.")
            await self.broker.save_insight(request_id, submission.client_id, submission.sanitized_insight)
            return {"status": "success"}

        @self.app.post("/api/v1/query/{request_id}/ack")
        async def ack_task(request_id: str, submission: AckSubmission):
            """4. REQUIRED: Clients acknowledge task completion to clear it from the processing queue."""
            logger.debug(f"Task {request_id} acknowledged by {submission.client_id}.")
            await self.broker.ack(submission.client_id, request_id)
            return {"status": "success", "message": "ACK"}

        @self.app.get("/api/v1/query/{request_id}/consensus")
        async def get_consensus(request_id: str):
            """5. Requesters hit this to retrieve the aggregated insights."""
            insights = await self.broker.get_consensus(request_id)
            return {"request_id": request_id, "consensus_data": insights}

    async def run(self, host: str = "0.0.0.0", port: int = 8010):
        """Starts the Uvicorn web server."""
        logger.info(f"🛡️ Booting Aethelgard FastAPI Server on {host}:{port}")

        try:
            await uvicorn.Server(
                config=uvicorn.Config(self.app, host=host, port=port, log_level="info")
            ).serve()
        except Exception as e:
            logger.critical(f"Server encountered a fatal error: {e}", exc_info=True)
            raise