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
-- Partnerek (maganszemelyek) - 30,300+ rekord
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

-- Tranzakciok - 106,000+ rekord
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
?type=custom_compare&months=1,2&category=X - Egyedi osszehasonlitas honapok+kategoria+demografia
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
?type=analysis&waste_type_ids=1,2&categories=Fier&date_from=X&date_to=X&aggregation=monthly - Reszletes hulladek elemzes
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
2. **Comparatie Anuala** - Dinamikus eves osszehasonlitas (minden ev), grafikonok, reszletes tablazat
   - **Comparatie Personalizata** (uj!): honap valaszto checkboxok + kategoria szuro
     - Eredmeny tablazat: tranzakciok, rulaj, partnerek, munkanapok, media/zi, trend % (minden evre)
     - 4 grafikon: Rulaj/Ev, Partnerek (szelekcio vs osszes), Nem M/F (stacked), Korcsoport (stacked)
     - Top megyek tablazat, kategoria bontas (kg+RON evre/kategorianként)
     - Pld: valaszd ki "Ianuarie" + "Cupru" = latod ki hozott rezet januarban, evrol-evre, demografiaval
3. **Parteneri** - 7 sub-tab:
   - VIP (Top 20)
   - O Singura Data (egyszeri latogatok)
   - Regulati (rendszeres: heti/havi/eves)
   - Inactivi (60+ nap)
   - Familii/Adresa (csaladtagok, azonos cim)
   - Mari Furnizori (nagy beszallitok)
   - Lista Completa (teljes lista, filterek, pagination)
4. **Deseuri** - Kategoria osszesites, kordiagram, trend, **Analiza Detaliata** (datum + tipus/kategoria valaszto, grafikon, tablazat)
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

## 11. STATISZTIKAK (2026 Februar)

### Persoane Fizice
| Mutato | Ertek |
|--------|-------|
| Osszes rulaj | ~250.3M RON |
| Tranzakciok | 112,765+ |
| Tranzakcio tetelek | 225,089+ |
| Regisztralt partnerek | 30,853+ |
| Hulladek kategoriak | 16 |
| Hulladek tipusok | 47 |
| Idoszak | 2022.01 - 2026.02 |

#### Eves bontas (Persoane Fizice)
| Ev | Tranzakciok | Partnerek | Munkanapok | Rulaj RON |
|----|-------------|-----------|------------|-----------|
| 2022 | 28,389 | ~8,500 | 271 | ~60.9M |
| 2023 | 28,355 | ~8,750 | 272 | ~61.0M |
| 2024 | 28,029 | 8,790 | 280 | ~70.8M |
| 2025 | 25,284 | ~8,800 | 272 | ~52.1M |
| 2026 | 2,708 | ~2,500 | 30 | ~5.4M |

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

### 2026-04-20 - Phase 3.5: Weather pill + Timeline chart

Ket kisebb polish feature a Phase 3 utan, felhasznaloi keresre.

#### Weather pill a partner modalban
- **Backend**: `api/partners.py` `get_partner_details` — a `recent_transactions` SELECT-et LEFT JOIN weather_oradea-val bovitettem (temp_max/min, precipitation_sum, snowfall_sum, wind_speed_max, wind_gusts_max, weather_code, humidity_mean, cloudcover_mean). Minden tranzakcio objektum kap egy `weather` mezot (vagy null ha nincs weather adat arra a napra).
- **Frontend**: `renderWeatherPill(w)` helper function (reuse a Phase 3-as `forecastEmoji`-t). Inline pastila jelenik meg a tranzakcio data+doc_id mellett: emoji + temp range + ploaie/ho/szel (ha >= kuszobok).
- **Peldak**:
  - `☀️ 8..12°C` — tiszta napos
  - `🌧️ 15°C · 15mm` — esos
  - `❄️ -2..1°C · 4cm ho` — havas
  - `💨 18°C · vant 72km/h` — szeles
- **Visszamenoleges mukodes**: Minden tranzakcio a 2020-2026 periodusbol get weather data (weather_oradea table 2,299 napja fedi le).

