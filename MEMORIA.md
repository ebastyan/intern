# PAJU Project - Memoria / Dokumentacio

## Projekt Leiras

**PAJU** - Hulladekfeldolgozo ceg belso dashboard rendszere, amely ket fo reszbol all:
1. **Persoane Fizice** - Maganszemelyek vasarlasi adatai (lakossagi beszerzesek)
2. **Firme (B2B)** - Cegek felei ertekesitesek (nagykereskedelmi)

---

## Technikai Stack

- **Frontend**: HTML + CSS + JavaScript (vanilla)
- **Charts**: Chart.js
- **Backend**: Python (Vercel Serverless Functions)
- **Database**: PostgreSQL (NeonDB)
- **Hosting**: Vercel
- **Git**: GitHub (ebastyan/intern repo)

---

## Adatbazis Struktura

### Tablak

1. **`firme`** - Cegek adatai
   - `id`, `name`

2. **`vanzari`** - Ertekesitesek (B2B tranzakciok)
   - `id`, `firma_id`, `data`, `year`, `month`
   - `numar_aviz`, `tip_deseu`
   - `cantitate_livrata`, `cantitate_receptionata`
   - `pret_achizitie`, `pret_vanzare`
   - `valoare_ron`, `adaos_final`

3. **`transporturi_firme`** - Szallitasi koltsegek
   - `id`, `year`, `month`
   - `destinatie`, `firma_name`
   - `descriere`, `transportator`
   - `suma_fara_tva`, `tva`, `total`

4. **`sumar_deseuri`** - Hulladek osszesites (FIGYELEM: csak 2022-es adatok!)
   - `tip_deseu`, `year`, `cantitate_kg`, `valoare_ron`, `adaos_ron`

5. **`persoane_fizice`** - Lakossagi vasarlasok
   - Kulonallo tabla a Persoane Fizice dashboardhoz

---

## API Endpoints

**File**: `api/firme.py`

| Endpoint | Leiras |
|----------|--------|
| `/api/firme?type=overview` | Altalanos osszesites |
| `/api/firme?type=list` | Cegek listaja |
| `/api/firme?type=firma&id=X` | Egy ceg reszletei |
| `/api/firme?type=vanzari&firma_id=X` | Ceg ertekesitesei |
| `/api/firme?type=monthly&year=2024` | Havi osszesites |
| `/api/firme?type=deseuri&year=2024` | Hulladek tipusok |
| `/api/firme?type=top` | Top cegek |
| `/api/firme?type=transporturi` | Szallitasi adatok |
| `/api/firme?type=yearly` | Eves osszehasonlitas |

---

## Frontend Oldalak

### firme.html - B2B Dashboard

**Tabok:**
1. **Sumar** - Osszesito nezet (yearly chart, top firme)
2. **Firme** - Cegek listaja kereshetoen
3. **Lunar** - Havi bontas
4. **Deseuri** - Hulladektipusok szerinti bontas
5. **Comparatie** - Eves osszehasonlitas
6. **Transport** - Szallitasi koltsegek
7. **Statistici** - Reszletes statisztikak

---

## ISMERT ADAT PROBLEMAK

### 1. tip_deseu (Deseuri tab) - KRITIKUS!
```
2022: 826 rekord tip_deseu adattal
2023: 0 rekord (MIND NULL!)
2024: 0 rekord (MIND NULL!)
```
**Ok**: Az eredeti Excel fajlban a tip_deseu oszlop nem lett kitoltve 2023/2024-re.
**Hatas**: A Deseuri tab csak 2022-es adatokat tud mutatni.

### 2. Transport adatok - HIANYOS
```
2023/1: 18 rekord, 74,599 RON
2024/1: 21 rekord, 74,599 RON (UGYANAZ az osszeg - duplikat?)
Ossz: 39 rekord, ~149,000 RON
```
**Ok**: Csak 2 honap adata van feltoltve az adatbazisba.
**Hatas**: Transport chart egy sik vonal, nincs ertelmes trend.

### 3. Comparatie Anuala tablazat
- 2022-nek nincs VALT % mert nincs elozo ev amivel osszehasonlitani
- 2023 -10.5% (csokkenés a rulajban)
- 2024 +15.6% (növekedés)
**Ez NORMALIS viselkedes!**

---

## MAI (2024-12-02) VALTOZTATASOK

### Session 1 - Firme Dashboard javitasok

1. **Ceg normalizalas az adatbazisban**
   - Duplikalt cegek osszevonasa (pl. PW SPIZ SPOLKA → SPIZ)
   - Transport adat destinatie/firma swap javitas

2. **Chart tooltip javitas**
   - Teljes szamok megjelenítese (nincs M/K rovidites)
   - Minden chart-on fmt() fuggveny hasznalata

3. **Lunar tab javitas**
   - "Vanzari" → "Tranzactii" (erthetobb)

4. **Deseuri tab javitas**
   - Uj filterek: month_from, month_to, tip_deseu dropdown
   - Kereses mezo
   - Reset gomb
   - Figyelmeztetes ha nincs adat 2023/2024-re

5. **Comparatie tab javitas**
   - YoY megjelenites javitva: "Crestere Anuala (2023 → 2024)"
   - Szinek: zold = novekedes, piros = csokkenes
   - Tobb reszlet: legjobb honapok evente

6. **Statistici tab javitas**
   - Profit trend: mindket vonal hover-re
   - Marje pe Categorii: MINDEN anyag (nem csak top 8)
   - Best month: evenkent kulon
   - Top 5 ceg nevei a sub text-ben

7. **Nyelv - Magyar → Roman**
   - Minden magyar szoveg romarra csereve
   - Eves Osszehasonlitas → Comparatie Anuala
   - Havonkenti → Costuri Lunare
   - Atlag → Media
   - stb.

---

## KOVETKEZO LEPESEK / TODO

1. **tip_deseu adat potlasa** - Eredeti Excel-bol ki kell nyerni a 2023/2024 tip_deseu adatokat es feltolteni
2. **Transport adat kiegeszites** - Tobbi honap transport adatainak feltoltese
3. **Persoane Fizice dashboard** - Meg nem fejlesztett reszletesen
4. **Terkep funkció** - Geocoded ceg adatok vannak (companyData_geocoded.json)

---

## HASZNOS FAJLOK

| Fajl | Cel |
|------|-----|
| `check_data.py` | Adatbazis ellenorzes |
| `check_all_data.py` | Reszletes adat ellenorzes |
| `fix_companies.py` | Ceg normalizalas |
| `fix_transport.py` | Transport adat javitas |
| `merge_spiz.py` | SPIZ cegek osszevonasa |
| `companyData_geocoded.json` | Geocoded ceg koordinatak |

---

## ADATBAZIS KAPCSOLAT

```python
db_url = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
```

---

## GIT HISTORY (mai nap)

```
120f425 Fix all Hungarian text to Romanian, add data warnings
cc91448 Fix dashboard issues: charts, filters, analytics improvements
201e2ea Enhanced Transport and Statistici tabs with more analytics
659dd42 Fix Firme dashboard: company normalization, transport data, filters
e094f42 Major improvements to Firme dashboard
```

---

## MEGJEGYZESEK

- A frontend NINCS framework-ben (React, Vue, stb.), tiszta vanilla JS
- Minden szoveg ROMAN kell legyen a dashboard-on
- Chart.js v3+ hasznalata
- Vercel automatikusan deploy-ol GitHub push utan
- NeonDB free tier - limitalt kapcsolat szam

---

*Utolso frissites: 2024-12-02*
