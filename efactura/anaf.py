"""ANAF web services.

`validate` and `to_pdf` are public endpoints and need no login.
`SpvClient` (upload / status / download) needs an OAuth token obtained with a
qualified digital certificate. It follows ANAF's published API but has NOT been
tested against the live service yet.
"""
from __future__ import annotations

import httpx
from lxml import etree

PUBLIC_BASE = "https://webservicesp.anaf.ro/prod/FCTEL/rest"
OAUTH_AUTHORIZE = "https://logincert.anaf.ro/anaf-oauth2/v1/authorize"
OAUTH_TOKEN = "https://logincert.anaf.ro/anaf-oauth2/v1/token"


def is_credit_note(xml: bytes) -> bool:
    return etree.QName(etree.fromstring(xml)).localname == "CreditNote"


def _standard(xml: bytes) -> str:
    return "FCN" if is_credit_note(xml) else "FACT1"


def validate(xml: bytes, timeout: float = 30) -> tuple[bool, list[str]]:
    """Check an invoice against ANAF's schema and CIUS-RO business rules."""
    r = httpx.post(f"{PUBLIC_BASE}/validare/{_standard(xml)}", content=xml,
                   headers={"Content-Type": "text/plain"}, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    messages = [m.get("message", "") for m in data.get("Messages", [])]
    return data.get("stare") == "ok", messages


def to_pdf(xml: bytes, timeout: float = 60) -> bytes:
    """Render the invoice as ANAF's official PDF (validates it first)."""
    r = httpx.post(f"{PUBLIC_BASE}/transformare/{_standard(xml)}/DA", content=xml,
                   headers={"Content-Type": "text/plain"}, timeout=timeout)
    r.raise_for_status()
    if not r.content.startswith(b"%PDF"):
        raise ValueError(r.text[:500])
    return r.content


class SpvClient:
    """Upload invoices to SPV and fetch responses. Untested: needs a certificate."""

    def __init__(self, access_token: str, cif: str, test: bool = True):
        env = "test" if test else "prod"
        self.base = f"https://api.anaf.ro/{env}/FCTEL/rest"
        self.cif = cif
        self.http = httpx.Client(headers={"Authorization": f"Bearer {access_token}"}, timeout=60)

    def upload(self, xml: bytes) -> str:
        """Returns the upload index (index_incarcare) used to poll status."""
        standard = "CN" if is_credit_note(xml) else "UBL"
        r = self.http.post(f"{self.base}/upload", params={"standard": standard, "cif": self.cif},
                           content=xml, headers={"Content-Type": "text/plain"})
        r.raise_for_status()
        root = etree.fromstring(r.content)
        index = root.get("index_incarcare")
        if not index:
            raise RuntimeError(r.text[:500])
        return index

    def status(self, upload_index: str) -> dict:
        r = self.http.get(f"{self.base}/stareMesaj", params={"id_incarcare": upload_index})
        r.raise_for_status()
        root = etree.fromstring(r.content)
        return dict(root.attrib)

    def messages(self, days: int = 60) -> list[dict]:
        r = self.http.get(f"{self.base}/listaMesajeFactura", params={"zile": days, "cif": self.cif})
        r.raise_for_status()
        return r.json().get("mesaje", [])

    def download(self, download_id: str) -> bytes:
        """ZIP with the signed invoice/response. SPV purges these after ~60 days."""
        r = self.http.get(f"{self.base}/descarcare", params={"id": download_id})
        r.raise_for_status()
        return r.content
