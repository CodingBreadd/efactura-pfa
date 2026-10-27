"""BNR reference exchange rates (public XML, no login).

Codul fiscal art. 290: VAT on a foreign-currency invoice uses the last rate BNR
published *before* the invoice date, so `rate_for` looks strictly before `day`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
from lxml import etree

YEAR_URL = "https://curs.bnr.ro/files/xml/years/nbrfxrates{year}.xml"
RECENT_URL = "https://curs.bnr.ro/nbrfxrates10days.xml"


def parse(xml: bytes, currency: str) -> dict[date, Decimal]:
    """{publishing date: RON per 1 unit}. The namespace changed in 2026, so match local names."""
    rates = {}
    for cube in etree.fromstring(xml).iter("{*}Cube"):
        for r in cube.iter("{*}Rate"):
            if r.get("currency") == currency:
                rates[date.fromisoformat(cube.get("date"))] = Decimal(r.text) / int(r.get("multiplier", "1"))
    return rates


def _fetch(url: str, timeout: float) -> bytes:
    r = httpx.get(url, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    return r.content


def rate_for(currency: str, day: date, timeout: float = 20) -> tuple[date, Decimal]:
    """(publishing date, rate) of the last BNR rate published before `day`."""
    urls = [RECENT_URL] if (date.today() - day).days < 9 else []
    urls += [YEAR_URL.format(year=day.year), YEAR_URL.format(year=day.year - 1)]
    for url in urls:
        earlier = {d: v for d, v in parse(_fetch(url, timeout), currency).items() if d < day}
        if earlier:
            last = max(earlier)
            return last, earlier[last]
    raise LookupError(f"BNR nu are curs {currency} înainte de {day}")
