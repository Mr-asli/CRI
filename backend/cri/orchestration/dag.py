"""Deterministic DAG scheduler with bounded concurrency, retries and circuit breaking."""
import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

@dataclass
class Node:
    name: str
    run: Callable[[], Awaitable[Any]]
    depends_on: tuple[str, ...] = ()
    retries: int = 0
    timeout: float = 10.0

class CircuitBreaker:
    def __init__(self, threshold=3): self.threshold, self.failures, self.open = threshold, 0, False
    def success(self): self.failures, self.open = 0, False
    def failure(self):
        self.failures += 1
        if self.failures >= self.threshold: self.open = True

class Orchestrator:
    def __init__(self, max_concurrency=4, backoff=0.01):
        if max_concurrency < 1: raise ValueError("max_concurrency must be positive")
        self.max_concurrency, self.backoff = max_concurrency, backoff
        self.breaker = CircuitBreaker()
    def _validate(self, nodes):
        by_name = {n.name: n for n in nodes}
        if len(by_name) != len(nodes): raise ValueError("duplicate node")
        for node in nodes:
            if any(dep not in by_name for dep in node.depends_on): raise ValueError("unknown dependency")
        visiting, visited = set(), set()
        def visit(name):
            if name in visiting: raise ValueError("DAG cycle")
            if name in visited: return
            visiting.add(name)
            for dep in by_name[name].depends_on: visit(dep)
            visiting.remove(name); visited.add(name)
        for name in by_name: visit(name)
        return by_name
    async def _execute(self, node):
        if self.breaker.open: raise RuntimeError("circuit breaker open")
        for attempt in range(node.retries + 1):
            try:
                result = await asyncio.wait_for(node.run(), timeout=node.timeout)
                self.breaker.success(); return result
            except Exception:
                self.breaker.failure()
                if attempt >= node.retries: raise
                await asyncio.sleep(self.backoff * (2 ** attempt))
    async def run(self, nodes):
        by_name = self._validate(list(nodes)); results = {}; pending = set(by_name)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        async def limited(node):
            async with semaphore: return await self._execute(node)
        while pending:
            ready = sorted(n for n in pending if set(by_name[n].depends_on).issubset(results))
            if not ready: raise RuntimeError("DAG cannot make progress")
            batch = await asyncio.gather(*(limited(by_name[n]) for n in ready), return_exceptions=True)
            errors = [(name, value) for name, value in zip(ready, batch) if isinstance(value, BaseException)]
            if errors: raise RuntimeError(f"node failed: {errors[0][0]}") from errors[0][1]
            results.update(zip(ready, batch)); pending.difference_update(ready)
        return results
