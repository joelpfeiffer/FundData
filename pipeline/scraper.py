import os
import sqlite3
import pandas as pd
import requests
from io import StringIO

# =========================
# CONFIG
# =========================
DB_PATH = "data/pension.db"
CSV_PATH = "data/prices.csv"
URL = "https://www.zwitserleven.nl/over-zwitserleven/verantwoord-beleggen/fondsen/"

# =========================
# FETCH DATA
# =========================
def fetch_data():
    print("🌐 Fetch data...")

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(URL, headers=headers, timeout=30)
    print("HTTP status:", response.status_code)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    print("Aantal tabellen:", len(tables))

    df = tables[0]

    # juiste kolommen
    df = df[["Fonds", "Datum", "Koers"]]

    # prijs cleanen
    df["Koers"] = (
        df["Koers"]
        .astype(str)
        .str.replace("€", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.strip()
        .astype(float)
    )

    # datum parsen
    df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True)

    # rename voor consistency
    df = df.rename(columns={
        "Fonds": "fund",
        "Datum": "date",
        "Koers": "price"
    })

    print("📊 Scrape resultaat:")
    print("Aantal records:", len(df))
    print("Max datum:", df["date"].max())

    return df


# =========================
# INIT DATABASE
# =========================
def init_db(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS prices (
        date TEXT,
        fund TEXT,
        price REAL,
        PRIMARY KEY (date, fund)
    )
    """)
    conn.commit()


# =========================
# INSERT DATA (ALLEEN NIEUWE DATUM)
# =========================
def insert_data(conn, df):
    cur = conn.cursor()

    # nieuwste datum uit scrape
    new_date = df["date"].max().strftime("%Y-%m-%d")

    # check laatste datum in DB
    cur.execute("SELECT MAX(date) FROM prices")
    result = cur.fetchone()[0]

    print("📅 Laatste datum DB:", result)
    print("📅 Nieuwe datum:", new_date)

    if result == new_date:
        print("⏭️ Datum bestaat al → geen insert")
        return 0

    print("➕ Nieuwe data toevoegen...")

    inserted = 0

    for _, row in df.iterrows():
        cur.execute(
            """
            INSERT OR IGNORE INTO prices (date, fund, price)
            VALUES (?, ?, ?)
            """,
            (
                row["date"].strftime("%Y-%m-%d"),
                row["fund"],
                float(row["price"])
            )
        )
        inserted += 1

    conn.commit()

    print(f"✅ Toegevoegd: {inserted} records")

    return inserted


# =========================
# EXPORT NAAR CSV
# =========================
def export_csv(conn):
    df = pd.read_sql_query(
        "SELECT date, fund, price FROM prices ORDER BY date, fund",
        conn
    )

    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    print("💾 CSV bijgewerkt:", CSV_PATH)
    print("Aantal regels:", len(df))


# =========================
# MAIN PIPELINE
# =========================
def main():
    print("🚀 START PIPELINE")

    # zorg dat map bestaat
    os.makedirs("data", exist_ok=True)

    # fetch
    df = fetch_data()

    if df.empty:
        print("❌ Geen data gevonden → STOP")
        return

    # connect DB
    conn = sqlite3.connect(DB_PATH)

    # init table
    init_db(conn)

    # insert
    insert_data(conn, df)

    # export
    export_csv(conn)

    conn.close()

    print("🎉 PIPELINE KLAAR")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()