#### Timeline trafic + vreme chart
- **Hely**: Meteo tab, "Insights" es "Cele mai atipice" koze szurt be (`#meteoTimelineChart` + `#meteoTimelineNotable`).
- **Tartalom**:
  - Chart.js line chart: napi actual trafic (solid cyan) + baseline (pontozott feher)
  - Kifestett pontok a "notable" napokon: eso >=10mm, ho >=2cm, ger <=-5°C, kanikula >=32°C, szel >=70km/h
  - Tooltip hover: teljes meteo kontextus adott napra
  - Alatta chip-strip: minden notable nap felsorolva emoji + data + leiras
- **Data source**: reuse `/api/weather?type=residuals` (mar van value + baseline + weather per day). Nincs uj endpoint.
- **Date range**: reuse a Meteo tab meglevo DateFrom/DateTo filter — `refreshMeteo()` hozzácsatolt `loadMeteoTimeline()`.
- **Chart implementacio**: Chart.js `pointRadius` + `pointBackgroundColor` per-index arrays-szel (csak notable napok radius=5, tobbi 0). `notableWeatherEmoji(r)` helper visszaad `{emoji, label, color}` vagy null-t.

#### Commits
- `e4b234d` — Add weather pill to each transaction row in partner profile modal
- `d8ae253` — Add Timeline trafic + vreme chart to Meteo tab

---

### 2026-04-20 - Phase 3: Prognoza 7-zile (elore tekinto forecast)

#### Cel
Eddig a dashboard tisztan visszafele nezett (mi tortent). Phase 3 elore tekint: a kovetkezo 7 nap idojaras-elorejelzese + becslet a varhato forgalomra a Phase 2-es hindcast motor felhasznalasaval.

#### Design (spec: `docs/superpowers/specs/2026-04-20-prognoza-7-zile-design.md`)
- **Ket felulet, egy backend endpoint**
  - Sumar tab widget: 7-oszlopos strip egy pillantasra (emoji + temp + estimat + %-delta)
  - Meteo tab card (legfelul): 7 blokk reszletezett breakdown-nal + confidence tier
- **Metrika**: mind a 4 (partners / transactions / kg / ron) mindket feluleten, dropdown-nal valthato
- **Formula (additiv)**: `predicted = baseline × (1 + Σ category_effect_pct)`
  - baseline = 28-napos heti-nap matched median (ugyanaz mint residuals)
  - category_effects = az adott nap meteojahoz illo osszes kategoria hatasa az OSSZES historikus adatbol (nem szelektalt periodus)
- **Confidence tier**: `min_n` a matchelt kategoriakbol — `high` ≥100, `ok` 30-99, `low` <30 (narancssarga badge)
- **Vasarnap**: `🔒 INCHIS` (fara program)

#### Backend (`api/weather.py`)
- **Module-level refactor**: `CATEGORIES` listat kiemeltem `overview()`-bol modul-szintre `_RANKING_CATEGORIES` neven → forecast is ugyanazt hasznalja
- **Uj helper-ek**:
  - `_open_meteo_forecast(forecast_days=7)` — Open-Meteo `/v1/forecast` endpoint (daily + hourly aggregalt), urllib stdlib, 10s timeout, None-t ad vissza halozati hibanal
  - `_forecast_desc(w)` — kompakt emberi leiras: "5..13°C, 2.2mm ploaie, vant 41km/h"
  - `_fetch_json(url, timeout)` — JSON GET helper
- **Uj methodusok a `handler` class-ben**:
  - `_all_time_category_effects(cur, metric)` — minden kategoriara kiszamolja az effect_pct-t az osszes historikus adatbol (min 5 minta), visszaad `{name → {emoji, range, effect_pct, n, fn}}`
  - `_forecast_baselines(cur, metric, dates)` — egy SQL round-trip: `unnest(dates::date[])` + korrelalt subquery `PERCENTILE_CONT(0.5) WHERE dow_match AND date BETWEEN d-28 AND d-1`, visszaad `{date_str → float|None}`
  - `forecast(cur, metric)` — a fo method: fetch forecast → per-day baseline + category matching → predicted + confidence tier → response JSON
