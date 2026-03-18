# =========================
# FIX IMPORT PATH (belangrijk voor GitHub Actions)
# =========================
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

# =========================
# LIBRARIES
# =========================
import requests
import pandas as pd
from io import StringIO

from app.config import URL

# =========================
# FETCH DATA
# =========================
def fetch_data():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))

    if not tables:
        raise ValueError("Geen tabellen gevonden")

    df = tables[0]

    # Check of kolommen bestaan
    expected_cols = ["Fonds", "Datum", "Koers"]
    for col in expected_cols:
        if col not in df.columns:
            raise ValueError(f"Kolom ontbreekt: {col}")

    df = df[["Fonds", "Datum", "Koers"]].copy()

    # =========================
    # DATA CLEANING
    # =========================
    df["Koers"] = (
        df["Koers"]
        .astype(str)
        .str.replace("€", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.replace("\xa0", "", regex=False)
        .str.strip()
    )

    df["Koers"] = pd.to_numeric(df["Koers"], errors="coerce")

    df["Datum"] = pd.to_datetime(df["Datum"], dayfirst=True, errors="coerce")

    # Drop slechte rijen
    df = df.dropna()

    if df.empty:
        raise ValueError("Dataframe leeg na cleaning")

    return df
