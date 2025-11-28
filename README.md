# PAJU - Sistem de Gestionare Achizitii Deseuri

<div align="center">

![PAJU Logo](https://img.shields.io/badge/PAJU-Reciclare_Deseuri-00d9ff?style=for-the-badge&logo=recycle&logoColor=white)

**Dashboard analitic complet pentru gestionarea achizitiilor de deseuri**

[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-black?style=flat-square&logo=vercel)](https://vercel.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)

</div>

---

## Descriere

Aplicatie web moderna pentru monitorizarea si analiza activitatii de achizitie deseuri reciclabile. Sistemul ofera vizualizari interactive, rapoarte detaliate si instrumente avansate de filtrare.

---

## Functionalitati

### Dashboard Principal
- Statistici globale in timp real
- Grafice interactive pentru tendinte
- Top 10 parteneri dupa valoare
- Distributie pe categorii de deseuri

### Comparatie Anuala (2024 vs 2025)
- Grafice comparative lunare
- Analiza rulaj si parteneri unici
- Tabel detaliat cu diferente procentuale
- Identificare cea mai buna luna/perioada

### Gestionare Parteneri
- **VIP (Top 20)** - Cei mai valorosi parteneri
- **O Singura Data** - Vizitatori unici (filtru numar vizite)
- **Regulati** - Parteneri fideli (saptamanal/lunar/anual)
- **Inactivi** - Parteneri 60+ zile fara activitate
- **Familii/Adresa** - Detectare familii si persoane la aceeasi adresa
- **Mari Furnizori** - Top furnizori pe categorie
- **Lista Completa** - Toate persoanele inregistrate cu filtre avansate:
  - Cautare dupa: nume, CNP, judet, oras, strada
  - Filtre: perioada, categorie, numar vizite, valoare minima, sex
  - Toggle "Mindenki" - afiseaza toti partenerii sau doar cu tranzactii
  - Paginare (25 per pagina)
  - Sortare multipla

### Analiza Deseuri
- Sumar categorii cu grafice
- Distributie procentuala (pie chart)
- Tendinte lunare pe categorii
- Statistici preturi (min/max/medie)
- Cel mai bun neferos pe luna

### Analiza Regionala
- Distributie pe judete
- Top localitati
- Analiza pe grupe de varsta
- Lista completa localitati cu detalii (click pentru popup)
- Filtrare deseuri pe regiune/varsta

### Predictii
- Grafic predictie bazat pe tendinte
- Metodologie explicata

### Statistici Detaliate
- Carduri lunare cu detalii complete
- Zile lucratoare, parteneri unici, valori

---

## Arhitectura Tehnica

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│         HTML5 + Vanilla JavaScript + Chart.js               │
│                    Single Page Application                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     VERCEL SERVERLESS                        │
│                   Python API Functions                       │
│  analytics.py │ partners.py │ transactions.py │ waste.py    │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                       DATABASE                               │
│                      PostgreSQL                              │
│         partners │ transactions │ transaction_items          │
│              waste_types │ waste_categories                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Structura Bazei de Date

```
partners              transactions           transaction_items
├── cnp (PK)          ├── document_id (PK)   ├── id (PK)
├── name              ├── date               ├── document_id (FK)
├── city              ├── cnp (FK)           ├── waste_type_id (FK)
├── county            ├── payment_type       ├── price_per_kg
├── street            ├── gross_value        ├── weight_kg
├── phone             ├── env_tax            └── value
├── email             ├── income_tax
├── birth_year        └── net_paid
└── sex

waste_types                    waste_categories
├── id (PK)                    ├── id (PK)
├── name                       └── name
└── category_id (FK)
```

---

## Statistici Sistem

| Indicator | Valoare |
|-----------|---------|
| Rulaj Total | **~118.7M RON** |
| Numar Tranzactii | **51,000+** |
| Parteneri Inregistrati | **30,000+** |
| Parteneri Activi | **13,000+** |
| Categorii Deseuri | **16** |
| Perioada | 2024.01 - 2025.11 |

---

## Categorii Deseuri Principale

| Categorie | Cantitate Totala |
|-----------|------------------|
| Fier | ~16.5M kg |
| Aluminiu | ~2.5M kg |
| DEEE (Electronice) | ~2.0M kg |
| Cupru | ~1.5M kg |
| Acumulatori | ~1.4M kg |
| Carton | ~1.1M kg |
| Alama | ~580K kg |
| Inox | ~243K kg |
| Sticla | ~181K kg |

---

## Structura Proiect

```
paju/
├── api/
│   ├── analytics.py     # Endpoint-uri analitice
│   ├── partners.py      # Gestionare parteneri
│   ├── transactions.py  # Gestionare tranzactii
│   ├── waste.py         # Statistici deseuri
│   ├── data.py          # Date dashboard
│   └── monthly.py       # Rapoarte lunare
├── index.html           # Aplicatia principala (SPA)
├── vercel.json          # Configurare Vercel
├── requirements.txt     # Dependinte Python
├── CLAUDE.md            # Documentatie tehnica detaliata
└── README.md            # Acest fisier
```

---

## Caracteristici Interfata

- **Design Dark Mode** - Tema intunecata profesionala
- **Responsive** - Adaptat pentru diverse rezolutii
- **Tabele cu Header Fix** - Antetul ramane vizibil la scroll
- **Popup-uri Detaliate** - Click pe parteneri/orase pentru detalii
- **Filtre Avansate** - Multiple criterii de cautare
- **Paginare** - Navigare usoara prin liste mari
- **Grafice Interactive** - Chart.js pentru vizualizari

---

## API Endpoints

### Analytics
- `GET /api/analytics?type=overview` - Sumar general
- `GET /api/analytics?type=monthly&year=2024` - Date lunare
- `GET /api/analytics?type=county` - Statistici pe judete
- `GET /api/analytics?type=city_details&city=Oradea` - Detalii localitate

### Partners
- `GET /api/partners?q=nume` - Cautare parteneri
- `GET /api/partners?cnp=XXX` - Profil partener
- `GET /api/partners?list=1&page=1` - Lista paginata
- `GET /api/partners?same_family` - Detectare familii

### Transactions
- `GET /api/transactions?cnp=XXX` - Tranzactii partener
- `GET /api/transactions?daily=2024-10-15` - Sumar zilnic

### Waste
- `GET /api/waste?type=categories` - Sumar categorii
- `GET /api/waste?type=monthly&category=Cupru` - Evolutie lunara

---

## Dezvoltare

### Cerinte
- Python 3.9+
- PostgreSQL
- Node.js (pentru Vercel CLI)

### Instalare Locala
```bash
# Instalare dependinte
pip install -r requirements.txt

# Pornire server dezvoltare
vercel dev
```

### Deployment
Proiectul se deployeaza automat pe Vercel la fiecare push pe branch-ul `main`.

---

<div align="center">

### Dezvoltat cu

**Python + JavaScript + PostgreSQL**

*Sistem profesional de gestionare date*

---

**2024-2025** | PAJU

</div>
