# Phase 1 — Sezonalitate & Calendar Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the calendar baseline — holidays table, company closures detection workflow, and a new "Sezonalitate" tab showing weekly/monthly patterns and holiday effects — so Phase 2 (weather analyzer) has a correct baseline to build on.

**Architecture:** Two new PostgreSQL tables (`holidays`, `company_closures`). One new Python serverless endpoint (`api/calendar.py`) following the existing pattern from `api/waste.py`. One new frontend tab in `index.html` with 6 sections, using Chart.js and the existing dark-theme styles. Holiday seeding via a standalone Python script (`scripts/seed_holidays.py`) that implements Butcher's Gregorian Easter algorithm for Catholic and Meeus' Julian algorithm for Orthodox.

**Tech Stack:** PostgreSQL (NeonDB), Python 3.12 + psycopg2, vanilla JS + Chart.js, Vercel serverless.

**Source spec:** `docs/superpowers/specs/2026-04-17-meteo-trafic-sezonalitate-design.md`

**Non-goals for this plan:** Weather ingestion, weather API, Meteo & Trafic tab, weather badge in partner modal. All three are covered by separate plans after Phase 1 ships.

---

## File Structure

**New files:**
- `scripts/migrations/001_create_holidays.sql` — DDL for `holidays` table
- `scripts/migrations/002_create_company_closures.sql` — DDL for `company_closures` table
- `scripts/run_migration.py` — simple helper to run a SQL file against `POSTGRES_URL`
- `scripts/seed_holidays.py` — holiday generator + upsert; contains `catholic_easter(year)`, `orthodox_easter(year)`, `generate_holidays(year_from, year_to)`, and a `main()` that seeds the DB. Also runs its own inline self-tests when invoked with `--self-test`.
- `api/calendar.py` — new API endpoint, mirrors structure of `api/waste.py`

**Modified files:**
- `requirements.txt` — no changes (psycopg2 already there, no new deps)
- `index.html` — add "Sezonalitate" nav button + tab panel with 6 sections; add JS loader functions + chart rendering + closure-validation UI handlers
- `CLAUDE.md` — append `/api/calendar` endpoint reference to the API docs

**No test framework is added.** The codebase has none, and introducing pytest for this project is out of scope. Correctness-critical code (the Easter algorithms) is verified via a `--self-test` flag on the seed script that asserts against hand-verified Easter dates. API endpoints are verified via curl smoke tests. UI is verified manually with a checklist at the end.

---

## Task 1: Create `holidays` table

**Files:**
- Create: `scripts/migrations/001_create_holidays.sql`
- Create: `scripts/run_migration.py`

- [ ] **Step 1: Write the migration SQL**

```sql
-- scripts/migrations/001_create_holidays.sql
CREATE TABLE IF NOT EXISTS holidays (
  date DATE NOT NULL,
  name VARCHAR(100) NOT NULL,
  type VARCHAR(20) NOT NULL CHECK (type IN ('national', 'catholic', 'orthodox')),
  is_official BOOLEAN NOT NULL,
  PRIMARY KEY (date, type)
);

CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(date);
CREATE INDEX IF NOT EXISTS idx_holidays_official ON holidays(date) WHERE is_official = true;
```

- [ ] **Step 2: Write the migration runner**

```python
# scripts/run_migration.py
"""Run a SQL migration file against POSTGRES_URL. Usage: python scripts/run_migration.py scripts/migrations/NNN_name.sql"""
import os, sys, psycopg2
from pathlib import Path

def load_env_local():
    env = Path(__file__).parent.parent / '.env.local'
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_migration.py <path-to-sql-file>")
        sys.exit(1)
    load_env_local()
    sql_path = Path(sys.argv[1])
    if not sql_path.exists():
        print(f"Missing: {sql_path}"); sys.exit(1)
    sql = sql_path.read_text()
    url = os.environ.get('POSTGRES_URL')
    if not url:
        print("POSTGRES_URL not set"); sys.exit(1)
    conn = psycopg2.connect(url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.close()
    print(f"Applied: {sql_path.name}")

if __name__ == '__main__':
    main()
```

- [ ] **Step 3: Run the migration**

Run: `python scripts/run_migration.py scripts/migrations/001_create_holidays.sql`
Expected: `Applied: 001_create_holidays.sql`

- [ ] **Step 4: Verify table exists**

Run:
```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL'])
cur = c.cursor()
cur.execute(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='holidays' ORDER BY ordinal_position\")
for r in cur.fetchall(): print(r)
"
```
Expected: four rows — `date/date`, `name/character varying`, `type/character varying`, `is_official/boolean`.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrations/001_create_holidays.sql scripts/run_migration.py
git commit -m "add holidays table migration + runner script"
```

---

## Task 2: Create `company_closures` table

**Files:**
- Create: `scripts/migrations/002_create_company_closures.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- scripts/migrations/002_create_company_closures.sql
CREATE TABLE IF NOT EXISTS company_closures (
  date DATE PRIMARY KEY,
  reason VARCHAR(200),
  detected_automatically BOOLEAN NOT NULL DEFAULT true,
  validated_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_closures_date ON company_closures(date);
```

`reason = '__ignored__'` is the sentinel for "auto-detected but user marked as not-a-closure" (needed so the candidate list stops showing it).

- [ ] **Step 2: Run the migration**

Run: `python scripts/run_migration.py scripts/migrations/002_create_company_closures.sql`
Expected: `Applied: 002_create_company_closures.sql`

- [ ] **Step 3: Commit**

```bash
git add scripts/migrations/002_create_company_closures.sql
git commit -m "add company_closures table migration"
```

---

## Task 3: Holiday seeder — Catholic Easter algorithm (with self-test)

**Files:**
- Create: `scripts/seed_holidays.py`

- [ ] **Step 1: Write the initial seeder with Butcher's Gregorian algorithm + self-test**

```python
# scripts/seed_holidays.py
"""Seed the holidays table for a year range. Computes Catholic and Orthodox Easter.

Usage:
  python scripts/seed_holidays.py --self-test              # just run algorithm checks
  python scripts/seed_holidays.py --year-from 2022 --year-to 2030
"""
import argparse, os, sys
from datetime import date, timedelta
from pathlib import Path

def load_env_local():
    env = Path(__file__).parent.parent / '.env.local'
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))

