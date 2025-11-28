# PAJU Hulladékfelvásárlás Dashboard

<div align="center">

![PAJU Logo](https://img.shields.io/badge/PAJU-Waste_Recycling-00d9ff?style=for-the-badge&logo=recycle&logoColor=white)

**Komplex hulladékfelvásárlási adatkezelő és analitikai rendszer**

[![Vercel](https://img.shields.io/badge/Deployed_on-Vercel-black?style=flat-square&logo=vercel)](https://intern-oho2mwsdq-ebastians-projects.vercel.app)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-NeonDB-336791?style=flat-square&logo=postgresql&logoColor=white)](https://neon.tech)

</div>

---

## Funkciók

- **Interaktív Dashboard** - Valós idejű összesítések, grafikonok és trendek
- **Partner Kezelés** - CNP alapú keresés, részletes profilok, tranzakció történet
- **Tranzakció Követés** - Dokumentum szintű nyomonkövetés, napi/havi összesítők
- **Hulladék Statisztikák** - Kategória szerinti bontás, árfolyam változások
- **Analitika** - Megye/város elemzés, korosztályi megoszlás, trendek

---

## Technológiai Stack

```
Frontend:    HTML5 + Chart.js + Vanilla JS
Backend:     Python Serverless Functions (Vercel)
Database:    PostgreSQL (NeonDB)
Deployment:  Vercel Edge Network
```

---

## API Dokumentáció

### `/api/analytics` - Összesített Analitika

| Paraméter | Leírás | Példa |
|-----------|--------|-------|
| `type=overview` | Teljes áttekintés | `/api/analytics?type=overview` |
| `type=yearly` | Éves összesítés | `/api/analytics?type=yearly` |
| `type=monthly` | Havi bontás | `/api/analytics?type=monthly&year=2024` |
| `type=county` | Megye szerinti | `/api/analytics?type=county` |
| `type=city` | Város szerinti | `/api/analytics?type=city&county=Bihor` |
| `type=weekday` | Heti minták | `/api/analytics?type=weekday` |
| `type=age` | Korosztály elemzés | `/api/analytics?type=age` |
| `type=trends` | Trend összehasonlítás | `/api/analytics?type=trends` |

### `/api/partners` - Partner Kezelés

| Paraméter | Leírás | Példa |
|-----------|--------|-------|
| `q=<keresés>` | Név/CNP keresés | `/api/partners?q=Kovacs` |
| `cnp=<cnp>` | Részletes profil | `/api/partners?cnp=1234567890123` |
| `top=<n>` | Top partnerek | `/api/partners?top=20` |
| `inactive=<napok>` | Inaktív partnerek | `/api/partners?inactive=60` |
| `onetime` | Egyszeri vásárlók | `/api/partners?onetime` |

### `/api/transactions` - Tranzakciók

| Paraméter | Leírás | Példa |
|-----------|--------|-------|
| `document_id=<id>` | Dokumentum részletek | `/api/transactions?document_id=PJ-123456` |
| `cnp=<cnp>` | Partner tranzakciói | `/api/transactions?cnp=1234567890123` |
| `date_from/to` | Dátum szűrés | `/api/transactions?date_from=2024-01-01&date_to=2024-12-31` |
| `daily=<dátum>` | Napi összesítő | `/api/transactions?daily=2024-10-15` |
| `category` | Kategória szűrés | `/api/transactions?date_from=2024-01-01&category=Cupru` |

### `/api/waste` - Hulladék Statisztikák

| Paraméter | Leírás | Példa |
|-----------|--------|-------|
| `type=categories` | Kategóriák összesítése | `/api/waste?type=categories` |
| `type=types` | Típusok listája | `/api/waste?type=types&category=Aluminiu` |
| `type=prices` | Árfolyam történet | `/api/waste?type=prices&category=Cupru` |
| `type=top` | Top szállítók | `/api/waste?type=top&category=Fier&limit=10` |
| `type=monthly` | Havi bontás | `/api/waste?type=monthly&category=Cupru` |
| `type=search` | Tranzakció keresés | `/api/waste?type=search&waste=Cupru&min_price=30` |

---

## Adatbázis Struktúra

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│    partners     │     │   transactions   │     │ transaction_items   │
├─────────────────┤     ├──────────────────┤     ├─────────────────────┤
│ cnp (PK)        │────<│ document_id (PK) │────<│ id (PK)             │
│ name            │     │ date             │     │ document_id (FK)    │
│ city            │     │ cnp (FK)         │     │ waste_type_id (FK)  │
│ county          │     │ payment_type     │     │ price_per_kg        │
│ street          │     │ iban             │     │ weight_kg           │
│ phone           │     │ gross_value      │     │ value               │
│ email           │     │ env_tax          │     └─────────────────────┘
│ birth_year      │     │ income_tax       │               │
│ sex             │     │ net_paid         │               │
└─────────────────┘     └──────────────────┘               ▼
                                              ┌─────────────────────┐
                                              │    waste_types      │
                                              ├─────────────────────┤
                                              │ id (PK)             │
                                              │ name                │
                                              │ category_id (FK)    │
                                              └─────────────────────┘
                                                         │
                                                         ▼
                                              ┌─────────────────────┐
                                              │  waste_categories   │
                                              ├─────────────────────┤
                                              │ id (PK)             │
                                              │ name                │
                                              └─────────────────────┘
```

---

## Statisztikák

| Mutató | Érték |
|--------|-------|
| Teljes forgalom | **118.7M RON** |
| Tranzakciók száma | **51,000+** |
| Regisztrált partnerek | **30,000+** |
| Aktív partnerek | **13,000+** |
| Hulladék kategóriák | **16** |
| Időszak | 2024.01 - 2025.11 |

---

## Hulladék Kategóriák

| Kategória | Összmennyiség |
|-----------|---------------|
| Fier (Vas) | 16.5M kg |
| Aluminiu | 2.5M kg |
| DEEE (Elektronika) | 2.0M kg |
| Cupru (Réz) | 1.5M kg |
| Acumulatori | 1.4M kg |
| Carton | 1.1M kg |
| Alama (Sárgaréz) | 580K kg |
| Inox | 243K kg |
| Sticla (Üveg) | 181K kg |

---

## Telepítés

### Követelmények

- Python 3.9+
- PostgreSQL adatbázis (ajánlott: NeonDB)
- Vercel CLI (deployment-hez)

### Környezeti változók

```env
POSTGRES_URL=postgresql://user:pass@host/db?sslmode=require
# vagy
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
```

### Helyi fejlesztés

```bash
# Függőségek telepítése
pip install -r requirements.txt

# Adatbázis inicializálás
python setup_database.py

# Vercel dev server
vercel dev
```

### Deployment

```bash
vercel --prod
```

---

## Projekt Struktúra

```
paju/
├── api/
│   ├── analytics.py     # Analitika API
│   ├── partners.py      # Partner kezelés API
│   ├── transactions.py  # Tranzakció API
│   ├── waste.py         # Hulladék statisztika API
│   ├── data.py          # Dashboard adat API
│   └── monthly.py       # Havi részletek API
├── index.html           # Főoldal (redirect)
├── dashboard_multi.html # Interaktív dashboard
├── setup_database.py    # DB inicializáló script
├── vercel.json          # Vercel konfiguráció
├── requirements.txt     # Python függőségek
└── README.md            # Ez a fájl
```

---

## Fejlesztők

<div align="center">

### Powered by

**zYztem & Claude**

*Building intelligent data solutions*

---

[![Made with Love](https://img.shields.io/badge/Made_with-Love-ff6b6b?style=for-the-badge&logo=heart&logoColor=white)](https://github.com)

</div>

---

## Licensz

MIT License - Szabadon felhasználható és módosítható.

---

<div align="center">

**2024-2025** | PAJU Hulladékfelvásárlás

</div>