- **Uj route**: `elif qtype == "forecast": result = self.forecast(cur, metric)`

#### Frontend (`index.html`)
- **Sumar widget** (`sumarForecastCard`): grid 7-oszlop, emoji mapper (`forecastEmoji`) eso/ho/felho alapjan, hover tooltip a breakdown-nal, kattintas → `showSection('meteo')`
- **Meteo tab card** (`meteoForecastCard`, legfelul a section-meteo-ban): 7 blokk, minden blokk tartalmaz:
  - Fejlec: date + dow + emoji + weather_desc
  - "Estimat: ~X parteneri · ±X% vs Dow normal (baseline Y) · confidence ok/high/low (min N zile similare)"
  - Cauze breakdown tabla (kategoria · effect_pct · n zile) + "Total ajustare"
- **Mindket widget wired a toltesi logikaba**: `loadAllData()` -ben `loadSumarForecast()` hivas + dropdown onchange binding; `loadMeteo()` -ben `loadMeteoForecast()` hivas + dropdown onchange binding
- **Error handling**: ha a backend `{error: "forecast_unavailable"}`-ot ad, narancssarga "Prognoza temporar nedisponibila" uzenet

#### Eles teszt (2026-04-20 11:57)
- `/api/weather?type=forecast&metric=partners` live on internpaju.vercel.app
- 7 nap vissza, math egyezik: Luni baseline 110 × 1.031 = 113.4 ✓
- Vasarnap (2026-04-26) correctly `is_closed: true`
- Sumar widget megjelenik, Meteo card is elerheto

#### Tasks: 8 task, 6 commit, ~45 perc (subagent-driven development)
- T1: `defe16e` — Open-Meteo forecast fetcher + `_forecast_desc`
- T2: `1fce52a` — `_RANKING_CATEGORIES` module-level + `_all_time_category_effects`
- T3: `58aa5a8` — `forecast()` method + `_forecast_baselines` + routing
- T4: (data) — live smoke test backend
- T5: `dc2c419` — Sumar widget (7-oszlop)
- T6: `65200b8` — Meteo tab detailed card
- T7: `6117d90` — CLAUDE.md doc update
- T8: (verify) — live verify mindket feluleten

#### Jovoben (nem ebben a plan-ben)
- DB cache a forecast-nak (weather_forecast tabla, naponta frissit) ha Open-Meteo rate-limit jon
- Predikcios pontossag nyomkovetese (48 ora utan osszehasonlitani valossagal)
- Scenario szimulator ("mi van ha 20mm holnap esne?")
- Reggeli email osszefoglalo ugyanezzel az endpoint-tal

---

### 2026-04-18 - Phase 1 (Sezonalitate) + Phase 2 (Meteo & Trafic) + 2020/2021/2026 Adat Import

#### Phase 1: Sezonalitate tab (Kalendar & Szezonalitas alap)
- **Uj DB tablak:**
  - `holidays` (date, name, type, is_official) — 220 sor, 2020-2030 lefedve
    - Roman nemzeti unnepek (10/ev), katolikus husvet+punkosd (5/ev), ortodox husvet+punkosd (5/ev)
    - Algoritmusok: Butcher Gergely-naptar (katolikus), Meeus julianus + 13 nap (ortodox)
  - `company_closures` (date, reason) — automatikus detekcio workflow
- **Uj scriptek:**
  - `scripts/run_migration.py` — SQL migracios runner
  - `scripts/seed_holidays.py` — unnep generator + DB upsert, `--self-test` flag
- **Uj API endpoint: `/api/calendar`**
  - `?type=holidays&year=` | `closures` | `closure_candidates` (auto-detektalt zarva periodusok)
  - `?type=working_days&date_from=&date_to=` | `weekly_pattern` | `monthly_pattern&year=`
  - `?type=holiday_effect&window=3` — unnep-blokk hatasok elemzese (konkret pelda napokkal)
  - `?type=illegal_workdays` — audit: piros napokon tortent tranzakciok
