# PAJU Dashboard - Database Schema Export

> **Cél:** TimesFM time series forecasting - heti forgalmi adatok fémenként, városonként, nemek szerint stb.
>
> **Database:** PostgreSQL (NeonDB) | **Időszak:** 2022-01-03 – 2026-02-12

---

## Táblák közötti kapcsolatok (ER)

```
waste_categories (16 db)
  └── waste_types (47 db)          [waste_types.category_id → waste_categories.id]
        └── transaction_items (225,089 db) [transaction_items.waste_type_id → waste_types.id]
              └── transactions (112,765 db) [transaction_items.document_id → transactions.document_id]
                    └── partners (30,853 db) [transactions.cnp → partners.cnp]

firme (77 db)
  ├── vanzari (4,390 db)           [vanzari.firma_id → firme.id]
  ├── sumar_firme (0 db)           [sumar_firme.firma_id → firme.id]
  └── transporturi_firme (39 db)   (nincs FK, de firma_name szöveges hivatkozás)

sumar_deseuri (435 db)             (standalone összesítő tábla)
```

---

## 1. `partners` — Partnerek (30,853 sor)

Minden természetes személy aki hulladékot ad el.

| Oszlop | Típus | NULL? | Megjegyzés |
|--------|-------|-------|------------|
| **cnp** (PK) | varchar(13) | NOT NULL | 13 jegyű román személyi szám |
| name | varchar(200) | NULL | Teljes név |
| id_series | varchar(100) | NULL | Személyi igazolvány szám |
| id_expiry | date | NULL | Személyi lejárat |
| street | varchar(500) | NULL | Utca, házszám |
| city | varchar(150) | NULL | Város/község |
| county | varchar(100) | NULL | Megye (42 különböző) |
| country | varchar(100) | NULL | Ország (default: 'Romania') |
| phone | varchar(100) | NULL | Telefon |
| email | varchar(150) | NULL | Email |
| birth_year | integer | NULL | Születési év |
| sex | char(1) | NULL | 'M' / 'F' (M: 26,480, F: 3,838, NULL: 535) |
| county_code_cnp | varchar(2) | NULL | CNP-ből kiolvasott megye kód |
| county_from_cnp | varchar(50) | NULL | CNP-ből kiolvasott megye név |
| created_at | timestamp | NULL | Létrehozás dátuma |
| modified_at | timestamp | NULL | Módosítás dátuma |
| is_active | boolean | NULL | Aktív-e (default: true) |

**Példa sorok:**

| cnp | name | city | county | birth_year | sex |
|-----|------|------|--------|------------|-----|
| 1890126211225 | Aanei Ionut | Oradea | Bihor | 1989 | M |
| 1621221272678 | Abalintoaiei Corneliu | Com Sagna | Neamt | 1962 | M |
| 1940308270857 | Abalintoaiei Eduard-Madalin | Com Sagna | Neamt | 1994 | M |

**Forecasting dimenziók:** `county` (42 megye), `city`, `sex` (M/F), `birth_year` (→ korosztály)

---

## 2. `transactions` — Tranzakciók (112,765 sor)

Minden egyes vásárlási bizonylat. **Egy tranzakció = egy nap, egy partner, egy bizonylat.**

| Oszlop | Típus | NULL? | Megjegyzés |
|--------|-------|-------|------------|
| **document_id** (PK) | varchar(50) | NOT NULL | Bizonylat szám (pl. PJ-173304) |
| **date** | date | NOT NULL | Tranzakció dátuma (NAPI granularitás!) |
| cnp (FK → partners) | varchar(13) | NULL | Partner azonosító |
| payment_type | varchar(100) | NULL | 'Numerar' (készpénz) / 'Ordin plata' (utalás) |
| iban | varchar(100) | NULL | Bankszámla |
| gross_value | numeric(12,2) | NULL | Bruttó érték (RON) |
| env_tax | numeric(10,2) | NULL | Környezetvédelmi adó |
| income_tax | numeric(10,2) | NULL | Jövedelemadó |
| net_paid | numeric(12,2) | NULL | Nettó kifizetett összeg (RON) |

