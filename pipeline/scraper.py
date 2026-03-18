import requests
import pandas as pd
from io import StringIO
from app.config import URL

def fetch_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))

    for table in tables:
        if "Fonds" in table.columns:
            df = table
            break
    else:
        raise ValueError("Geen juiste tabel gevonden")

    df = df[["Fonds", "Koers"]]
    df["Koers"] = pd.to_numeric(df["Koers"], errors="coerce")
    df = df.dropna()

    return df