- **Uj frontend tab: Sezonalitate**
  - Tipar saptamanal (H-Szo) — nap/ora alapu bar chart, ev-szelektor (2020-2026)
  - Tipar lunar — havi vonaldiagram, ev-szelektor
  - Impactul sarbatorilor & vacantelor — unnep-blokk alapu elemzes per-ev breakdown-nal + dating, piros/zold legenda
  - Perioade inchise (auto-detectate) — grouped by year, collapsed Sundays/holidays
  - Audit tranzactii pe zile oficial nelucratoare
- **Key insights:**
  - Nyitva: H-P 9h, Szo 5h; Vasarnap mindig zarva
  - Szombat a legintenzivebb (~17 partner/ora vs. 10-11 hetkoznap)

#### Phase 2: Meteo & Trafic (Idojaras-elemzo)
- **Uj DB tabla: `weather_oradea`** — 22 oszlop (hom, precipitacio, szel, sugarzas, paratartlom, WMO kod)
- **Uj script: `scripts/fetch_weather.py`** — Open-Meteo Historical API kliens (ingyen, API kulcs nelkul)
  - Oradea koordinatak: 47.0722°N, 21.9217°E
  - Parallel daily + hourly lekerdezes, hourly -> daily mean aggregalas (pressure/humidity/cloud)
  - Idempotens (ON CONFLICT DO UPDATE + fetched_at)
  - `--self-test` flag ellenorzi az Open-Meteo API mukodeset
- **Uj API endpoint: `/api/weather`**
  - `?type=residuals&metric=&date_from=&date_to=` — napi actual + baseline + residual + weather
  - `?type=buckets&variable=` — bucket alapu osszehasonlitas (7 valtozora)
  - `?type=lag_curve&variable=` — Pearson korrelacio lag -2..+3 napokon
  - `?type=extreme_days&limit=` — top-N atipikus nap teljes meteo szignaturaval
  - `?type=overview&metric=` — kovetkezteto engine: 4 hipotezis-csalad (bucket, kuszob, lag, interakcio) + ranking 25 meteo-kategoriaval + period_context (ev-osszehasonlitas)
- **Baseline model:** 28-napos heti-nap matched median (tipar adjusting, nem szezonalitas-fix)
- **Hypothesis engine (narativan):**
  - Family A: bucket osszehasonlitas (rain/snow/temp/wind bin-ekre)
  - Family B: Kuszob-detektalas (t-statisztika max)
  - Family C: Lag-elemzes (peak lag kiemelese)
  - Family D: Interakciok (cold+wet, hot+dry, etc.)
- **Uj frontend tab: Meteo**
  - Kontextus banner — szelektalt periodus vs. mas evek ugyan azok a napjai
  - "Ce invata datele" — sinteza + kuszob-gradient 6 csaladra (hom, eso, ho, szel, paratartlom, eg)
  - Vreme STRICA traficul — bad weather cards (effect <= -2% VAGY 3+ strong-negativ nap)
  - Vreme OPTIMA pentru trafic — good weather cards
  - Alte conditii (fara efect clar)
  - Detalii cu zile concrete — insight cards konkret napok peldakkal + lag trigger
  - Cele mai atipice 20 zile — tabla teljes meteo szignaturaval
- **"Strong classification":** ha egy kategoria avg kicsi, de 3+ nap van erős hatassal (residual_pct >= 15%), akkor is "bad"/"good" kategoria — elkulonit narrativan
- **Key UX principles levont:**
  - Statisztika helyett NARRATIVA (`+33% vs normal` helyett `vin cu 33% mai multi parteneri`)
  - KONKRET NAPOK bizonyitekkent (verifikalhato)
  - Szezonalis dekonvolucio baseline-al
  - "Ez a periodus szezonal gyenge volt" kontextus a verdiktben