**Példa sorok:**

| document_id | date | cnp | payment_type | gross_value | net_paid |
|-------------|------|-----|-------------|-------------|----------|
| PJ-173304 | 2024-01-03 | 1630225054651 | NULL | 125.00 | 122.50 |
| PJ-173401 | 2024-01-03 | 1750521052886 | NULL | 302.50 | 296.45 |
| PJ-173331 | 2024-01-03 | 1740815050020 | NULL | 6,534.00 | 6,403.32 |

**Időbeli granularitás: NAPI** — minden tranzakciónak van pontos dátuma. Heti aggregáció könnyen képezhető.

---

## 3. `transaction_items` — Tranzakció tételek (225,089 sor)

Egy tranzakción belül több hulladéktípus is lehet. **Ez a legfontosabb tábla a forecasting-hez!**

| Oszlop | Típus | NULL? | Megjegyzés |
|--------|-------|-------|------------|
| **id** (PK) | integer (serial) | NOT NULL | Auto increment |
| document_id (FK → transactions) | varchar(50) | NULL | Bizonylat szám |
| waste_type_id (FK → waste_types) | integer | NULL | Hulladék típus ID |
| price_per_kg | numeric(8,2) | NULL | Ár per kilogramm (RON/kg) |
| weight_kg | numeric(10,2) | NULL | Súly kilogrammban |
| value | numeric(12,2) | NULL | Összérték (RON) = price_per_kg × weight_kg |

**Példa sorok:**

| id | document_id | waste_type_id | price_per_kg | weight_kg | value |
|----|-------------|---------------|-------------|-----------|-------|
| 1 | PJ-173304 | 32 | 1.25 | 100.00 | 125.00 |
| 2 | PJ-173401 | 1 | 3.70 | 15.00 | 55.50 |
| 3 | PJ-173401 | 19 | 0.95 | 100.00 | 95.00 |

---

## 4. `waste_categories` — Hulladék kategóriák (16 sor)

Fő fémkategóriák / anyagtípusok.

| Oszlop | Típus | NULL? |
|--------|-------|-------|
| **id** (PK) | integer (serial) | NOT NULL |
| name | varchar(100) | NOT NULL |

**Teljes lista:**

| id | name |
|----|------|
| 1 | Acumulatori |
| 2 | Alama |
| 3 | Aluminiu |
| 4 | Neferos Mix |
| 5 | Cablu Aluminiu |
| 6 | Cablu Cupru |
| 7 | Carton |
| 8 | Cupru |
| 9 | Fier |
| 10 | Plastic |
| 11 | Inox |
| 12 | Plumb |
| 13 | Sticla |
| 14 | Zamac |
| 15 | Zinc |
| 16 | DEEE |

---

## 5. `waste_types` — Hulladék típusok (47 sor)

Altípusok, kategóriánként csoportosítva.

| Oszlop | Típus | NULL? |
|--------|-------|-------|
| **id** (PK) | integer (serial) | NOT NULL |
| category_id (FK → waste_categories) | integer | NULL |
| name | varchar(100) | NULL |

**Teljes lista (kategóriánként):**

