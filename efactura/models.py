"""Invoice data model and totals, kept independent of XML and storage."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

TWO = Decimal("0.01")

# ISO 3166-2:RO codes, required by CIUS-RO in CountrySubentity.
COUNTIES = {
    "AB": "Alba", "AR": "Arad", "AG": "Argeș", "BC": "Bacău", "BH": "Bihor",
    "BN": "Bistrița-Năsăud", "BT": "Botoșani", "BV": "Brașov", "BR": "Brăila",
    "B": "București", "BZ": "Buzău", "CS": "Caraș-Severin", "CL": "Călărași",
    "CJ": "Cluj", "CT": "Constanța", "CV": "Covasna", "DB": "Dâmbovița",
    "DJ": "Dolj", "GL": "Galați", "GR": "Giurgiu", "GJ": "Gorj", "HR": "Harghita",
    "HD": "Hunedoara", "IL": "Ialomița", "IS": "Iași", "IF": "Ilfov",
    "MM": "Maramureș", "MH": "Mehedinți", "MS": "Mureș", "NT": "Neamț",
    "OT": "Olt", "PH": "Prahova", "SM": "Satu Mare", "SJ": "Sălaj", "SB": "Sibiu",
    "SV": "Suceava", "TR": "Teleorman", "TM": "Timiș", "TL": "Tulcea",
    "VS": "Vaslui", "VL": "Vâlcea", "VN": "Vrancea",
}

# UN/ECE Rec 20 unit codes most useful to freelancers.
UNITS = {
    "HUR": "oră", "DAY": "zi", "MON": "lună", "H87": "bucată",
    "C62": "unitate", "KGM": "kg", "MTR": "metru",
}

# VAT categories supported for now: S = standard rate, O = not subject to VAT
# (the usual case for a PFA that is not VAT registered).
VAT_CATEGORIES = {"S": "Standard", "O": "Neplătitor de TVA"}

CURRENCIES = {"RON": "lei", "EUR": "euro", "USD": "dolari SUA", "GBP": "lire sterline"}


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(TWO, rounding=ROUND_HALF_UP)


@dataclass
class Party:
    name: str
    cui: str                      # fiscal code, digits only (no RO prefix)
    street: str
    city: str                     # for București: SECTOR1..SECTOR6
    county: str                   # key of COUNTIES
    vat_payer: bool = False
    reg_com: str = ""             # trade register number, optional
    iban: str = ""
    bank: str = ""
    email: str = ""

    @property
    def vat_id(self) -> str:
        return f"RO{self.cui}" if self.vat_payer else ""


@dataclass
class Line:
    name: str
    quantity: Decimal
    unit_price: Decimal
    unit: str = "HUR"
    vat_category: str = "O"
    vat_rate: Decimal = Decimal("0")

    @property
    def amount(self) -> Decimal:
        return money(Decimal(self.quantity) * Decimal(self.unit_price))


@dataclass
class Invoice:
    number: str
    issue_date: date
    supplier: Party
    customer: Party
    lines: list[Line]
    due_date: date | None = None
    currency: str = "RON"
    note: str = ""
    exchange_rate: Decimal | None = None  # RON per 1 unit of currency (BNR), required unless RON
    credit_note: bool = False             # storno: a UBL CreditNote (type 381) for ref_number
    ref_number: str = ""                  # the invoice being corrected
    ref_date: date | None = None

    def tax_groups(self) -> list[dict]:
        """One subtotal per (category, rate), as EN 16931 requires."""
        groups: dict[tuple, dict] = {}
        for line in self.lines:
            key = (line.vat_category, Decimal(line.vat_rate))
            g = groups.setdefault(key, {"category": key[0], "rate": key[1], "taxable": Decimal("0")})
            g["taxable"] += line.amount
        for g in groups.values():
            g["taxable"] = money(g["taxable"])
            g["tax"] = money(g["taxable"] * g["rate"] / 100) if g["category"] == "S" else money(0)
        return list(groups.values())

    @property
    def net_total(self) -> Decimal:
        return money(sum((l.amount for l in self.lines), Decimal("0")))

    @property
    def tax_total(self) -> Decimal:
        return money(sum((g["tax"] for g in self.tax_groups()), Decimal("0")))

    @property
    def gross_total(self) -> Decimal:
        return money(self.net_total + self.tax_total)

    @property
    def tax_total_ron(self) -> Decimal:
        """VAT in RON (BT-111). CIUS-RO wants it whenever the invoice is in another currency."""
        if self.currency == "RON":
            return self.tax_total
        return money(self.tax_total * Decimal(self.exchange_rate))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["issue_date"] = self.issue_date.isoformat()
        d["due_date"] = self.due_date.isoformat() if self.due_date else None
        d["ref_date"] = self.ref_date.isoformat() if self.ref_date else None
        d["exchange_rate"] = str(self.exchange_rate) if self.exchange_rate is not None else None
        for l in d["lines"]:
            l["quantity"] = str(l["quantity"])
            l["unit_price"] = str(l["unit_price"])
            l["vat_rate"] = str(l["vat_rate"])
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Invoice":
        return cls(
            number=d["number"],
            issue_date=date.fromisoformat(d["issue_date"]),
            due_date=date.fromisoformat(d["due_date"]) if d.get("due_date") else None,
            supplier=Party(**d["supplier"]),
            customer=Party(**d["customer"]),
            lines=[Line(name=l["name"], quantity=Decimal(l["quantity"]),
                        unit_price=Decimal(l["unit_price"]), unit=l["unit"],
                        vat_category=l["vat_category"], vat_rate=Decimal(l["vat_rate"]))
                   for l in d["lines"]],
            currency=d.get("currency", "RON"),
            note=d.get("note", ""),
            exchange_rate=Decimal(d["exchange_rate"]) if d.get("exchange_rate") else None,
            credit_note=d.get("credit_note", False),
            ref_number=d.get("ref_number", ""),
            ref_date=date.fromisoformat(d["ref_date"]) if d.get("ref_date") else None,
        )