def catholic_easter(year: int) -> date:
    """Butcher's Gregorian Easter algorithm (returns Sunday)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

# Known Catholic Easter Sunday dates, hand-verified.
KNOWN_CATHOLIC_EASTER = {
    2022: date(2022, 4, 17),
    2023: date(2023, 4, 9),
    2024: date(2024, 3, 31),
    2025: date(2025, 4, 20),
    2026: date(2026, 4, 5),
    2027: date(2027, 3, 28),
    2028: date(2028, 4, 16),
    2029: date(2029, 4, 1),
    2030: date(2030, 4, 21),
}

def self_test():
    for y, expected in KNOWN_CATHOLIC_EASTER.items():
        got = catholic_easter(y)
        assert got == expected, f"catholic_easter({y}) -> {got}, expected {expected}"
    print(f"Catholic Easter OK for {len(KNOWN_CATHOLIC_EASTER)} years")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--year-from', type=int, default=2022)
    parser.add_argument('--year-to', type=int, default=2030)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        sys.exit(0)
    print("Seeding not yet implemented in this task; run --self-test for now.")
```

- [ ] **Step 2: Run the self-test to verify Catholic Easter algorithm**

Run: `python scripts/seed_holidays.py --self-test`
Expected: `Catholic Easter OK for 9 years`

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_holidays.py
git commit -m "add holiday seeder skeleton with Catholic Easter algorithm"
```

---

## Task 4: Holiday seeder — Orthodox Easter algorithm

**Files:**
- Modify: `scripts/seed_holidays.py`

- [ ] **Step 1: Add Orthodox Easter + extended self-test**

Insert the `orthodox_easter` function immediately after `catholic_easter`, and add the known-dates dict and extra assertions to `self_test()`.

```python
def orthodox_easter(year: int) -> date:
    """Meeus' Julian Easter algorithm, then Julian -> Gregorian shift (+13 days for 1900-2099)."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month_julian = (d + e + 114) // 31
    day_julian = ((d + e + 114) % 31) + 1
    julian_date = date(year, month_julian, day_julian)
    return julian_date + timedelta(days=13)

# Known Orthodox Easter Sunday dates, hand-verified.
KNOWN_ORTHODOX_EASTER = {
    2022: date(2022, 4, 24),
    2023: date(2023, 4, 16),
    2024: date(2024, 5, 5),
    2025: date(2025, 4, 20),
    2026: date(2026, 4, 12),
    2027: date(2027, 5, 2),
    2028: date(2028, 4, 16),
    2029: date(2029, 4, 8),
    2030: date(2030, 4, 28),
}
```

Then update `self_test()`:

```python
def self_test():
    for y, expected in KNOWN_CATHOLIC_EASTER.items():
        got = catholic_easter(y)
        assert got == expected, f"catholic_easter({y}) -> {got}, expected {expected}"
    print(f"Catholic Easter OK for {len(KNOWN_CATHOLIC_EASTER)} years")
    for y, expected in KNOWN_ORTHODOX_EASTER.items():
        got = orthodox_easter(y)
        assert got == expected, f"orthodox_easter({y}) -> {got}, expected {expected}"
    print(f"Orthodox Easter OK for {len(KNOWN_ORTHODOX_EASTER)} years")
```

- [ ] **Step 2: Run the self-test**

Run: `python scripts/seed_holidays.py --self-test`
Expected: two OK lines — Catholic 9 years, Orthodox 9 years.

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_holidays.py
git commit -m "add Orthodox Easter algorithm to holiday seeder"
```

---

## Task 5: Holiday seeder — generate full holiday set for a year range

**Files:**
- Modify: `scripts/seed_holidays.py`

- [ ] **Step 1: Add `generate_holidays()` producing the complete list**

Insert this function after `orthodox_easter`:

```python
def generate_holidays(year_from: int, year_to: int):
    """Yield (date, name, type, is_official) tuples for all holidays in the year range."""
    for year in range(year_from, year_to + 1):
        # Fixed national holidays (is_official=True)
        yield (date(year, 1, 1), 'Anul Nou', 'national', True)
        yield (date(year, 1, 2), 'Anul Nou (a doua zi)', 'national', True)
        yield (date(year, 1, 24), 'Ziua Unirii Principatelor Romane', 'national', True)
        yield (date(year, 5, 1), 'Ziua Muncii', 'national', True)
        yield (date(year, 6, 1), 'Ziua Copilului', 'national', True)
        yield (date(year, 8, 15), 'Adormirea Maicii Domnului', 'national', True)
        yield (date(year, 11, 30), 'Sfantul Andrei', 'national', True)
        yield (date(year, 12, 1), 'Ziua Nationala', 'national', True)
        yield (date(year, 12, 25), 'Craciunul', 'national', True)
        yield (date(year, 12, 26), 'Craciunul (a doua zi)', 'national', True)

        # Catholic (is_official=False — cultural, not a Romanian public holiday)
        ce = catholic_easter(year)
        yield (ce - timedelta(days=2), 'Vinerea Mare (catolica)', 'catholic', False)
        yield (ce, 'Pastele catolic', 'catholic', False)
        yield (ce + timedelta(days=1), 'A doua zi de Pasti (catolic)', 'catholic', False)
        yield (ce + timedelta(days=49), 'Rusalii catolice', 'catholic', False)
        yield (ce + timedelta(days=50), 'A doua zi de Rusalii (catolic)', 'catholic', False)

        # Orthodox (is_official=True for Good Friday since 2018, Easter and Pentecost always)
        oe = orthodox_easter(year)
        yield (oe - timedelta(days=2), 'Vinerea Mare (ortodoxa)', 'orthodox', year >= 2018)
        yield (oe, 'Pastele ortodox', 'orthodox', True)
        yield (oe + timedelta(days=1), 'A doua zi de Pasti (ortodox)', 'orthodox', True)
        yield (oe + timedelta(days=49), 'Rusalii ortodoxe', 'orthodox', True)
        yield (oe + timedelta(days=50), 'A doua zi de Rusalii (ortodoxe)', 'orthodox', True)
```

Then extend `self_test()` to verify the count and some known non-trivial dates:

```python
def self_test():
    for y, expected in KNOWN_CATHOLIC_EASTER.items():
        assert catholic_easter(y) == expected
    for y, expected in KNOWN_ORTHODOX_EASTER.items():
        assert orthodox_easter(y) == expected
    print(f"Easter algorithms OK ({len(KNOWN_CATHOLIC_EASTER)} + {len(KNOWN_ORTHODOX_EASTER)} years)")

    rows = list(generate_holidays(2024, 2024))
    # 10 fixed national + 5 catholic + 5 orthodox = 20 per year
    assert len(rows) == 20, f"Expected 20 entries for 2024, got {len(rows)}"
    by_type = {}
    for _, _, t, _ in rows:
        by_type[t] = by_type.get(t, 0) + 1
    assert by_type == {'national': 10, 'catholic': 5, 'orthodox': 5}, by_type

    # Spot-check: Romanian National Day 2024 is Dec 1
    dates_2024 = {name: d for d, name, *_ in rows}
    assert dates_2024['Ziua Nationala'] == date(2024, 12, 1)
    # Spot-check: Orthodox Easter Monday 2024 = May 6 (Easter was May 5)
    assert dates_2024['A doua zi de Pasti (ortodox)'] == date(2024, 5, 6)

    print(f"generate_holidays() OK: 20 entries/year, correct type split, known dates match")
```

- [ ] **Step 2: Run the self-test**

Run: `python scripts/seed_holidays.py --self-test`
Expected:
```
Easter algorithms OK (9 + 9 years)
generate_holidays() OK: 20 entries/year, correct type split, known dates match
```

- [ ] **Step 3: Commit**

```bash
git add scripts/seed_holidays.py
git commit -m "add generate_holidays() with fixed + computed entries"
```

---

## Task 6: Holiday seeder — database upsert + CLI run

**Files:**
- Modify: `scripts/seed_holidays.py`

- [ ] **Step 1: Add the DB upsert and wire up CLI**

Add imports at the top if missing:

```python
import psycopg2
```

Add this function after `generate_holidays`:

