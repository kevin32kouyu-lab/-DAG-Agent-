import asyncio
from dataclasses import dataclass, field
from src.dag.models import DAGNode


@dataclass
class TaskQueue:
    _queue: asyncio.PriorityQueue = field(default_factory=asyncio.PriorityQueue)

    async def enqueue(self, node: DAGNode) -> None:
        await self._queue.put((node.priority, node.node_id, node))

    async def dequeue(self) -> DAGNode:
        _, _, node = await self._queue.get()
        return node

    def size(self) -> int:
        return self._queue.qsize()
