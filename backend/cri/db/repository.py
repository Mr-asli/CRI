"""Synchronous repository boundary used by API services and unit tests."""
from __future__ import annotations
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import TaskRecord, AuditRecord, MemoryRecord

class SQLRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    def save_task(self, task_id: str, goal: str, status: str, proposal: dict | None = None):
        with self.sessions() as db:
            row = db.get(TaskRecord, task_id)
            if row is None:
                row = TaskRecord(id=task_id, goal=goal, status=status, proposal=proposal or {})
                db.add(row)
            else:
                row.goal, row.status, row.proposal = goal, status, proposal or {}
            db.commit()
            return row

    def get_task(self, task_id: str):
        with self.sessions() as db:
            return db.get(TaskRecord, task_id)

    def list_tasks(self, limit: int = 100):
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        with self.sessions() as db:
            return list(db.scalars(select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit)))

    def append_audit(self, event: str, actor: str, details: dict, previous_hash: str, event_hash: str):
        with self.sessions() as db:
            row = AuditRecord(event_id=uuid.uuid4().hex, event=event, actor=actor, details=details, previous_hash=previous_hash, event_hash=event_hash)
            db.add(row); db.commit(); return row

    def save_memory(self, kind: str, content: str, metadata: dict | None = None):
        with self.sessions() as db:
            row = MemoryRecord(id=uuid.uuid4().hex, kind=kind, content=content, metadata_json=metadata or {})
            db.add(row); db.commit(); return row

    def list_memory(self, limit: int = 200):
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        with self.sessions() as db:
            return list(db.scalars(select(MemoryRecord).order_by(MemoryRecord.created_at.desc()).limit(limit)))

    def save_embedding(self, memory_id: str, embedding: list[float]):
        import math
        if len(embedding) != 1536 or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in embedding):
            raise ValueError("embedding must contain exactly 1536 finite numeric values")
        try:
            from .models import MemoryEmbedding
        except ImportError as exc:
            raise RuntimeError("pgvector dependency is required for embeddings") from exc
        if MemoryEmbedding is None:
            raise RuntimeError("pgvector dependency is required for embeddings")
        with self.sessions() as db:
            row = db.get(MemoryEmbedding, memory_id)
            if row is None:
                row = MemoryEmbedding(memory_id=memory_id, embedding=embedding)
                db.add(row)
            else:
                row.embedding = embedding
            db.commit()
            return row

    def nearest_memories(self, embedding: list[float], limit: int = 10):
        import math
        if len(embedding) != 1536 or any(not isinstance(value, (int, float)) or not math.isfinite(value) for value in embedding):
            raise ValueError("embedding must contain exactly 1536 finite numeric values")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        from sqlalchemy import select
        from .models import MemoryEmbedding
        if MemoryEmbedding is None:
            raise RuntimeError("pgvector dependency is required for embeddings")
        with self.sessions() as db:
            statement = select(MemoryEmbedding).order_by(MemoryEmbedding.embedding.cosine_distance(embedding)).limit(limit)
            return list(db.scalars(statement))
