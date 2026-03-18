import pandas as pd
import requests
from io import StringIO
from app.config import URL

def fetch_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
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

    return df
