CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT PRIMARY KEY,
    objective       TEXT NOT NULL,
    owner           TEXT DEFAULT 'unowned',
    status          TEXT DEFAULT 'PENDING',
    priority        INTEGER DEFAULT 3,
    source          TEXT,
    created_at      TEXT,
    updated_at      TEXT,
    expected_output TEXT,
    result          TEXT,
    evidence        TEXT,
    dependencies    TEXT
);
