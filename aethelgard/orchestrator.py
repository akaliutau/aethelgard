from aethelgard.core.transport import BaseServerTransport

class FedRagOrchestrator:
    """The central routing layer. Technology-agnostic."""
    def __init__(self, transport: BaseServerTransport):
        self.transport = transport

    async def run(self, host: str = "0.0.0.0", port: int = 8000):
        print(f"🛡️ Booting Aethelgard Orchestrator on {host}:{port}")
        await self.transport.start(host, port)