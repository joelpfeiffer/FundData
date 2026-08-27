"""GitHub Actions entry point: collect newest quote per fund into SQLite."""
import csv
import logging
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.multisource import Http, asn_quotes, cardano_quotes, choose, csv_quotes, load_config, parse_zwitserleven, reaal_quotes, ZWITSERLEVEN_URL

DB_PATH = ROOT / "data" / "pension.db"
CONFIG_PATH = ROOT / "fund_sources.json"
AUDIT_PATH = ROOT / "data" / "price_sources.csv"
LOG = logging.getLogger("fund-prices")


def collect_quotes():
    config, http = load_config(CONFIG_PATH), Http(timeout=30)
    primary = parse_zwitserleven(http.text(ZWITSERLEVEN_URL))
    alternatives = []
    try:
        alternatives.extend(cardano_quotes(http, workers=6))
    except Exception as exc:
        LOG.warning("Cardano niet beschikbaar; Zwitserleven blijft actief: %s", exc)
    try:
        alternatives.extend(asn_quotes(http))
    except Exception as exc:
        LOG.warning("ASN niet beschikbaar: %s", exc)
    try:
        alternatives.extend(reaal_quotes(http, workers=6))
    except Exception as exc:
        LOG.warning("Reaal niet beschikbaar: %s", exc)
    for spec in config.get("csv_sources", []):
        try:
            alternatives.extend(csv_quotes(http, spec, CONFIG_PATH.parent))
        except Exception as exc:
            LOG.warning("Extra bron %s niet beschikbaar: %s", spec.get("name", "onbekend"), exc)
    return choose(primary, alternatives, config)


def save_to_db(quotes):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS prices (
            date TEXT NOT NULL, fund TEXT NOT NULL, price REAL NOT NULL,
            PRIMARY KEY (date, fund))""")
        conn.executemany(
            "INSERT OR REPLACE INTO prices (date, fund, price) VALUES (?, ?, ?)",
            [(q.day.isoformat(), q.fund, float(q.price)) for q in quotes],
        )


def save_audit(rows):
    fields = ["fund", "selected_source", "date", "price", "fallback", "zwitserleven_date", "candidate_count", "url"]
    with AUDIT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    quotes, audit = collect_quotes()
    save_to_db(quotes)
    save_audit(audit)
    fallback_count = sum(row["fallback"] == "true" for row in audit)
    LOG.info("Klaar: %d fondsen; %d keer alternatieve bron gekozen", len(quotes), fallback_count)


if __name__ == "__main__":
    main()
