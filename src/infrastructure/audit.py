import json
import sqlite3
from datetime import datetime
from typing import Any


class AuditLogger:
    def __init__(self, db_path: str = "data/audit.db"):
        import os
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS task_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL, node_id TEXT NOT NULL,
                agent_type TEXT NOT NULL, event TEXT NOT NULL,
                data TEXT DEFAULT '{}', timestamp TEXT NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS step_traces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL, node_id TEXT NOT NULL, agent_type TEXT NOT NULL,
                step_number INTEGER NOT NULL, phase TEXT NOT NULL,
                summary TEXT DEFAULT '', reasoning TEXT DEFAULT '',
                action TEXT DEFAULT '', params TEXT DEFAULT '{}',
                tokens INTEGER DEFAULT 0, cost REAL DEFAULT 0.0,
                nodes_created TEXT DEFAULT '[]', edges_created TEXT DEFAULT '[]',
                timestamp TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def log_event(self, task_id: str, node_id: str, agent_type: str,
                  event: str, data: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            "INSERT INTO task_audit_log (task_id, node_id, agent_type, event, data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, node_id, agent_type, event, json.dumps(data or {}), datetime.now().isoformat()),
        )
        self._conn.commit()

    def log_step_trace(self, trace) -> None:
        self._conn.execute(
            "INSERT INTO step_traces (task_id, node_id, agent_type, step_number, phase, summary, reasoning, action, params, tokens, cost, nodes_created, edges_created, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (trace.task_id, trace.node_id, trace.agent_type, trace.step_number,
             "act" if trace.action and trace.action != "finalize" else "think",
             trace.observation_summary or "", trace.reasoning or "",
             trace.action or "", json.dumps(trace.action_params or {}),
             trace.llm_tokens, trace.llm_cost,
             json.dumps(trace.nodes_created), json.dumps(trace.edges_created),
             trace.timestamp.isoformat() if trace.timestamp else datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_task_log(self, task_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM task_audit_log WHERE task_id = ? ORDER BY timestamp", (task_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_task_events(self, task_id: str, event: str | None = None) -> list[dict]:
        if event is None:
            rows = self._conn.execute(
                "SELECT * FROM task_audit_log WHERE task_id = ? ORDER BY timestamp", (task_id,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM task_audit_log WHERE task_id = ? AND event = ? ORDER BY timestamp",
                (task_id, event),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_step_traces(self, task_id: str, node_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM step_traces WHERE task_id = ? AND node_id = ? ORDER BY step_number",
            (task_id, node_id),
        ).fetchall()
        return [dict(r) for r in rows]
