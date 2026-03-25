import os
import sqlite3
import pandas as pd
import requests
from io import StringIO

DB_PATH = "data/pension.db"
URL = "https://www.zwitserleven.nl/over-zwitserleven/verantwoord-beleggen/fondsen/"

def fetch_data():
    print("🌐 Fetching data...")

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))

    df = tables[0][["Fonds", "Datum", "Koers"]]

    # Clean prijs
    df["Koers"] = (
        df["Koers"]
        .astype(str)
        .str.replace("€", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.strip()
        .astype(float)
    )

    # Datum fix
    df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True)

    print(f"✅ {len(df)} records opgehaald")
    return df

def save_to_db(df):
    os.makedirs("data", exist_ok=True)

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

    new_date = df["Datum"].iloc[0].strftime("%Y-%m-%d")

    cur.execute("SELECT MAX(date) FROM prices")
    last_date = cur.fetchone()[0]

    print("Laatste datum in DB:", last_date)
    print("Nieuwe datum:", new_date)

    if last_date == new_date:
        print("⏭️ Data al aanwezig — skip")
    else:
        print("➕ Nieuwe data toevoegen")
        for _, row in df.iterrows():
            cur.execute(
                "INSERT OR IGNORE INTO prices (date, fund, price) VALUES (?, ?, ?)",
                (new_date, row["Fonds"], float(row["Koers"]))
            )
        conn.commit()
        print(f"✅ {len(df)} records toegevoegd")

    conn.close()

def main():
    print("🔥 SCRAPER START 🔥")
    df = fetch_data()
    save_to_db(df)
    print("🎉 SCRAPER KLAAR")

if __name__ == "__main__":
    main()