| id | category | name |
|----|----------|------|
| 1 | Acumulatori | Deseu Acumulatori |
| 2 | Alama | Deseu Alama |
| 3 | Alama | Deseu Alama Radiator |
| 4 | Alama | Deseu Alama Span |
| 5 | Aluminiu | Deseu Aluminiu |
| 6 | Aluminiu | Deseu Aluminiu JANTE |
| 7 | Aluminiu | Deseu Aluminiu PREMIUM |
| 8 | Aluminiu | Deseu Aluminiu Radiator |
| 9 | Aluminiu | Deseu Aluminiu Radiator cu CUPRU |
| 10 | Aluminiu | Deseu Aluminiu Span |
| 11 | Neferos Mix | Deseu Amestec NEFEROS |
| 12 | Cablu Aluminiu | Deseu Cablu Aluminiu |
| 13 | Cablu Cupru | Deseu Cablu Cupru |
| 14 | Carton | Deseu Carton |
| 15 | Carton | Deseu Carton / Hartie |
| 16 | Cupru | Deseu Cupru |
| 17 | Cupru | Deseu Cupru Junkers |
| 18 | Aluminiu | Deseu Doze Aluminiu |
| 19 | Fier | Deseu Fier |
| 20 | Fier | Deseu Fier (VSU) |
| 21 | Fier | Deseu Fier Span |
| 22 | Plastic | Deseu Folie |
| 23 | Inox | Deseu Inox |
| 24 | Inox | Deseu Inox Span |
| 25 | Plastic | Deseu PET |
| 26 | Plastic | Deseu Plastic |
| 27 | Plumb | Deseu Plumb |
| 28 | Sticla | Deseu Sticla Ambalaj |
| 29 | Zamac | Deseu Zamac |
| 30 | Zinc | Deseu Zinc |
| 31-43, 47-50 | DEEE | Deseuri DEEE (különböző elektromos/elektronikus hulladékok) |
| 47 | Plastic | Deseu Ambalaj Plastic (ladite si navete) |
| 50 | Fier | Deseu Ambalaj Metalic |

---

## 6. `firme` — B2B Vevők (77 sor)

Cégek akiknek eladjuk a begyűjtött hulladékot.

| Oszlop | Típus | NULL? | Megjegyzés |
|--------|-------|-------|------------|
| **id** (PK) | integer (serial) | NOT NULL | |
| name | varchar(200) | NOT NULL | Cégnév |
| name_normalized | varchar(200) | NULL | Normalizált cégnév |
| country | varchar(100) | NULL | Ország |
| city | varchar(100) | NULL | Város |
| is_active | boolean | NULL | Aktív (default: true) |
| created_at | timestamp | NULL | Létrehozva |

**Példa sorok:**

| id | name | country | city |
|----|------|---------|------|
| 1 | ABED NEGO COM | NULL | NULL |
| 4 | ABS-ACCIAIERIE BERTOLI SAFAU | NULL | NULL |
| 7 | AFV-ACCIAIERIE BELTRAME | NULL | NULL |

---

## 7. `vanzari` — B2B Értékesítések (4,390 sor)

Hulladék eladása cégeknek (kimenő forgalom).

| Oszlop | Típus | NULL? | Megjegyzés |
|--------|-------|-------|------------|
| **id** (PK) | integer (serial) | NOT NULL | |
| firma_id (FK → firme) | integer | NULL | Vevő cég |
| **data** | date | NOT NULL | Eladás dátuma |
| year | integer | NOT NULL | Év |
| month | integer | NOT NULL | Hónap |
| numar_aviz | varchar(100) | NULL | Szállítólevél szám |
| tip_deseu | varchar(100) | NULL | Hulladék típus (szöveges) |
| cantitate_livrata | numeric(14,2) | NULL | Szállított mennyiség (kg) |
| pret_achizitie | numeric(12,4) | NULL | Beszerzési ár (RON/kg) |
| scazamant_kg | numeric(12,2) | NULL | Apadás (kg) |
| scazamant_ron | numeric(12,2) | NULL | Apadás értéke (RON) |
| cantitate_receptionata | numeric(14,2) | NULL | Átvett mennyiség (kg) |
| pret_vanzare | numeric(12,4) | NULL | Eladási ár (RON/kg) |
| valoare_ron | numeric(14,2) | NULL | Érték (RON) |
| valoare_euro | numeric(14,2) | NULL | Érték (EUR) |
| adaos | numeric(14,2) | NULL | Árrés |
| transport_ron | numeric(12,2) | NULL | Szállítási költség |
| adaos_final | numeric(14,2) | NULL | Végleges árrés |
| serie_factura | varchar(50) | NULL | Számla sorozat |
| numar_factura | varchar(50) | NULL | Számla szám |
| data_factura | date | NULL | Számla dátum |
| observatii | text | NULL | Megjegyzések |
| numar_auto | varchar(100) | NULL | Rendszám |
| nume_sofer | varchar(100) | NULL | Sofőr neve |
| tara_destinatie | varchar(100) | NULL | Célország |
| transportator | varchar(100) | NULL | Szállító cég |