#### 2020/2021/2026 Adat Import
- **Uj script: `scripts/import_xls.py`**
  - .xls feldolgozas pandas + xlrd-vel (openpyxl fallback sérült fajlokra)
  - Romanian CNP parser: birth_year/sex/county_from_cnp automatikus
  - Filename-date parser folder context-tel (`2020/01_ianuarie/` -> year=2020, month=1)
  - Idempotens: `existing_docs` + `ON CONFLICT DO NOTHING`
  - execute_values batch inserts (gyors)
  - `--use-com` opcio Excel COM fallback sérült fajlokra
- **Import adatok:**
  - 2020: 243 fajl, 16,102 tranzakcio (Jan 7 – Nov 28, nincs december adat)
  - 2021: 278 fajl, 25,838 tranzakcio (Jan 4 – Dec 18)
  - 2026: 82 fajl, +2,719 uj tranzakcio (febr-apr hozzaadva)
- **Hibakezeles:**
  - 6 COM-szuksegu fajl (utf-16-le encoding): 2020/21.01, 2020/23.01, 2021/04.05, 2021/25.09, 2021/11.10, 2021/15.11 — mind sikeresen behuzva COM fallback-el
  - 1 bugos filename: `29.0102020.xls` (hianyzik pont) -> parser javitva folder hints-szel, DB-ben date 202-01-29 -> 2020-01-29 javítva
  - 9 deadlock (2021+2026 parallel futott): mind sikeresen re-imported serial modban
- **Kiterjesztesek:**
  - `weather_oradea`: +731 nap (2020-01-01 -> 2021-12-31), total 2,299 sor
  - `holidays`: +40 sor (2020-2021), total 220
  - Frontend datum filterek: default 2022-01-01 -> 2020-01-01 (5 helyen)
  - Sezonalitate ev-dropdown: 2020, 2021 hozzaadva
  - Big suppliers dropdown: 2020, 2021 hozzaadva
  - Meteo tab default datum: 2022-01-03 -> 2020-01-01
  - `api/partners.py`, `api/transactions.py`: default date_from 2022-01-01 -> 2020-01-01
- **DB FINAL: 160,769 tranzakcio, ~323,000 tetel, 31,220 partner, 2020.01.07 - 2026.04.17** (all 602 file-dates accounted for, 0 missing)

#### Utolag talalt es kijavitott bugok az importhoz:
- **commit-every=20 + deadlock rollback**: parhuzamos 2021+2026 import deadlockokat kapott. Mivel `conn.rollback()` az egesz batch-et torli, az elozo ~20 fajl ertekei elvesztek. Javítás: commit-every=1 + serial re-run → 2021-be +854 tx, 2026-ba +2,491 tx.
- **2 misnamed xls fájl**:
  - `2020/03_martie/13.02.2020.xls` (valodi datum: 2020-03-13, PJ 76189-76280)
  - `2021/12_decembrie/10.01.2021.xls` (valodi datum: 2021-12-10, PJ kontinuus)
  - Javítás: parser frissítve — folder_month > filename_month precedenssel. DB-ben 205 sor `UPDATE date` -el korrigalva.

### 2026-02-24 - Analiza Detaliata Deseuri (uj funkcio)
- **Uj feature a Deseuri szekcioban**: reszletes hulladek elemzo panel
- **Backend (`api/waste.py`):**
  - Uj endpoint: `?type=analysis`
  - Parameterek: `waste_type_ids` (egyedi tipusok), `categories` (egesz kategoriak), `date_from`, `date_to`, `aggregation` (daily/monthly/yearly)
  - Kategoriak feloldasa: a megadott kategoria nevek alapjan lekerdezi az osszes altipus ID-t, majd egyetlen sorozatkent osszesiti
  - Egyedi tipus ID-k felulirjak a kategoria csoportositast (ha mindketto meg van adva)
  - Visszaadott adat: `periods[]`, `series[]` (tipusonkent/kategorianként: kg, ertek, tranzakciok, atlag ar), `summary` (osszes kg, ertek, atlag/periodus)
