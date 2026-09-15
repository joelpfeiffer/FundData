# ============================================================
# FundData Multi Source Scraper
#
# Bronnen:
#   1. Zwitserleven - volledige fondsenpagina
#   2. Cardano       - waar een fonds daar beschikbaar is
#   3. prices.csv    - historische fallback
#
# Selectieregel:
#   NIEUWSTE KOERSDATUM WINT
#
# Bij gelijke datum:
#   Zwitserleven > Cardano > history
#
# Output:
#   data/prices.csv
#
# Kolommen:
#   date, fund, price
# ============================================================

from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

ZWITSERLEVEN_URL = (
    "https://www.zwitserleven.nl/"
    "over-zwitserleven/verantwoord-beleggen/fondsen/"
)

CARDANO_BASE_URL = (
    "https://www.cardano.nl/onze-fondsen/"
)

CSV_PATH = Path(
    os.getenv(
        "PRICES_CSV",
        "data/prices.csv"
    )
)

REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; "
        "FundDataBot/2.0; "
        "+https://github.com/joelpfeiffer/FundData)"
    )
}


# Bij gelijke koersdatum:
# Zwitserleven > Cardano > historische CSV

SOURCE_PRIORITY = {
    "zwitserleven": 100,
    "cardano": 90,
    "history": 0,
}


# ============================================================
# ALIASES
# ============================================================

# Rechterkant is altijd de CANONIEKE naam die in nieuwe
# regels van prices.csv moet worden gebruikt.

RAW_ALIASES = {

    # Oude Vanguard naam
    "Zwitserleven Vanguard US 500 Stock Index Fund":
        "Zwitserleven Vanguard US 500 Hedged",

    # Eventuele soft-hyphen variant
    "Zwitser­leven Vanguard US 500 Hedged":
        "Zwitserleven Vanguard US 500 Hedged",

    # Normale variant
    "Zwitserleven Vanguard US 500 Hedged":
        "Zwitserleven Vanguard US 500 Hedged",
}


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class FundQuote:

    fund: str
    quote_date: date
    price: float
    source: str
    original_name: str = ""
    source_url: str = ""


# ============================================================
# UNICODE / NAME NORMALIZATION
# ============================================================

def clean_unicode(value: str) -> str:
    """
    Maakt visueel gelijke fondsnamen technisch gelijk.

    Verwijdert o.a.:
    - soft hyphen U+00AD
    - zero width characters
    - non-breaking spaces
    - vreemde Unicode whitespace
    """

    if value is None:
        return ""

    value = str(value)

    # Unicode normaliseren
    value = unicodedata.normalize(
        "NFKC",
        value
    )

    # Unicode format/control chars verwijderen.
    # Hiermee verdwijnt bijvoorbeeld soft hyphen.
    value = "".join(
        char
        for char in value
        if unicodedata.category(char) != "Cf"
    )

    # Bekende bijzondere spaties
    value = (
        value
        .replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u2007", " ")
    )

    # Diverse streepjes uniform maken
    value = (
        value
        .replace("–", "-")
        .replace("—", "-")
        .replace("−", "-")
    )

    # Meervoudige whitespace verwijderen
    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def fund_key(value: str) -> str:
    """
    Interne vergelijkingssleutel.

    Bewust GEEN fuzzy matching.

    Daardoor worden bijvoorbeeld:

    Zwitserleven Vanguard US 500 Hedged

    en

    Zwitserleven PPI Vanguard US 500 Hedged

    nooit per ongeluk hetzelfde fonds.
    """

    value = clean_unicode(value)

    return value.casefold()


NORMALIZED_ALIASES = {
    fund_key(alias):
        clean_unicode(canonical)
    for alias, canonical
    in RAW_ALIASES.items()
}