```python
def upsert_holidays(year_from: int, year_to: int):
    url = os.environ.get('POSTGRES_URL')
    if not url:
        raise RuntimeError('POSTGRES_URL not set (check .env.local)')
    conn = psycopg2.connect(url)
    conn.autocommit = False
    rows = list(generate_holidays(year_from, year_to))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO holidays (date, name, type, is_official)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (date, type) DO UPDATE
              SET name = EXCLUDED.name,
                  is_official = EXCLUDED.is_official
            """,
            rows,
        )
    conn.commit()
    conn.close()
    return len(rows)
```

Replace the placeholder at the bottom of `__main__`:

```python
    if args.self_test:
        self_test()
        sys.exit(0)
    load_env_local()
    n = upsert_holidays(args.year_from, args.year_to)
    print(f"Upserted {n} holidays for {args.year_from}-{args.year_to}")
```

- [ ] **Step 2: Self-test still passes**

Run: `python scripts/seed_holidays.py --self-test`
Expected: same two OK lines as before.

- [ ] **Step 3: Seed the database for 2022-2030**

Run: `python scripts/seed_holidays.py --year-from 2022 --year-to 2030`
Expected: `Upserted 180 holidays for 2022-2030` (9 years × 20 entries).

- [ ] **Step 4: Verify DB contents**

