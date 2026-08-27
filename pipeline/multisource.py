#!/usr/bin/env python3
"""Collect Zwitserleven fund prices from multiple public sources.

The newest dated candidate wins per canonical Zwitserleven fund. Source priority
is only used as a tie-breaker. Output remains compatible with date,fund,price.
"""

from __future__ import annotations

import argparse
import csv
import html as html_module
import json
import logging
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ZWITSERLEVEN_URL = "https://www.zwitserleven.nl/over-zwitserleven/verantwoord-beleggen/fondsen/"
CARDANO_URL = "https://www.cardano.nl/onze-fondsen/?cardano_target_audience=institutioneel"
ASN_URL = "https://www.asnbank.nl/beleggen/koersen.html"
REAAL_SITEMAP_URL = "https://www.reaal.nl/sitemap.xml"
USER_AGENT = "ZwitserlevenFundMonitor/1.0 (+personal portfolio data collector)"
LOG = logging.getLogger("fund-prices")


@dataclass(frozen=True)
class Quote:
    fund: str
    day: date
    price: Decimal
    source: str
    url: str


def clean(value: str) -> str:
    return " ".join(value.replace("\u00ad", "").replace("\u00a0", " ").split()).strip()


def key(value: str) -> str:
    value = unicodedata.normalize("NFKD", clean(value)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def parse_date(value: str) -> date:
    value = clean(value)
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"ongeldige datum: {value!r}")


def parse_price(value: str) -> Decimal:
    value = re.sub(r"[^0-9,.-]", "", clean(value))
    if not value:
        raise ValueError("lege koers")
    if "," in value and "." in value:
        value = value.replace(".", "").replace(",", ".") if value.rfind(",") > value.rfind(".") else value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"ongeldige koers: {value!r}") from exc
    if result <= 0:
        raise ValueError(f"koers moet positief zijn: {result}")
    return result