**Példa sor:**

| data | tip_deseu | cantitate_livrata | pret_achizitie | pret_vanzare | valoare_ron | adaos_final |
|------|-----------|-------------------|----------------|--------------|-------------|-------------|
| 2022-01-19 | ALAMĂ, RADIATOR ALAMĂ | 22,065 kg | 23.00 | 25.56 | 557,347.74 | 45,829.98 |

---

## 8. `sumar_deseuri` — Havi hulladék összesítő (435 sor)

Előre aggregált havi összesítés hulladéktípusonként.

| Oszlop | Típus | NULL? | Megjegyzés |
|--------|-------|-------|------------|
| **id** (PK) | integer (serial) | NOT NULL | |
| year | integer | NOT NULL | Év |
| month | integer | NOT NULL | Hónap |
| tip_deseu | varchar(100) | NOT NULL | Hulladék típus neve |
| cantitate_kg | numeric(14,2) | NULL | Mennyiség (kg) |
| valoare_ron | numeric(14,2) | NULL | Érték (RON) |
| adaos_ron | numeric(14,2) | NULL | Árrés (RON) |
| procent_vanzari | numeric(10,6) | NULL | Értékesítési % |
| procent_profit | numeric(10,6) | NULL | Profit % |

**Példa sorok:**

| year | month | tip_deseu | cantitate_kg | valoare_ron | adaos_ron |
|------|-------|-----------|-------------|-------------|----------|
| 2024 | 1 | Acumulatori | 275,805.00 | 1,276,593.45 | 62,249.90 |
| 2024 | 1 | Alama | 46,164.00 | 1,081,479.98 | 63,692.98 |
| 2024 | 1 | Aluminiu | 113,039.00 | 859,274.75 | 123,049.55 |

---

## 9. `sumar_firme` — Havi cég összesítő (0 sor - üres)

| Oszlop | Típus | NULL? |
|--------|-------|-------|
| **id** (PK) | integer (serial) | NOT NULL |
| year | integer | NOT NULL |
| month | integer | NOT NULL |
| firma_id (FK → firme) | integer | NULL |
| cantitate_livrata | numeric(14,2) | NULL |
| pret_mediu_achizitie | numeric(12,4) | NULL |
| scazamant_kg | numeric(12,2) | NULL |
| scazamant_ron | numeric(12,2) | NULL |
| cantitate_receptionata | numeric(14,2) | NULL |
| pret_mediu_vanzare | numeric(12,4) | NULL |
| valoare_ron | numeric(14,2) | NULL |
| valoare_euro | numeric(14,2) | NULL |
| transport_ron | numeric(12,2) | NULL |
| adaos | numeric(14,2) | NULL |
| adaos_final | numeric(14,2) | NULL |

> Jelenleg üres tábla.

---

## 10. `transporturi_firme` — Szállítások (39 sor)

| Oszlop | Típus | NULL? |
|--------|-------|-------|
| **id** (PK) | integer (serial) | NOT NULL |
| year | integer | NOT NULL |
| month | integer | NOT NULL |
| destinatie | varchar(200) | NULL |
| firma_name | varchar(200) | NULL |
| descriere | varchar(200) | NULL |
| suma_fara_tva | numeric(12,2) | NULL |
| tva | numeric(10,2) | NULL |
| total | numeric(12,2) | NULL |
| transportator | varchar(100) | NULL |

**Példa sor:**

| year | month | destinatie | firma_name | total |
|------|-------|-----------|------------|-------|
| 2024 | 1 | SLATINA | REIF | 5,355.00 |

---

## Forecasting szempontból fontos dimenziók összefoglalása

### Elérhető dimenziók (JOIN-okkal)

