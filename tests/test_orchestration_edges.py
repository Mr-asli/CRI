import asyncio

import pytest

from cri.orchestration import Node, Orchestrator
from cri.orchestration.dag import CircuitBreaker


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(threshold=2)

    breaker.failure()
    assert breaker.open is False

    breaker.failure()
    assert breaker.open is True


def test_circuit_breaker_success_resets_state():
    breaker = CircuitBreaker(threshold=2)
    breaker.failure()
    breaker.failure()

    breaker.success()

    assert breaker.failures == 0
    assert breaker.open is False


def test_orchestrator_rejects_zero_concurrency():
    with pytest.raises(ValueError, match="max_concurrency"):
        Orchestrator(max_concurrency=0)


def test_dag_rejects_duplicate_node_names():
    async def noop():
        return None

    nodes = [Node("same", noop), Node("same", noop)]

    with pytest.raises(ValueError, match="duplicate node"):
        asyncio.run(Orchestrator().run(nodes))


def test_open_circuit_breaker_blocks_execution():
    async def task():
        return "should not run"

    orchestrator = Orchestrator()
    orchestrator.breaker.open = True

    with pytest.raises(RuntimeError, match="circuit breaker open"):
        asyncio.run(orchestrator._execute(Node("task", task)))


def test_failed_dependency_prevents_dependent_execution():
    executed = []

    async def fail():
        raise ValueError("expected failure")

    async def dependent():
        executed.append("dependent")

    nodes = [
        Node("first", fail),
        Node("second", dependent, depends_on=("first",)),
    ]

    with pytest.raises(RuntimeError, match="node failed: first"):
        asyncio.run(Orchestrator().run(nodes))

    assert executed == []


def test_node_rejects_invalid_execution_parameters():
    async def noop():
        return None

    with pytest.raises(ValueError, match="retries"):
        Node("x", noop, retries=-1)
    with pytest.raises(ValueError, match="timeout"):
        Node("x", noop, timeout=0)
    with pytest.raises(ValueError, match="callable"):
        Node("x", None)


def test_orchestrator_rejects_invalid_limits():
    with pytest.raises(ValueError, match="max_concurrency"):
        Orchestrator(max_concurrency=129)
    with pytest.raises(ValueError, match="backoff"):
        Orchestrator(backoff=-1)


def test_empty_dag_returns_empty_result():
    assert asyncio.run(Orchestrator().run([])) == {}


def test_orchestrator_rejects_non_node_entries():
    with pytest.raises(ValueError, match="Node instances"):
        asyncio.run(Orchestrator().run([object()]))