Run:
```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL'])
cur = c.cursor()
cur.execute(\"SELECT type, COUNT(*) FROM holidays GROUP BY type ORDER BY type\")
print('By type:', cur.fetchall())
cur.execute(\"SELECT COUNT(*) FROM holidays WHERE is_official\")
print('Official count:', cur.fetchone())
cur.execute(\"SELECT date, name FROM holidays WHERE date BETWEEN '2024-04-28' AND '2024-05-10' AND type='orthodox' ORDER BY date\")
for r in cur.fetchall(): print(r)
"
```
Expected output:
```
By type: [('catholic', 45), ('national', 90), ('orthodox', 45)]
Official count: (135,)
(datetime.date(2024, 5, 3), 'Vinerea Mare (ortodoxa)')
(datetime.date(2024, 5, 5), 'Pastele ortodox')
(datetime.date(2024, 5, 6), 'A doua zi de Pasti (ortodox)')
```

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_holidays.py
git commit -m "wire up holiday upsert and seed 2022-2030"
```

---

## Task 7: Create `api/calendar.py` skeleton

**Files:**
- Create: `api/calendar.py`

- [ ] **Step 1: Write the handler skeleton (mirrors `api/waste.py` structure)**

```python
"""
Calendar API - Sarbatori, zile lucratoare, inchideri companie
Endpoints:
  GET  /api/calendar?type=holidays&year=YYYY
  GET  /api/calendar?type=closures
  GET  /api/calendar?type=closure_candidates
  GET  /api/calendar?type=working_days&date_from=X&date_to=Y
  GET  /api/calendar?type=weekly_pattern&date_from=X&date_to=Y
  GET  /api/calendar?type=monthly_pattern&year=YYYY
  GET  /api/calendar?type=holiday_effect&window=3
  GET  /api/calendar?type=bridge_days
  GET  /api/calendar?type=illegal_workdays
  POST /api/calendar?action=confirm_closure   body: {date_from, date_to, reason}
  POST /api/calendar?action=ignore_closure    body: {date_from, date_to}
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qs
from decimal import Decimal
from datetime import date, datetime

def get_db():
    db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL_NO_SSL')
    if not db_url:
        raise Exception("No database URL configured")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")

class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload, default=json_default).encode('utf-8'))

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            query_type = params.get('type', [''])[0]

            conn = get_db()
            cur = conn.cursor()

            if query_type == 'ping':
                result = {'ok': True, 'endpoint': 'calendar'}
            else:
                result = {'error': 'Unknown query type', 'got': query_type}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {'error': str(e)})

    def do_POST(self):
        try:
            self._send(200, {'error': 'No POST actions yet'})
        except Exception as e:
            self._send(500, {'error': str(e)})
```

- [ ] **Step 2: Smoke-test via Vercel dev**

In one terminal: `vercel dev` (or use the already-deployed preview).
In another: `curl http://localhost:3000/api/calendar?type=ping`
Expected: `{"ok": true, "endpoint": "calendar"}`

If `vercel dev` is not running, skip the live check — it will be verified when pushed.

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add api/calendar.py skeleton"
```

---

## Task 8: `GET /api/calendar?type=holidays` endpoint

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the holidays lister**

Inside the `handler` class, add:

```python
    def list_holidays(self, cur, year):
        if year:
            cur.execute(
                "SELECT date, name, type, is_official FROM holidays WHERE EXTRACT(year FROM date) = %s ORDER BY date",
                (int(year),),
            )
        else:
            cur.execute("SELECT date, name, type, is_official FROM holidays ORDER BY date")
        return [dict(r) for r in cur.fetchall()]
```

Wire it into `do_GET` — replace the `if query_type == 'ping'` branch with:

```python
            if query_type == 'ping':
                result = {'ok': True, 'endpoint': 'calendar'}
            elif query_type == 'holidays':
                year = params.get('year', [None])[0]
                result = {'holidays': self.list_holidays(cur, year)}
            else:
                result = {'error': 'Unknown query type', 'got': query_type}
```

- [ ] **Step 2: Smoke-test**

Run:
```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL'])
cur = c.cursor()
cur.execute(\"SELECT date, name, type FROM holidays WHERE EXTRACT(year FROM date) = 2024 ORDER BY date LIMIT 5\")
for r in cur.fetchall(): print(r)
"
```
Expected: five 2024 holidays starting Jan 1, Jan 2, Jan 24, ...

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add /api/calendar?type=holidays endpoint"
```

---

## Task 9: `GET /api/calendar?type=closure_candidates` + `GET closures`

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the closures-list method**

Inside the `handler` class:

```python
    def list_closures(self, cur):
        cur.execute(
            """
            SELECT date, reason, detected_automatically, validated_at
            FROM company_closures
            WHERE reason IS DISTINCT FROM '__ignored__'
            ORDER BY date
            """
        )
        return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 2: Add the candidate-detection method**

```python
    def closure_candidates(self, cur):
        # Days in the transactions range that are: not Sunday, not an official holiday,
        # not already validated/ignored in company_closures, AND have zero transactions.
        cur.execute(
            """
            WITH bounds AS (
              SELECT MIN(date) AS dmin, MAX(date) AS dmax FROM transactions
            ),
            days AS (
              SELECT generate_series(b.dmin, b.dmax, '1 day'::interval)::date AS d FROM bounds b
            ),
            official_holiday_dates AS (
              SELECT DISTINCT date FROM holidays WHERE is_official
            ),
            known_closures AS (
              SELECT date FROM company_closures
            ),
            tx_days AS (
              SELECT DISTINCT date FROM transactions
            )
            SELECT d AS date,
                   TO_CHAR(d, 'Dy') AS dow_label,
                   EXTRACT(ISODOW FROM d)::int AS dow
            FROM days
            WHERE EXTRACT(ISODOW FROM d) <> 7                -- not Sunday
              AND d NOT IN (SELECT date FROM official_holiday_dates)
              AND d NOT IN (SELECT date FROM known_closures)
              AND d NOT IN (SELECT date FROM tx_days)
            ORDER BY d
            """
        )
        singles = [dict(r) for r in cur.fetchall()]

        # Group into contiguous runs for easier validation.
        runs = []
        for row in singles:
            if runs and (row['date'] - runs[-1]['date_to']).days == 1:
                runs[-1]['date_to'] = row['date']
                runs[-1]['working_days'] += 1
            else:
                runs.append({'date_from': row['date'], 'date_to': row['date'], 'working_days': 1})
        return {'runs': runs, 'total_days': len(singles)}
```

Note: `EXTRACT(ISODOW FROM d) = 7` is Sunday in ISO (Mon=1..Sun=7).

- [ ] **Step 3: Wire into `do_GET`**

Replace the routing block with:

```python
            if query_type == 'ping':
                result = {'ok': True, 'endpoint': 'calendar'}
            elif query_type == 'holidays':
                year = params.get('year', [None])[0]
                result = {'holidays': self.list_holidays(cur, year)}
            elif query_type == 'closures':
                result = {'closures': self.list_closures(cur)}
            elif query_type == 'closure_candidates':
                result = self.closure_candidates(cur)
            else:
                result = {'error': 'Unknown query type', 'got': query_type}
```

- [ ] **Step 4: Smoke-test the candidate query**

Run:
```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL'])
cur = c.cursor()
cur.execute('''
WITH bounds AS (SELECT MIN(date) AS dmin, MAX(date) AS dmax FROM transactions),
days AS (SELECT generate_series(b.dmin, b.dmax, '1 day'::interval)::date AS d FROM bounds b)
SELECT COUNT(*) FROM days
WHERE EXTRACT(ISODOW FROM d) <> 7
  AND d NOT IN (SELECT date FROM holidays WHERE is_official)
  AND d NOT IN (SELECT DISTINCT date FROM transactions)
''')
print('Raw candidates:', cur.fetchone())
"
```
Expected: a non-zero integer count (the days that are candidates for closure). Eyeball that it's a plausible number — if you take ~4 weeks of closures per year × 5 years × ~5 days = roughly 100, give or take. If it's >500, something is wrong with the join.

- [ ] **Step 5: Commit**

```bash
git add api/calendar.py
git commit -m "add closures and closure_candidates endpoints"
```

---

## Task 10: `POST /api/calendar` — confirm_closure / ignore_closure

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Replace the `do_POST` stub with the real implementation**

```python
    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            action = params.get('action', [''])[0]

            length = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(length).decode('utf-8') if length else '{}'
            data = json.loads(body) if body else {}

            conn = get_db()
            cur = conn.cursor()

            if action in ('confirm_closure', 'ignore_closure'):
                df = data.get('date_from'); dt = data.get('date_to')
                if not df or not dt:
                    conn.close(); self._send(400, {'error': 'date_from and date_to required'}); return
                reason = data.get('reason') or ('' if action == 'confirm_closure' else '__ignored__')
                if action == 'ignore_closure':
                    reason = '__ignored__'
                cur.execute(
                    """
                    INSERT INTO company_closures (date, reason, detected_automatically)
                    SELECT generate_series(%s::date, %s::date, '1 day'::interval)::date, %s, true
                    ON CONFLICT (date) DO UPDATE SET reason = EXCLUDED.reason, validated_at = now()
                    """,
                    (df, dt, reason),
                )
                conn.commit()
                result = {'ok': True, 'action': action, 'date_from': df, 'date_to': dt}
            else:
                result = {'error': 'Unknown action', 'got': action}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {'error': str(e)})
```

- [ ] **Step 2: Smoke-test with an insert and a read-back**

Run:
```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); c.autocommit = True
cur = c.cursor()
cur.execute(\"\"\"
  INSERT INTO company_closures (date, reason, detected_automatically)
  SELECT generate_series('2099-12-01'::date, '2099-12-03'::date, '1 day'::interval)::date, 'TEST_DELETE_ME', true
  ON CONFLICT (date) DO UPDATE SET reason = EXCLUDED.reason
\"\"\")
cur.execute(\"SELECT * FROM company_closures WHERE reason='TEST_DELETE_ME'\")
for r in cur.fetchall(): print(r)
cur.execute(\"DELETE FROM company_closures WHERE reason='TEST_DELETE_ME'\")
print('Cleaned up.')
"
```
Expected: three rows listed, then "Cleaned up." — confirms the range insert pattern works.

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add confirm_closure and ignore_closure POST actions"
```

---

## Task 11: `GET /api/calendar?type=weekly_pattern`

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the weekly-pattern query (Mon-Sat only, working days)**

```python
    def weekly_pattern(self, cur, date_from, date_to):
        where = []
        args = []
        if date_from: where.append("t.date >= %s"); args.append(date_from)
        if date_to:   where.append("t.date <= %s"); args.append(date_to)
        where_sql = (' AND '.join(where)) if where else 'TRUE'
        # Exclude Sundays + official holidays + validated closures (not ignored)
        cur.execute(
            f"""
            WITH daily AS (
              SELECT t.date,
                     EXTRACT(ISODOW FROM t.date)::int AS dow,
                     COUNT(DISTINCT t.cnp) AS partners,
                     COUNT(*) AS tx_count,
                     COALESCE(SUM(i.weight_kg), 0) AS kg,
                     COALESCE(SUM(t.gross_value), 0) AS ron
              FROM transactions t
              LEFT JOIN transaction_items i ON i.document_id = t.document_id
              WHERE {where_sql}
                AND EXTRACT(ISODOW FROM t.date) <> 7
                AND t.date NOT IN (SELECT date FROM holidays WHERE is_official)
                AND t.date NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
              GROUP BY t.date
            )
            SELECT dow,
                   CASE dow WHEN 1 THEN 'Luni' WHEN 2 THEN 'Marti' WHEN 3 THEN 'Miercuri'
                            WHEN 4 THEN 'Joi' WHEN 5 THEN 'Vineri' WHEN 6 THEN 'Sambata' END AS dow_label,
                   COUNT(*) AS working_days,
                   ROUND(AVG(partners)::numeric, 1) AS avg_partners,
                   ROUND(AVG(tx_count)::numeric, 1) AS avg_transactions,
                   ROUND(AVG(kg)::numeric, 1) AS avg_kg,
                   ROUND(AVG(ron)::numeric, 2) AS avg_ron
            FROM daily
            GROUP BY dow
            ORDER BY dow
            """,
            args,
        )
        return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 2: Wire into `do_GET`**

Add branch above the `else` in the routing block:

```python
            elif query_type == 'weekly_pattern':
                df = params.get('date_from', [None])[0]
                dt = params.get('date_to', [None])[0]
                result = {'weekly_pattern': self.weekly_pattern(cur, df, dt)}
```

- [ ] **Step 3: Smoke-test the query locally**

Run:
```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); cur = c.cursor()
cur.execute('''
WITH daily AS (
  SELECT t.date, EXTRACT(ISODOW FROM t.date)::int AS dow, COUNT(DISTINCT t.cnp) AS partners
  FROM transactions t
  WHERE EXTRACT(ISODOW FROM t.date) <> 7
    AND t.date NOT IN (SELECT date FROM holidays WHERE is_official)
  GROUP BY t.date
)
SELECT dow, COUNT(*), ROUND(AVG(partners)::numeric,1) FROM daily GROUP BY dow ORDER BY dow
''')
for r in cur.fetchall(): print(r)
"
```
Expected: 6 rows, dow 1-6, each with working-day count and avg partners. Most working weeks have all six dow values populated.

- [ ] **Step 4: Commit**

```bash
git add api/calendar.py
git commit -m "add weekly_pattern endpoint"
```

---

## Task 12: `GET /api/calendar?type=monthly_pattern`

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the monthly-pattern query**

```python
    def monthly_pattern(self, cur, year):
        year = int(year) if year else None
        where = ["EXTRACT(ISODOW FROM t.date) <> 7",
                 "t.date NOT IN (SELECT date FROM holidays WHERE is_official)",
                 "t.date NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')"]
        args = []
        if year:
            where.append("EXTRACT(year FROM t.date) = %s")
            args.append(year)
        cur.execute(
            f"""
            WITH daily AS (
              SELECT t.date,
                     EXTRACT(month FROM t.date)::int AS month,
                     COUNT(DISTINCT t.cnp) AS partners,
                     COUNT(*) AS tx_count,
                     COALESCE(SUM(i.weight_kg), 0) AS kg,
                     COALESCE(SUM(t.gross_value), 0) AS ron
              FROM transactions t
              LEFT JOIN transaction_items i ON i.document_id = t.document_id
              WHERE {' AND '.join(where)}
              GROUP BY t.date
            )
            SELECT month,
                   COUNT(*) AS working_days,
                   ROUND(AVG(partners)::numeric, 1) AS avg_partners_per_day,
                   ROUND(AVG(tx_count)::numeric, 1) AS avg_transactions_per_day,
                   ROUND(AVG(kg)::numeric, 1) AS avg_kg_per_day,
                   ROUND(AVG(ron)::numeric, 2) AS avg_ron_per_day,
                   ROUND(SUM(partners)::numeric, 0) AS total_partners,
                   SUM(tx_count) AS total_transactions,
                   ROUND(SUM(kg)::numeric, 1) AS total_kg,
                   ROUND(SUM(ron)::numeric, 2) AS total_ron
            FROM daily
            GROUP BY month
            ORDER BY month
            """,
            args,
        )
        return [dict(r) for r in cur.fetchall()]
```

Wire it up with:

```python
            elif query_type == 'monthly_pattern':
                year = params.get('year', [None])[0]
                result = {'monthly_pattern': self.monthly_pattern(cur, year)}
```

- [ ] **Step 2: Smoke-test locally for 2024**

Same pattern as prior task — confirm 12 rows returned and `avg_partners_per_day` values are plausible (tens to low hundreds).

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add monthly_pattern endpoint"
```

---

## Task 13: `GET /api/calendar?type=working_days`

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the working-days endpoint**

```python
    def working_days(self, cur, date_from, date_to):
        cur.execute(
            """
            WITH days AS (
              SELECT generate_series(%s::date, %s::date, '1 day'::interval)::date AS d
            )
            SELECT
              COUNT(*) FILTER (
                WHERE EXTRACT(ISODOW FROM d) <> 7
                  AND d NOT IN (SELECT date FROM holidays WHERE is_official)
                  AND d NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
              ) AS working_days,
              COUNT(*) FILTER (WHERE EXTRACT(ISODOW FROM d) = 7) AS sundays,
              COUNT(*) FILTER (WHERE d IN (SELECT date FROM holidays WHERE is_official)) AS official_holidays,
              COUNT(*) FILTER (WHERE d IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')) AS company_closed
            FROM days
            """,
            (date_from, date_to),
        )
        return dict(cur.fetchone())
```

Wire up:

```python
            elif query_type == 'working_days':
                df = params.get('date_from', [None])[0]
                dt = params.get('date_to', [None])[0]
                if not df or not dt:
                    result = {'error': 'date_from and date_to required'}
                else:
                    result = self.working_days(cur, df, dt)
```

- [ ] **Step 2: Smoke-test**

Run a quick Python check against a known year (e.g. 2024 had ~280 working days per CLAUDE.md stats):

```bash
python -c "
import os, psycopg2, json
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); cur = c.cursor()
cur.execute('''
WITH days AS (SELECT generate_series('2024-01-01'::date, '2024-12-31'::date, '1 day'::interval)::date AS d)
SELECT COUNT(*) FILTER (WHERE EXTRACT(ISODOW FROM d) <> 7 AND d NOT IN (SELECT date FROM holidays WHERE is_official)) FROM days
''')
print('2024 working days (no closures yet):', cur.fetchone())
"
```
Expected: a number around 290 ± 10. Once closures are validated, it'll drop closer to 280.

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add working_days endpoint"
```

---

## Task 14: `GET /api/calendar?type=holiday_effect`

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the holiday-effect endpoint**

```python
    def holiday_effect(self, cur, window):
        window = int(window) if window else 3
        cur.execute(
            f"""
            WITH daily AS (
              SELECT t.date, COUNT(DISTINCT t.cnp) AS partners
              FROM transactions t
              GROUP BY t.date
            ),
            official AS (
              SELECT DISTINCT date, name FROM holidays WHERE is_official
            ),
            offsets AS (
              SELECT generate_series(-{window}, {window})::int AS offset_days
            ),
            pairs AS (
              SELECT o.date AS holiday_date, o.name AS holiday_name,
                     off.offset_days,
                     (o.date + off.offset_days * INTERVAL '1 day')::date AS target_date
              FROM official o CROSS JOIN offsets off
            )
            SELECT p.holiday_name,
                   p.offset_days,
                   ROUND(AVG(d.partners)::numeric, 1) AS avg_partners,
                   COUNT(d.partners) AS sample_size
            FROM pairs p
            LEFT JOIN daily d ON d.date = p.target_date
            GROUP BY p.holiday_name, p.offset_days
            ORDER BY p.holiday_name, p.offset_days
            """
        )
        return [dict(r) for r in cur.fetchall()]
```

Wire up:

```python
            elif query_type == 'holiday_effect':
                win = params.get('window', ['3'])[0]
                result = {'holiday_effect': self.holiday_effect(cur, win)}
```

Note: this is the basic shape. A full seasonal-baseline comparison is left to Phase 2, where we already compute 28-day weekday baselines. For Phase 1 the raw average around each holiday is the useful visible signal.

- [ ] **Step 2: Smoke-test**

```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); cur = c.cursor()
cur.execute(\"\"\"
SELECT h.name, COUNT(*) as samples
FROM (SELECT DISTINCT date, name FROM holidays WHERE is_official) h
JOIN transactions t ON t.date BETWEEN h.date - 3 AND h.date + 3
GROUP BY h.name ORDER BY samples DESC LIMIT 5
\"\"\")
for r in cur.fetchall(): print(r)
"
```
Expected: top-5 holidays by sample size (should be the recurring ones: Craciunul, Anul Nou, Ziua Muncii...).

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add holiday_effect endpoint"
```

---

## Task 15: `GET /api/calendar?type=bridge_days`

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the bridge-days endpoint**

A "bridge day" is a working day with both the day before and day after being closed (Sunday, official holiday, or validated closure).

```python
    def bridge_days(self, cur):
        cur.execute(
            """
            WITH bounds AS (SELECT MIN(date) AS dmin, MAX(date) AS dmax FROM transactions),
            days AS (
              SELECT generate_series(b.dmin, b.dmax, '1 day'::interval)::date AS d FROM bounds b
            ),
            closed AS (
              SELECT d FROM days
              WHERE EXTRACT(ISODOW FROM d) = 7
                 OR d IN (SELECT date FROM holidays WHERE is_official)
                 OR d IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
            ),
            bridges AS (
              SELECT d.d AS bridge_date
              FROM days d
              WHERE EXTRACT(ISODOW FROM d.d) <> 7
                AND d.d NOT IN (SELECT date FROM holidays WHERE is_official)
                AND d.d NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
                AND (d.d - INTERVAL '1 day')::date IN (SELECT d FROM closed)
                AND (d.d + INTERVAL '1 day')::date IN (SELECT d FROM closed)
            )
            SELECT b.bridge_date,
                   COALESCE(COUNT(DISTINCT t.cnp), 0) AS partners,
                   COALESCE(COUNT(t.document_id), 0) AS transactions
            FROM bridges b
            LEFT JOIN transactions t ON t.date = b.bridge_date
            GROUP BY b.bridge_date
            ORDER BY b.bridge_date
            """
        )
        return [dict(r) for r in cur.fetchall()]
```

Wire up:

```python
            elif query_type == 'bridge_days':
                result = {'bridge_days': self.bridge_days(cur)}
```

- [ ] **Step 2: Smoke-test**

Same pattern. Expect a small list (a few bridge days per year).

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add bridge_days endpoint"
```

---

## Task 16: `GET /api/calendar?type=illegal_workdays`

**Files:**
- Modify: `api/calendar.py`

- [ ] **Step 1: Add the audit endpoint**

```python
    def illegal_workdays(self, cur):
        cur.execute(
            """
            SELECT t.date,
                   STRING_AGG(DISTINCT h.name, ', ') AS holiday_names,
                   COUNT(*) AS tx_count,
                   COUNT(DISTINCT t.cnp) AS partners,
                   ROUND(SUM(t.gross_value)::numeric, 2) AS ron
            FROM transactions t
            JOIN holidays h ON h.date = t.date AND h.is_official = true
            GROUP BY t.date
            ORDER BY t.date
            """
        )
        return [dict(r) for r in cur.fetchall()]
```

Wire up:

```python
            elif query_type == 'illegal_workdays':
                result = {'illegal_workdays': self.illegal_workdays(cur)}
```

- [ ] **Step 2: Smoke-test**

Run the raw SQL directly; depending on actual data, this may return zero rows (good, law respected) or a few (worth a look).

- [ ] **Step 3: Commit**

```bash
git add api/calendar.py
git commit -m "add illegal_workdays audit endpoint"
```

---

## Task 17: Frontend — Sezonalitate tab scaffold in `index.html`

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Locate the top nav and tab panels**

Open `index.html` and find the section with the navigation buttons (`Sumar`, `Comparatie`, `Parteneri`, `Deseuri`, `Reguni`, `Predictii`, `Statistice`). Insert a new button **immediately after `Statistice`** so it becomes the last main tab:

```html
<button class="nav-tab" data-tab="sezonalitate">Sezonalitate</button>
```

Then find the `<div class="tab-content">` blocks (one per existing tab). Add a new one immediately after the `statistice` tab content:

```html
<div id="sezonalitate" class="tab-content">
  <div class="section-header">
    <h2>Sezonalitate & Sarbatori</h2>
    <p class="muted">Tiparul calendaristic al traficului — baza fara influenta meteo.</p>
  </div>

  <div id="sez-weekly" class="card">
    <h3>Tipar saptamanal (Luni-Sambata)</h3>
    <div class="metric-toggle" data-target="sez-weekly">
      <button class="active" data-metric="partners">Parteneri</button>
      <button data-metric="transactions">Tranzactii</button>
      <button data-metric="kg">Kg</button>
      <button data-metric="ron">RON</button>
    </div>
    <canvas id="sezWeeklyChart" height="120"></canvas>
  </div>

  <div id="sez-monthly" class="card">
    <h3>Tipar lunar</h3>
    <div class="metric-toggle" data-target="sez-monthly">
      <button class="active" data-metric="avg_partners_per_day">Parteneri/zi</button>
      <button data-metric="avg_transactions_per_day">Tranzactii/zi</button>
      <button data-metric="avg_kg_per_day">Kg/zi</button>
      <button data-metric="avg_ron_per_day">RON/zi</button>
    </div>
    <canvas id="sezMonthlyChart" height="120"></canvas>
  </div>

  <div id="sez-holiday-effect" class="card">
    <h3>Impactul sarbatorilor (±3 zile)</h3>
    <div id="sezHolidayTable" class="table-wrap"></div>
  </div>

  <div id="sez-bridge" class="card">
    <h3>Bridge days (zi lucratoare intre doua zile inchise)</h3>
    <div id="sezBridgeTable" class="table-wrap"></div>
  </div>

  <div id="sez-closure-validation" class="card">
    <h3>Zile fara tranzactii (de validat)</h3>
    <p class="muted">Candidati pentru concedii companie — confirma sau ignora.</p>
    <div id="sezClosureCandidates"></div>
  </div>

  <div id="sez-audit" class="card">
    <h3>Audit: tranzactii pe zile oficial nelucratoare</h3>
    <div id="sezAuditTable" class="table-wrap"></div>
  </div>
</div>
```

- [ ] **Step 2: Hook the new tab into the existing tab-switch handler**

Search for where other tabs are activated (likely a function like `showTab(tabName)` or an event listener on `.nav-tab`). Add a dispatch that triggers `loadSezonalitate()` the first time `sezonalitate` is shown. If the existing pattern uses a dispatch table, add `sezonalitate: loadSezonalitate` to it. If it's a switch statement, add a `case 'sezonalitate': if (!window._sezLoaded) { loadSezonalitate(); window._sezLoaded = true; } break;` branch.

- [ ] **Step 3: Add a placeholder `loadSezonalitate()` at the bottom of the existing `<script>` block**

```javascript
async function loadSezonalitate() {
  // Populated in following tasks.
  console.log('loadSezonalitate called');
}
```

- [ ] **Step 4: Manual verification**

Open the dashboard (deploy or `vercel dev`), click the new "Sezonalitate" tab. Expected:
- Tab button appears in nav between `Statistice` and `Predicii`.
- Clicking it shows the empty sections with section headers.
- Browser console logs `loadSezonalitate called`.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "scaffold Sezonalitate tab structure"
```

---

## Task 18: Frontend — Tipar săptămânal chart

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Implement the weekly chart loader**

Replace the placeholder `loadSezonalitate()` with an initial loader that fetches weekly data. Also add the `renderSezWeekly` helper. Put both at the bottom of the existing `<script>` block.

```javascript
let _sezWeeklyChart = null;
let _sezWeeklyData = null;
let _sezWeeklyMetric = 'partners';

async function loadSezonalitate() {
  await loadSezWeekly();
}

async function loadSezWeekly() {
  const res = await fetch('/api/calendar?type=weekly_pattern');
  const data = await res.json();
  _sezWeeklyData = data.weekly_pattern || [];
  renderSezWeekly();
  bindSezWeeklyToggle();
}

function renderSezWeekly() {
  const rows = _sezWeeklyData;
  if (!rows.length) return;
  const labels = rows.map(r => r.dow_label);
  const field = ({partners: 'avg_partners', transactions: 'avg_transactions', kg: 'avg_kg', ron: 'avg_ron'})[_sezWeeklyMetric];
  const values = rows.map(r => parseFloat(r[field] || 0));
  const ctx = document.getElementById('sezWeeklyChart').getContext('2d');
  if (_sezWeeklyChart) _sezWeeklyChart.destroy();
  _sezWeeklyChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ label: _sezWeeklyMetric, data: values, backgroundColor: '#00d9ff88', borderColor: '#00d9ff', borderWidth: 1 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { color: '#aaa' } }, x: { ticks: { color: '#aaa' } } }
    }
  });
}

function bindSezWeeklyToggle() {
  document.querySelectorAll('[data-target="sez-weekly"] button').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('[data-target="sez-weekly"] button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _sezWeeklyMetric = btn.dataset.metric;
      renderSezWeekly();
    };
  });
}
```

- [ ] **Step 2: Manual verification**

Reload dashboard → Sezonalitate tab. Expected:
- Bar chart shows six bars Luni-Sâmbătă with plausible heights.
- Clicking a different metric button re-renders (e.g. "RON" shows larger values).
- No console errors.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "implement Tipar saptamanal chart"
```

---

## Task 19: Frontend — Tipar lunar chart

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add monthly chart loader + renderer**

Append below the weekly section:

```javascript
let _sezMonthlyChart = null;
let _sezMonthlyData = null;
let _sezMonthlyMetric = 'avg_partners_per_day';

async function loadSezMonthly() {
  const res = await fetch('/api/calendar?type=monthly_pattern');
  const data = await res.json();
  _sezMonthlyData = data.monthly_pattern || [];
  renderSezMonthly();
  bindSezMonthlyToggle();
}

function renderSezMonthly() {
  const rows = _sezMonthlyData;
  if (!rows.length) return;
  const monthNames = ['Ian','Feb','Mar','Apr','Mai','Iun','Iul','Aug','Sep','Oct','Nov','Dec'];
  const labels = rows.map(r => monthNames[r.month - 1]);
  const values = rows.map(r => parseFloat(r[_sezMonthlyMetric] || 0));
  const ctx = document.getElementById('sezMonthlyChart').getContext('2d');
  if (_sezMonthlyChart) _sezMonthlyChart.destroy();
  _sezMonthlyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{ label: _sezMonthlyMetric, data: values, borderColor: '#00ff88', backgroundColor: '#00ff8833', tension: 0.3, fill: true }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { ticks: { color: '#aaa' } }, x: { ticks: { color: '#aaa' } } }
    }
  });
}

function bindSezMonthlyToggle() {
  document.querySelectorAll('[data-target="sez-monthly"] button').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('[data-target="sez-monthly"] button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _sezMonthlyMetric = btn.dataset.metric;
      renderSezMonthly();
    };
  });
}
```

Update `loadSezonalitate()`:

```javascript
async function loadSezonalitate() {
  await Promise.all([loadSezWeekly(), loadSezMonthly()]);
}
```

- [ ] **Step 2: Manual verification**

Tab still works. Monthly chart shows 12 points, metric toggle works, values are plausible (hundreds of partners/day range depending on metric).

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "implement Tipar lunar chart"
```

---

## Task 20: Frontend — Impactul sărbătorilor table

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add holiday-effect loader + table renderer**

Append:

```javascript
async function loadSezHolidayEffect() {
  const res = await fetch('/api/calendar?type=holiday_effect&window=3');
  const data = await res.json();
  const rows = data.holiday_effect || [];
  // Group by holiday name into { name: { -3: avg, -2: avg, ..., +3: avg } }
  const grouped = {};
  rows.forEach(r => {
    if (!grouped[r.holiday_name]) grouped[r.holiday_name] = {};
    grouped[r.holiday_name][r.offset_days] = { avg: r.avg_partners, n: r.sample_size };
  });
  const offsets = [-3, -2, -1, 0, 1, 2, 3];
  let html = '<table class="data-table"><thead><tr><th>Sarbatoare</th>' +
             offsets.map(o => `<th>${o >= 0 ? '+' : ''}${o}</th>`).join('') +
             '</tr></thead><tbody>';
  Object.keys(grouped).sort().forEach(name => {
    html += `<tr><td>${name}</td>` +
            offsets.map(o => {
              const cell = grouped[name][o];
              if (!cell || cell.avg == null) return '<td class="muted">–</td>';
              return `<td>${cell.avg}<br><span class="muted" style="font-size:.75em">n=${cell.n}</span></td>`;
            }).join('') + '</tr>';
  });
  html += '</tbody></table>';
  document.getElementById('sezHolidayTable').innerHTML = html;
}
```

Add to `loadSezonalitate`:

```javascript
async function loadSezonalitate() {
  await Promise.all([loadSezWeekly(), loadSezMonthly(), loadSezHolidayEffect()]);
}
```

- [ ] **Step 2: Manual verification**

Holiday table appears with rows per recurring holiday and columns -3..+3. Day 0 of each holiday should have zero or very low avg_partners (since it's a closed day), ±1 should be elevated.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "implement Impactul sarbatorilor table"
```

---

## Task 21: Frontend — Bridge days table

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add bridge-days loader + table**

Append:

```javascript
async function loadSezBridges() {
  const res = await fetch('/api/calendar?type=bridge_days');
  const data = await res.json();
  const rows = data.bridge_days || [];
  if (!rows.length) {
    document.getElementById('sezBridgeTable').innerHTML = '<p class="muted">Niciun bridge day in perioada.</p>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>Data</th><th>Zi</th><th>Parteneri</th><th>Tranzactii</th></tr></thead><tbody>';
  const dayNames = ['','Luni','Marti','Miercuri','Joi','Vineri','Sambata','Duminica'];
  rows.forEach(r => {
    const d = new Date(r.bridge_date);
    const dow = dayNames[((d.getDay() + 6) % 7) + 1];
    html += `<tr><td>${r.bridge_date}</td><td>${dow}</td><td>${r.partners}</td><td>${r.transactions}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('sezBridgeTable').innerHTML = html;
}
```

Add to `loadSezonalitate`:

```javascript
async function loadSezonalitate() {
  await Promise.all([loadSezWeekly(), loadSezMonthly(), loadSezHolidayEffect(), loadSezBridges()]);
}
```

- [ ] **Step 2: Manual verification**

Section populates with a handful of dates (if any) or a "niciun bridge day" muted message.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "implement Bridge days table"
```

---

## Task 22: Frontend — Closure validation UI

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add candidate loader + UI handlers**

Append:

```javascript
async function loadSezClosureCandidates() {
  const res = await fetch('/api/calendar?type=closure_candidates');
  const data = await res.json();
  const runs = data.runs || [];
  const host = document.getElementById('sezClosureCandidates');
  if (!runs.length) {
    host.innerHTML = '<p class="muted">Niciun candidat in asteptare. ✓</p>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>De la</th><th>Pana la</th><th>Zile lucratoare</th><th>Actiuni</th></tr></thead><tbody>';
  runs.forEach((r, i) => {
    html += `
      <tr data-run="${i}">
        <td><input type="date" value="${r.date_from}" class="closure-from"></td>
        <td><input type="date" value="${r.date_to}" class="closure-to"></td>
        <td>${r.working_days}</td>
        <td>
          <input type="text" placeholder="Motiv (optional)" class="closure-reason" style="width:200px">
          <button class="btn-confirm" data-run="${i}">Confirma</button>
          <button class="btn-ignore" data-run="${i}">Ignora</button>
        </td>
      </tr>`;
  });
  html += '</tbody></table>';
  host.innerHTML = html;

  host.querySelectorAll('.btn-confirm').forEach(b => b.onclick = async (e) => {
    const row = e.target.closest('tr');
    await postClosure('confirm_closure', {
      date_from: row.querySelector('.closure-from').value,
      date_to: row.querySelector('.closure-to').value,
      reason: row.querySelector('.closure-reason').value || 'Inchidere companie'
    });
    loadSezClosureCandidates();
  });
  host.querySelectorAll('.btn-ignore').forEach(b => b.onclick = async (e) => {
    const row = e.target.closest('tr');
    await postClosure('ignore_closure', {
      date_from: row.querySelector('.closure-from').value,
      date_to: row.querySelector('.closure-to').value
    });
    loadSezClosureCandidates();
  });
}

async function postClosure(action, body) {
  const res = await fetch(`/api/calendar?action=${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await res.json();
  if (data.error) alert('Eroare: ' + data.error);
  return data;
}
```

Add to `loadSezonalitate`:

```javascript
async function loadSezonalitate() {
  await Promise.all([
    loadSezWeekly(), loadSezMonthly(), loadSezHolidayEffect(),
    loadSezBridges(), loadSezClosureCandidates()
  ]);
}
```

- [ ] **Step 2: Manual verification**

A list of candidate closure runs appears with editable date inputs + reason field + two buttons. Click "Confirma" on one known closure (e.g. a range in August where company was closed) with a reason like "Concediu de vara 2024" → row disappears from list (re-fetched). Confirm in DB:

```bash
python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); cur = c.cursor()
cur.execute(\"SELECT * FROM company_closures ORDER BY date\")
for r in cur.fetchall(): print(r)
"
```

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "implement closure validation UI"
```

---

## Task 23: Frontend — Illegal workdays audit table

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add loader + table**

Append:

```javascript
async function loadSezAudit() {
  const res = await fetch('/api/calendar?type=illegal_workdays');
  const data = await res.json();
  const rows = data.illegal_workdays || [];
  if (!rows.length) {
    document.getElementById('sezAuditTable').innerHTML = '<p style="color:#00ff88">Nicio tranzactie pe zile oficial nelucratoare. ✓</p>';
    return;
  }
  let html = '<table class="data-table"><thead><tr><th>Data</th><th>Sarbatoare</th><th>Parteneri</th><th>Tranzactii</th><th>RON</th></tr></thead><tbody>';
  rows.forEach(r => {
    html += `<tr><td>${r.date}</td><td>${r.holiday_names}</td><td>${r.partners}</td><td>${r.tx_count}</td><td>${r.ron}</td></tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('sezAuditTable').innerHTML = html;
}
```

Extend `loadSezonalitate`:

```javascript
async function loadSezonalitate() {
  await Promise.all([
    loadSezWeekly(), loadSezMonthly(), loadSezHolidayEffect(),
    loadSezBridges(), loadSezClosureCandidates(), loadSezAudit()
  ]);
}
```

- [ ] **Step 2: Manual verification**

Either shows a green "nicio tranzactie" confirmation or a table listing offending dates. Both are valid outcomes — user decides if action is needed.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "implement illegal workdays audit table"
```

---

## Task 24: Update `CLAUDE.md` API docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Append new API section**

Find the API endpoints section (after `/api/waste`) and add:

```markdown
### `/api/calendar`
| Parameter | Description |
|-----------|-------------|
| `type=holidays&year=YYYY` | Sarbatori pentru un an (national + catolic + ortodox) |
| `type=closures` | Lista inchiderilor companiei validate |
| `type=closure_candidates` | Candidati auto-detectati pentru validare |
| `type=working_days&date_from=X&date_to=Y` | Numar zile lucratoare in interval |
| `type=weekly_pattern&date_from=X&date_to=Y` | Tipar H-Sb (medii pe zi lucratoare) |
| `type=monthly_pattern&year=YYYY` | Tipar lunar (normalizat pe zi lucratoare) |
| `type=holiday_effect&window=N` | Impactul sarbatorilor ±N zile |
| `type=bridge_days` | Bridge days detectate |
| `type=illegal_workdays` | Audit: tranzactii pe zile oficial nelucratoare |
| POST `?action=confirm_closure` body `{date_from,date_to,reason}` | Confirma interval ca inchidere |
| POST `?action=ignore_closure` body `{date_from,date_to}` | Marcheaza ca non-inchidere |
```

Also add a `Working day definition` block to the "Important Notes" section:

```markdown
### Working Day Definition
Working day = Mon-Sat AND NOT in `holidays` (is_official=true) AND NOT in `company_closures` (reason ≠ '__ignored__').
Sunday is closed by default (no opening hours).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "document /api/calendar endpoints and working day rule"
```

---

## Task 25: Final end-to-end verification

**Files:** none (verification only)

- [ ] **Step 1: Push to Vercel and wait for deploy**

```bash
git push
```

Wait ~1 minute for Vercel auto-deploy.

- [ ] **Step 2: Live smoke-test each endpoint**

Hit each with curl (replace the URL with the actual Vercel URL):

```bash
for q in 'type=ping' 'type=holidays&year=2024' 'type=closures' 'type=closure_candidates' \
         'type=working_days&date_from=2024-01-01&date_to=2024-12-31' \
         'type=weekly_pattern' 'type=monthly_pattern&year=2024' \
         'type=holiday_effect&window=3' 'type=bridge_days' 'type=illegal_workdays'; do
  echo "=== $q ==="
  curl -s "https://<your-project>.vercel.app/api/calendar?$q" | head -c 400
  echo
done
```

Expected: each returns valid JSON, no `error` key.

- [ ] **Step 3: Live UI walkthrough**

In the deployed dashboard:
- Click Sezonalitate tab → all six cards load without console errors.
- Weekly chart: toggle between Parteneri / Tranzacții / Kg / RON → each re-renders.
- Monthly chart: toggle metrics → each renders.
- Holiday table: contains ≥6 well-known holidays.
- Bridge days: either a few rows or the empty-state message.
- Closure candidates: list populated; validate one known summer vacation range → disappears on refresh.
- Audit: either green check or a table — both valid.

- [ ] **Step 4: Mark Phase 1 complete**

No code change. Simply confirm with the user that Phase 1 is working in production and ready to proceed to Phase 2 planning.

---

## Rollback Plan (if needed)

If Phase 1 causes problems in production:

1. `git revert <commit-range>` to drop the index.html + api/calendar.py changes (visual regression prevented).
2. Tables `holidays` and `company_closures` can stay — they don't affect existing queries.
3. No data migration needed for rollback.

## What's Next After Phase 1

Once Phase 1 is live and the user has validated the closure list + confirmed the weekly/monthly patterns look right, the next plan covers Phase 2 (Meteo & Trafic) — a separate plan in `docs/superpowers/plans/`. Phase 3 (weather badges in partner modal) is an even smaller follow-up.
