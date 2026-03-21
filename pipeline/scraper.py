import pandas as pd
import numpy as np
import os
from datetime import datetime

DATA_PATH = "data/prices.csv"
BACKUP_PATH = "data/prices_backup_auto.csv"

# =========================
# MOCK FETCH (VERVANG DIT)
# =========================
def fetch_data():
    """
    Vervang dit met jouw echte data bron
    """
    today = pd.Timestamp.today().normalize()

    data = [
        {"date": today, "fund": "Fund A", "price": 100 + np.random.rand()},
        {"date": today, "fund": "Fund B", "price": 200 + np.random.rand()},
    ]

    return pd.DataFrame(data)

# =========================
# LOAD BESTAANDE DATA
# =========================
def load_existing():
    if not os.path.exists(DATA_PATH):
        print("Geen bestaande data gevonden → nieuwe file")
        return pd.DataFrame(columns=["date","fund","price"])

    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df

# =========================
# BACKUP (OVERSCHRIJFT AUTO FILE)
# =========================
def backup_data(df):
    df.to_csv(BACKUP_PATH, index=False)
    print(f"Backup opgeslagen in: {BACKUP_PATH}")

# =========================
# MAIN PIPELINE
# =========================
def main():
    print("Start pipeline...")

    df_old = load_existing()
    print(f"Bestaande records: {len(df_old)}")

    df_new = fetch_data()
    print(f"Nieuwe records: {len(df_new)}")

    # =========================
    # SAFETY CHECK
    # =========================
    if df_new.empty:
        print("❌ Geen nieuwe data → STOP (voorkomt overschrijven)")
        return

    # =========================
    # CLEAN DATA
    # =========================
    df_new["date"] = pd.to_datetime(df_new["date"], errors="coerce")

    # =========================
    # BACKUP (BELANGRIJK!)
    # =========================
    if not df_old.empty:
        backup_data(df_old)

    # =========================
    # COMBINE
    # =========================
    df = pd.concat([df_old, df_new], ignore_index=True)
    print(f"Na concat: {len(df)}")

    # =========================
    # DEDUPE (CRUCIAAL)
    # =========================
    df = df.drop_duplicates(subset=["date","fund"])
    print(f"Na dedupe: {len(df)}")

    # =========================
    # SORT
    # =========================
    df = df.sort_values("date")

    # =========================
    # SAVE
    # =========================
    df.to_csv(DATA_PATH, index=False)
    print("✅ Data opgeslagen")

    print("Pipeline klaar.")

if __name__ == "__main__":
    main()