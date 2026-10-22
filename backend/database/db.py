import sqlite3
import os
from pathlib import Path

DB_PATH = os.environ.get(
    'SQLITE_DB_PATH',
    str(Path(__file__).resolve().parent.parent / 'devfix.db')
)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            language TEXT NOT NULL,
            code TEXT NOT NULL,
            traceback TEXT NOT NULL,
            context TEXT,
            workflow_status TEXT DEFAULT 'diagnosis',
            verification_status TEXT DEFAULT 'in_progress',
            diagnosis_json TEXT,
            proposed_fix_json TEXT,
            verification_json TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
