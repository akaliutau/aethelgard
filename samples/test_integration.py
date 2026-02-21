import asyncio
import httpx
import json
import random
import time

# --- Configuration ---
SERVER_URL = "http://localhost:8010"
TARGET_NODES = ["Hospital_A", "Hospital_B"]
VECTOR_DIMENSIONS = 1920  # Matches LanceDB (768 text + 1152 image)

# --- Polling Tuning ---
POLL_INTERVAL = 10  # Longer delay between checks (seconds)
MAX_ATTEMPTS = 4  # Fewer total checks (Max timeout = 40 seconds)


def print_insights(data: list, start_time: float, is_partial: bool = False):
    """Helper to cleanly format and print the consensus data."""
    elapsed = time.time() - start_time

    if is_partial:
        print(
            f"\n Timeout reached after {elapsed:.2f}s. Displaying partial results ({len(data)}/{len(TARGET_NODES)}):")
    else:
        print(f"\n Global Consensus Reached in {elapsed:.2f} seconds!")

    print("=" * 60)

    if not data:
        print("\nNo insights received from any node.")
    else:
        for item in data:
            node_id = item.get("client_id", "Unknown")
            insight_json_str = item.get("insight", "{}")

            print(f"\n Source: {node_id}")
            try:
                # Pretty-print the sanitized JSON returned by the Semantic Firewall
                parsed_insight = json.loads(insight_json_str)
                print(json.dumps(parsed_insight, indent=2))
            except json.JSONDecodeError:
                # Fallback if the firewall returned raw text
                print(insight_json_str)

    print("\n" + "=" * 60)


async def run_integration_test():
    print(f"Starting Aethelgard Integration Test...")
    print(f"Target Nodes: {', '.join(TARGET_NODES)}")

    # 1. Simulate the Multimodal Vector
    query_vector = [random.uniform(-1.0, 1.0) for _ in range(VECTOR_DIMENSIONS)]
    query_text = "What are the standard diuretic adjustment protocols for this presentation?"

    payload = {
        "query_text": query_text,
        "query_vector": query_vector,
        "target_clients": TARGET_NODES
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 2. Broadcast Query to the Orchestrator
        print("\n Broadcasting query to the Orchestrator...")
        start_time = time.time()

        try:
            broadcast_resp = await client.post(f"{SERVER_URL}/api/v1/query/broadcast", json=payload)
            broadcast_resp.raise_for_status()
        except httpx.RequestError as e:
            print(f"❌ Failed to connect to server: {e}")
            return

        req_id = broadcast_resp.json()["request_id"]
        print(f"✅ Broadcast successful! Request ID: {req_id}")

        # 3. Poll for Consensus
        print(f"\n Polling every {POLL_INTERVAL}s for global consensus...")

        data = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            await asyncio.sleep(POLL_INTERVAL)

            try:
                cons_resp = await client.get(f"{SERVER_URL}/api/v1/query/{req_id}/consensus")
                cons_resp.raise_for_status()
                data = cons_resp.json().get("consensus_data", [])
            except httpx.RequestError as e:
                print(f"   [Attempt {attempt}/{MAX_ATTEMPTS}] Error fetching consensus: {e}")
                continue

            print(f"   [Attempt {attempt}/{MAX_ATTEMPTS}] Received {len(data)}/{len(TARGET_NODES)} insights...")

            # 4. Success Condition
            if len(data) == len(TARGET_NODES):
                print_insights(data, start_time, is_partial=False)
                return

        # 5. Timeout Fallback (Prints partial data if available)
        print_insights(data, start_time, is_partial=True)


if __name__ == "__main__":
    asyncio.run(run_integration_test())