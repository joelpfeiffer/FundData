import pandas as pd
import requests
from bs4 import BeautifulSoup
import os

DATA_PATH = "data/prices.csv"
BACKUP_PATH = "data/prices_backup_auto.csv"
URL = "https://www.zwitserleven.nl/over-zwitserleven/verantwoord-beleggen/fondsen/"

# =========================
# FETCH DATA (FIXED)
# =========================
def fetch_data():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    res = requests.get(URL, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")

    data = []

    rows = soup.select("tr.fundoverview__item")

    for row in rows:
        try:
            fund = row.select_one("td.fundoverview__fund a").get_text(strip=True)
            date = row.select_one("td.fundoverview__date").get_text(strip=True)
            price = row.select_one("td.fundoverview__rate").get_text(strip=True)

            # prijs schoonmaken
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

        except Exception as e:
            print("⚠️ Fout bij rij:", e)

    df = pd.DataFrame(data)

    # Europese datum parsing
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")

    print("📊 Scrape resultaat:")
    print(df.head())
    print("Max datum:", df["date"].max())
    print("Aantal rows:", len(df))

    return df


# =========================
# LOAD BESTAANDE DATA
# =========================
def load_existing():
    if not os.path.exists(DATA_PATH):
        print("Geen bestaande data → nieuwe dataset")
        return pd.DataFrame(columns=["date", "fund", "price"])

    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


# =========================
# BACKUP
# =========================
def backup_data(df):
    df.to_csv(BACKUP_PATH, index=False)
    print(f"💾 Backup opgeslagen: {BACKUP_PATH}")


# =========================
# MAIN PIPELINE
# =========================
def main():
    print("🚀 Start pipeline...")

    df_old = load_existing()
    print(f"Bestaande records: {len(df_old)}")

    df_new = fetch_data()
    print(f"Nieuwe records (scrape): {len(df_new)}")

    if df_new.empty:
        print("❌ Geen nieuwe data → STOP")
        return

    # backup
    if not df_old.empty:
        backup_data(df_old)

    # =========================
    # COMBINE + UPDATE LOGIC
    # =========================
    df = pd.concat([df_old, df_new], ignore_index=True)

    print("Na concat:", len(df))

    # sorteren zodat nieuwste onderaan staat
    df = df.sort_values("date")

    # 🔥 BELANGRIJK: overschrijf oude met nieuwe
    df = df.drop_duplicates(subset=["date", "fund"], keep="last")

    print("Na dedupe:", len(df))

    # =========================
    # SAVE
    # =========================
    df.to_csv(DATA_PATH, index=False)
    print("✅ Data opgeslagen")

    # =========================
    # SAMENVATTING
    # =========================
    print("\n📈 Samenvatting:")
    print("Totaal records:", len(df))
    print("Datum range:", df["date"].min(), "→", df["date"].max())
    print("Aantal fondsen:", df["fund"].nunique())

    print("\n🎉 Pipeline succesvol afgerond!")


if __name__ == "__main__":
    main()
