# Draft post (r/programare, r/Romania, grupuri PFA)

**Titlu:** Am făcut o aplicație gratuită și open-source pentru e-Factura la PFA. Caut testeri cu certificat digital.

Salut! Sunt PFA și m-am săturat să plătesc abonamente sau să completez XML-uri de mână
pentru e-Factura, așa că am făcut **e-Factura PFA**: o aplicație mică, gratuită, open-source (MIT),
care rulează doar pe calculatorul tău.

Ce face acum:
- formular simplu în română → generează XML-ul UBL / CIUS-RO
- îl validează automat cu validatorul public ANAF (fără certificat)
- îți dă PDF-ul oficial ANAF
- păstrează o arhivă locală (SPV șterge mesajele după ~60 de zile)
- neplătitori de TVA (categoria O) și plătitori (S, 21%)
- pe Windows e un singur `.exe`, fără instalare

Ce nu face încă: trimiterea directă în SPV. Codul există, dar am nevoie de oameni
**cu certificat digital calificat** care să mă ajute să-l testez. Până atunci, descarci
XML-ul și îl încarci manual în SPV.

Download și cod sursă: https://github.com/CodingBreadd/efactura-pfa

Orice feedback e binevenit: ce lipsește, ce e greu de folosit, erori de la ANAF.
Nu sunt afiliat cu ANAF; verifică facturile și cu contabilul tău.
