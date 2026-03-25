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
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    print("🌐 Selenium scrape...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.get("https://www.zwitserleven.nl/over-zwitserleven/verantwoord-beleggen/fondsen/")

    wait = WebDriverWait(driver, 20)

    # wacht tot tabel zichtbaar is
    wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "tr.fundoverview__item"))
    )

    # 🔥 WACHT TOT NIEUWE DATA ER IS
    wait.until(
        lambda d: any(
            "2026" in el.text and "24-03" in el.text
            for el in d.find_elements(By.CSS_SELECTOR, "td.fundoverview__date")
        )
    )

    rows = driver.find_elements(By.CSS_SELECTOR, "tr.fundoverview__item")

    data = []

    for row in rows:
        fund = row.find_element(By.CSS_SELECTOR, "td.fundoverview__fund a").text
        date = row.find_element(By.CSS_SELECTOR, "td.fundoverview__date").text
        price = row.find_element(By.CSS_SELECTOR, "td.fundoverview__rate").text

        price = (
            price.replace("€", "")
            .replace("\xa0", "")
            .replace(",", ".")
            .strip()
        )

        data.append({
            "fund": fund,
            "date": date,
            "price": float(price)
        })

    driver.quit()

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True)

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
