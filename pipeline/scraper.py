import requests
import pandas as pd
from io import StringIO
from app.config import URL

def fetch_data():
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "nl-NL,nl;q=0.9"
    }

    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    try:
        tables = pd.read_html(StringIO(response.text))
    except ValueError:
        raise ValueError("Geen tabellen gevonden op pagina")

    df = None

    for table in tables:
        cols = [str(c).lower() for c in table.columns]

        if any("fonds" in c for c in cols) and any("koers" in c for c in cols):
            df = table
            break

    if df is None:
        raise ValueError("Geen juiste tabel gevonden")

    # Kolomnamen vinden
    fund_col = [c for c in df.columns if "fonds" in str(c).lower()][0]
    price_col = [c for c in df.columns if "koers" in str(c).lower()][0]

    df = df[[fund_col, price_col]]
    df.columns = ["Fonds", "Koers"]

    df["Koers"] = pd.to_numeric(df["Koers"], errors="coerce")
    df = df.dropna()

    if df.empty:
        raise ValueError("Dataframe is leeg na parsing")

    return df
