# PAJU - Sistem de Gestionare Achizitii Deseuri

<div align="center">

![PAJU Logo](https://img.shields.io/badge/PAJU-Reciclare_Deseuri-00d9ff?style=for-the-badge&logo=recycle&logoColor=white)

**Dashboard analitic complet pentru gestionarea achizitiilor de deseuri reciclabile — Oradea, Romania**

[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-black?style=flat-square&logo=vercel)](https://vercel.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-NeonDB-336791?style=flat-square&logo=postgresql&logoColor=white)](https://neon.tech)
[![Chart.js](https://img.shields.io/badge/Chart.js-FF6384?style=flat-square&logo=chart.js&logoColor=white)](https://chartjs.org)

</div>

---

## Descriere

Aplicatie web pentru monitorizarea si analiza activitatii de achizitie deseuri. Sistemul ofera vizualizari interactive, rapoarte detaliate si instrumente avansate de filtrare pe baza a **peste 160,000 tranzactii** acoperind **7 ani** (2020-2026).

Doua module principale:
- **Persoane Fizice** (`index.html`) — Dashboard pentru achizitii de la persoane fizice
- **Firme B2B** (`firme.html`) — Dashboard pentru vanzari catre firme

---

## Statistici Sistem

| Indicator | Valoare |
|-----------|---------|
| Numar Tranzactii | **160,769+** |
| Articole Tranzactii | **~323,000+** |
| Parteneri Inregistrati | **31,220+** |
| Categorii Deseuri | **16** |
| Tipuri Deseuri | **47+** |
| Perioada Acoperita | **2020.01 - 2026.04** (7 ani) |
| Date Meteo (Oradea) | **2,299 zile** (Open-Meteo) |
| Sarbatori in DB | **220** (2020-2030, nationale + catolice + ortodoxe) |

### Defalcare anuala

| Year | Transactii | Working days | Rulaj (RON) | Note |
|------|-----------:|-------------:|-----------:|------|
| 2020 | 16,102 | 243 | 15.9M | Jan-Nov (fara Dec), Apr COVID (4 zile) |
| 2021 | 26,692 | 278 | 48.9M | full year |
| 2022 | 28,389 | 276 | 60.9M | full year |
| 2023 | 28,355 | 275 | 61.0M | full year |
| 2024 | 28,029 | 280 | 70.8M | full year |
| 2025 | 25,284 | 278 | 52.1M | full year |
| 2026 | 7,918 | 81 | 14.6M | Jan-Apr partial |
| **Total** | **160,769** | **1,711** | **~324M** | |

---

## Functionalitati

### 📊 Sumar (Dashboard Principal)
- 6 carduri statistici globale
- Top 10 parteneri dupa valoare
- Distributie pe categorii de deseuri
- Grafice comparative interactive (Chart.js)

### 📈 Comparatie Anuala (Toti Anii)
- **Comparatie Personalizata** — analiza multi-criteriu:
  - Selector luni (checkbox-uri, orice combinatie)
  - Filtru optional pe categorie
  - Demografie completa: Sex (M/F), Grupe varsta, Top judete
  - Indicatori: tranzactii, rulaj, parteneri, medie/zi, trend %
- Grafice lunare dinamice pe toti anii (2020-2026+)

### 👥 Parteneri
- **VIP (Top 20)**, **O Singura Data**, **Regulati** (saptamanal/lunar/anual)
- **Inactivi** (60+ zile), **Familii/Adresa**, **Mari Furnizori**
- **Lista Completa** — filtre avansate pe nume/CNP/judet/oras, paginare, sortare

### ♻️ Deseuri
- Sumar categorii, pie chart, evolutie pe tipuri
- Statistici preturi (min/max/medie), cel mai bun neferos/luna
- **Analiza Detaliata** — interval date + agregare (zilnic/lunar/anual), selectie tipuri sau categorii intregi

### 🗺️ Regiuni
- Distributie pe judete, top localitati, lista completa cu popup-uri
- Analiza pe grupe de varsta, filtrare pe regiune

### 📅 Sezonalitate & Sarbatori *(Phase 1)*
- **Tipar saptamanal** (Luni-Sambata) — cu selector an (2020-2026)
  - Toggle `/zi` vs `/ora` (program L-V 9h, Sa 5h)
- **Tipar lunar** — per an sau medie
- **Impactul sarbatorilor** — grupare in **blocuri de sarbatoare** (Paste = Vineri+Sambata+Duminica+Luni intr-un singur bloc)
  - Analiza per-an cu variatia anuala vizibila
  - Comparatie **3 zile deschise INAINTE** vs **3 zile deschise DUPA** (nu zile calendaristice — evita zilele de vacanta)
- **Perioade inchise (auto-detectate)** — concedii detectate automat (vara 2 saptamani, prelungiri Craciun, etc.)
- **Audit** — tranzactii inregistrate in zile oficial nelucratoare

### 🌦️ Meteo & Trafic *(Phase 2)*
- **Context banner** — perioda selectata vs aceleasi zile in alti ani (PESTE/SUB normal)
- **Sinteza + praguri vizuale** — top 4 conditii care stirnesc traficul, top 4 care ajuta
- **Gradient de prag pe variabila**: temperatura, ploaie, zapada, vant, umiditate, cer
  - Scala cu bara rosie la stanga (scade) si verde la dreapta (creste)
- **Vreme care STRICA traficul** — carduri expandabile cu zile concrete ca exemple
- **Vreme OPTIMA pentru trafic** — carduri expandabile
- **Efect cu intarziere (lag)** — ploaia are efect la +2 zile, etc.
- **Cele mai atipice 20 zile** — tabel cu meteo + actual vs asteptat
- **Baseline** = mediana ultimelor 28 zile lucratoare cu aceeasi zi a saptamanii (exclude sezon)

### 🔮 Predictii
- Grafic predictie multi-ani bazat pe tendinte (2020+)
- Metodologie dinamica cu media YoY

### 📋 Statistice
- Top per categorie (kg si RON), parteneri consistenti, cea mai buna perioada
- Analiza sarbatori (rulaj inainte/in/dupa)

---

## Dashboard Firme (B2B)

Modul separat pentru vanzari catre firme (`firme.html`):
- **Sumar** — statistici globale, top firme
- **Firme** — lista completa cu cautare
- **Lunar** / **Deseuri** / **Comparatie Anuala**
- **Transport** — costuri si profiluri soferi/transportatori/tari
- **Statistici** — Top 10 profit/cantitate, sezonalitate, marje, trend profit

---

## Arhitectura

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND                                                │
│  HTML5 + Vanilla JS + Chart.js                           │
│  Single Page Application, dark theme (#0a0a14)           │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  VERCEL SERVERLESS (Python 3.12)                         │
│  analytics │ partners │ transactions │ waste │ data     │
│  monthly │ calendar │ weather │ firme                   │
└───────────────────┬─────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│  POSTGRESQL (NeonDB)                                     │
│  Tranzactii: partners │ transactions │ transaction_items │
│  Deseuri:    waste_types │ waste_categories              │
│  Calendar:   holidays │ company_closures                 │
│  Meteo:      weather_oradea                              │
└─────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### `/api/analytics`
Overview, yearly, monthly, county, city_details, weekday, age, trends, custom_compare

### `/api/partners`
Search, profile, top, inactive, onetime, regulars, same_address, same_family, big_suppliers, list

### `/api/transactions`
Document details, per-CNP history, daily summary, date range filters

### `/api/waste`
Categories, types, prices, monthly, top per category, analysis (daily/monthly/yearly aggregation)

### `/api/calendar` *(Phase 1)*
- `holidays&year=YYYY` — sarbatori nationale + catolice + ortodoxe
- `closures` / `closure_candidates` — inchideri companie (auto-detectate)
- `weekly_pattern` / `monthly_pattern` — tipar calendaristic
- `working_days` — zile lucratoare in interval
- `holiday_effect` — impact sarbatori cu blocuri
- `bridge_days` — zile "punte" intre doua zile inchise
- `illegal_workdays` — audit tranzactii pe piros

### `/api/weather` *(Phase 2)*
- `residuals` — actual vs baseline vs residual per zi
- `buckets` — pragurile meteo pe variabila
- `lag_curve` — corelatie la lag -2..+3
- `extreme_days` — top N zile atipice
- `overview` — 4 familii de ipoteze + ranking + period context

---

## Scripts

### `scripts/fetch_weather.py`
Descarca date meteo de la Open-Meteo Historical API (gratuit, fara API key).
- Oradea coords: 47.0722°N, 21.9217°E
- Daily + hourly aggregated (pressure, humidity, cloud)
- Idempotent (ON CONFLICT DO UPDATE)
- `--self-test` — sanity check live API

### `scripts/seed_holidays.py`
Genereaza si insereaza sarbatori pentru interval de ani.
- Sarbatori nationale fixe (10/an)
- Paste catolic (Butcher's algorithm)
- Paste ortodox (Meeus Julian + 13 zile)
- Rusalii ambele + Vinerea Mare
- `--self-test` — verifica algoritmii

### `scripts/import_xls.py`
Importator .xls pentru tranzactii persoane fizice.
- Parser filename + folder hints (e.g. `2020/03_martie/13.02.2020.xls` → 2020-03-13)
- CNP parser: birth_year, sex, county din CNP
- Idempotent (existing_docs + ON CONFLICT DO NOTHING)
- `--use-com` — fallback Excel COM pentru fisiere corupte (utf-16-le)
- `--dry-run` — parsare fara scriere in DB

### `scripts/run_migration.py`
Runner pentru migratii SQL din `scripts/migrations/NNN_*.sql`.

---

## Structura Baza de Date

```
partners              transactions           transaction_items
├── cnp (PK)          ├── document_id (PK)   ├── id (PK)
├── name              ├── date               ├── document_id (FK)
├── city/county       ├── cnp (FK)           ├── waste_type_id (FK)
├── street/phone      ├── payment_type       ├── price_per_kg
├── birth_year/sex    ├── gross_value        ├── weight_kg
└── county_from_cnp   ├── env_tax            └── value
                      ├── income_tax
                      └── net_paid

waste_types           waste_categories       holidays
├── id (PK)           ├── id (PK)            ├── date
├── name              └── name               ├── type (national/catolic/ortodox)
└── category_id                              ├── name
                                             └── is_official

company_closures      weather_oradea (22 cols)
├── date (PK)         ├── date (PK)
├── reason            ├── temp_max/min/mean
└── detected_auto     ├── precipitation/rain/snow
                      ├── wind_speed/gusts/direction
                      ├── pressure/humidity/cloudcover
                      ├── sunshine/daylight/radiation
                      └── weather_code (WMO)
```

---

## Structura Proiect

```
paju/
├── api/                   # Vercel serverless functions (Python)
│   ├── analytics.py
│   ├── calendar.py       # Phase 1 — Sezonalitate endpoints
│   ├── data.py
│   ├── firme.py
│   ├── monthly.py
│   ├── partners.py
│   ├── transactions.py
│   ├── waste.py
│   └── weather.py        # Phase 2 — Meteo endpoints
├── scripts/
│   ├── fetch_weather.py
│   ├── import_xls.py
│   ├── run_migration.py
│   ├── seed_holidays.py
│   └── migrations/
│       ├── 001_create_holidays.sql
│       ├── 002_create_company_closures.sql
│       └── 003_create_weather_oradea.sql
├── docs/
│   └── superpowers/
│       ├── specs/         # Design specifications
│       └── plans/         # Implementation plans
├── 2020-2026/            # Source .xls data files (gitignored)
├── index.html            # Persoane Fizice SPA
├── firme.html            # Firme B2B SPA
├── vercel.json           # Vercel config + explicit routes
├── requirements.txt      # psycopg2-binary only
├── CLAUDE.md             # Technical doc for AI-assisted development
├── MEMORIA.md            # Change log + tehnical details
└── README.md             # Acest fisier
```

---

## Dezvoltare

### Cerinte
- Python 3.12
- `psycopg2-binary` (singura dependenta runtime)
- `pandas`, `xlrd`, `openpyxl` (doar pentru scripts/import_xls.py)
- `pywin32` optional (doar pentru --use-com pe Windows)
- Node.js (pentru Vercel CLI)

### Setup local
```bash
pip install -r requirements.txt
pip install pandas xlrd openpyxl  # pentru import scripts
# .env.local cu POSTGRES_URL=postgresql://...

# Rulare locala
vercel dev
```

### Import date noi
```bash
# Pachete xls cu tranzactii
python scripts/import_xls.py 2026/04_aprilie  # un folder de luna
python scripts/import_xls.py 2020             # un folder de an
python scripts/import_xls.py --dry-run 2021   # verificare fara scriere

# Date meteo (incremental)
python scripts/fetch_weather.py --date-from 2026-04-18

# Sarbatori pentru ani noi
python scripts/seed_holidays.py --year-from 2031 --year-to 2035
```

### Deployment
Push pe `main` → Vercel auto-deploy. Branch-uri → preview URLs.

---

## Caracteristici UI

- **Dark Mode** (`#0a0a14` background, `#00d9ff` accent, `#00ff88` secondary)
- **Sticky Table Headers** (pozitia fixa la scroll)
- **Partner Profile Modal** (click pe nume oriunde)
- **City Details Modal** (click in Regiuni → Lista Localitati)
- **Filtre Avansate** multi-criteriu
- **Paginare** (25/pagina pe liste lungi)
- **Grafice Interactive** (Chart.js, tooltips detaliate)
- **Responsive** pana la mobile

---

<div align="center">

**Proiect on-production: https://internpaju.vercel.app/**

Dezvoltat cu Python + JavaScript + PostgreSQL, asistat de Claude Code (Anthropic).

---

**2020 - 2026** | **PAJU Reciclare** | Oradea, Romania

</div>
