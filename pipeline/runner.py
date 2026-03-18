# =========================
# FIX IMPORT PATH (BELANGRIJK)
# =========================
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# =========================
# LIBRARIES
# =========================
import sqlite3
from datetime import datetime

from app.config import DB_PATH
from pipeline.scraper import fetch_data
from pipeline.database import init_db

# =========================
# MAIN RUNNER
# =========================
def run():
    print("=== START PIPELINE ===")

    # Zorg dat DB bestaat
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()

    # Data ophalen
    df = fetch_data()

    today = df["Datum"].iloc[0].strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check laatste datum
    cur.execute("SELECT MAX(date) FROM prices")
    result = cur.fetchone()[0]

    print("Laatste datum in DB:", result)
    print("Nieuwe datum:", today)

    if result == today:
        print("Data al up-to-date")
    else:
        print("Nieuwe data toevoegen...")

        rows = [
            (today, row["Fonds"], float(row["Koers"]))
            for _, row in df.iterrows()
        ]

        cur.executemany(
            "INSERT OR IGNORE INTO prices (date, fund, price) VALUES (?, ?, ?)",
            rows
        )

        conn.commit()
        print(f"{len(rows)} records toegevoegd")

    conn.close()
    print("=== EINDE PIPELINE ===")


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    run()
