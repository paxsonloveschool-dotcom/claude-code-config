"""JARVIS global task registry — SQLite backend, stdlib only, thread-safe."""
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".claude" / "jarvis" / "tasks.db"
_SCHEMA = Path(__file__).parent / "schema.sql"
_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(_SCHEMA.read_text())
        _conn.commit()
    return _conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    return dict(row) if row else None


def claim_task(
    objective: str,
    owner: str,
    source: str,
    expected_output: Optional[str] = None,
    priority: int = 3,
) -> str:
    task_id = str(uuid.uuid4())
    now = _now()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO tasks
               (task_id, objective, owner, status, priority, source,
                created_at, updated_at, expected_output)
               VALUES (?, ?, ?, 'IN_PROGRESS', ?, ?, ?, ?, ?)""",
            (task_id, objective, owner, priority, source, now, now, expected_output),
        )
        conn.commit()
    return task_id


def check_duplicate(objective_keywords: list[str]) -> Optional[dict]:
    """Return an active task if any keyword appears in its objective."""
    with _lock:
        conn = _get_conn()
        for kw in objective_keywords:
            row = conn.execute(
                "SELECT * FROM tasks WHERE status = 'IN_PROGRESS' AND lower(objective) LIKE ?",
                (f"%{kw.lower()}%",),
            ).fetchone()
            if row:
                return _row_to_dict(row)
    return None


def _update_task(task_id: str, **fields):
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    with _lock:
        conn = _get_conn()
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE task_id = ?", values)
        conn.commit()


def complete_task(task_id: str, result: str, evidence: str):
    _update_task(task_id, status="COMPLETED", result=result, evidence=evidence)


def block_task(task_id: str, reason: str):
    _update_task(task_id, status="BLOCKED", result=reason)


def fail_task(task_id: str, reason: str):
    _update_task(task_id, status="FAILED", result=reason)


def get_task(task_id: str) -> Optional[dict]:
    with _lock:
        row = _get_conn().execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
    return _row_to_dict(row)


def list_tasks(status: Optional[str] = None, owner: Optional[str] = None, limit: int = 20) -> list[dict]:
    query = "SELECT * FROM tasks"
    params = []
    clauses = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if owner:
        clauses.append("owner = ?")
        params.append(owner)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with _lock:
        rows = _get_conn().execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


if __name__ == "__main__":
    tid = claim_task("smoke test", owner="test", source="__main__", expected_output="ok")
    complete_task(tid, result="passed", evidence="direct run")
    count = len(list_tasks())
    print(f"JARVIS registry OK — {count} task(s) in {DB_PATH}")
