# PAJU Project Memory

## Project Overview
Hulladék felvásárló üzlet (waste recycling) analytics és adatbázis rendszer.
Helyszín: Románia, Bihor megye

## File Structure

### Source Data (XLS)
- `persoanefizice.xls` - Partner/ügyfél adatok (30,294 sor)
  - CNP, név, személyi szám, lejárat, cím, város, megye, telefon, email
- `2024/MM_HonapNev/*.xls` - Napi tranzakciók 2024
- `2025/MM_HonapNev/*.xls` - Napi tranzakciók 2025
- Fájlnév formátum: `DD.MM.YYYY.xls` (pl: 03.01.2024.xls)

### XLS Structure (Old - 2024 Jan-Aug)
- Col 1: Nume (név)
- Col 2: CNP
- Col 3: Nr. APP (document ID - UNIQUE!)
- Col 4: Valoare (bruttó érték)
- Col 5: Fond mediu (környezetvédelmi adó)
- Col 6: Impozit (jövedelemadó)
- Col 7: Achitat (nettó kifizetett)
- Col 8+: Hulladék típusok "Deseu Tipus (ar)" formátumban

### XLS Structure (New - 2024 Sept+)
FONTOS: Két variáció létezik!

**Variáció A (pl: 01.10.2024.xls):**
- Col 1: Nume, Col 2: CNP, Col 3: Nr.APP
- Col 4: Tip plata, Col 5: IBAN
- Col 6-9: Valoare, Fond, Impozit, Achitat
- Col 10+: Hulladék típusok

**Variáció B (pl: 21.10.2024.xls):**
- Col 1: Nume, Col 2: CNP
- Col 3: Tip plata, Col 4: IBAN, Col 5: Nr.APP
- Col 6-9: Valoare, Fond, Impozit, Achitat
- Col 10+: Hulladék típusok

A setup_database.py automatikusan detektálja a header pozíciókat!

## Database Schema (NeonDB PostgreSQL)

### Tables
1. **partners** - CNP alapú, persoanefizice.xls-ből
   - cnp (PK), name, id_series, id_expiry, street, city, county, phone, email
   - birth_year, sex, county_code_cnp (CNP-ből számolt)

2. **waste_categories** - Fő kategóriák (16 db)
   - Fier, Cupru, Aluminiu, Alama, Acumulatori, DEEE, Inox, Plumb, Zinc, Zamac, Carton, Sticla, Plastic, Neferos Mix, Cablu Cupru, Cablu Aluminiu

3. **waste_types** - Altípusok (41 db)
   - category_id FK, name (pl: "Deseu Cupru", "Deseu Cupru Junkers")

4. **transactions** - Minden tranzakció
   - document_id (PK - Nr. APP), date, cnp (FK), payment_type, iban
   - gross_value, env_tax, income_tax, net_paid

5. **transaction_items** - Minden hulladék tétel
   - document_id (FK), waste_type_id (FK), price_per_kg, weight_kg, value

## Scripts

### setup_database.py
Teljes import script:
1. Táblák létrehozása (DROP + CREATE)
2. Partners import persoanefizice.xls-ből
3. Waste categories/types generálás header-ekből
4. Összes tranzakció + tétel import

### process_all.py
Régi script - összesített JSON generálás (all_data.json)

### analyze_partners.py
Partner analytics - analytics.json generálás

## Deployed

### Vercel
- URL: https://intern-XXX.vercel.app
- dashboard_multi.html - Éves összefoglaló
- analytics.html - Partner analytics (ROMÁN nyelven!)

### NeonDB
- Host: ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech
- DB: neondb
- User: neondb_owner

## TODO - Current Task
1. [x] Adatbázis struktúra tervezés
2. [x] setup_database.py futtatás + adatminőség javítás
   - SSL timeout probléma volt - retry logika hozzáadva
   - Batch méret csökkentve 100-ra
   - **JENTI → JANTE typo normalizálás**
   - **Dinamikus header detektálás** (különböző XLS struktúrák kezelése)
3. [ ] **KÖVETKEZŐ: API endpoints létrehozása query-khez**
4. [ ] Dashboard frissítés DB-ből

