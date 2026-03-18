import sqlite3
from app.config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            date TEXT,
            fund TEXT,
            price REAL,
            PRIMARY KEY (date, fund)
        )
    """)
    conn.commit()
    conn.close()
