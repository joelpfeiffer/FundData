import sys
import os

# FIX PATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import sqlite3
from datetime import datetime

DB_PATH = "data/pension.db"
from pipeline.scraper import fetch_data
from pipeline.database import init_db


def run():
    print("=== START PIPELINE ===")

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()

    df = fetch_data()
    today = df["Datum"].iloc[0].strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT MAX(date) FROM prices")
    result = cur.fetchone()[0]

    print("Laatste datum:", result)
    print("Nieuwe datum:", today)

    if result != today:
        rows = [
            (today, row["Fonds"], float(row["Koers"]))
            for _, row in df.iterrows()
        ]

        cur.executemany(
            "INSERT OR IGNORE INTO prices VALUES (?, ?, ?)",
            rows
        )

        conn.commit()
        print(f"{len(rows)} records toegevoegd")
    else:
        print("Data al up-to-date")

    conn.close()
    print("=== EINDE PIPELINE ===")


if __name__ == "__main__":
    run()
