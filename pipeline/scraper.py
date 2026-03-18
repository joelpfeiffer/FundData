import requests
from bs4 import BeautifulSoup
import pandas as pd
from app.config import URL

def fetch_data():
    headers = {
        "User-Agent": "Mozilla/5.0",
    }

    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Zoek alle rijen
    rows = soup.find_all("tr")

    data = []

    for row in rows:
        cols = row.find_all("td")

        if len(cols) >= 2:
            fund = cols[0].get_text(strip=True)
            price = cols[1].get_text(strip=True)

            # probeer prijs te parsen
            try:
                price = price.replace(",", ".")
                price = float(price)
                data.append((fund, price))
            except:
                continue

    if not data:
        raise ValueError("Geen data gevonden (site waarschijnlijk JS-based)")

    df = pd.DataFrame(data, columns=["Fonds", "Koers"])

    return df
