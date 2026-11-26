import asyncio
import pytest
from cri.core import Audit, Kill, Policy, Denied
from cri.tools import ToolGateway, ToolSpec
from cri.agents import AgentFactory
from cri.orchestration import Node, Orchestrator


def setup(tmp_path):
    audit = Audit(tmp_path / "audit.jsonl")
    policy = Policy(audit)
    kill = Kill(tmp_path / "KILL")
    gateway = ToolGateway(policy, audit, kill)
    gateway.register(
        ToolSpec(
            "memory.write",
            "memory_write",
            frozenset({"memory"}),
            lambda p: {"text": p["text"]},
        )
    )
    return audit, policy, kill, gateway


def test_all_six_agents_have_role_checked_lifecycle(tmp_path):
    _, policy, _, gateway = setup(tmp_path)
    factory = AgentFactory(policy, gateway)
    expected = {
        "master": {"goal": "Build CRI"},
        "developer": {"specification": "safe proposal"},
        "research": {"question": "what is needed"},
        "testing": {"checks": ["unit"]},
        "auditor": {"invariants_violated": []},
        "memory": {"text": "safe note"},
    }
    for role, payload in expected.items():
        agent = factory.create_root(role, role)
        result = agent.execute("task-1", payload)
        assert result.status == "completed" and result.agent == role
        assert agent.history[-1] == result


def test_agent_factory_child_is_intersection(tmp_path):
    _, policy, _, gateway = setup(tmp_path)
    parent = policy.identity("parent", "research")
    child = AgentFactory(policy, gateway).create(parent, "child", "developer")
    assert child.identity.scopes == frozenset()
    with pytest.raises(Denied):
        child.gateway.invoke(child.identity, "memory.write", "memory", {"text": "x"})


def test_gateway_checks_kill_policy_and_resource(tmp_path):
    audit, policy, kill, gateway = setup(tmp_path)
    identity = policy.identity("mem", "memory")
    assert gateway.invoke(identity, "memory.write", "memory", {"text": "ok"}) == {
        "text": "ok"
    }
    with pytest.raises(Denied):
        gateway.invoke(identity, "memory.write", "other", {"text": "no"})
    kill.stop()
    with pytest.raises(RuntimeError):
        gateway.invoke(identity, "memory.write", "memory", {"text": "no"})


def test_dag_dependencies_and_parallel_nodes():
    seen = []

    async def step(x):
        seen.append(x)
        return x

    async def run():
        return await Orchestrator(max_concurrency=2).run(
            [
                Node("a", lambda: step("a")),
                Node("b", lambda: step("b")),
                Node("c", lambda: step("c"), ("a", "b")),
            ]
        )

    result = asyncio.run(run())
    assert result == {"a": "a", "b": "b", "c": "c"}
    assert seen.index("c") > seen.index("a") and seen.index("c") > seen.index("b")


def test_dag_rejects_cycle_and_missing_dependency():
    async def noop():
        return None

    orch = Orchestrator()
    with pytest.raises(ValueError):
        asyncio.run(orch.run([Node("a", noop, ("b",)), Node("b", noop, ("a",))]))
    with pytest.raises(ValueError):
        asyncio.run(orch.run([Node("a", noop, ("missing",))]))


def test_dag_retry_then_success():
    attempts = {"n": 0}

    async def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ValueError("transient")
        return "ok"

    assert asyncio.run(
        Orchestrator(backoff=0).run([Node("flaky", flaky, retries=1)])
    ) == {"flaky": "ok"}


def test_dag_timeout_and_failure():
    async def slow():
        await asyncio.sleep(0.02)

    with pytest.raises(RuntimeError):
        asyncio.run(Orchestrator(backoff=0).run([Node("slow", slow, timeout=0.001)]))
