from datetime import datetime
import sqlite3
from app.config import DB_PATH
from pipeline.scraper import fetch_data
from pipeline.database import init_db

def run():
    init_db()
    df = fetch_data()
    today = datetime.today().strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    rows = [(today, r["Fonds"], float(r["Koers"])) for _, r in df.iterrows()]

    cur.executemany(
        "INSERT OR IGNORE INTO prices VALUES (?, ?, ?)",
        rows
    )

    conn.commit()
    conn.close()

if __name__ == "__main__":
    run()
