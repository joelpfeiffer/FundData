import sqlite3
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

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
