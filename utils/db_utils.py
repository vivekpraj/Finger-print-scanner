import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "fingerprints.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # create users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            gender TEXT,
            extra TEXT,
            timestamp TEXT
        )
    """)
    # create captures table
    c.execute("""
        CREATE TABLE IF NOT EXISTS captures (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            finger_label TEXT,
            capture_idx INTEGER,
            file_path TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    conn.commit()
    conn.close()