class Http:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.7"})

    def text(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.content.decode("utf-8", errors="replace")


def parse_zwitserleven(html: str, url: str = ZWITSERLEVEN_URL) -> list[Quote]:
    soup = BeautifulSoup(html, "html.parser")
    quotes: list[Quote] = []
    for row in soup.select("tr"):
        cells = [clean(x.get_text(" ", strip=True)) for x in row.select("th,td")]
        if len(cells) < 3:
            continue
        try:
            quotes.append(Quote(cells[0], parse_date(cells[1]), parse_price(cells[2]), "zwitserleven", url))
        except ValueError:
            continue
    # Fallback for accessible div/list markup: locate a date and euro value in blocks.
    if not quotes:
        pattern = re.compile(r"(.+?)\s+(\d{2}-\d{2}-\d{4})\s+€\s*([\d.,]+)")
        for line in soup.get_text("\n", strip=True).splitlines():
            match = pattern.search(clean(line))
            if match:
                quotes.append(Quote(clean(match[1]), parse_date(match[2]), parse_price(match[3]), "zwitserleven", url))
    if not quotes:
        raise RuntimeError("geen fondsregels gevonden op de Zwitserleven-pagina")
    return quotes


def label_value(soup: BeautifulSoup, label: str) -> str | None:
    target = key(label)
    nodes = soup.find_all(string=lambda s: s and key(str(s)) == target)
    for node in nodes:
        parent = node.parent
        # Cardano renders label and value as adjacent elements.
        for sibling in parent.next_siblings:
            if getattr(sibling, "get_text", None):
                value = clean(sibling.get_text(" ", strip=True))
                if value:
                    return value
        nxt = parent.find_next()
        for _ in range(5):
            if nxt is None:
                break
            value = clean(nxt.get_text(" ", strip=True))
            if value and key(value) != target:
                return value
            nxt = nxt.find_next()
    return None


def parse_cardano_detail(html: str, url: str) -> Quote:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    if not heading:
        raise ValueError("fondsnaam ontbreekt")
    name = clean(heading.get_text(" ", strip=True))
    price = label_value(soup, "Handelskoers") or label_value(soup, "NAV")
    day = label_value(soup, "Datum")
    if not price or not day:
        # Text fallback is resilient to modest Cardano template changes.
        text = clean(soup.get_text(" ", strip=True))
        p = re.search(r"Handelskoers\s+€?\s*([\d.,]+)", text, re.I)
        d = re.search(r"Datum\s+(\d{2}-\d{2}-\d{4})", text, re.I)
        price, day = (p.group(1) if p else None), (d.group(1) if d else None)
    if not price or not day:
        raise ValueError("Handelskoers/NAV of Datum ontbreekt")
    return Quote(name, parse_date(day), parse_price(price), "cardano", url)


def cardano_quotes(http: Http, workers: int) -> list[Quote]:
    soup = BeautifulSoup(http.text(CARDANO_URL), "html.parser")
    links: dict[str, str] = {}
    for anchor in soup.select("a[href]"):
        name = clean(anchor.get_text(" ", strip=True))
        url = urljoin(CARDANO_URL, anchor.get("href", ""))
        if "zwitserleven" in key(name) and "/onze-fondsen/" in urlparse(url).path:
            links[url] = name
    results: list[Quote] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = {pool.submit(lambda u: parse_cardano_detail(http.text(u), u), url): url for url in links}
        for job in as_completed(jobs):
            try:
                results.append(job.result())
            except Exception as exc:
                LOG.warning("Cardano-detail overgeslagen: %s (%s)", jobs[job], exc)
    return results


def asn_quotes(http: Http) -> list[Quote]:
    """Parse the latest non-empty price column in ASN's three-day table."""
    soup = BeautifulSoup(http.text(ASN_URL), "html.parser")
    output: list[Quote] = []
    for table in soup.select("table"):
        rows = table.select("tr")
        if not rows:
            continue
        header = [clean(cell.get_text(" ", strip=True)) for cell in rows[0].select("th,td")]
        dates: list[date | None] = []
        for cell in header:
            try:
                dates.append(parse_date(cell))
            except ValueError:
                dates.append(None)
        if not any(dates):
            continue
        for row in rows[1:]:
            cells = [clean(cell.get_text(" ", strip=True)) for cell in row.select("th,td")]
            if len(cells) < 2 or not key(cells[0]).startswith("asn "):
                continue
            candidates = []
            for index in range(1, min(len(cells), len(dates))):
                if dates[index] is None or key(cells[index]) in {"", "n a", "na"}:
                    continue
                try:
                    candidates.append(Quote(cells[0].rstrip("*"), dates[index], parse_price(cells[index]), "asn", ASN_URL))
                except ValueError:
                    pass
            if candidates:
                output.append(max(candidates, key=lambda quote: quote.day))
    if not output:
        raise RuntimeError("geen gedateerde ASN-koersen gevonden")
    return output


def parse_reaal_detail(html: str, url: str) -> Quote:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    if not heading:
        raise ValueError("fondsnaam ontbreekt")
    name = clean(heading.get_text(" ", strip=True))
    text = clean(soup.get_text(" ", strip=True))
    match = re.search(r"Datum\s+(\d{2}-\d{2}-\d{4})\s+Koers\s+€?\s*([\d.,]+)", text, re.I)
    if not match:
        raise ValueError("actuele Datum/Koers ontbreekt")
    return Quote(name, parse_date(match.group(1)), parse_price(match.group(2)), "reaal", url)


def _sitemap_urls(http: Http, url: str, depth: int = 0) -> set[str]:
    if depth > 2:
        return set()
    xml = http.text(url)
    locations = {clean(html_module.unescape(value)) for value in re.findall(r"<loc>(.*?)</loc>", xml, re.I | re.S)}
    nested = {item for item in locations if item.lower().endswith(".xml")}
    output = locations - nested
    for child in nested:
        try:
            output.update(_sitemap_urls(http, child, depth + 1))
        except Exception as exc:
            LOG.debug("Reaal-sitemapdeel overgeslagen: %s (%s)", child, exc)
    return output


def reaal_quotes(http: Http, workers: int) -> list[Quote]:
    urls = {
        url for url in _sitemap_urls(http, REAAL_SITEMAP_URL)
        if "/beleggen/rzl-" in urlparse(url).path.casefold()
    }
    if not urls:
        raise RuntimeError("geen RZL-fondspagina's in Reaal-sitemap gevonden")
    output: list[Quote] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        jobs = {pool.submit(lambda u: parse_reaal_detail(http.text(u), u), url): url for url in urls}
        for job in as_completed(jobs):
            try:
                output.append(job.result())
            except Exception as exc:
                LOG.debug("Reaal-detail overgeslagen: %s (%s)", jobs[job], exc)
    return output


def csv_quotes(http: Http, spec: dict, base: Path) -> list[Quote]:
    location = spec["location"]
    if location.startswith(("http://", "https://")):
        raw = http.text(location)
    else:
        raw = (base / location).read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t")
    fields = spec.get("columns", {})
    output: list[Quote] = []
    for row in csv.DictReader(raw.splitlines(), dialect=dialect):
        try:
            output.append(Quote(
                clean(row[fields.get("fund", "fund")]),
                parse_date(row[fields.get("date", "date")]),
                parse_price(row[fields.get("price", "price")]),
                spec["name"], location,
            ))
        except (KeyError, ValueError) as exc:
            LOG.warning("Ongeldige rij in bron %s overgeslagen: %s", spec["name"], exc)
    return output


def load_config(path: Path) -> dict:
    if not path.exists():
        return {"aliases": {}, "source_priority": ["cardano", "zwitserleven"], "csv_sources": []}
    return json.loads(path.read_text(encoding="utf-8"))


def resolver(canonical: Iterable[str], aliases: dict[str, str]):
    exact = {key(name): name for name in canonical}
    for alias, destination in aliases.items():
        if key(destination) not in exact:
            LOG.warning("Aliasdoel bestaat niet op Zwitserleven en is genegeerd: %s -> %s", alias, destination)
            continue
        exact[key(alias)] = exact[key(destination)]
    return lambda name: exact.get(key(name))


def choose(canonical_quotes: list[Quote], alternatives: list[Quote], config: dict) -> tuple[list[Quote], list[dict]]:
    canonical = {q.fund: q for q in canonical_quotes}
    resolve = resolver(canonical, config.get("aliases", {}))
    priorities = {name: i for i, name in enumerate(config.get("source_priority", []))}
    grouped: dict[str, list[Quote]] = {name: [quote] for name, quote in canonical.items()}
    for quote in alternatives:
        name = resolve(quote.fund)
        if name:
            grouped[name].append(Quote(name, quote.day, quote.price, quote.source, quote.url))
        else:
            LOG.info("Niet-gekoppeld alternatief genegeerd: %s (%s)", quote.fund, quote.source)
    selected: list[Quote] = []
    audit: list[dict] = []
    for name in sorted(canonical):
        candidates = grouped[name]
        winner = sorted(candidates, key=lambda q: (-q.day.toordinal(), priorities.get(q.source, 999), q.source))[0]
        primary = canonical[name]
        fallback = winner.source != primary.source
        selected.append(winner)
        audit.append({
            "fund": name, "selected_source": winner.source, "date": winner.day.isoformat(),
            "price": str(winner.price), "fallback": str(fallback).lower(),
            "zwitserleven_date": primary.day.isoformat(), "candidate_count": len(candidates), "url": winner.url,
        })
        LOG.info("%-55s bron=%-14s datum=%s koers=%s fallback=%s kandidaten=%d",
                 name, winner.source, winner.day, winner.price, fallback, len(candidates))
    return selected, audit


def write_prices(path: Path, quotes: list[Quote]) -> None:
    rows: dict[tuple[str, str], dict] = {}
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if {"date", "fund", "price"} <= row.keys():
                    rows[(row["date"], row["fund"])] = {"date": row["date"], "fund": row["fund"], "price": row["price"]}
    for quote in quotes:
        row = {"date": quote.day.isoformat(), "fund": quote.fund, "price": str(quote.price)}
        rows[(row["date"], row["fund"])] = row
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "fund", "price"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda r: (r["date"], r["fund"])))