def canonical_fund_name(
    name: str,
    historical_names: Optional[dict] = None
) -> str:

    cleaned = clean_unicode(name)
    key = fund_key(cleaned)

    # Expliciete alias heeft hoogste prioriteit
    if key in NORMALIZED_ALIASES:

        return NORMALIZED_ALIASES[key]

    # Bestaande naam uit prices.csv gebruiken
    # zodat hoofdletters/spelling stabiel blijven
    if (
        historical_names
        and key in historical_names
    ):

        return historical_names[key]

    return cleaned


# ============================================================
# PARSERS
# ============================================================

def parse_price(value) -> float:

    value = clean_unicode(str(value))

    value = (
        value
        .replace("€", "")
        .replace("EUR", "")
        .strip()
    )

    value = re.sub(
        r"[^\d,.\-]",
        "",
        value
    )

    if not value:

        raise ValueError(
            "Lege koerswaarde"
        )

    # Europees formaat:
    # 1.234,56 -> 1234.56

    if "," in value and "." in value:

        value = (
            value
            .replace(".", "")
            .replace(",", ".")
        )

    elif "," in value:

        value = value.replace(",", ".")

    return float(value)


def parse_date(value) -> date:

    parsed = pd.to_datetime(
        value,
        dayfirst=True,
        errors="raise"
    )

    return parsed.date()


# ============================================================
# HTTP
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


def get_html(url: str) -> str:

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.text


# ============================================================
# SOURCE 1 - ZWITSERLEVEN
# ============================================================

def scrape_zwitserleven(
    historical_names: dict
) -> list[FundQuote]:

    print()
    print("=" * 70)
    print("ZWITSERLEVEN")
    print("=" * 70)

    html = get_html(
        ZWITSERLEVEN_URL
    )

    tables = pd.read_html(
        StringIO(html)
    )

    fund_table = None

    for table in tables:

        columns = {
            clean_unicode(str(col))
            for col in table.columns
        }

        if {
            "Fonds",
            "Datum",
            "Koers"
        }.issubset(columns):

            fund_table = table.copy()
            break

    if fund_table is None:

        raise RuntimeError(
            "Geen fondsentabel gevonden "
            "op Zwitserleven."
        )

    # Kolomnamen opschonen
    fund_table.columns = [
        clean_unicode(str(col))
        for col in fund_table.columns
    ]

    results = []

    for _, row in fund_table.iterrows():

        try:

            raw_name = clean_unicode(
                row["Fonds"]
            )

            canonical_name = (
                canonical_fund_name(
                    raw_name,
                    historical_names
                )
            )

            quote_date = parse_date(
                row["Datum"]
            )

            price = parse_price(
                row["Koers"]
            )

            results.append(
                FundQuote(
                    fund=canonical_name,
                    quote_date=quote_date,
                    price=price,
                    source="zwitserleven",
                    original_name=raw_name,
                    source_url=ZWITSERLEVEN_URL,
                )
            )

            print(
                f"OK  | "
                f"{quote_date} | "
                f"{price:10.4f} | "
                f"{canonical_name}"
            )

        except Exception as exc:

            print(
                f"ERR | Zwitserleven rij: "
                f"{exc}"
            )

    print(
        f"\nZwitserleven: "
        f"{len(results)} koersen gevonden."
    )

    return results


# ============================================================
# SOURCE 2 - CARDANO
# ============================================================

def slugify_cardano(name: str) -> str:

    value = clean_unicode(name)

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        char
        for char in value
        if not unicodedata.combining(char)
    )

    value = value.casefold()

    value = re.sub(
        r"[^a-z0-9]+",
        "-",
        value
    )

    return value.strip("-")


def cardano_eligible(
    fund_name: str
) -> bool:
    """
    Cardano heeft vooral de eigen Zwitserleven-fondsen.

    Vanguard/PPI/PW/VP slaan we over om tientallen
    nutteloze 404-requests te voorkomen.
    """

    key = fund_key(fund_name)

    if not key.startswith(
        "zwitserleven "
    ):
        return False

    exclusions = [
        "vanguard",
        "ppi ",
        "pw ",
        "vp ",
    ]

    return not any(
        exclusion in key
        for exclusion in exclusions
    )


