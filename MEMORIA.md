# PAJU - Teljes Projekt Dokumentacio

> **FONTOS**: Ez a fajl tartalmazza a projekt MINDEN reszletet. Ha ujra megnyitod a chat-et, olvasd el ezt a fajlt es tudni fogod pontosan mi ez es hogy mukodik.

---

## 1. MI EZ A PROJEKT?

**PAJU** = Hulladekfelvasarlo ceg (Nagyvarad/Oradea, Romania) belso dashboard rendszere.

### Cel
Ket kulonallo dashboard a ceg ket fo tevekenysegerol:

| Dashboard | URL | Leiras |
|-----------|-----|--------|
| **Persoane Fizice** | `/` vagy `/index.html` | Lakossagi hulladekfelvasarlas (maganszemelyek) |
| **Firme (B2B)** | `/firme.html` | Cegeknek torteno hulladek ERTEKESITES |

### Uzleti logika
1. **Persoane Fizice**: A ceg VASAROL hulladekot maganszemelektol (reztol a vasig)
2. **Firme**: A ceg ELAD hulladekot mas cegeknek (nagykereskedelem)

---

## 2. TECHNOLOGIAI STACK

### Frontend
```
- HTML5 + Vanilla JavaScript (NINCS React/Vue/Angular!)
- Chart.js v3+ (grafikonok)
- CSS (dark theme: #0a0a14 hatter, #00d9ff accent szin)
- Single Page Application (SPA) - tab rendszer
```

### Backend
```
- Python 3.12 (Vercel Serverless Functions)
- psycopg2 (PostgreSQL driver)
- API endpoints: /api/*.py
```

### Database
```
- PostgreSQL (hosted: NeonDB)
- Connection string: POSTGRES_URL env variable
- SSL: REQUIRED
```

### Hosting & Deployment
```
- Platform: Vercel
- GitHub repo: ebastyan/intern
- Branch: main
- Deploy: Automatikus push utan
```

---

## 3. ADATBAZIS KAPCSOLAT

```python
# NeonDB PostgreSQL connection
db_url = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Vagy Vercel env variable-bol:
import os
db_url = os.environ.get('POSTGRES_URL')
```

---

## 4. ADATBAZIS STRUKTURA

### 4.1 Persoane Fizice tablak

```sql
-- Partnerek (maganszemelyek) - 30,000+ rekord
partners (
    cnp VARCHAR(13) PRIMARY KEY,  -- Roman szemelyi szam (13 jegy)
    name VARCHAR(255),
    city VARCHAR(100),
    county VARCHAR(50),           -- Megye (judet)
    street VARCHAR(255),
    phone VARCHAR(20),
    email VARCHAR(100),
    birth_year INTEGER,
    sex CHAR(1),                  -- M/F
    county_from_cnp VARCHAR(50)   -- CNP-bol kiolvasott megye
)

-- Tranzakciok - 51,000+ rekord
transactions (
    document_id VARCHAR(20) PRIMARY KEY,  -- Format: PJ-XXXXXX
    date DATE,
    cnp VARCHAR(13) REFERENCES partners(cnp),
    payment_type VARCHAR(20),
    iban VARCHAR(50),
    gross_value DECIMAL(12,2),
    env_tax DECIMAL(12,2),
    income_tax DECIMAL(12,2),
    net_paid DECIMAL(12,2)
)

-- Tranzakcio tetelek
transaction_items (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(20) REFERENCES transactions(document_id),
    waste_type_id INTEGER REFERENCES waste_types(id),
    price_per_kg DECIMAL(8,2),
    weight_kg DECIMAL(10,2),
    value DECIMAL(12,2)
)

-- Hulladek tipusok
waste_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    category_id INTEGER REFERENCES waste_categories(id)
)

-- Hulladek kategoriak
waste_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50)  -- Cupru, Aluminiu, Fier, DEEE, Acumulatori, etc.
)
```

### 4.2 Firme (B2B) tablak