- **Frontend (`index.html`):**
  - Uj HTML panel: datum valaszto (De la / Pana la), aggregacio valaszto (Zilnic/Lunar/Anual), hulladek tipus checkbox-ok kategorianként csoportositva
  - Kategoria fejlec checkbox = egesz kategoria kivalasztasa (nem kell altipusokat kulon bejelolni)
  - Egyedi altipus checkbox-ok = reszletes bontas
  - "Selecteaza tot" / "Deselecteaza tot" gombok
  - Eredmeny: 3 osszefoglalo kartya (Total KG, Total Valoare, Medie/Perioada)
  - Chart.js grafikon: vonal (<=6 tipus) vagy stacked bar (>6 tipus)
  - Tooltip: `mode: 'index'` - hovereleskor az osszes ertek megjelenik, nem csak az adott pont
  - Adattablazat: sorok = idoszakok, oszlopok = tipusonkent kg + TOTAL, TOTAL sor alul
  - Dinamikus default datumok: jan 1. aktualis ev → mai nap (nem hardcoded)
- **CSS:** `.waste-analysis-types`, `.waste-cat-group`, `.waste-type-cb-label`, `.wa-summary-cards` stilusok

### 2026-02-18 - Hibajavitas: prevYear is not defined (initPredictions)
- **Hiba:** `ReferenceError: prevYear is not defined` az `initPredictions` fuggvenyben (index.html:1349)
  - A "RULAJ TOTAL" kartya "Eroare!" feliratot mutatott a dashboard-on
  - A Predictii szekció sem toltodott be
- **Ok:** A 2026-02-14-es atiras soran a regi `prevYear` valtozot lecsereltuk `baseYear`/`predYear`-re, de a fuggveny vegen az alerts szekcioban (eves rulaj osszehasonlitas) maradt ket hivatkozas a mar nem letezo `prevYear` valtozora
- **Javitas:** `prevYear` → `compareYear` (= `latestYear - 1`) uj valtozo bevezetve
  - Nem lehetett `prevFullYear`-t hasznalni, mert az mar definialva volt feljebb mint adattomb (1276. sor)
  - A `compareYear` nev pontosan tukorzi a celit: az elozo evet hasonlitja ossze az aktualis evvel
- **Erintett fajl:** `index.html` (3 sor modositva a ~1349-1354 kornyeken)
- **Tanulsag:** Valtozo atnevezes/torles utan mindig keresni kell az osszes hivatkozast a regi nevre!

### 2026-02-14 - 2025 Nov-Dec + 2026 Jan-Feb Adat Import es Frontend Adaptacio
- **Adat import:**
  - 2025 november 24-29 (6 nap, ~676 tranzakcio)
  - 2025 december teljes (19 nap, ~1,637 tranzakcio)
  - 2026 januar teljes (20 nap, ~1,815 tranzakcio) - 1 serult fajl (12.01.2026) megoldva Excel COM konverzioval
  - 2026 februar 02-12 (10 nap, ~893 tranzakcio uj) + 103 uj partner
  - 1 uj hulladek tipus: Deseu Ambalaj Metalic (Fier kategoria)
  - 1 rosszul elnevezett fajl: 02.02.2024.xls → 2026-02-02 datummal importalva
  - Ossz: +5,021 uj tranzakcio, +4,552 uj tetel
- **Frontend valtoztatasok (index.html):**
  - Datum szurok: 5 helyen 2025-12-31 → 2026-12-31 (filterDateTo, onetimeDateTo, familyDateTo, listaDateTo, resetPartnerListFilters)
  - Big suppliers dropdown: 2026 ev opció hozzaadva
  - Regulati leirasok frissitve (2022-2026)
  - Predictii logika teljesen ujrairva: dinamikusan kezeli a reszleges eveket (pl. 2026 csak Jan-Feb), eves becslest mutat, base ev automatikus valasztas
- **Backend valtoztatasok:**
  - `api/transactions.py`: Default date_from 2024-01-01 → 2022-01-01
  - `api/analytics.py`: Craciun 2025, Mos Nicolae 2025 unnepnapok hozzaadva
