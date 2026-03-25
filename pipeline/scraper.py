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
    import pandas as pd
    import requests
    from io import StringIO

    print("🌐 Fetch data...")

    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36",
        "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.zwitserleven.nl/"
    }

    session.headers.update(headers)

    res = session.get(URL, timeout=30)
    print("HTTP status:", res.status_code)

    html = res.text

    # 🔥 CRUCIALE DEBUG
    print("24-03 in HTML:", "24-03-2026" in html)

    tables = pd.read_html(StringIO(html))
    df = tables[0]

    df = df[["Fonds", "Datum", "Koers"]]

    df["Koers"] = (
        df["Koers"]
        .astype(str)
        .str.replace("€", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.strip()
        .astype(float)
    )

    df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True)

    df = df.rename(columns={
        "Fonds": "fund",
        "Datum": "date",
        "Koers": "price"
    })

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
