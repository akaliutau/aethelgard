import pytest
from aethelgard.brokers.in_memory import InMemoryBroker


@pytest.fixture
def broker():
    """Provides a fresh instance of the broker for each test."""
    return InMemoryBroker()


async def test_enqueue_and_dequeue(broker):
    """Tests that a node can enqueue a task and the client can pull it."""
    client_id = "Hospital_A"
    req_id = "req_123"
    vector = [0.1, 0.2, 0.3]

    # 1. Enqueue a query
    await broker.enqueue_query(client_id, req_id, vector)

    # 2. Dequeue the query
    tasks = await broker.dequeue_queries(client_id)

    assert len(tasks) == 1
    assert tasks[0]["request_id"] == req_id
    assert tasks[0]["query_vector"] == vector


async def test_dequeue_clears_queue(broker):
    """Tests that polling clears the queue to prevent duplicate processing."""
    client_id = "Hospital_A"
    await broker.enqueue_query(client_id, "req_123", [0.1])

    # First pull should return the task
    first_pull = await broker.dequeue_queries(client_id)
    assert len(first_pull) == 1

    # Second pull should be empty since the queue was cleared by the first pull
    second_pull = await broker.dequeue_queries(client_id)
    assert len(second_pull) == 0