def scrape_cardano_fund(
    fund_name: str,
    historical_names: dict
) -> Optional[FundQuote]:

    slug = slugify_cardano(
        fund_name
    )

    url = (
        f"{CARDANO_BASE_URL}"
        f"{slug}/"
    )

    try:

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 404:

            return None

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        heading = soup.find("h1")

        if not heading:

            return None

        page_name = clean_unicode(
            heading.get_text(
                " ",
                strip=True
            )
        )

        requested_key = fund_key(
            canonical_fund_name(
                fund_name,
                historical_names
            )
        )

        page_key = fund_key(
            canonical_fund_name(
                page_name,
                historical_names
            )
        )

        if requested_key != page_key:

            print(
                f"SKIP | Cardano mismatch: "
                f"{fund_name} -> {page_name}"
            )

            return None

        lines = [
            clean_unicode(line)
            for line in soup.stripped_strings
        ]

        price = None
        quote_date = None

        for index, line in enumerate(lines):

            if line == "Handelskoers":

                for next_line in lines[
                    index + 1:
                    index + 5
                ]:

                    if (
                        "€" in next_line
                        or re.search(
                            r"\d+[,.]\d+",
                            next_line
                        )
                    ):

                        try:

                            price = parse_price(
                                next_line
                            )
                            break

                        except Exception:

                            pass

            if line == "Datum":

                for next_line in lines[
                    index + 1:
                    index + 4
                ]:

                    if re.fullmatch(
                        r"\d{2}-\d{2}-\d{4}",
                        next_line
                    ):

                        quote_date = parse_date(
                            next_line
                        )

                        break

        if (
            price is None
            or quote_date is None
        ):

            return None

        canonical_name = (
            canonical_fund_name(
                page_name,
                historical_names
            )
        )

        return FundQuote(
            fund=canonical_name,
            quote_date=quote_date,
            price=price,
            source="cardano",
            original_name=page_name,
            source_url=url,
        )

    except Exception as exc:

        print(
            f"WARN | Cardano "
            f"{fund_name}: {exc}"
        )

        return None


def scrape_cardano(
    target_funds: list[str],
    historical_names: dict
) -> list[FundQuote]:

    print()
    print("=" * 70)
    print("CARDANO")
    print("=" * 70)

    results = []

    for fund_name in target_funds:

        if not cardano_eligible(
            fund_name
        ):

            continue

        result = scrape_cardano_fund(
            fund_name,
            historical_names
        )

        if result:

            results.append(result)

            print(
                f"OK  | "
                f"{result.quote_date} | "
                f"{result.price:10.4f} | "
                f"{result.fund}"
            )

        # website niet onnodig belasten
        time.sleep(0.10)

    print(
        f"\nCardano: "
        f"{len(results)} koersen gevonden."
    )

    return results


# ============================================================
# HISTORISCHE CSV
# ============================================================

def load_history() -> pd.DataFrame:

    if not CSV_PATH.exists():

        return pd.DataFrame(
            columns=[
                "date",
                "fund",
                "price"
            ]
        )

    history = pd.read_csv(
        CSV_PATH
    )

    required = {
        "date",
        "fund",
        "price"
    }

    missing = (
        required
        - set(history.columns)
    )

    if missing:

        raise RuntimeError(
            f"prices.csv mist kolommen: "
            f"{sorted(missing)}"
        )

    history["date"] = pd.to_datetime(
        history["date"],
        errors="coerce"
    )

    history["price"] = pd.to_numeric(
        history["price"],
        errors="coerce"
    )

    history = history.dropna(
        subset=[
            "date",
            "fund",
            "price"
        ]
    )

    return history


