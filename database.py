"""SQLite 数据库管理"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

from models import WorkflowDefinition, ExecutionRecord


class WorkflowDatabase:
    """工作流数据库"""

    def __init__(self, db_path: str = "data/workflow.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    version INTEGER DEFAULT 1,
                    definition TEXT NOT NULL,
                    author TEXT,
                    tags TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS executions (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT REFERENCES workflows(id),
                    workflow_version INTEGER,
                    status TEXT DEFAULT 'pending',
                    inputs TEXT,
                    outputs TEXT,
                    node_executions TEXT,
                    started_at DATETIME,
                    completed_at DATETIME,
                    duration_ms REAL DEFAULT 0,
                    total_tokens INTEGER DEFAULT 0,
                    nodes_succeeded INTEGER DEFAULT 0,
                    nodes_failed INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_executions_workflow ON executions(workflow_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
            """)

    def save_workflow(self, workflow: WorkflowDefinition) -> str:
        """保存工作流定义"""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO workflows (id, name, description, version, definition, author, tags, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow.id, workflow.name, workflow.description, workflow.version,
                    json.dumps(workflow.model_dump(), ensure_ascii=False, default=str),
                    workflow.author, json.dumps(workflow.tags, ensure_ascii=False),
                    datetime.now().isoformat(),
                ),
            )
        return workflow.id

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """获取工作流定义"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
            if row:
                data = json.loads(row["definition"])
                return WorkflowDefinition(**data)
        return None

    def list_workflows(self, limit: int = 50) -> list[dict]:
        """列出所有工作流"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT id, name, description, version, author, tags, created_at, updated_at FROM workflows ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))
            return cursor.rowcount > 0

    def save_execution(self, record: ExecutionRecord) -> str:
        """保存执行记录"""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO executions (id, workflow_id, workflow_version, status, inputs, outputs,
                   node_executions, started_at, completed_at, duration_ms, total_tokens, nodes_succeeded, nodes_failed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.id, record.workflow_id, record.workflow_version, record.status.value,
                    json.dumps(record.inputs, ensure_ascii=False, default=str),
                    json.dumps(record.outputs, ensure_ascii=False, default=str),
                    json.dumps({k: v.model_dump() for k, v in record.node_executions.items()},
                              ensure_ascii=False, default=str),
                    record.started_at.isoformat() if record.started_at else None,
                    record.completed_at.isoformat() if record.completed_at else None,
                    record.duration_ms, record.total_tokens,
                    record.nodes_succeeded, record.nodes_failed,
                ),
            )
        return record.id

    def get_execution(self, execution_id: str) -> ExecutionRecord | None:
        """获取执行记录"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM executions WHERE id = ?", (execution_id,)).fetchone()
            if row:
                return ExecutionRecord(
                    id=row["id"],
                    workflow_id=row["workflow_id"],
                    workflow_version=row["workflow_version"],
                    status=row["status"],
                    inputs=json.loads(row["inputs"]) if row["inputs"] else {},
                    outputs=json.loads(row["outputs"]) if row["outputs"] else {},
                    started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                    completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    duration_ms=row["duration_ms"],
                    total_tokens=row["total_tokens"],
                    nodes_succeeded=row["nodes_succeeded"],
                    nodes_failed=row["nodes_failed"],
                )
        return None

    def list_executions(self, workflow_id: str = None, limit: int = 50) -> list[dict]:
        """列出执行记录"""
        with self._get_conn() as conn:
            if workflow_id:
                rows = conn.execute(
                    "SELECT * FROM executions WHERE workflow_id = ? ORDER BY created_at DESC LIMIT ?",
                    (workflow_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM executions ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._get_conn() as conn:
            workflow_count = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
            execution_count = conn.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
            success_count = conn.execute("SELECT COUNT(*) FROM executions WHERE status = 'success'").fetchone()[0]
            total_tokens = conn.execute("SELECT COALESCE(SUM(total_tokens), 0) FROM executions").fetchone()[0]
        return {
            "workflows": workflow_count,
            "executions": execution_count,
            "success_rate": f"{success_count/execution_count*100:.1f}%" if execution_count > 0 else "N/A",
            "total_tokens": total_tokens,
        }