## API Endpoints (Vercel serverless functions)
Összes API kész és működik!

### `api/partners.py` - Partner keresés
```
GET /api/partners?q=keresés       - Név/CNP keresés
GET /api/partners?cnp=XXX         - Partner részletei
GET /api/partners?inactive=30     - 30+ napja inaktívak
GET /api/partners?top=20          - Top 20 partner (érték szerint)
GET /api/partners?top=20&category=Cupru - Top Cupru behozók
GET /api/partners?onetime         - Egyszeri látogatók
```

### `api/transactions.py` - Tranzakciók
```
GET /api/transactions?document_id=PJ-XXX  - Tranzakció részletei
GET /api/transactions?cnp=XXX             - Partner tranzakciói
GET /api/transactions?date_from=2024-01-01&date_to=2024-12-31
GET /api/transactions?daily=2024-10-15    - Napi összesítő
GET /api/transactions?date_from=2024-01-01&category=Cupru&min_value=1000
```

### `api/analytics.py` - Összesítések
```
GET /api/analytics?type=overview  - Teljes áttekintés
GET /api/analytics?type=yearly    - Éves összesítés
GET /api/analytics?type=monthly&year=2024 - Havi bontás
GET /api/analytics?type=county    - Megye szerinti
GET /api/analytics?type=city&county=Bihor - Város szerinti
GET /api/analytics?type=weekday   - Hétnapok mintázata
GET /api/analytics?type=age       - Korcsoportok
GET /api/analytics?type=trends    - Trendek (7/30 napos összehasonlítás)
```

### `api/waste.py` - Hulladék statisztikák
```
GET /api/waste?type=categories    - Összes kategória
GET /api/waste?type=types&category=Cupru - Altípusok
GET /api/waste?type=prices&category=Cupru - Ár történet
GET /api/waste?type=top&category=Fier&limit=20 - Top behozók
GET /api/waste?type=monthly&category=Aluminiu - Havi bontás
GET /api/waste?type=search&waste=Cupru&min_price=30&max_price=40 - Keresés
```

### `api/data.py` - Dashboard kompatibilitás (régi formátum)
### `api/monthly.py` - Részletes havi adatok

## KÖVETKEZŐ LÉPÉS
- [ ] Dashboard HTML-ek tesztelése az új API-kkal
- [ ] Vercel deploy és tesztelés

## Current Status (2025-11-27)
- setup_database.py SIKERESEN LEFUTOTT!
- Táblák: partners, waste_categories, waste_types, transactions, transaction_items
- **Adatminőség ellenőrizve és javítva:**
  - Minden document_id PJ-xxx formátumú ✓
  - Typo-k normalizálva (JENTI → JANTE) ✓
  - Mindkét XLS struktúra kezelve ✓
- Eredmények:
  - 30,318 partner
  - 16 kategória, 43 altípus
  - **51,000 tranzakció**
  - 99,367 tétel
  - **118,698,565.21 RON összérték**
  - Időszak: 2024-01-03 - 2025-11-22

## Required Queries (User Requirements)

### Partner alapú
- CNP/Név → hányszor volt, mikor, mit hozott
- Filterezés dátum range-re
- 1x volt és soha többet
- Járt sűrűn de 15/30/60/90+ napja nem volt
- Aktív kliensek utolsó X hónapban
- Top behozók anyagtípusonként

### Hulladék alapú
- Típus + ár range + dátum range → kik hozták
- Fő kategória legjobb időszaka (év/hónap/hét/nap)

### Földrajzi
- Megye/város bontás
- Ugyanaz utca/falu → potenciális csoportok
- Családnév + hely → rokonok
- Ugyanaz dátum + falu + magas érték → jelzés

### Időbeli
- Nap/hét/hónap/év összesítések
- Hétnapok mintázata

## Important Notes
- Minden adat ROMÁNUL kell legyen
- CNP az egyedi azonosító (13 számjegy)
- Document ID (Nr. APP) egyedi tranzakciónként
- Normalizálás fontos: BIHOR = Bihor = bihor
- Whitespace és typo kezelés szükséges