def historical_name_map(
    history: pd.DataFrame
) -> dict:

    mapping = {}

    if history.empty:

        return mapping

    ordered = history.sort_values(
        "date"
    )

    for fund_name in ordered["fund"]:

        cleaned = clean_unicode(
            fund_name
        )

        canonical = (
            canonical_fund_name(
                cleaned
            )
        )

        mapping[
            fund_key(canonical)
        ] = canonical

    return mapping


def history_candidates(
    history: pd.DataFrame,
    historical_names: dict
) -> list[FundQuote]:

    if history.empty:

        return []

    latest = (
        history
        .sort_values("date")
        .groupby("fund")
        .tail(1)
    )

    results = []

    for _, row in latest.iterrows():

        fund_name = canonical_fund_name(
            row["fund"],
            historical_names
        )

        results.append(
            FundQuote(
                fund=fund_name,

                quote_date=pd.to_datetime(
                    row["date"]
                ).date(),

                price=float(
                    row["price"]
                ),

                source="history",

                original_name=str(
                    row["fund"]
                ),
            )
        )

    return results


# ============================================================
# NEWEST-DATE-WINS
# ============================================================

def select_best_quotes(
    candidates: list[FundQuote]
) -> dict[str, FundQuote]:

    grouped = {}

    for quote in candidates:

        key = fund_key(
            quote.fund
        )

        grouped.setdefault(
            key,
            []
        ).append(
            quote
        )

    winners = {}

    print()
    print("=" * 70)
    print("BRONSELECTIE - NEWEST DATE WINS")
    print("=" * 70)

    for key, quotes in sorted(
        grouped.items()
    ):

        quotes = sorted(
            quotes,
            key=lambda q: (
                q.quote_date,
                SOURCE_PRIORITY.get(
                    q.source,
                    0
                )
            ),
            reverse=True
        )

        winner = quotes[0]

        winners[key] = winner

        print()
        print(
            f"FUND: {winner.fund}"
        )

        for quote in quotes:

            marker = (
                "SELECTED"
                if quote is winner
                else ""
            )

            print(
                f"  {marker:8} | "
                f"{quote.source:12} | "
                f"{quote.quote_date} | "
                f"{quote.price:.4f}"
            )

    return winners


# ============================================================
# SAVE
# ============================================================

