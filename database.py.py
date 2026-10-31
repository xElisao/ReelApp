# database.py
import sqlite3

DB_FILE = "velocut_users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            is_pro INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def add_pro_user(email: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (email, is_pro) VALUES (?, 1)
        ON CONFLICT(email) DO UPDATE SET is_pro=1
    """, (email.strip().lower(),))
    conn.commit()
    conn.close()

def check_user_is_pro(email: str) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT is_pro FROM users WHERE email = ?", (email.strip().lower(),))
    result = cursor.fetchone()
    conn.close()
    return result is not None and result[0] == 1