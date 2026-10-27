"""Local archive: SQLite for search, plus plain XML files per year for easy backup.

ANAF's SPV deletes messages after ~60 days, so this is the user's permanent copy.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path


def _documents_dir() -> Path:
    """The real Documents folder, even when OneDrive has redirected it."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:  # CSIDL_PERSONAL
            return Path(buf.value)
    except (AttributeError, OSError):
        pass
    return Path.home() / "Documents"


def _default_data_dir() -> Path:
    if env := os.environ.get("EFACTURA_DATA"):
        return Path(env)
    if getattr(sys, "frozen", False):  # the .exe can be run from anywhere, so don't use cwd
        return _documents_dir() / "e-Factura PFA"
    return Path.cwd() / "data"


DATA_DIR = _default_data_dir()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    number TEXT UNIQUE NOT NULL,
    issue_date TEXT NOT NULL,
    customer TEXT NOT NULL,
    total TEXT NOT NULL,
    currency TEXT NOT NULL,
    data TEXT NOT NULL,
    xml BLOB NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',      -- draft | valid | invalid | sent
    messages TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Store:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.dir / "efactura.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # settings
    def get(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row["value"]) if row else default

    def set(self, key: str, value) -> None:
        self.db.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, json.dumps(value)))
        self.db.commit()

    def number(self, n: int) -> str:
        return f"{self.get('series', 'PFA')}{n:04d}"

    def next_number(self) -> str:
        return self.number(self.get("next_number", 1))

    def bump_number(self) -> None:
        self.set("next_number", self.get("next_number", 1) + 1)

    # invoices
    @staticmethod
    def _columns(inv, xml: bytes, status: str, messages: list[str]) -> tuple:
        """issue_date, customer, total, currency, data, xml, status, messages"""
        return (inv.issue_date.isoformat(), inv.customer.name,
                str(-inv.gross_total if inv.credit_note else inv.gross_total),
                inv.currency, json.dumps(inv.to_dict(), ensure_ascii=False), xml, status,
                json.dumps(messages, ensure_ascii=False))

    def save_invoice(self, inv, xml: bytes, status: str, messages: list[str]) -> int:
        cur = self.db.execute(
            "INSERT INTO invoices (number, issue_date, customer, total, currency, data, xml, status, messages)"
            " VALUES (?,?,?,?,?,?,?,?,?)", (inv.number, *self._columns(inv, xml, status, messages)))
        self.db.commit()
        self._path(inv.issue_date.year, inv.number).write_bytes(xml)
        return cur.lastrowid

    def update_invoice(self, invoice_id: int, inv, xml: bytes, status: str, messages: list[str]) -> None:
        old = self.get_invoice(invoice_id)
        self._path(int(old["issue_date"][:4]), old["number"]).unlink(missing_ok=True)  # the year may change
        self.db.execute(
            "UPDATE invoices SET issue_date=?, customer=?, total=?, currency=?, data=?, xml=?, status=?,"
            " messages=? WHERE id=?", (*self._columns(inv, xml, status, messages), invoice_id))
        self.db.commit()
        self._path(inv.issue_date.year, inv.number).write_bytes(xml)

    def delete_invoice(self, invoice_id: int) -> None:
        row = self.get_invoice(invoice_id)
        self.db.execute("DELETE FROM invoices WHERE id=?", (invoice_id,))
        self.db.commit()
        self._path(int(row["issue_date"][:4]), row["number"]).unlink(missing_ok=True)
        # Hand the number back if it was the last one, so the sequence has no gap.
        n = self.get("next_number", 1)
        if n > 1 and row["number"] == self.number(n - 1):
            self.set("next_number", n - 1)

    def update_status(self, invoice_id: int, status: str, messages: list[str]) -> None:
        self.db.execute("UPDATE invoices SET status=?, messages=? WHERE id=?",
                        (status, json.dumps(messages, ensure_ascii=False), invoice_id))
        self.db.commit()

    def list_invoices(self, q: str = "") -> list[sqlite3.Row]:
        like = f"%{q}%"
        return self.db.execute(
            "SELECT * FROM invoices WHERE number LIKE ? OR customer LIKE ? ORDER BY issue_date DESC, id DESC",
            (like, like)).fetchall()

    def get_invoice(self, invoice_id: int) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()

    def find_id(self, number: str) -> int | None:
        row = self.db.execute("SELECT id FROM invoices WHERE number=?", (number,)).fetchone()
        return row["id"] if row else None

    def credit_notes_for(self, number: str) -> list[sqlite3.Row]:
        return self.db.execute(
            "SELECT id, number FROM invoices WHERE json_extract(data, '$.credit_note')"
            " AND json_extract(data, '$.ref_number') = ?", (number,)).fetchall()

    def customers(self) -> list[dict]:
        """Distinct past customers, newest first, for quick re-use in the form."""
        seen, out = set(), []
        for row in self.db.execute("SELECT data FROM invoices ORDER BY id DESC"):
            c = json.loads(row["data"])["customer"]
            key = c["cui"] or c["name"]  # foreign customers may have no id
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out

    def _path(self, year: int, number: str) -> Path:
        folder = self.dir / "arhiva" / str(year)
        folder.mkdir(parents=True, exist_ok=True)
        safe = "".join(ch for ch in number if ch.isalnum() or ch in "-_")
        return folder / f"{safe}.xml"