- **DB statisztikak:** 112,765 tranzakcio, 225,089 tetel, 30,853 partner, 2022.01 - 2026.02
- **Uj feature: Comparatie Personalizata**
  - Backend: `api/analytics.py` - `?type=custom_compare` endpoint
    - Tetszoleges honapok kivalasztasa (checkbox)
    - Opcionalis hulladek kategoria szures
    - Per-ev visszaadott adatok: tranzakciok, ertek, netto, partnerek, munkanapok
    - Demografia: nem (M/F), korcsoport (18-24, 25-34, 35-44, 45-54, 55-64, 65+), top megyek
    - Kategoria-specifikus: kg, ertek, atlag ar, partnerek szama
    - Osszes partner/ev (kontextushoz)
  - Frontend: `index.html` - Comparatie tab elejen
    - Honap checkboxok (Jan-Dec), kategoria dropdown
    - Eredmeny tablazat (minden indikator, trend szazalekkal)
    - 4 grafikon: Rulaj/Ev, Partnerek/Ev, Nem/Ev (stacked bar), Korcsoport/Ev (stacked bar)
    - Top megyek tablazat
    - Kategoria bontas tablazat (ha nincs szuro)

### 2026-02-11 - Frontend/Backend Adaptacio 2022-2025 Teljes Lefedettseggel
- **MINDEN hardcoded ev hivatkozas eltavolitva** - frontend es backend egyarant dinamikus
- **Backend valtoztatasok:**
  - `api/analytics.py`: Korosztaly szamitas dinamikus (`EXTRACT(YEAR FROM CURRENT_DATE)` a hardcoded ev helyett)
  - `api/partners.py`: Default datum 2024-01-01 → 2022-01-01, regulars query dinamikus (egymast koveto evek osszehasonlitasa), `current_year` dinamikus
  - `api/data.py`: `months_in_year` szamitas dinamikus (`COUNT(DISTINCT EXTRACT(MONTH FROM date))` SQL-bol)
- **Frontend valtoztatasok (index.html):**
  - "2024 vs 2025" tab → "Comparatie" (dinamikus, osszes ev)
  - Dinamikus yearColors tomb a Chart.js grafikonokhoz (6 szin, bovitheto)
  - `initCompare()`: teljes ujrairas - dinamikus ev szinek, tablazat, insights YoY minden evparhoz
  - `loadWeekday()`: ujrairas - osszes ev adatait lekeeri
  - Neferos tablazat: `.slice(0, 12)` eltavolitva → osszes honap megjelenik (~48)
  - `initPredictions()`: ujrairas - dinamikus latestYear/prevYear, tobbeves YoY atlag
  - VIP statisztikak: hardcoded 118700000 → dinamikus osszes ev osszeg
  - Overview chart: dinamikus ev szinek
  - Datum szurok: 5 helyen 2024-01-01 → 2022-01-01 (filterDateFrom, onetimeDateFrom, familyDateFrom, listaDateFrom, resetPartnerListFilters)
  - Big suppliers dropdown: 2022/2023 ev opciok hozzaadva
  - Regulati leirasok altalanositva ("orice 2 ani consecutivi")
  - Weekday gombok: dinamikus generalas evekbol
- **Hibajavitas:** `nextYear` valtozo deklaralas attelepitese (const TDZ hiba initPredictions-ben)

### 2026-02-09 - 2022/2023 Adat Import
- 55,856 uj tranzakcio importalva (2022: 27,855 + 2023: 28,001)
- 114,451 tranzakcio tetel importalva
- 3 uj hulladek tipus letrehozva:
  - Deseu Ambalaj Plastic (ladite si navete) [Plastic]
  - Deseuri DEEE ( Mufe, Cabluri IDE ) [DEEE]
  - nu - Deseuri DEEE [DEEE]
- 106 belso duplikat kiszurve (azonos document_id)
- 7 serult XLS fajl (utf-16-le codec hiba) - MEGOLDVA Excel COM konverzioval:
  - 2022: 11.04, 25.08, 05.12, 13.12, 21.12
  - 2023: 01.03, 30.06, 01.11
  - +388 uj tranzakcio es +308 tetel importalva beloluk
- DB most 4 evet fed le: 2022.01 - 2025.11

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

*Utolso frissites: 2026-02-24*
