# PAJU Dashboard - Claude Memory File

## Project Overview
PAJU hulladekfelvásárlási dashboard - komplex adatkezelő és analitikai rendszer a hulladékfelvásárlási tevékenységek nyomon követésére.

## Tech Stack

### Frontend
- **HTML5** + **Vanilla JavaScript**
- **Chart.js** - grafikonokhoz
- Single-page application (SPA) - `index.html`
- Dark theme design (#0a0a14 háttér, #00d9ff accent)

### Backend
- **Python 3.12** Serverless Functions (Vercel)
- API endpoints az `api/` mappában
- `psycopg2` PostgreSQL driver

### Database
- **PostgreSQL** hosted on **NeonDB**
- Connection: `POSTGRES_URL` environment variable (Vercel-ben beállítva)
- SSL required

### Deployment
- **Vercel** - automatic deployment from GitHub
- GitHub repo: `ebastyan/intern`
- Branch: `main`
- Auto-deploy on push

## Database Structure

### Tables
```
partners          - Partnerek (30,300+)
├── cnp (PK)      - 13 jegyű azonosító
├── name          - Teljes név
├── city          - Város
├── county        - Megye (judet)
├── street        - Utca
├── phone         - Telefon
├── email         - Email
├── birth_year    - Születési év
├── sex           - M/F
└── county_from_cnp - CNP-ből kiolvasott megye

transactions      - Tranzakciók (106,000+)
├── document_id (PK) - Dokumentum azonosító (PJ-XXXXXX)
├── date          - Dátum
├── cnp (FK)      - Partner CNP
├── payment_type  - Fizetési mód
├── iban          - Bankszámla
├── gross_value   - Bruttó érték
├── env_tax       - Környezetvédelmi adó
├── income_tax    - Jövedelemadó
└── net_paid      - Nettó kifizetett

transaction_items - Tranzakció tételek
├── id (PK)
├── document_id (FK)
├── waste_type_id (FK)
├── price_per_kg  - Ár/kg
├── weight_kg     - Súly kg
└── value         - Érték RON

waste_types       - Hulladék típusok
├── id (PK)
├── name          - Típus neve
└── category_id (FK)

waste_categories  - Hulladék kategóriák
├── id (PK)
└── name          - Kategória neve (Cupru, Aluminiu, Fier, stb.)
```

## API Endpoints

### `/api/analytics`
| Parameter | Description |
|-----------|-------------|
| `type=overview` | Teljes áttekintés |
| `type=yearly` | Éves összesítés |
| `type=monthly&year=YYYY` | Havi bontás |
| `type=county` | Megye szerinti |
| `type=city&county=X` | Város szerinti |
| `type=city_details&city=X` | Város részletek popup |
| `type=all_cities` | Összes város lista |
| `type=weekday` | Heti minták |
| `type=age` | Korosztály elemzés |
| `type=trends` | Trend összehasonlítás |
| `type=waste_by_region` | Hulladék regionális bontás |
| `type=custom_compare&months=1,2&category=X` | Egyedi összehasonlítás: hónapok + kategória szűrés, demográfia |

### `/api/partners`
| Parameter | Description |
|-----------|-------------|
| `q=keresés` | Név/CNP keresés |
| `cnp=XXX` | Partner profil |
| `top=N` | Top N partner |
| `inactive=days` | Inaktív partnerek |
| `onetime` | Egyszeri vásárlók |
| `filter` | Összetett szűrés |
| `regulars=weekly/monthly/yearly` | Rendszeres látogatók |
| `same_address` | Azonos címen élők |
| `same_family` | Családtagok |
| `big_suppliers` | Nagy beszállítók |
| `list=1` | Teljes partner lista (pagination) |

### `/api/transactions`
| Parameter | Description |
|-----------|-------------|
| `document_id=X` | Dokumentum részletek |
| `cnp=X` | Partner tranzakciói |
| `date_from/to` | Dátum szűrés |
| `daily=YYYY-MM-DD` | Napi összesítő |
| `visitors` | Látogatók szűrése |

### `/api/waste`
| Parameter | Description |
|-----------|-------------|
| `type=categories` | Kategóriák összesítése |
| `type=types&category=X` | Típusok listája |
| `type=prices&category=X` | Árfolyam történet |
| `type=monthly&category=X` | Havi bontás |

### `/api/monthly`
| Parameter | Description |
|-----------|-------------|
| `year=YYYY&month=MM` | Specifikus hónap részletei |
| (nincs param) | Összes hónap összefoglalója |

### `/api/data`
Dashboard fő adatok (summary cards)

## Frontend Sections

### 1. Sumar (Dashboard)
- 6 nagy statisztika kártya
- Top 10 partnerek
- Kategória megoszlás

### 2. Comparatie Anuala
- **Comparatie Personalizata** - Egyedi összehasonlítás:
  - Hónap választó (checkbox, bármely kombináció)
  - Kategória szűrő (opcionális)
  - Eredmény: tranzakciók, érték, partnerek minden évre
  - Demográfia: nem (M/F), korosztály (18-24, 25-34, stb.), top megyék
  - Kategória-specifikus: kg, érték, átlagár, partnerek
- Dinamikus éves összehasonlítás (minden év: 2022-2026+)
- Részletes táblázat YoY változásokkal
- Trend elemzés, dinamikus színek évekhez

### 3. Parteneri
**Tabs:**
- **VIP (Top 20)** - Legjobb partnerek
- **O Singura Data** - Egyszeri látogatók (szűrhető vizit számra)
- **Regulati** - Rendszeres látogatók (heti/havi/éves)
- **Inactivi** - 60+ napja inaktív partnerek
- **Familii/Adresa** - Családtagok, azonos címen lakók (megye/kategória szűrés)
- **Mari Furnizori** - Nagy beszállítók kategóriánként
- **Lista Completa** - TELJES partner lista:
  - Filterek: név, CNP, megye, város, utca, dátum, kategória, min vizit, min érték, nem
  - "Mindenki" toggle - összes partner vs csak tranzakcióval
  - Pagination (25/oldal)
  - Sortolás (érték, vizit, név, utolsó látogatás)

### 4. Deseuri
- Kategória összesítés (bar chart)
- Kördiagram
- Trend grafikon
- Havi "bajnok" kategória
- Árstatisztikák

### 5. Regiuni
- Megye megoszlás
- Top városok
- Hulladék regionális bontás (kategóriánként)
- **Lista Completa Localitati** - kattintható városok popup-pal
- Korosztály elemzés

### 6. Predictii
- Előrejelzési grafikon (összes történeti adatból)
- Dinamikus metodológia (multi-éves YoY átlag)

### 7. Statistice
- Részletes statisztikák
- Havi bontás kártyák

## Key Features

### Sticky Table Headers
Minden táblázatnál a fejléc rögzített görgetéskor:
```css
th { position: sticky; top: 0; background: #1a1a2e; z-index: 10; }
```

### Partner Profile Modal
- Click on partner name anywhere -> opens detailed profile
- Transaction history, waste breakdown, monthly pattern

### City Details Modal
- Click on city in "Lista Completa Localitati"
- Shows: partners, transactions, waste by category, top partners

### Family/Address Filters
- County (Judet) filter
- Category filter
- Date range filter
- Search by name/city/street

### Toggle Switch (Lista Completa)
- "Mindenki" ON: shows ALL 30,000+ partners
- "Mindenki" OFF: shows only partners with transactions

## File Structure
```
paju/
├── api/
│   ├── analytics.py   - Analitika API
│   ├── partners.py    - Partner kezelés API
│   ├── transactions.py - Tranzakció API
│   ├── waste.py       - Hulladék statisztika API
│   ├── data.py        - Dashboard adat API
│   └── monthly.py     - Havi részletek API
├── index.html         - Főoldal (teljes SPA)
├── firme.html         - Firme B2B dashboard (SPA)
├── vercel.json        - Vercel konfiguráció
├── requirements.txt   - Python függőségek
├── CLAUDE.md          - Ez a fájl (memoria)
├── MEMORIA.md         - Részletes projekt dokumentáció
└── README.md          - Projekt dokumentáció
```

## Important Notes

### SQL Parameter Ordering
When building dynamic queries with multiple WHERE clauses and subqueries, parameter order must match placeholder order in SQL:
- Stats params (category, dates) separate from where params (search)
- Order depends on query structure (CTE first vs subquery first)

### ILIKE vs =
Use `ILIKE %s` for case-insensitive matching (city names, categories)
Use `= %s` for exact match (CNP, sex)

### LEFT JOIN vs JOIN
- `LEFT JOIN` when showing partners even without transactions
- `JOIN` when filtering requires transaction data

## Statistics (as of Feb 2026)
- Total turnover: ~250.3M RON (2022-2026)
- Transactions: 112,765+
- Transaction items: 225,089+
- Registered partners: 30,853+
- Waste categories: 16
- Waste types: 47
- Period: 2022.01 - 2026.02

### Yearly breakdown
| Year | Transactions | Partners | Working days | Total RON |
|------|-------------|----------|-------------|-----------|
| 2022 | 28,389 | ~8,500 | 271 | ~60.9M |
| 2023 | 28,355 | ~8,750 | 272 | ~61.0M |
| 2024 | 28,029 | 8,790 | 280 | ~70.8M |
| 2025 | 25,284 | ~8,800 | 272 | ~52.1M |
| 2026 | 2,708 | ~2,500 | 30 | ~5.4M |

## Development

### Local
```bash
pip install -r requirements.txt
vercel dev
```

### Deploy
```bash
git add . && git commit -m "message" && git push
# Vercel auto-deploys from GitHub
```

### Environment Variables (Vercel)
- `POSTGRES_URL` - NeonDB connection string
