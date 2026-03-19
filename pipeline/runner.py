import pandas as pd
import sqlite3
import os

# =========================
# CONFIG
# =========================
DB_PATH = "data/pension.db"
CSV_PATH = "data/prices.csv"
BACKUP_PATH = "data/prices_backup_auto.csv"

# =========================
# LOAD DATA UIT DATABASE
# =========================
def load_from_db():
    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT date, fund, price
    FROM prices
    """

    df = pd.read_sql(query, conn)
    conn.close()

    return df

# =========================
# MAIN
# =========================
def main():
    print("🔄 Start export pipeline...")

    # nieuwe data uit database
    new_df = load_from_db()

    if new_df.empty:
        print("⚠️ Geen data uit database")
        return

    # zorg voor juiste types
    new_df["date"] = pd.to_datetime(new_df["date"], errors="coerce")
    new_df = new_df.dropna(subset=["date", "fund", "price"])

    print(f"📥 Nieuwe records: {len(new_df)}")

    # =========================
    # BESTAANDE CSV INLADEN
    # =========================
    if os.path.exists(CSV_PATH):
        old_df = pd.read_csv(CSV_PATH)

        old_df["date"] = pd.to_datetime(old_df["date"], errors="coerce")
        old_df = old_df.dropna(subset=["date", "fund", "price"])

        print(f"📦 Bestaande records: {len(old_df)}")

        # =========================
        # MERGE + DEDUPE
        # =========================
        combined = pd.concat([old_df, new_df])

        combined = combined.drop_duplicates(
            subset=["date", "fund"],
            keep="last"
        )

    else:
        print("🆕 Geen bestaande CSV gevonden")
        combined = new_df

    # =========================
    # SORTEREN
    # =========================
    combined = combined.sort_values("date")

    # =========================
    # OPSLAAN
    # =========================
    combined.to_csv(CSV_PATH, index=False)

    print(f"✅ CSV geüpdatet: {CSV_PATH}")

    # =========================
    # BACKUP (AUTOMATISCH)
    # =========================
    combined.to_csv(BACKUP_PATH, index=False)

    print(f"💾 Backup opgeslagen: {BACKUP_PATH}")

    # =========================
    # EXTRA CHECKS
    # =========================
    print("📊 Samenvatting:")
    print(f"   Totaal records: {len(combined)}")
    print(f"   Datum range: {combined['date'].min()} → {combined['date'].max()}")
    print(f"   Aantal fondsen: {combined['fund'].nunique()}")

    print("🎉 Pipeline succesvol afgerond!")

# =========================
# RUN
# =========================
if __name__ == "__main__":
    main()