| Dimenzió | Tábla.Oszlop | Egyedi értékek |
|----------|-------------|----------------|
| **Hulladék kategória** | waste_categories.name | 16 (Fier, Cupru, Aluminiu, stb.) |
| **Hulladék altípus** | waste_types.name | 47 |
| **Megye** | partners.county | 42 |
| **Város** | partners.city | ~2,000+ |
| **Nem** | partners.sex | M / F |
| **Korosztály** | partners.birth_year | Számítható (pl. 18-24, 25-34, 35-44, 45-54, 55-64, 65+) |
| **Fizetési mód** | transactions.payment_type | Numerar / Ordin plata |
| **Partner aktív?** | partners.is_active | true / false |
| **CNP megye** | partners.county_from_cnp | Születési hely megye |

### Időbeli granularitás

| Szint | Elérhető? | Forrás |
|-------|-----------|--------|
| **Napi** | Igen | transactions.date |
| **Heti** | Igen (aggregálható) | DATE_TRUNC('week', date) |
| **Havi** | Igen | Közvetlen + sumar_deseuri előre számolva |
| **Éves** | Igen | EXTRACT(year FROM date) |

### Mértékek (target variables)

| Mérték | Oszlop | Megjegyzés |
|--------|--------|------------|
| **Forgalom (RON)** | transaction_items.value / transactions.gross_value | Fő target |
| **Mennyiség (kg)** | transaction_items.weight_kg | Fémenként |
| **Átlagár (RON/kg)** | transaction_items.price_per_kg | Árfolyam tracking |
| **Tranzakció szám** | COUNT(transactions) | Aktivitás mérő |
| **Partner szám** | COUNT(DISTINCT cnp) | Egyedi partnerek |
| **Nettó kifizetett** | transactions.net_paid | Tényleges kifizetés |

### Példa SQL a heti forecasting adathoz

```sql
-- Heti forgalom fémenként + megye + nem
SELECT 
    DATE_TRUNC('week', t.date) AS week,
    wc.name AS category,
    p.county,
    p.sex,
    CASE 
        WHEN EXTRACT(YEAR FROM t.date) - p.birth_year BETWEEN 18 AND 24 THEN '18-24'
        WHEN EXTRACT(YEAR FROM t.date) - p.birth_year BETWEEN 25 AND 34 THEN '25-34'
        WHEN EXTRACT(YEAR FROM t.date) - p.birth_year BETWEEN 35 AND 44 THEN '35-44'
        WHEN EXTRACT(YEAR FROM t.date) - p.birth_year BETWEEN 45 AND 54 THEN '45-54'
        WHEN EXTRACT(YEAR FROM t.date) - p.birth_year BETWEEN 55 AND 64 THEN '55-64'
        ELSE '65+'
    END AS age_group,
    SUM(ti.weight_kg) AS total_kg,
    SUM(ti.value) AS total_ron,
    AVG(ti.price_per_kg) AS avg_price_per_kg,
    COUNT(DISTINCT t.document_id) AS transaction_count,
    COUNT(DISTINCT t.cnp) AS unique_partners
FROM transactions t
JOIN transaction_items ti ON ti.document_id = t.document_id
JOIN waste_types wt ON wt.id = ti.waste_type_id
JOIN waste_categories wc ON wc.id = wt.category_id
JOIN partners p ON p.cnp = t.cnp
GROUP BY 1, 2, 3, 4, 5
ORDER BY 1, 2;
```

---

## Adatbázis méret összefoglaló

| Tábla | Sorok | Megjegyzés |
|-------|-------|------------|
| partners | 30,853 | Természetes személyek |
| transactions | 112,765 | Bizonylatok (2022.01 – 2026.02) |
| transaction_items | 225,089 | Tételsorok (~2x tranzakció) |
| waste_categories | 16 | Fő kategóriák |
| waste_types | 47 | Altípusok |
| firme | 77 | B2B vevők |
| vanzari | 4,390 | B2B eladások |
| sumar_deseuri | 435 | Havi összesítő |
| transporturi_firme | 39 | Szállítások |
| sumar_firme | 0 | Üres |
