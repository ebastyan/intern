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

Sistemul contine doua module principale:
- **Persoane Fizice** (`index.html`) - Dashboard pentru achizitii de la persoane fizice
- **Firme B2B** (`firme.html`) - Dashboard pentru vanzari catre firme

---

## Functionalitati

### Dashboard Principal
- Statistici globale in timp real
- Grafice interactive pentru tendinte
- Top 10 parteneri dupa valoare
- Distributie pe categorii de deseuri

### Comparatie Anuala (Toti Anii)
- **Comparatie Personalizata** - Instrument avansat de analiza:
  - Selector luni (checkbox-uri Ian-Dec, orice combinatie)
  - Filtru optional pe categorie deseu (Cupru, Alama, Fier, etc.)
  - Tabel comparativ cu: tranzactii, rulaj, parteneri, medie/zi, trend %
  - Grafice: Rulaj pe ani, Parteneri pe ani (selectie vs total)
  - **Demografie detaliata**: Sex (M/F stacked bar), Grupe varsta (18-24 pana la 65+), Top judete
  - Detalii categorie: kg, valoare RON, pret mediu/kg, numar parteneri
  - Exemplu: selectezi doar "Ianuarie" + "Cupru" = vezi cati au adus cupru in ianuarie, comparativ pe toti anii
- Grafice comparative lunare dinamice (2022-2026+)
- Analiza rulaj si parteneri unici pentru fiecare an
- Tabel detaliat cu diferente procentuale YoY
- Identificare cea mai buna luna/perioada
- Culori distincte per an, actualizare automata

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
- Grafic predictie bazat pe tendinte (toate datele istorice 2022+)
- Metodologie dinamica cu media YoY multi-anuala

### Statistici Detaliate
- Carduri lunare cu detalii complete
- Zile lucratoare, parteneri unici, valori

---

## Dashboard Firme (B2B)

Dashboard dedicat pentru vanzari catre firme (`firme.html`):

### Tab-uri disponibile:
- **Sumar** - Statistici globale, grafice anuale, top firme
- **Firme** - Lista completa de firme cu cautare
- **Lunar** - Analiza lunara detaliata
- **Deseuri** - Statistici pe tipuri de deseuri
- **Comparatie** - Comparatie anuala (2022-2024)
- **Transport** - Costuri si profiluri transport
- **Statistici** - Analize avansate:
  - Top 10 Firme dupa Profit (sortabil)
  - Top 10 Firme dupa Cantitate (sortabil)
  - Sezonalitate (media lunara multi-anuala)
  - Marje pe categorii
  - Trend profit

### Caracteristici:
- Tabele sortabile cu indicatori vizuali
- Profile detaliate pentru soferi, transportatori, tari
- Grafice interactive cu tooltips complete
- Filtre avansate pe an, luna, tip deseu

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
| Rulaj Total | **~250.3M RON** |
| Numar Tranzactii | **112,765+** |
| Articole Tranzactii | **225,089+** |
| Parteneri Inregistrati | **30,853+** |
| Categorii Deseuri | **16** |
| Tipuri Deseuri | **47** |
| Perioada | 2022.01 - 2026.02 |

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
├── index.html           # Dashboard Persoane Fizice (SPA)
├── firme.html           # Dashboard Firme B2B (SPA)
├── vercel.json          # Configurare Vercel
├── requirements.txt     # Dependinte Python
├── CLAUDE.md            # Documentatie tehnica pentru dezvoltare
├── MEMORIA.md           # Jurnal modificari si detalii tehnice
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
- `GET /api/analytics?type=custom_compare&months=1,2&category=Cupru` - Comparatie personalizata cu demografie

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

**2022-2026** | PAJU

</div>