def write_audit(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["fund", "selected_source", "date", "price", "fallback", "zwitserleven_date", "candidate_count", "url"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("fund_sources.json"))
    parser.add_argument("--output", type=Path, default=Path("data/prices.csv"))
    parser.add_argument("--audit", type=Path, default=Path("data/price_sources.csv"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--no-cardano", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    config = load_config(args.config)
    http = Http(args.timeout)
    try:
        primary = parse_zwitserleven(http.text(ZWITSERLEVEN_URL))
    except Exception as exc:
        LOG.error("Zwitserleven ophalen mislukt; fonds-universum kan niet veilig worden bepaald: %s", exc)
        return 2
    alternatives: list[Quote] = []
    if not args.no_cardano:
        try:
            alternatives.extend(cardano_quotes(http, args.workers))
        except Exception as exc:
            LOG.warning("Cardano-bron mislukt; Zwitserleven blijft beschikbaar: %s", exc)
    for spec in config.get("csv_sources", []):
        try:
            alternatives.extend(csv_quotes(http, spec, args.config.parent))
        except Exception as exc:
            LOG.warning("CSV-bron %s mislukt: %s", spec.get("name", "onbekend"), exc)
    selected, audit = choose(primary, alternatives, config)
    write_prices(args.output, selected)
    write_audit(args.audit, audit)
    fallback_count = sum(row["fallback"] == "true" for row in audit)
    LOG.info("Klaar: %d fondsen, %d alternatieve bronnen gekozen, output=%s", len(selected), fallback_count, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