```sql
-- Cegek - 50+ rekord
firme (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
)

-- Ertekesitesek (B2B tranzakciok) - 4,400+ rekord
vanzari (
    id SERIAL PRIMARY KEY,
    firma_id INTEGER REFERENCES firme(id),
    data DATE,
    year INTEGER,
    month INTEGER,
    numar_aviz VARCHAR(50),
    tip_deseu VARCHAR(100),
    cantitate_livrata DECIMAL(12,2),
    cantitate_receptionata DECIMAL(12,2),
    pret_achizitie DECIMAL(10,2),
    pret_vanzare DECIMAL(10,2),
    valoare_ron DECIMAL(12,2),
    adaos_final DECIMAL(12,2),
    transport_ron DECIMAL(12,2),
    numar_auto VARCHAR(20),
    nume_sofer VARCHAR(100),
    tara_destinatie VARCHAR(50),
    transportator VARCHAR(100)
)

-- Hulladek osszesites (Excel Sumar sheet-ekbol)
sumar_deseuri (
    id SERIAL PRIMARY KEY,
    tip_deseu VARCHAR(100),
    year INTEGER,
    month INTEGER,
    cantitate_kg DECIMAL(12,2),
    valoare_ron DECIMAL(12,2),
    adaos_ron DECIMAL(12,2)
)

-- Szallitasi koltsegek (regi tabla, mar NEM hasznalt)
transporturi_firme (
    id SERIAL PRIMARY KEY,
    year INTEGER,
    month INTEGER,
    destinatie VARCHAR(100),
    firma_name VARCHAR(255),
    descriere VARCHAR(255),
    transportator VARCHAR(100),
    suma_fara_tva DECIMAL(12,2),
    tva DECIMAL(12,2),
    total DECIMAL(12,2)
)
```

---

## 5. API ENDPOINTS

### 5.1 Persoane Fizice API-k

#### `/api/analytics`
```
?type=overview        - Teljes attekintes
?type=yearly          - Eves osszesites
?type=monthly&year=X  - Havi bontas
?type=county          - Megye szerinti
?type=city&county=X   - Varos szerinti
?type=city_details&city=X - Varos popup reszletek
?type=all_cities      - Osszes varos lista
?type=weekday         - Heti mintak
?type=age             - Korosztaly elemzes
?type=trends          - Trend osszehasonlitas
?type=waste_by_region - Hulladek regionalis bontas
?type=tops            - Top statisztikak
?type=holidays        - Unnepnapok elemzese
```

#### `/api/partners`
```
?q=kereso             - Nev/CNP kereses
?cnp=XXX              - Partner profil
?top=N                - Top N partner
?inactive=days        - Inaktiv partnerek
?onetime              - Egyszeri vasarlok
?filter               - Osszetett szures
?regulars=weekly/monthly/yearly - Rendszeres latogatok
?same_address         - Azonos cimen elok
?same_family          - Csaladtagok
?big_suppliers        - Nagy beszallitok
?list=1&page=X        - Teljes lista (pagination)
```

#### `/api/transactions`
```
?document_id=X        - Dokumentum reszletek
?cnp=X                - Partner tranzakcioi
?date_from/to         - Datum szures
?daily=YYYY-MM-DD     - Napi osszesito
?visitors             - Latogatok szurese
```

#### `/api/waste`
```
?type=categories      - Kategoriak osszesitese
?type=types&category=X - Tipusok listaja
?type=prices&category=X - Arfolyam tortenet
?type=monthly&category=X - Havi bontas
```

#### `/api/monthly`
```
?year=YYYY&month=MM   - Specifikus honap reszletei
(nincs param)         - Osszes honap osszefoglaloja
```

#### `/api/data`
```
(nincs param)         - Dashboard fo adatok (summary cards)
```

### 5.2 Firme API-k

#### `/api/firme`
```
?type=overview        - Altalanos osszesites
?type=list            - Cegek listaja
?type=firma&id=X      - Egy ceg reszletei
?type=vanzari&firma_id=X - Ceg ertekesitesei
?type=monthly&year=X  - Havi osszesites
?type=deseuri&year=X  - Hulladek tipusok
?type=top&limit=N     - Top cegek
?type=transporturi    - Szallitasi adatok
?type=yearly          - Eves osszehasonlitas
?type=sofer_profile&sofer=X - Sofor profil
?type=transportator_profile&transportator=X - Szallito ceg profil
?type=country_profile&country=X - Orszag profil
```

