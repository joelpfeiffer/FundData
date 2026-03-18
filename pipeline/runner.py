# =========================
# FIX IMPORT PATH
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
import pandas as pd

from pipeline.scraper import fetch_data
from pipeline.database import init_db

# =========================
# CONFIG (LOS van app!)
# =========================
DB_PATH = "data/pension.db"
CSV_PATH = "data/prices.csv"

# =========================
# MAIN RUNNER
# =========================
def run():
    print("=== START PIPELINE ===")

    # Zorg dat data map bestaat
    os.makedirs("data", exist_ok=True)

    # Init DB
    init_db()

    # Data ophalen
    df = fetch_data()

    today = df["Datum"].iloc[0].strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Check laatste datum
    cur.execute("SELECT MAX(date) FROM prices")
    result = cur.fetchone()[0]

    print("Laatste datum:", result)
    print("Nieuwe datum:", today)

    # Insert alleen als nieuw
    if result != today:
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

    else:
        print("Data al up-to-date")

    # =========================
    # CSV EXPORT (ALTJD DOEN)
    # =========================
    export_df = pd.read_sql_query(
        "SELECT date, fund, price FROM prices ORDER BY date, fund",
        conn
    )

    export_df.to_csv(CSV_PATH, index=False)
    print("CSV bijgewerkt:", CSV_PATH)

    conn.close()
    print("=== EINDE PIPELINE ===")


# =========================
# ENTRY POINT
# =========================
if __name__ == "__main__":
    run()
