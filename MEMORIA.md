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

## ISMERT ADAT PROBLEMAK (FRISSITVE 2024-12-03)

### 1. Deseuri tab (sumar_deseuri tabla)
A Deseuri tab a `sumar_deseuri` tablat hasznalja, ami az Excel Sumar sheet-ekbol szarmazik.

| Ev | Honapok | Lefedettség | Megjegyzes |
|----|---------|-------------|------------|
| 2022 | 12/12 | ~79% | vanzari.tip_deseu oszlopbol szamitva |
| 2023 | 5/12 | ~37% | Csak Aug-Dec, Jan-Jul Excel-ben NINCS tip deseu szekció! |
| 2024 | 12/12 | 100% | Teljes adat |

**Figyelmeztetés a frontend-en jelenik meg év kiválasztásakor.**

### 2. Transport adatok - JAVÍTVA ✅
Korabban a `transporturi_firme` tablat hasznaltuk (39 rekord, 149k RON).
Most a `vanzari.transport_ron` oszlopot hasznaljuk:
- **2022**: 1,998,986 RON
- **2023**: 1,993,346 RON
- **2024**: 2,404,429 RON
- **Ossz**: 6,396,761 RON

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

## 2024-12-03 VALTOZTATASOK

### Session 1 - Deseuri es Transport javitasok

1. **Deseuri tab - sumar_deseuri tabla hasznalata**
   - Korabban vanzari.tip_deseu-t nezett (ami 2023/2024-re ures volt)
   - Most sumar_deseuri tablat hasznal (Excel Sumar sheet-ekbol)
   - 2022 adatok importalva a vanzari.tip_deseu alapjan
   - Figyelmeztetés jelenik meg 2022/2023 kivalasztasakor

2. **Transport tab - vanzari.transport_ron hasznalata**
   - Korabban transporturi_firme tablat nezett (csak 39 rekord, 149k RON)
   - Most vanzari.transport_ron oszlopot hasznal
   - 6.4M RON osszes transport koltseg (2022-2024)
   - Uj chartok: eves osszehasonlitas, % transport/rulaj, top firmak

3. **Adatbazis frissites**
   - 154 rekord hozzaadva a sumar_deseuri tablahoz (2022 adatok)
   - 2022: 12 honap, 56 hulladektipus

### Session 2 - tip_deseu nevek normalizalasa

1. **Duplikalt nevek osszevonasa**
   - 101 kulonbozo nevbol 39 tiszta nev lett
   - Title Case format (pl. "CUPRU" -> "Cupru")
   - Roman karakterek csereje (ă->a, â->a, Ș->S, etc.)

2. **Hibas adatok torlese**
   - Cegnevek torolve (Heneken, Ragmet, Reif, Spiz, Syntom, Zlatcup, etc.)
   - Kombinalt ertekek torolve (pl. "Alama, Cupru" - nem ertelmezheto)

3. **Elirások javitasa**
   - "Span Alumniu" -> "Span Aluminiu"
   - "Aluminiu Jante" -> "Aluminiu Jenti"

**Vegleges sumar_deseuri statisztika:**
| Ev | Tipusok | Rekordok | Ertek RON |
|----|---------|----------|-----------|
| 2022 | 24 | 96 | 74,262,053 |
| 2023 | 29 | 92 | 45,164,877 |
| 2024 | 37 | 247 | 141,128,085 |

### Session 3 - Transport profil es tip_deseu import

1. **Transport profilok hozzaadva**
   - Sofer profil: kattinthato sofor neve → osszes fuvar, kg, ertek, hulladek tipusok
   - Transportator profil: ceg profil → osszes fuvar, kg, ertek, hulladek tipusok
   - Tara profil: orszag profil → osszes fuvar, kg, ertek, hulladek tipusok
   - Tablak 40 sorra novelve
   - API endpoints: sofer_profile, transportator_profile, country_profile

2. **tip_deseu adat import a vanzari tablaba**
   - 2024: 1,520 / 1,594 rekordhoz importalva (95.4%) - Excel-bol
   - 2023: 0 / 1,500 - Excel-ben NINCS tip_deseu oszlop!
   - 2022: 826 / 1,296 - mar benne volt
   - Forras: ALE_situatie transport_2024 (1).xlsx

**vanzari.tip_deseu statisztika:**
| Ev | Rekordok tip_deseu-val | Ossz rekord | Lefedettség |
|----|------------------------|-------------|-------------|
| 2022 | 826 | 1,296 | 63.7% |
| 2023 | 0 | 1,500 | 0% |
| 2024 | 1,520 | 1,594 | 95.4% |

---

## MEGJEGYZESEK

- A frontend NINCS framework-ben (React, Vue, stb.), tiszta vanilla JS
- Minden szoveg ROMAN kell legyen a dashboard-on
- Chart.js v3+ hasznalata
- Vercel automatikusan deploy-ol GitHub push utan
- NeonDB free tier - limitalt kapcsolat szam

---

*Utolso frissites: 2024-12-03*