---

## 6. FRONTEND STRUKTURA

### 6.1 index.html - Persoane Fizice Dashboard

**Tabok:**
1. **Sumar** - 6 nagy stat kartya, top 10 partnerek, kategoria megoszlas
2. **2024 vs 2025** - Havi osszehasonlito grafikonok, reszletes tablazat
3. **Parteneri** - 7 sub-tab:
   - VIP (Top 20)
   - O Singura Data (egyszeri latogatok)
   - Regulati (rendszeres: heti/havi/eves)
   - Inactivi (60+ nap)
   - Familii/Adresa (csaladtagok, azonos cim)
   - Mari Furnizori (nagy beszallitok)
   - Lista Completa (teljes lista, filterek, pagination)
4. **Deseuri** - Kategoria osszesites, kordiagram, trend
5. **Regiuni** - Megye/varos megoszlas, korosztaly
6. **Predictii** - Elojelzes grafikon
7. **Statistice** - Reszletes statisztikak

### 6.2 firme.html - B2B Dashboard

**Tabok:**
1. **Sumar** - Yearly chart, top firmak, osszesites
2. **Firme** - Cegek listaja kereshetoen, kattinthato profilok
3. **Lunar** - Havi bontas tablazat es chart
4. **Deseuri** - Hulladektipusok szerinti bontas, filterek
5. **Comparatie** - Eves osszehasonlitas (2022-2024)
6. **Transport** - Szallitasi koltsegek, sofor/transportator/orszag profilok
7. **Statistici** - Top 10 tablak (rendezhetok), sezonalitas, marjak

---

## 7. FONTOS TECHNIKAI RESZLETEK

### 7.1 Dark Theme CSS
```css
body {
    background: #0a0a14;
    color: #e0e0e0;
}
.accent { color: #00d9ff; }
.card { background: #1a1a2e; }
th {
    position: sticky;
    top: 0;
    background: #1a1a2e;
    z-index: 10;
}
```

### 7.2 Chart.js Tooltip Format
```javascript
function fmt(n) {
    return n.toLocaleString('ro-RO', {maximumFractionDigits: 0});
}
// Tooltip: teljes szam, nincs M/K rovidites
```

### 7.3 Rendezheto Tablazat
```javascript
// Sortable headers
document.querySelectorAll('.sortable').forEach(th => {
    th.addEventListener('click', () => {
        const key = th.dataset.sort;
        const asc = !th.classList.contains('asc');
        // Sort logic...
    });
});
```

### 7.4 SQL Parameter Sorrend
```python
# FONTOS: Parameter sorrend egyeznie kell a placeholder-ekkel!
# Rossz: params = [search, category, date]  de SQL: WHERE category=%s AND date=%s AND name ILIKE %s
# Jo: params = [category, date, search]
```

---

## 8. ISMERT ADAT PROBLEMAK

### 8.1 sumar_deseuri tabla
| Ev | Honapok | Lefedettség | Megjegyzes |
|----|---------|-------------|------------|
| 2022 | 12/12 | ~79% | OK |
| 2023 | 5/12 | ~37% | Jan-Jul Excel-ben NINCS tip_deseu! |
| 2024 | 12/12 | 100% | Teljes |

**Frontend figyelmeztetest mutat ha 2022/2023 van kivalasztva!**

### 8.2 vanzari.tip_deseu
| Ev | Rekordok tip_deseu-val | Ossz rekord | Lefedettség |
|----|------------------------|-------------|-------------|
| 2022 | 826 | 1,296 | 63.7% |
| 2023 | 0 | 1,500 | 0% |
| 2024 | 1,520 | 1,594 | 95.4% |

### 8.3 Transport koltsegek
- Regi: `transporturi_firme` tabla (39 rekord, 149k RON) - NEM HASZNALT
- Uj: `vanzari.transport_ron` oszlop (6.4M RON ossz)