def save_winners(
    history: pd.DataFrame,
    winners: dict[str, FundQuote]
):

    new_rows = []

    print()
    print("=" * 70)
    print("CSV UPDATE")
    print("=" * 70)

    for winner in winners.values():

        # Alleen bestaande historische data:
        # niets nieuws opslaan
        if winner.source == "history":

            print(
                f"UNCHANGED | "
                f"{winner.fund} | "
                f"laatste data "
                f"{winner.quote_date}"
            )

            continue

        existing = history[
            (
                history["fund"]
                .apply(fund_key)
                ==
                fund_key(winner.fund)
            )
            &
            (
                history["date"].dt.date
                ==
                winner.quote_date
            )
        ]

        if not existing.empty:

            existing_price = float(
                existing.iloc[-1]["price"]
            )

            # Zelfde datum + zelfde koers
            if abs(
                existing_price
                - winner.price
            ) < 0.000001:

                print(
                    f"EXISTS    | "
                    f"{winner.fund} | "
                    f"{winner.quote_date}"
                )

                continue

            # Zelfde datum maar koers gewijzigd:
            # oude regel vervangen
            print(
                f"UPDATE    | "
                f"{winner.fund} | "
                f"{winner.quote_date} | "
                f"{existing_price:.4f} "
                f"-> {winner.price:.4f}"
            )

            mask = (
                (
                    history["fund"]
                    .apply(fund_key)
                    ==
                    fund_key(winner.fund)
                )
                &
                (
                    history["date"].dt.date
                    ==
                    winner.quote_date
                )
            )

            history = history[
                ~mask
            ].copy()

        else:

            print(
                f"NEW       | "
                f"{winner.fund} | "
                f"{winner.quote_date} | "
                f"{winner.price:.4f} | "
                f"{winner.source}"
            )

        new_rows.append({
            "date":
                winner.quote_date.isoformat(),

            "fund":
                winner.fund,

            "price":
                winner.price,
        })

    if new_rows:

        new_df = pd.DataFrame(
            new_rows
        )

        history_to_save = (
            history.copy()
        )

        history_to_save[
            "date"
        ] = (
            history_to_save[
                "date"
            ]
            .dt.strftime(
                "%Y-%m-%d"
            )
        )

        combined = pd.concat(
            [
                history_to_save,
                new_df
            ],
            ignore_index=True
        )

    else:

        combined = history.copy()

        if not combined.empty:

            combined["date"] = (
                combined["date"]
                .dt.strftime(
                    "%Y-%m-%d"
                )
            )

    if combined.empty:

        print(
            "Geen data om op te slaan."
        )

        return

    combined["date"] = pd.to_datetime(
        combined["date"]
    )

    combined = (
        combined
        .drop_duplicates(
            subset=[
                "date",
                "fund"
            ],
            keep="last"
        )
        .sort_values(
            [
                "date",
                "fund"
            ]
        )
    )

    combined["date"] = (
        combined["date"]
        .dt.strftime(
            "%Y-%m-%d"
        )
    )

    CSV_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    combined.to_csv(
        CSV_PATH,
        index=False
    )

    print()
    print(
        f"prices.csv opgeslagen: "
        f"{CSV_PATH}"
    )

    print(
        f"Totaal records: "
        f"{len(combined)}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("FUNDDATA MULTI SOURCE SCRAPER")
    print(
        datetime.now()
        .strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )
    print("=" * 70)

    # --------------------------------------------------------
    # Historische gegevens
    # --------------------------------------------------------

    history = load_history()

    historical_names = (
        historical_name_map(
            history
        )
    )

    print(
        f"Historische records: "
        f"{len(history)}"
    )

    # --------------------------------------------------------
    # Zwitserleven
    # --------------------------------------------------------

    zwitserleven_quotes = []

    try:

        zwitserleven_quotes = (
            scrape_zwitserleven(
                historical_names
            )
        )

    except Exception as exc:

        # Eén kapotte bron mag niet
        # de hele scraper stoppen.
        print(
            f"ERROR Zwitserleven: "
            f"{exc}"
        )

    # --------------------------------------------------------
    # Target fondsen
    # --------------------------------------------------------

    target_names = {}

    # Bestaande fondsen
    for name in historical_names.values():

        canonical = canonical_fund_name(
            name,
            historical_names
        )

        target_names[
            fund_key(canonical)
        ] = canonical

    # Fondsen die vandaag op Zwitserleven staan
    for quote in zwitserleven_quotes:

        target_names[
            fund_key(quote.fund)
        ] = quote.fund

    target_funds = sorted(
        target_names.values()
    )

    # --------------------------------------------------------
    # Cardano
    # --------------------------------------------------------

    cardano_quotes = (
        scrape_cardano(
            target_funds,
            historical_names
        )
    )

    # --------------------------------------------------------
    # Historische fallback
    # --------------------------------------------------------

    old_quotes = (
        history_candidates(
            history,
            historical_names
        )
    )

    # --------------------------------------------------------
    # Alle kandidaten combineren
    # --------------------------------------------------------

    all_candidates = (
        zwitserleven_quotes
        +
        cardano_quotes
        +
        old_quotes
    )

    if not all_candidates:

        raise RuntimeError(
            "Geen enkele koersbron "
            "heeft data opgeleverd."
        )

    # --------------------------------------------------------
    # Nieuwste datum wint
    # --------------------------------------------------------

    winners = (
        select_best_quotes(
            all_candidates
        )
    )

    # --------------------------------------------------------
    # Opslaan
    # --------------------------------------------------------

    save_winners(
        history,
        winners
    )

    print()
    print("=" * 70)
    print("KLAAR")
    print("=" * 70)


if __name__ == "__main__":

    main()
