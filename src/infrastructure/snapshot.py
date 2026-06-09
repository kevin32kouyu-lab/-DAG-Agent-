import json
import sqlite3
from datetime import datetime
from src.dag.models import NodeSnapshot, NodeState


class SnapshotStore:
    def __init__(self, db_path: str = "data/snapshots.db"):
        import os
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                task_id TEXT NOT NULL, node_id TEXT NOT NULL,
                state TEXT NOT NULL, kg_changeset TEXT DEFAULT '{}',
                checkpoint_time TEXT NOT NULL, llm_cost REAL DEFAULT 0.0,
                PRIMARY KEY (task_id, node_id)
            )
        """)
        self._conn.commit()

    def save(self, snapshot: NodeSnapshot) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?, ?)",
            (snapshot.task_id, snapshot.node_id, snapshot.state.value,
             json.dumps(snapshot.kg_changeset),
             snapshot.checkpoint_time.isoformat(), snapshot.llm_cost),
        )
        self._conn.commit()

    def load(self, task_id: str) -> dict[str, NodeSnapshot] | None:
        rows = self._conn.execute(
            "SELECT * FROM snapshots WHERE task_id = ?", (task_id,)
        ).fetchall()
        if not rows:
            return None
        return {
            r["node_id"]: NodeSnapshot(
                task_id=r["task_id"], node_id=r["node_id"],
                state=NodeState(r["state"]),
                kg_changeset=json.loads(r["kg_changeset"]),
                checkpoint_time=datetime.fromisoformat(r["checkpoint_time"]),
                llm_cost=r["llm_cost"],
            )
            for r in rows
        }

    def clear(self, task_id: str) -> None:
        self._conn.execute("DELETE FROM snapshots WHERE task_id = ?", (task_id,))
        self._conn.commit()