---

## 9. FAJL STRUKTURA

```
paju/
├── api/
│   ├── analytics.py    # Persoane Fizice analitika
│   ├── partners.py     # Partner kezeles
│   ├── transactions.py # Tranzakciok
│   ├── waste.py        # Hulladek statisztika
│   ├── data.py         # Dashboard fo adatok
│   ├── monthly.py      # Havi reszletek
│   └── firme.py        # Firme (B2B) osszes endpoint
├── index.html          # Persoane Fizice dashboard (SPA)
├── firme.html          # Firme B2B dashboard (SPA)
├── vercel.json         # Vercel konfiguracio
├── requirements.txt    # Python fuggosegek (psycopg2-binary)
├── .gitignore          # Git ignore szabalyok
├── CLAUDE.md           # Claude AI kontextus fajl
├── MEMORIA.md          # Ez a fajl
└── README.md           # Projekt leiras (roman nyelven)
```

---

## 10. FEJLESZTESI KORNYEZET

### Lokalis fejlesztes
```bash
# Fuggosegek telepitese
pip install -r requirements.txt

# Vercel CLI-vel lokalis szerver
vercel dev

# Vagy kozvetlen Python
python -m http.server 8000
```

### Deploy
```bash
git add .
git commit -m "description"
git push
# Vercel automatikusan deploy-ol!
```

### Vercel Environment Variables
```
POSTGRES_URL = postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require
```

---

## 11. STATISZTIKAK (2024 December)

### Persoane Fizice
| Mutato | Ertek |
|--------|-------|
| Osszes rulaj | ~118.7M RON |
| Tranzakciok | 51,000+ |
| Regisztralt partnerek | 30,000+ |
| Aktiv partnerek | 13,000+ |
| Hulladek kategoriak | 16 |
| Idoszak | 2024.01 - 2025.11 |

### Firme (B2B)
| Mutato | Ertek |
|--------|-------|
| Osszes ertek | ~260M RON (2022-2024) |
| Tranzakciok | 4,400+ |
| Cegek | 50+ |
| Transport koltseg | ~6.4M RON |
| Idoszak | 2022.01 - 2024.12 |

---

## 12. NYELV

- **Dashboard nyelv**: ROMAN (minden felirat!)
- **Kod kommentek**: Magyar/Angol
- **Dokumentacio**: Magyar

---

## 13. FEJLESZTESI NAPLO (Legutobbi)

### 2024-12-04 - Cleanup
- Torolve 31 felesleges fajl:
  - 4 regi dashboard HTML
  - 10 JSON adat fajl (~5.5 MB)
  - 16 egyszeri migration script
  - 1 redundans dokumentacio
- Repo most tiszta es production-ready

### 2024-12-03 - Firme fejlesztesek
- Rendezheto Top 10 tablak
- Transport profilok (sofor, szallito, orszag)
- tip_deseu import 2024-re
- Sezonalitas chart magyarazat

### 2024-12-02 - Firme dashboard javitasok
- Ceg normalizalas
- Chart tooltip javitas
- Nyelv: Magyar -> Roman
- Deseuri/Comparatie/Statistici tab fejlesztesek

---

## 14. GYORS HIVATKOZASOK

| Mit akarsz? | Hol talalhato? |
|-------------|----------------|
| Persoane Fizice dashboard | `/index.html` |
| Firme dashboard | `/firme.html` |
| API endpoints | `/api/*.py` |
| DB connection | Section 3 fent |
| DB struktura | Section 4 fent |
| Ismert hibak | Section 8 fent |

---

## 15. MEGJEGYZESEK CLAUDE-NAK

1. **NE hasznalj framework-ot** - tiszta vanilla JS
2. **Minden szoveg ROMAN** a dashboardon
3. **Chart.js v3+** formatumot hasznalj
4. **psycopg2** a PostgreSQL-hez
5. **Vercel** auto-deploy GitHub push-ra
6. **NeonDB** free tier - limitalt connection

---

*Utolso frissites: 2024-12-04*
