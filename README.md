# e-Factura PFA

A free, open-source, local app that helps Romanian freelancers (PFA / II) create
**e-Factura** invoices, check them against ANAF's rules, and keep a permanent archive.

> **RO:** Aplicație gratuită și open-source pentru PFA-uri: emiți facturi e-Factura
> (UBL / CIUS-RO), le validezi automat la ANAF și le păstrezi arhivate local.
> SPV șterge mesajele după ~60 de zile, deci arhiva ta trebuie să fie la tine.

## Download (Windows)

**RO:** Descarcă `efactura-pfa.exe` de la
[Releases](https://github.com/CodingBreadd/efactura-pfa/releases/latest) și dă dublu-click.
Nu trebuie instalat nimic. Se deschide o fereastră neagră (lasă-o deschisă cât lucrezi;
o închizi ca să oprești aplicația) și aplicația în browser, la http://127.0.0.1:8765.
Datele se salvează în `Documente\e-Factura PFA`. Fă backup la acest folder.

Windows may show *"Windows protected your PC"* because the exe is not code-signed:
click **More info → Run anyway**. The source and the build are public; each release
is built by GitHub Actions from this repo (`.github/workflows/build.yml`).

## Why

- Paid ERPs are overkill for a one-person PFA.
- ANAF's SPV is **not storage**: messages are purged after about 60 days.
- Hand-writing UBL XML is error-prone (county codes, `SECTOR1..6` for Bucharest,
  VAT category rules for non-VAT payers…).

## Features (v0.2)

- Simple web form in Romanian, runs only on your computer (`127.0.0.1`)
- Generates UBL 2.1 XML in the **CIUS-RO** format
- Non-VAT payers (category `O`) and VAT payers (category `S`, 21%)
- Automatic validation with ANAF's public validator (no certificate needed)
- Official ANAF PDF rendering
- Local archive: SQLite + one XML file per invoice in `data/arhiva/<year>/`
- Invoice numbering, saved customers
- Single-file Windows `.exe`, no Python needed

**Not yet:** sending to SPV. That needs a qualified digital certificate (OAuth).
The client code exists in `efactura/anaf.py` but is untested. For now, download
the XML and upload it in SPV manually.

## Run from source

Requires Python 3.11+.

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
python -m efactura
```

It opens http://127.0.0.1:8765. Fill in your details under **Setări**, then
create invoices. Your data lives in `./data` (set `EFACTURA_DATA` to move it).
Back that folder up.

Build the `.exe` yourself with `pip install pyinstaller` and `pyinstaller efactura-pfa.spec`
(output in `dist/`).

## Tests

```bash
pip install pytest
pytest                      # includes live calls to ANAF's public validator
EFACTURA_OFFLINE=1 pytest   # skip network tests
```

## Roadmap

- [ ] Send to SPV via OAuth (needs testers with a certificate)
- [ ] Download received invoices and SPV responses into the archive
- [ ] Credit notes (storno), foreign currency (EUR with RON VAT totals)
- [x] Windows `.exe` build

Contributions welcome, especially from people who can test the SPV upload.

## Disclaimer

Not affiliated with ANAF. Check your invoices and talk to your accountant;
you are responsible for what you submit.

## License

MIT
