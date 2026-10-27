from datetime import date
from decimal import Decimal

from efactura.models import Invoice, Line, Party


def pfa_invoice(vat_payer: bool = False) -> Invoice:
    cat, rate = ("S", Decimal("21")) if vat_payer else ("O", Decimal("0"))
    return Invoice(
        number="PFA0001",
        issue_date=date(2026, 10, 27),
        due_date=date(2026, 11, 10),
        supplier=Party(name="Popescu Ion PFA", cui="12345674", street="Str. Memorandumului 10",
                       city="Cluj-Napoca", county="CJ", vat_payer=vat_payer,
                       iban="RO49AAAA1B31007593840000", bank="Banca Test"),
        customer=Party(name="Client Exemplu SRL", cui="18547290", street="Bd. Unirii 1",
                       city="SECTOR3", county="B", vat_payer=vat_payer),
        lines=[
            Line(name="Dezvoltare software", quantity=Decimal("40"), unit_price=Decimal("150"),
                 unit="HUR", vat_category=cat, vat_rate=rate),
            Line(name="Mentenanță lunară", quantity=Decimal("1"), unit_price=Decimal("499.99"),
                 unit="MON", vat_category=cat, vat_rate=rate),
        ],
    )
