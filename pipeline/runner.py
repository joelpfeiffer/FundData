import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import sqlite3
import pandas as pd
from pipeline.scraper import fetch_data
from pipeline.database import init_db

DB_PATH = "data/pension.db"
CSV_PATH = "data/prices.csv"


def run():
    print("=== START PIPELINE ===")

    os.makedirs("data", exist_ok=True)
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

    export_df = pd.read_sql_query(
        "SELECT date, fund, price FROM prices ORDER BY date, fund",
        conn
    )

    export_df.to_csv(CSV_PATH, index=False)
    print("CSV bijgewerkt:", CSV_PATH)

    conn.close()
    print("=== EINDE PIPELINE ===")


if __name__ == "__main__":
    run()
