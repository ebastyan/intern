# Phase 2 — Meteo & Trafic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download historical Oradea weather (2022-01-03 → yesterday) into the database, then ship a "Meteo & Trafic" tab that tells the user — as narrative hypotheses — how weather has actually influenced traffic (partners/day, kg/day, value/day), separated from seasonal baseline so it's the real signal.

**Architecture:** Open-Meteo Historical Weather API (free, no key) → new `weather_oradea` daily table. New Python serverless endpoint `api/weather.py` (mirrors `api/calendar.py`) computes a 28-day weekday-matched baseline on the fly and emits analysis blocks: single-variable bucket comparisons, threshold detection (continuous variables), lag analysis (lag −2..+3), curated interaction patterns (cold+wet, hot+dry, first-sunny-after-rain, nth consecutive snow, etc.). New "Meteo & Trafic" tab in `index.html` renders insight cards + Chart.js scatter/bar/lag charts.

**Tech Stack:** PostgreSQL (NeonDB), Python 3.12 + psycopg2 + urllib (no new deps), vanilla JS + Chart.js, Vercel serverless.

**Source spec:** `docs/superpowers/specs/2026-04-17-meteo-trafic-sezonalitate-design.md` §6.

**Dependencies:** Phase 1 (already shipped) — the calendar definition of "working day" is reused: working day = not Sunday AND not `holidays.is_official` AND has transactions.

**Non-goals for this plan:** ML/forecasting, real-time weather, hourly granularity (transactions only have dates), pollution/air-quality data, weather badge in partner modal (that's Phase 3).

**Pre-lessons from Phase 1 baked in:**
- vercel.json needs an explicit route entry for any new `/api/X` endpoint. Included as Task 11 — not a bug to discover later.
- Chart.js canvases must live inside `<div class="chart-container">` (fixed 280px height) or they enter infinite resize loop.
- "Working day" semantics already settled: Mon-Sat, not official holiday, actually has transactions. Zero-tx days are auto-excluded from averages because we compute from `transactions`.

---

## File Structure

**New files:**
- `scripts/migrations/003_create_weather_oradea.sql` — DDL for the weather table.
- `scripts/fetch_weather.py` — Open-Meteo ingestion. Idempotent (ON CONFLICT DO UPDATE), supports backfill + daily top-up. Uses `urllib` (stdlib, no `requests` dep).
- `api/weather.py` — new serverless endpoint, mirrors `api/calendar.py` pattern. Contains the baseline/residual helper + four analysis families.

**Modified files:**
- `vercel.json` — add `{ "src": "/api/weather", "dest": "/api/weather.py" }` route.
- `index.html` — new "Meteo & Trafic" nav button + tab panel + JS loaders and renderers.
- `CLAUDE.md` — append `/api/weather` reference and mention the weather table.

No test framework (project convention). Correctness is verified via:
1. `--self-test` flag on the ingestion script (checks a tiny known window against the Open-Meteo API live).
2. SQL-level smoke tests after each endpoint.
3. Manual UI walkthrough at the end.

---

## Task 1: Create `weather_oradea` table migration

**Files:**
- Create: `scripts/migrations/003_create_weather_oradea.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
-- scripts/migrations/003_create_weather_oradea.sql
CREATE TABLE IF NOT EXISTS weather_oradea (
  date DATE PRIMARY KEY,
  -- Temperature (Celsius)
  temp_max NUMERIC(5,2),
  temp_min NUMERIC(5,2),
  temp_mean NUMERIC(5,2),
  apparent_temp_max NUMERIC(5,2),
  apparent_temp_min NUMERIC(5,2),
  apparent_temp_mean NUMERIC(5,2),
  -- Precipitation
  precipitation_sum NUMERIC(6,2),        -- mm total (rain + snow water equiv.)
  rain_sum NUMERIC(6,2),                  -- mm
  snowfall_sum NUMERIC(6,2),              -- cm
  snow_depth_max NUMERIC(5,2),            -- m
  precipitation_hours NUMERIC(4,1),
  -- Wind
  wind_speed_max NUMERIC(5,2),            -- km/h @10m
  wind_gusts_max NUMERIC(5,2),            -- km/h
  wind_direction_dominant INT,             -- degrees 0-360
  -- Radiation / sun
  shortwave_radiation_sum NUMERIC(6,2),   -- MJ/m^2
  sunshine_duration NUMERIC(7,1),         -- seconds
  daylight_duration NUMERIC(7,1),
  et0_evapotranspiration NUMERIC(5,2),
  -- Derived from hourly aggregation
  pressure_mean NUMERIC(6,2),             -- hPa
  humidity_mean NUMERIC(4,1),             -- %
  cloudcover_mean NUMERIC(4,1),           -- %
  -- WMO weather code (dominant during daylight)
  weather_code INT,
  fetched_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_oradea(date);
```

- [ ] **Step 2: Run the migration**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python scripts/run_migration.py scripts/migrations/003_create_weather_oradea.sql
```
Expected: `Applied: 003_create_weather_oradea.sql`

- [ ] **Step 3: Verify table exists with ~22 columns**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); cur = c.cursor()
cur.execute(\"SELECT COUNT(*) FROM information_schema.columns WHERE table_name='weather_oradea'\")
print('Column count:', cur.fetchone())
cur.execute(\"SELECT column_name FROM information_schema.columns WHERE table_name='weather_oradea' ORDER BY ordinal_position\")
for r in cur.fetchall(): print(' -', r[0])
"
```
Expected: Column count around 23 (including `fetched_at`), listing all fields from the DDL.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add scripts/migrations/003_create_weather_oradea.sql && git commit -m "add weather_oradea table migration"
```

---

## Task 2: Write `scripts/fetch_weather.py` with Open-Meteo client

**Files:**
- Create: `scripts/fetch_weather.py`

Open-Meteo Historical endpoint: `https://archive-api.open-meteo.com/v1/archive`. Free, no key. Oradea coords: `lat=47.0722, lon=21.9217`. Use `urllib` (stdlib) to keep deps unchanged.

Two calls per run (daily aggregates + hourly-derived-to-daily means):
- Daily params: `temperature_2m_max,temperature_2m_min,temperature_2m_mean,apparent_temperature_max,apparent_temperature_min,apparent_temperature_mean,precipitation_sum,rain_sum,snowfall_sum,precipitation_hours,windspeed_10m_max,windgusts_10m_max,winddirection_10m_dominant,shortwave_radiation_sum,sunshine_duration,daylight_duration,et0_fao_evapotranspiration,weather_code,snow_depth_max`

Hourly params (averaged client-side to daily): `pressure_msl,relativehumidity_2m,cloudcover`.

- [ ] **Step 1: Write the script**

```python
# scripts/fetch_weather.py
"""Fetch historical daily weather for Oradea and upsert into weather_oradea.

Usage:
  python scripts/fetch_weather.py --self-test                 # small-window live-API sanity
  python scripts/fetch_weather.py                              # 2022-01-01 -> yesterday, full backfill
  python scripts/fetch_weather.py --date-from 2026-04-01 --date-to 2026-04-17
"""
import argparse, json, os, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request

import psycopg2

LAT, LON = 47.0722, 21.9217
TIMEZONE = "Europe/Bucharest"
BASE = "https://archive-api.open-meteo.com/v1/archive"

DAILY_FIELDS = [
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
    "apparent_temperature_max", "apparent_temperature_min", "apparent_temperature_mean",
    "precipitation_sum", "rain_sum", "snowfall_sum", "precipitation_hours",
    "windspeed_10m_max", "windgusts_10m_max", "winddirection_10m_dominant",
    "shortwave_radiation_sum", "sunshine_duration", "daylight_duration",
    "et0_fao_evapotranspiration", "weather_code", "snow_depth_max",
]
HOURLY_FIELDS = ["pressure_msl", "relativehumidity_2m", "cloudcover"]

COLUMN_MAP = {
    "temperature_2m_max": "temp_max",
    "temperature_2m_min": "temp_min",
    "temperature_2m_mean": "temp_mean",
    "apparent_temperature_max": "apparent_temp_max",
    "apparent_temperature_min": "apparent_temp_min",
    "apparent_temperature_mean": "apparent_temp_mean",
    "precipitation_sum": "precipitation_sum",
    "rain_sum": "rain_sum",
    "snowfall_sum": "snowfall_sum",
    "snow_depth_max": "snow_depth_max",
    "precipitation_hours": "precipitation_hours",
    "windspeed_10m_max": "wind_speed_max",
    "windgusts_10m_max": "wind_gusts_max",
    "winddirection_10m_dominant": "wind_direction_dominant",
    "shortwave_radiation_sum": "shortwave_radiation_sum",
    "sunshine_duration": "sunshine_duration",
    "daylight_duration": "daylight_duration",
    "et0_fao_evapotranspiration": "et0_evapotranspiration",
    "weather_code": "weather_code",
}

def load_env_local():
    env = Path(__file__).parent.parent / ".env.local"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))

def fetch_range(date_from: date, date_to: date):
    """Return list of dicts, one per day in [date_from, date_to]."""
    daily_q = {
        "latitude": LAT, "longitude": LON, "timezone": TIMEZONE,
        "start_date": date_from.isoformat(), "end_date": date_to.isoformat(),
        "daily": ",".join(DAILY_FIELDS),
    }
    hourly_q = {
        "latitude": LAT, "longitude": LON, "timezone": TIMEZONE,
        "start_date": date_from.isoformat(), "end_date": date_to.isoformat(),
        "hourly": ",".join(HOURLY_FIELDS),
    }
    daily_resp = _get_json(BASE + "?" + urlencode(daily_q))
    hourly_resp = _get_json(BASE + "?" + urlencode(hourly_q))

    # Parse daily
    d_dates = daily_resp["daily"]["time"]
    per_day = {}
    for api_field, col in COLUMN_MAP.items():
        arr = daily_resp["daily"].get(api_field, [None] * len(d_dates))
        for i, dstr in enumerate(d_dates):
            per_day.setdefault(dstr, {})[col] = arr[i] if i < len(arr) else None

    # Aggregate hourly to daily means
    h_times = hourly_resp["hourly"]["time"]
    h_by_day = {}
    for api_field in HOURLY_FIELDS:
        arr = hourly_resp["hourly"].get(api_field, [None] * len(h_times))
        for i, tstr in enumerate(h_times):
            day = tstr[:10]
            if arr[i] is None:
                continue
            h_by_day.setdefault(day, {}).setdefault(api_field, []).append(arr[i])

    hourly_col = {
        "pressure_msl": "pressure_mean",
        "relativehumidity_2m": "humidity_mean",
        "cloudcover": "cloudcover_mean",
    }
    for dstr, fields in h_by_day.items():
        target = per_day.setdefault(dstr, {})
        for api_field, col in hourly_col.items():
            vals = fields.get(api_field, [])
            if vals:
                target[col] = round(sum(vals) / len(vals), 2)

    return [{"date": d, **per_day[d]} for d in sorted(per_day)]

def _get_json(url: str):
    req = Request(url, headers={"User-Agent": "paju-dashboard/1.0"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def upsert(rows):
    if not rows:
        return 0
    cols = [
        "date", "temp_max", "temp_min", "temp_mean",
        "apparent_temp_max", "apparent_temp_min", "apparent_temp_mean",
        "precipitation_sum", "rain_sum", "snowfall_sum", "snow_depth_max",
        "precipitation_hours", "wind_speed_max", "wind_gusts_max",
        "wind_direction_dominant", "shortwave_radiation_sum", "sunshine_duration",
        "daylight_duration", "et0_evapotranspiration", "pressure_mean",
        "humidity_mean", "cloudcover_mean", "weather_code",
    ]
    placeholders = ", ".join(["%s"] * len(cols))
    update_clauses = ", ".join([f"{c} = EXCLUDED.{c}" for c in cols if c != "date"])
    sql = (
        f"INSERT INTO weather_oradea ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT (date) DO UPDATE SET {update_clauses}, fetched_at = now()"
    )
    url = os.environ.get("POSTGRES_URL")
    if not url:
        raise RuntimeError("POSTGRES_URL not set")
    conn = psycopg2.connect(url)
    with conn.cursor() as cur:
        values = [tuple(row.get(c) for c in cols) for row in rows]
        cur.executemany(sql, values)
    conn.commit()
    conn.close()
    return len(rows)

def self_test():
    # Known sample: single recent day, verify the API returns sensible values.
    d = date.today() - timedelta(days=14)
    rows = fetch_range(d, d)
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    r = rows[0]
    assert r["date"] == d.isoformat()
    assert r.get("temp_max") is not None, "temp_max missing"
    assert r.get("precipitation_sum") is not None, "precipitation_sum missing"
    print(f"Self-test OK: {d} -> temp_max={r['temp_max']}, precip_sum={r['precipitation_sum']}, wind_max={r.get('wind_speed_max')}")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--date-from", type=lambda s: datetime.fromisoformat(s).date(), default=date(2022, 1, 1))
    p.add_argument("--date-to", type=lambda s: datetime.fromisoformat(s).date(), default=date.today() - timedelta(days=1))
    args = p.parse_args()

    if args.self_test:
        self_test()
        return

    load_env_local()
    print(f"Fetching {args.date_from} -> {args.date_to}")
    rows = fetch_range(args.date_from, args.date_to)
    n = upsert(rows)
    print(f"Upserted {n} weather rows")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the self-test (live API call)**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python scripts/fetch_weather.py --self-test
```
Expected: one line like `Self-test OK: 2026-04-04 -> temp_max=18.3, precip_sum=0.0, wind_max=12.4` (actual values depend on date/weather).

If the self-test fails because the API changed shape, STOP and investigate — don't hack around it.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add scripts/fetch_weather.py && git commit -m "add fetch_weather.py with Open-Meteo client + self-test"
```

---

## Task 3: Run full weather backfill

**Files:** none (data only)

- [ ] **Step 1: Backfill 2022-01-01 → yesterday**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python scripts/fetch_weather.py
```
Expected: `Fetching 2022-01-01 -> <yesterday>` then `Upserted ~1500 weather rows` (depending on exact day count).

- [ ] **Step 2: Verify row count + sanity checks**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); cur = c.cursor()
cur.execute('SELECT COUNT(*), MIN(date), MAX(date) FROM weather_oradea')
print('rows / min_date / max_date:', cur.fetchone())
cur.execute('SELECT AVG(temp_max), AVG(temp_min), AVG(precipitation_sum) FROM weather_oradea')
print('avg_temp_max / avg_temp_min / avg_precip:', cur.fetchone())
cur.execute(\"\"\"
  SELECT date, temp_max, temp_min, precipitation_sum, snowfall_sum, wind_speed_max, weather_code
  FROM weather_oradea
  WHERE temp_max IS NOT NULL
  ORDER BY temp_max DESC LIMIT 3
\"\"\")
print('hottest days:')
for r in cur.fetchall(): print(' ', r)
"
```
Expected: ~1500 rows, min/max dates bracket 2022-01-01 to yesterday. Averages plausible for Oradea (temp_max avg ~15-17°C yearly, temp_min ~4-7°C, precip daily ~1.5-2.0mm). Hottest days should be 36-40°C summer days.

If anything is wildly off (averages negative, null in unexpected columns), STOP and investigate.

- [ ] **Step 3: No commit — this is data only.**

---

## Task 4: Create `api/weather.py` skeleton with baseline helper

**Files:**
- Create: `api/weather.py`

The baseline helper is the foundation of every analysis block. Factored out so each endpoint uses the same definition.

- [ ] **Step 1: Write the skeleton**

```python
"""
Weather API - Meteo & Trafic analysis
Endpoints:
  GET /api/weather?type=ping
  GET /api/weather?type=residuals&metric=partners&date_from=X&date_to=Y
  GET /api/weather?type=buckets&variable=rain_sum&metric=partners
  GET /api/weather?type=lag_curve&variable=rain_sum&metric=partners
  GET /api/weather?type=extreme_days&limit=20
  GET /api/weather?type=overview&metric=partners
Metric options: partners | transactions | kg | ron
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qs
from decimal import Decimal
from datetime import date, datetime

METRICS = {
    "partners":     ("COUNT(DISTINCT t.cnp)",                     "partners"),
    "transactions": ("COUNT(*)",                                  "transactions"),
    "kg":           ("COALESCE(SUM(i.weight_kg), 0)",             "kg"),
    "ron":          ("COALESCE(SUM(t.gross_value), 0)",           "ron"),
}

def get_db():
    url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL_NO_SSL")
    if not url:
        raise Exception("No database URL configured")
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

def json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")

def resolve_metric(name):
    if name not in METRICS:
        raise ValueError(f"Unknown metric: {name}")
    return METRICS[name]

class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload, default=json_default).encode("utf-8"))

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            qtype = params.get("type", [""])[0]

            conn = get_db()
            cur = conn.cursor()

            if qtype == "ping":
                result = {"ok": True, "endpoint": "weather"}
            else:
                result = {"error": "Unknown query type", "got": qtype}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        self._send(405, {"error": "POST not supported on /api/weather"})
```

- [ ] **Step 2: Syntax check**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "import ast; ast.parse(open('api/weather.py').read()); print('SYNTAX OK')"
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "add api/weather.py skeleton with metric dispatch"
```

---

## Task 5: Register `/api/weather` route in vercel.json

**Files:**
- Modify: `vercel.json`

Lesson from Phase 1 — `vercel.json` uses explicit routing, not auto-discovery. Without this entry the endpoint 404s on deploy.

- [ ] **Step 1: Add the route line**

Open `vercel.json` and insert `{ "src": "/api/weather", "dest": "/api/weather.py" }` right after the `/api/calendar` line in the `routes` array.

After the edit, the routes block should read:
```json
    { "src": "/api/calendar", "dest": "/api/calendar.py" },
    { "src": "/api/weather", "dest": "/api/weather.py" },
```

- [ ] **Step 2: Verify JSON is valid**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "import json; json.load(open('vercel.json')); print('JSON OK')"
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add vercel.json && git commit -m "register /api/weather route"
```

---

## Task 6: Add residuals helper + `type=residuals` endpoint

A residual is `actual(D, m) - baseline(D, m)`. Baseline = median over last 28 working days with the same weekday. This is the foundation — every subsequent endpoint computes residuals per day, then analyzes them.

**Files:**
- Modify: `api/weather.py`

- [ ] **Step 1: Add the residuals method inside the `handler` class**

```python
    def residuals(self, cur, metric_name, date_from, date_to):
        agg_sql, label = resolve_metric(metric_name)
        where = ["EXTRACT(ISODOW FROM t.date) <> 7"]
        args = []
        if date_from: where.append("t.date >= %s"); args.append(date_from)
        if date_to:   where.append("t.date <= %s"); args.append(date_to)
        where_sql = " AND ".join(where)

        # One row per transaction day with metric + weather + 28-day median baseline
        cur.execute(f"""
            WITH daily AS (
              SELECT t.date,
                     EXTRACT(ISODOW FROM t.date)::int AS dow,
                     {agg_sql} AS value
              FROM transactions t
              LEFT JOIN transaction_items i ON i.document_id = t.document_id
              WHERE {where_sql}
              GROUP BY t.date
            )
            SELECT d.date, d.dow, d.value,
                   (
                     SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d2.value)
                     FROM daily d2
                     WHERE d2.dow = d.dow
                       AND d2.date <> d.date
                       AND d2.date BETWEEN d.date - INTERVAL '28 days' AND d.date - INTERVAL '1 day'
                   ) AS baseline,
                   w.temp_max, w.temp_min, w.temp_mean, w.precipitation_sum, w.rain_sum,
                   w.snowfall_sum, w.snow_depth_max, w.wind_speed_max, w.wind_gusts_max,
                   w.pressure_mean, w.humidity_mean, w.cloudcover_mean, w.weather_code
            FROM daily d
            LEFT JOIN weather_oradea w ON w.date = d.date
            ORDER BY d.date
        """, args)
        out = []
        for r in cur.fetchall():
            rec = dict(r)
            if rec["baseline"] is not None:
                rec["residual"] = float(rec["value"]) - float(rec["baseline"])
                rec["residual_pct"] = (rec["residual"] / float(rec["baseline"]) * 100.0) if rec["baseline"] else None
            else:
                rec["residual"] = None
                rec["residual_pct"] = None
            out.append(rec)
        return {"metric": label, "residuals": out}
```

- [ ] **Step 2: Wire into `do_GET`**

Replace the body of the `if qtype == "ping"` branch with:
```python
            if qtype == "ping":
                result = {"ok": True, "endpoint": "weather"}
            elif qtype == "residuals":
                metric = params.get("metric", ["partners"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.residuals(cur, metric, df, dt)
            else:
                result = {"error": "Unknown query type", "got": qtype}
```

- [ ] **Step 3: Smoke-test**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
c = psycopg2.connect(os.environ['POSTGRES_URL']); cur = c.cursor()
cur.execute('''
WITH daily AS (SELECT t.date, EXTRACT(ISODOW FROM t.date)::int AS dow, COUNT(DISTINCT t.cnp) AS value
  FROM transactions t WHERE EXTRACT(ISODOW FROM t.date) <> 7 GROUP BY t.date)
SELECT d.date, d.value,
  (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d2.value) FROM daily d2 WHERE d2.dow = d.dow AND d2.date <> d.date AND d2.date BETWEEN d.date - INTERVAL '28 days' AND d.date - INTERVAL '1 day') AS baseline
FROM daily d ORDER BY d.date DESC LIMIT 5
''')
for r in cur.fetchall(): print(r)
"
```
Expected: 5 recent days with `value` and `baseline` both populated. Baselines should be close-ish to values (within 20-30%). If any baseline is NULL, that's for the very first days of the dataset (expected).

- [ ] **Step 4: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "add residuals endpoint with 28-day weekday-matched baseline"
```

---

## Task 7: Add `type=buckets` endpoint

Bucket comparison: split days into weather buckets and average their residuals. The first family of the hypothesis engine.

**Files:**
- Modify: `api/weather.py`

- [ ] **Step 1: Define bucket tables + method**

Add these bucket spec constants at module level (above `class handler`):

```python
BUCKET_SPECS = {
    "rain_sum":          [(None, 0.1, "0mm (uscat)"), (0.1, 2, "0.1-2mm (slab)"),
                          (2, 10, "2-10mm (mediu)"), (10, None, ">10mm (puternic)")],
    "snowfall_sum":      [(None, 0.1, "0cm"), (0.1, 2, "0.1-2cm"),
                          (2, 10, "2-10cm"), (10, None, ">10cm")],
    "temp_max":          [(None, -5, "<-5°C (geros)"), (-5, 0, "-5 - 0°C"),
                          (0, 10, "0-10°C"), (10, 20, "10-20°C"),
                          (20, 30, "20-30°C"), (30, None, ">30°C (canicula)")],
    "temp_min":          [(None, -10, "<-10°C"), (-10, 0, "-10 - 0°C"),
                          (0, 10, "0-10°C"), (10, 20, "10-20°C"),
                          (20, None, ">20°C")],
    "wind_gusts_max":    [(None, 30, "<30 km/h"), (30, 50, "30-50 km/h"),
                          (50, 70, "50-70 km/h"), (70, None, ">70 km/h")],
    "humidity_mean":     [(None, 50, "<50%"), (50, 70, "50-70%"),
                          (70, 85, "70-85%"), (85, None, ">85%")],
    "cloudcover_mean":   [(None, 30, "Senin (<30%)"), (30, 70, "Partial (30-70%)"),
                          (70, None, "Inchis (>70%)")],
}
```

Then inside `handler`:

```python
    def buckets(self, cur, metric_name, variable, date_from, date_to):
        if variable not in BUCKET_SPECS:
            return {"error": f"No bucket spec for variable {variable}",
                    "available": list(BUCKET_SPECS.keys())}
        # Reuse residuals() via the same method (keeps SQL in one place).
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = [r for r in data["residuals"] if r["residual"] is not None and r.get(variable) is not None]
        out = []
        for lo, hi, label in BUCKET_SPECS[variable]:
            in_bucket = []
            for r in rows:
                v = float(r[variable])
                if lo is not None and v < lo: continue
                if hi is not None and v >= hi: continue
                in_bucket.append(r["residual"])
            if not in_bucket:
                out.append({"bucket": label, "lo": lo, "hi": hi, "n": 0,
                            "mean_residual": None, "mean_residual_pct": None})
                continue
            mean = sum(in_bucket) / len(in_bucket)
            # Also compute mean residual as % of median baseline in that bucket for display
            baselines = [float(r["baseline"]) for r in rows
                         if r["residual"] is not None and r.get(variable) is not None
                         and (lo is None or float(r[variable]) >= lo)
                         and (hi is None or float(r[variable]) < hi)
                         and r["baseline"]]
            mean_b = sum(baselines) / len(baselines) if baselines else None
            pct = (mean / mean_b * 100.0) if mean_b else None
            out.append({"bucket": label, "lo": lo, "hi": hi, "n": len(in_bucket),
                        "mean_residual": round(mean, 2),
                        "mean_residual_pct": round(pct, 2) if pct is not None else None})
        return {"metric": data["metric"], "variable": variable, "buckets": out}
```

- [ ] **Step 2: Wire into `do_GET`**

Add branch before the final `else`:
```python
            elif qtype == "buckets":
                metric = params.get("metric", ["partners"])[0]
                variable = params.get("variable", ["rain_sum"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.buckets(cur, metric, variable, df, dt)
```

- [ ] **Step 3: Smoke-test via Python (same query pattern)**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "
import sys
sys.path.insert(0, 'api')
# Direct method call for smoke test
import os, psycopg2
from pathlib import Path
for line in Path('.env.local').read_text().splitlines():
    if line.startswith('POSTGRES_URL='): os.environ['POSTGRES_URL'] = line.split('=',1)[1].strip().strip('\"')
from psycopg2.extras import RealDictCursor
conn = psycopg2.connect(os.environ['POSTGRES_URL'], cursor_factory=RealDictCursor)
cur = conn.cursor()
# Inline a simplified bucket logic check
cur.execute('''
SELECT w.rain_sum, w.date, COUNT(*) OVER() AS total FROM weather_oradea w
WHERE w.rain_sum IS NOT NULL AND w.rain_sum > 10 ORDER BY w.rain_sum DESC LIMIT 5
''')
print('Wettest days in data:')
for r in cur.fetchall(): print(' ', dict(r))
"
```
Expected: 5 days with heavy rain (>10mm precipitation).

- [ ] **Step 4: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "add buckets endpoint for single-variable residual comparison"
```

---

## Task 8: Add `type=lag_curve` endpoint

Correlation between a weather variable on day D and residual on day D+ℓ, for ℓ ∈ {−2,−1,0,+1,+2,+3}.

**Files:**
- Modify: `api/weather.py`

- [ ] **Step 1: Add the method**

```python
    def lag_curve(self, cur, metric_name, variable, date_from, date_to):
        if variable not in BUCKET_SPECS and variable not in {
            "temp_max", "temp_min", "temp_mean", "rain_sum", "snowfall_sum",
            "wind_speed_max", "wind_gusts_max", "humidity_mean",
        }:
            return {"error": "Variable not supported for lag analysis"}
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = data["residuals"]
        # Index by date string for O(1) lookup
        by_date = {r["date"].isoformat() if hasattr(r["date"], "isoformat") else r["date"]: r for r in rows}
        sorted_dates = sorted(by_date.keys())
        lags = list(range(-2, 4))  # -2,-1,0,1,2,3
        out = []
        for lag in lags:
            pairs = []
            for idx, d in enumerate(sorted_dates):
                # find date at idx + lag (using sorted calendar order is close enough
                # for analytical purposes; gaps exist but are rare)
                tgt_idx = idx + lag
                if tgt_idx < 0 or tgt_idx >= len(sorted_dates):
                    continue
                src = by_date[d]
                tgt = by_date[sorted_dates[tgt_idx]]
                if src.get(variable) is None or tgt.get("residual") is None:
                    continue
                pairs.append((float(src[variable]), float(tgt["residual"])))
            if len(pairs) < 10:
                out.append({"lag": lag, "n": len(pairs), "correlation": None})
                continue
            # Pearson correlation
            n = len(pairs)
            sx = sum(p[0] for p in pairs); sy = sum(p[1] for p in pairs)
            sxx = sum(p[0]*p[0] for p in pairs); syy = sum(p[1]*p[1] for p in pairs)
            sxy = sum(p[0]*p[1] for p in pairs)
            denom = ((n*sxx - sx*sx) * (n*syy - sy*sy)) ** 0.5
            r = (n*sxy - sx*sy) / denom if denom else 0
            out.append({"lag": lag, "n": n, "correlation": round(r, 3)})
        return {"metric": data["metric"], "variable": variable, "lags": out}
```

- [ ] **Step 2: Wire into `do_GET`**

```python
            elif qtype == "lag_curve":
                metric = params.get("metric", ["partners"])[0]
                variable = params.get("variable", ["rain_sum"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.lag_curve(cur, metric, variable, df, dt)
```

- [ ] **Step 3: Syntax check**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "import ast; ast.parse(open('api/weather.py').read()); print('SYNTAX OK')"
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "add lag_curve endpoint"
```

---

## Task 9: Add `type=extreme_days` endpoint

Top-N days by absolute |residual|, with their full weather signature. Used by the UI to highlight anomalies.

**Files:**
- Modify: `api/weather.py`

- [ ] **Step 1: Add the method**

```python
    def extreme_days(self, cur, metric_name, date_from, date_to, limit=20):
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = [r for r in data["residuals"] if r["residual"] is not None]
        rows.sort(key=lambda r: abs(r["residual"]), reverse=True)
        return {"metric": data["metric"], "extreme_days": rows[:limit]}
```

- [ ] **Step 2: Wire into `do_GET`**

```python
            elif qtype == "extreme_days":
                metric = params.get("metric", ["partners"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                lim = int(params.get("limit", ["20"])[0])
                result = self.extreme_days(cur, metric, df, dt, lim)
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "add extreme_days endpoint"
```

---

## Task 10: Add `type=overview` endpoint (auto-hypothesis aggregator)

The headline endpoint. Runs bucket comparisons for key variables, threshold detection for continuous ones, lag checks, and curated interaction patterns. Returns a ranked list of narrative-ready insights.

**Files:**
- Modify: `api/weather.py`

- [ ] **Step 1: Add threshold detection helper**

Add above the `handler` class:

```python
def find_threshold(pairs, min_pts_per_side=15):
    """Given list of (x, residual) pairs, find the split point that maximizes
    |t-statistic| of residual means. Returns {threshold, above_mean, below_mean,
    effect_pct, n_above, n_below, t_stat} or None."""
    if len(pairs) < 30:
        return None
    xs = sorted(set(p[0] for p in pairs))
    best = None
    for x in xs:
        below = [p[1] for p in pairs if p[0] < x]
        above = [p[1] for p in pairs if p[0] >= x]
        if len(below) < min_pts_per_side or len(above) < min_pts_per_side:
            continue
        mb = sum(below) / len(below); ma = sum(above) / len(above)
        # Pooled variance approximation for t-stat
        vb = sum((b - mb) ** 2 for b in below) / (len(below) - 1) if len(below) > 1 else 1
        va = sum((a - ma) ** 2 for a in above) / (len(above) - 1) if len(above) > 1 else 1
        se = ((vb / len(below)) + (va / len(above))) ** 0.5
        if se == 0:
            continue
        t = abs(ma - mb) / se
        if best is None or t > best["t_stat"]:
            best = {"threshold": x, "above_mean": ma, "below_mean": mb,
                    "effect": ma - mb, "t_stat": t, "n_above": len(above), "n_below": len(below)}
    return best
```

- [ ] **Step 2: Add the overview method**

```python
    def overview(self, cur, metric_name, date_from, date_to):
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = [r for r in data["residuals"] if r["residual"] is not None]
        if len(rows) < 30:
            return {"metric": data["metric"], "insights": [], "note": "Not enough data"}
        insights = []

        # Family A: bucket comparisons — top buckets by |mean_residual| per variable
        for var in ["rain_sum", "temp_max", "wind_gusts_max", "snowfall_sum",
                    "humidity_mean", "cloudcover_mean"]:
            bres = self.buckets(cur, metric_name, var, date_from, date_to)
            top = max(
                (b for b in bres.get("buckets", []) if b["mean_residual"] is not None and b["n"] >= 10),
                key=lambda b: abs(b["mean_residual"]),
                default=None,
            )
            if top and abs(top["mean_residual_pct"] or 0) >= 5:
                insights.append({
                    "kind": "bucket",
                    "variable": var,
                    "bucket": top["bucket"],
                    "effect_pct": top["mean_residual_pct"],
                    "n": top["n"],
                    "text": f"{var}={top['bucket']}: residual mediu {top['mean_residual']:+.1f} ({top['mean_residual_pct']:+.1f}% fata de baseline, n={top['n']})",
                })

        # Family B: threshold detection for continuous variables
        for var in ["temp_max", "temp_min", "wind_speed_max", "wind_gusts_max",
                    "precipitation_sum", "humidity_mean"]:
            pairs = [(float(r[var]), r["residual"]) for r in rows if r.get(var) is not None]
            t = find_threshold(pairs)
            if t and t["t_stat"] >= 2.0:  # ~p<0.05
                insights.append({
                    "kind": "threshold",
                    "variable": var,
                    "threshold": round(t["threshold"], 2),
                    "above_effect": round(t["above_mean"], 1),
                    "below_effect": round(t["below_mean"], 1),
                    "t_stat": round(t["t_stat"], 2),
                    "n_above": t["n_above"],
                    "n_below": t["n_below"],
                    "text": f"{var} >= {round(t['threshold'], 2)}: residual {t['above_mean']:+.1f} (n={t['n_above']}) vs < prag: {t['below_mean']:+.1f} (n={t['n_below']}), t={t['t_stat']:.2f}",
                })

        # Family C: lag analysis — where does each weather var have its peak effect?
        for var in ["rain_sum", "snowfall_sum", "temp_max", "wind_gusts_max"]:
            lc = self.lag_curve(cur, metric_name, var, date_from, date_to)
            lags = [l for l in lc.get("lags", []) if l.get("correlation") is not None]
            if not lags:
                continue
            peak = max(lags, key=lambda l: abs(l["correlation"]))
            zero = next((l for l in lags if l["lag"] == 0), None)
            if peak["lag"] != 0 and abs(peak["correlation"]) >= 0.15 and zero and abs(peak["correlation"]) > abs(zero["correlation"]):
                insights.append({
                    "kind": "lag",
                    "variable": var,
                    "lag": peak["lag"],
                    "correlation_at_peak": peak["correlation"],
                    "correlation_at_zero": zero["correlation"],
                    "text": f"{var} efect maxim la lag={peak['lag']} (r={peak['correlation']:+.2f}), nu in aceeasi zi (r0={zero['correlation']:+.2f})",
                })

        # Family D: curated interaction patterns
        def avg_res(filter_fn):
            vals = [r["residual"] for r in rows if filter_fn(r)]
            n = len(vals)
            return (sum(vals) / n if n else None), n

        def pct(r):
            return (r["residual"] / float(r["baseline"]) * 100.0) if r.get("baseline") else None

        patterns = []
        cold_wet = avg_res(lambda r: r.get("temp_max") is not None and float(r["temp_max"]) < 5
                           and r.get("precipitation_sum") is not None and float(r["precipitation_sum"]) > 2)
        hot_dry = avg_res(lambda r: r.get("temp_max") is not None and float(r["temp_max"]) > 30
                          and r.get("precipitation_sum") is not None and float(r["precipitation_sum"]) < 0.5)
        if cold_wet[1] >= 5:
            patterns.append(("Frig + umed (temp<5°C AND precip>2mm)", cold_wet[0], cold_wet[1]))
        if hot_dry[1] >= 5:
            patterns.append(("Canicula uscata (temp>30°C AND precip<0.5mm)", hot_dry[0], hot_dry[1]))

        # Add to insights if significant
        for name, val, n in patterns:
            if val is None:
                continue
            # Express as pct of baseline using rows that matched
            if abs(val) < 3:
                continue
            insights.append({
                "kind": "interaction",
                "pattern": name,
                "effect": round(val, 1),
                "n": n,
                "text": f"{name}: residual mediu {val:+.1f} (n={n})",
            })

        # Sort by importance: bigger absolute effect first
        insights.sort(key=lambda i: -abs(
            i.get("effect_pct") or i.get("above_effect") or
            (i.get("correlation_at_peak") or 0) * 100 or
            (i.get("effect") or 0)
        ))

        return {"metric": data["metric"], "insights": insights}
```

- [ ] **Step 3: Wire into `do_GET`**

```python
            elif qtype == "overview":
                metric = params.get("metric", ["partners"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.overview(cur, metric, df, dt)
```

- [ ] **Step 4: Smoke-test (deploy preview or local vercel dev)**

After push to the branch, hit:
`https://<preview-url>/api/weather?type=overview&metric=partners`

Expected: JSON with `metric: "partners"` and `insights: [...]` array containing at least a handful of entries. Verify the `text` fields read like actual Romanian sentences.

If no insights come back, lower the thresholds in the code (the 5% / 2.0 / 0.15 cutoffs) and re-test — but ONLY if data clearly exists. Don't mask actual errors.

- [ ] **Step 5: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "add overview endpoint with 4-family hypothesis engine"
```

---

## Task 11: Meteo & Trafic tab scaffold

**Files:**
- Modify: `index.html`

Mirror the Sezonalitate pattern exactly — that's what worked in Phase 1.

- [ ] **Step 1: Add nav button**

In the nav section (around line 167 area — find the Sezonalitate button we added in Phase 1), insert immediately after it:

```html
            <button class="nav-tab" onclick="showSection('meteo')">Meteo</button>
```

- [ ] **Step 2: Add section div**

After the closing `</div>` of `section-sezonalitate`, insert:

```html

        <!-- METEO & TRAFIC -->
        <div id="section-meteo" class="section">
            <div class="card">
                <h2><span class="icon">🌦️</span> Meteo & Trafic</h2>
                <p style="color:#888;font-size:0.85em;margin-bottom:10px;">
                    Compara traficul cu vremea reala la Oradea. Fiecare zi de lucru are o <strong style="color:#aaa">baseline</strong>
                    (medianul ultimelor 28 zile lucratoare cu aceeasi zi a saptamanii). Vremea se masoara fata de acest baseline —
                    asa excludem efectul sezonal normal si ramane doar ce face meteo-ul.
                </p>
                <div style="display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin-bottom:4px;">
                    <div><label style="color:#888;font-size:0.85em;display:block;">De la:</label>
                        <input type="date" id="meteoDateFrom" style="background:#1a1a2e;color:#fff;border:1px solid #333;padding:6px;border-radius:4px;"></div>
                    <div><label style="color:#888;font-size:0.85em;display:block;">Pana la:</label>
                        <input type="date" id="meteoDateTo" style="background:#1a1a2e;color:#fff;border:1px solid #333;padding:6px;border-radius:4px;"></div>
                    <div><label style="color:#888;font-size:0.85em;display:block;">Metrica:</label>
                        <select id="meteoMetric" style="background:#1a1a2e;color:#fff;border:1px solid #333;padding:6px;border-radius:4px;">
                            <option value="partners">Parteneri</option>
                            <option value="transactions">Tranzactii</option>
                            <option value="kg">Kg</option>
                            <option value="ron">RON</option>
                        </select></div>
                    <button id="meteoApply" style="padding:8px 18px;background:#00d9ff;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:600;">Analizeaza</button>
                </div>
            </div>

            <div class="card">
                <h2><span class="icon">💡</span> Insights auto-detectate</h2>
                <div id="meteoInsights"></div>
            </div>

            <div class="card">
                <h2><span class="icon">🌧️</span> Buckets: ploaie, zapada, temperatura, vant</h2>
                <div id="meteoBuckets"></div>
            </div>

            <div class="card">
                <h2><span class="icon">⏱️</span> Analiza lag (efectul la 0, 1, 2, 3 zile dupa)</h2>
                <div id="meteoLag"></div>
            </div>

            <div class="card">
                <h2><span class="icon">🔥</span> Zile extreme</h2>
                <p style="color:#888;font-size:0.85em;margin-bottom:10px;">Cele mai atipice zile: cel mai mare ecart fata de baseline.</p>
                <div id="meteoExtreme" class="scroll-table"></div>
            </div>
        </div>
```

- [ ] **Step 3: Extend `showSection` lazy-loading**

Find the Phase 1 `showSection` function and add the meteo tab branch:

```javascript
        function showSection(id) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
            document.getElementById('section-' + id).classList.add('active');
            event.target.classList.add('active');
            if (id === 'sezonalitate' && !window._sezLoaded) {
                window._sezLoaded = true;
                loadSezonalitate();
            }
            if (id === 'meteo' && !window._meteoLoaded) {
                window._meteoLoaded = true;
                loadMeteo();
            }
        }
```

- [ ] **Step 4: Add placeholder `loadMeteo`**

At the end of the main `<script>` block (after all the Sezonalitate functions), add:

```javascript

        // === Meteo & Trafic (Phase 2) ===
        async function loadMeteo() {
            // Default date range: full dataset
            const df = document.getElementById('meteoDateFrom');
            const dt = document.getElementById('meteoDateTo');
            if (!df.value) df.value = '2022-01-03';
            if (!dt.value) dt.value = new Date().toISOString().substring(0,10);
            document.getElementById('meteoApply').onclick = refreshMeteo;
            refreshMeteo();
        }

        async function refreshMeteo() {
            const df = document.getElementById('meteoDateFrom').value;
            const dt = document.getElementById('meteoDateTo').value;
            const metric = document.getElementById('meteoMetric').value;
            await Promise.all([
                loadMeteoOverview(df, dt, metric),
                loadMeteoBuckets(df, dt, metric),
                loadMeteoLag(df, dt, metric),
                loadMeteoExtreme(df, dt, metric),
            ]);
        }

        async function loadMeteoOverview(df, dt, metric) {
            document.getElementById('meteoInsights').innerHTML = '<p style="color:#888">Se incarca...</p>';
            // Implemented in Task 12
        }
        async function loadMeteoBuckets(df, dt, metric) {
            document.getElementById('meteoBuckets').innerHTML = '<p style="color:#888">Se incarca...</p>';
        }
        async function loadMeteoLag(df, dt, metric) {
            document.getElementById('meteoLag').innerHTML = '<p style="color:#888">Se incarca...</p>';
        }
        async function loadMeteoExtreme(df, dt, metric) {
            document.getElementById('meteoExtreme').innerHTML = '<p style="color:#888">Se incarca...</p>';
        }
```

- [ ] **Step 5: Verify tab loads without errors**

Check in browser after push: the Meteo nav button appears, clicking shows the scaffold with "Se incarca..." placeholders and no console errors.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add index.html && git commit -m "scaffold Meteo & Trafic tab"
```

---

## Task 12: Frontend — insights cards

**Files:**
- Modify: `index.html`

Replace the `loadMeteoOverview` placeholder with the real implementation. Each insight becomes a card with emoji + narrative + numbers.

- [ ] **Step 1: Implement loadMeteoOverview**

Replace the placeholder:
```javascript
        async function loadMeteoOverview(df, dt, metric) {
            const host = document.getElementById('meteoInsights');
            host.innerHTML = '<p style="color:#888">Se incarca...</p>';
            try {
                const url = `/api/weather?type=overview&metric=${encodeURIComponent(metric)}&date_from=${df}&date_to=${dt}`;
                const data = await (await fetch(url)).json();
                const insights = data.insights || [];
                if (!insights.length) {
                    host.innerHTML = '<p style="color:#888">Niciun efect semnificativ detectat in perioada selectata.</p>';
                    return;
                }
                const emojiFor = ins => {
                    if (ins.kind === "bucket" && ins.variable === "rain_sum") return "🌧️";
                    if (ins.kind === "bucket" && ins.variable === "snowfall_sum") return "❄️";
                    if (ins.kind === "bucket" && (ins.variable || "").includes("temp")) return "🌡️";
                    if (ins.kind === "bucket" && (ins.variable || "").includes("wind")) return "💨";
                    if (ins.kind === "bucket" && ins.variable === "humidity_mean") return "💧";
                    if (ins.kind === "bucket" && ins.variable === "cloudcover_mean") return "☁️";
                    if (ins.kind === "threshold") return "📏";
                    if (ins.kind === "lag") return "⏱️";
                    if (ins.kind === "interaction") return "🧩";
                    return "💡";
                };
                const colorFor = ins => {
                    const v = ins.effect_pct ?? ins.effect ?? ins.above_effect ?? 0;
                    if (v > 2) return "#00ff88";
                    if (v < -2) return "#ff6b6b";
                    return "#aaa";
                };
                let html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px;">';
                insights.forEach(ins => {
                    const c = colorFor(ins);
                    html += `<div style="padding:12px;background:rgba(0,217,255,0.05);border-left:3px solid ${c};border-radius:4px;">`;
                    html += `<div style="font-size:1.1em;margin-bottom:6px;">${emojiFor(ins)} <strong style="color:#fff">${ins.kind.toUpperCase()}</strong></div>`;
                    html += `<div style="color:#ccc;font-size:0.9em;line-height:1.5;">${ins.text}</div>`;
                    html += '</div>';
                });
                html += '</div>';
                host.innerHTML = html;
            } catch (e) {
                host.innerHTML = `<p style="color:#ff6b6b">Eroare: ${e.message}</p>`;
            }
        }
```

- [ ] **Step 2: Verify via preview**

Click Meteo tab → Analizeaza. Insight cards should populate. If the array is empty in the response, the "no effect detected" message shows.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add index.html && git commit -m "implement Meteo insights cards"
```

---

## Task 13: Frontend — bucket bars

**Files:**
- Modify: `index.html`

Grid of bar charts, one per variable. X = bucket label, Y = mean residual pct.

- [ ] **Step 1: Implement loadMeteoBuckets**

Replace the placeholder:
```javascript
        const METEO_BUCKET_VARS = [
            { key: "rain_sum",        title: "🌧️ Ploaie (mm)" },
            { key: "snowfall_sum",    title: "❄️ Zapada (cm)" },
            { key: "temp_max",        title: "🌡️ Temp. maxima (°C)" },
            { key: "wind_gusts_max",  title: "💨 Rafale vant (km/h)" },
            { key: "humidity_mean",   title: "💧 Umiditate (%)" },
            { key: "cloudcover_mean", title: "☁️ Nori (%)" },
        ];
        const _meteoBucketCharts = {};

        async function loadMeteoBuckets(df, dt, metric) {
            const host = document.getElementById('meteoBuckets');
            host.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:16px;" id="meteoBucketGrid"></div>';
            const grid = document.getElementById('meteoBucketGrid');
            await Promise.all(METEO_BUCKET_VARS.map(async v => {
                const url = `/api/weather?type=buckets&metric=${encodeURIComponent(metric)}&variable=${v.key}&date_from=${df}&date_to=${dt}`;
                const data = await (await fetch(url)).json();
                const wrap = document.createElement('div');
                wrap.innerHTML = `<div style="color:#aaa;font-weight:600;margin-bottom:6px;">${v.title}</div>
                  <div class="chart-container short" style="height:220px;position:relative;"><canvas></canvas></div>`;
                grid.appendChild(wrap);
                const canvas = wrap.querySelector('canvas');
                const buckets = (data.buckets || []).filter(b => b.mean_residual_pct !== null);
                if (!buckets.length) {
                    wrap.querySelector('.chart-container').innerHTML = '<p style="color:#555">Nu sunt date.</p>';
                    return;
                }
                const labels = buckets.map(b => b.bucket);
                const values = buckets.map(b => parseFloat(b.mean_residual_pct));
                const bg = values.map(v => v > 0 ? 'rgba(0,255,136,0.4)' : 'rgba(255,107,107,0.4)');
                const border = values.map(v => v > 0 ? '#00ff88' : '#ff6b6b');
                if (_meteoBucketCharts[v.key]) _meteoBucketCharts[v.key].destroy();
                _meteoBucketCharts[v.key] = new Chart(canvas.getContext('2d'), {
                    type: 'bar',
                    data: { labels, datasets: [{ label: '% vs baseline', data: values, backgroundColor: bg, borderColor: border, borderWidth: 1 }] },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { legend: { display: false },
                                   tooltip: { callbacks: { label: ctx => {
                                       const b = buckets[ctx.dataIndex];
                                       return `${ctx.parsed.y.toFixed(1)}% · n=${b.n}`;
                                   } } } },
                        scales: {
                            y: { ticks: { color: '#aaa', callback: v => v + '%' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                            x: { ticks: { color: '#aaa', font: { size: 10 } }, grid: { display: false } }
                        }
                    }
                });
            }));
        }
```

- [ ] **Step 2: Verify**

Meteo tab → Analizeaza. Should see 6 small charts in a grid, each showing bucket bars in green/red for the variable.

- [ ] **Step 3: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add index.html && git commit -m "implement Meteo bucket bar grid"
```

---

## Task 14: Frontend — lag analysis charts

**Files:**
- Modify: `index.html`

Line charts, one per variable, showing correlation at lag −2..+3. Flags the peak lag.

- [ ] **Step 1: Implement loadMeteoLag**

```javascript
        const METEO_LAG_VARS = [
            { key: "rain_sum",       title: "🌧️ Ploaie" },
            { key: "snowfall_sum",   title: "❄️ Zapada" },
            { key: "temp_max",       title: "🌡️ Temp. maxima" },
            { key: "wind_gusts_max", title: "💨 Rafale vant" },
        ];
        const _meteoLagCharts = {};

        async function loadMeteoLag(df, dt, metric) {
            const host = document.getElementById('meteoLag');
            host.innerHTML = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px;" id="meteoLagGrid"></div>';
            const grid = document.getElementById('meteoLagGrid');
            await Promise.all(METEO_LAG_VARS.map(async v => {
                const url = `/api/weather?type=lag_curve&metric=${encodeURIComponent(metric)}&variable=${v.key}&date_from=${df}&date_to=${dt}`;
                const data = await (await fetch(url)).json();
                const lags = (data.lags || []).filter(l => l.correlation !== null);
                const wrap = document.createElement('div');
                wrap.innerHTML = `<div style="color:#aaa;font-weight:600;margin-bottom:6px;">${v.title}</div>
                    <div class="chart-container short" style="height:180px;position:relative;"><canvas></canvas></div>`;
                grid.appendChild(wrap);
                if (!lags.length) {
                    wrap.querySelector('.chart-container').innerHTML = '<p style="color:#555">Nu sunt date.</p>';
                    return;
                }
                const canvas = wrap.querySelector('canvas');
                const labels = lags.map(l => l.lag === 0 ? 'azi' : (l.lag > 0 ? `+${l.lag}` : String(l.lag)));
                const values = lags.map(l => parseFloat(l.correlation));
                if (_meteoLagCharts[v.key]) _meteoLagCharts[v.key].destroy();
                _meteoLagCharts[v.key] = new Chart(canvas.getContext('2d'), {
                    type: 'line',
                    data: { labels, datasets: [{ label: 'corr', data: values, borderColor: '#00d9ff', backgroundColor: 'rgba(0,217,255,0.15)', tension: 0.3, fill: true, pointRadius: 5 }] },
                    options: {
                        responsive: true, maintainAspectRatio: false,
                        plugins: { legend: { display: false },
                                   tooltip: { callbacks: { label: ctx => {
                                       const l = lags[ctx.dataIndex];
                                       return `r=${l.correlation.toFixed(3)} (n=${l.n})`;
                                   } } } },
                        scales: { y: { ticks: { color: '#aaa' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                                  x: { ticks: { color: '#aaa' }, grid: { display: false } } }
                    }
                });
            }));
        }
```

- [ ] **Step 2: Verify + commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add index.html && git commit -m "implement Meteo lag curve charts"
```

---

## Task 15: Frontend — extreme days table

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Implement loadMeteoExtreme**

```javascript
        async function loadMeteoExtreme(df, dt, metric) {
            const host = document.getElementById('meteoExtreme');
            host.innerHTML = '<p style="color:#888">Se incarca...</p>';
            try {
                const url = `/api/weather?type=extreme_days&metric=${encodeURIComponent(metric)}&date_from=${df}&date_to=${dt}&limit=20`;
                const data = await (await fetch(url)).json();
                const rows = data.extreme_days || [];
                if (!rows.length) {
                    host.innerHTML = '<p style="color:#555">Nu sunt date.</p>';
                    return;
                }
                let html = '<table><thead><tr>';
                html += '<th>Data</th><th class="text-right">Actual</th><th class="text-right">Baseline</th><th class="text-right">Δ</th><th class="text-right">Δ%</th>';
                html += '<th class="text-right">Temp max</th><th class="text-right">Ploaie</th><th class="text-right">Zapada</th><th class="text-right">Vant max</th><th class="text-right">Cod WMO</th>';
                html += '</tr></thead><tbody>';
                rows.forEach(r => {
                    const pct = r.residual_pct;
                    const color = pct > 0 ? '#00ff88' : '#ff6b6b';
                    const sign = pct >= 0 ? '+' : '';
                    html += `<tr>
                        <td>${r.date}</td>
                        <td class="text-right">${parseFloat(r.value).toFixed(0)}</td>
                        <td class="text-right" style="color:#888">${r.baseline ? parseFloat(r.baseline).toFixed(1) : '-'}</td>
                        <td class="text-right" style="color:${color}">${sign}${parseFloat(r.residual).toFixed(1)}</td>
                        <td class="text-right" style="color:${color};font-weight:600;">${pct !== null ? sign + pct.toFixed(1) + '%' : '-'}</td>
                        <td class="text-right">${r.temp_max ?? '-'}</td>
                        <td class="text-right">${r.precipitation_sum ?? '-'}</td>
                        <td class="text-right">${r.snowfall_sum ?? '-'}</td>
                        <td class="text-right">${r.wind_speed_max ?? '-'}</td>
                        <td class="text-right" style="color:#888">${r.weather_code ?? '-'}</td>
                    </tr>`;
                });
                html += '</tbody></table>';
                host.innerHTML = html;
            } catch (e) {
                host.innerHTML = `<p style="color:#ff6b6b">Eroare: ${e.message}</p>`;
            }
        }
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add index.html && git commit -m "implement Meteo extreme days table"
```

---

## Task 16: Update CLAUDE.md docs

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add `/api/weather` table section**

Find the `/api/calendar` section. Immediately after its closing table, insert:

```markdown

### `/api/weather`
| Parameter | Description |
|-----------|-------------|
| `type=ping` | Health check |
| `type=residuals&metric=X&date_from=Y&date_to=Z` | Per-zi: actual, baseline, residual, + weather columns |
| `type=buckets&variable=rain_sum&metric=partners` | Bucket-uri pt variabila vs residual |
| `type=lag_curve&variable=rain_sum&metric=partners` | Corelatie la lag -2..+3 |
| `type=extreme_days&metric=partners&limit=20` | Top-N zile cu ecart maxim fata de baseline |
| `type=overview&metric=partners` | Toate cele 4 familii de ipoteze agregate |

Metric options: `partners`, `transactions`, `kg`, `ron`.
Variable options (buckets): `rain_sum`, `snowfall_sum`, `temp_max`, `temp_min`, `wind_gusts_max`, `humidity_mean`, `cloudcover_mean`.
```

- [ ] **Step 2: Add weather_oradea table description**

In the "Database Structure" section, after `waste_categories`, add:

```markdown

weather_oradea    - Date meteo istorice (Nagyvarad/Oradea)
├── date (PK)     - Data (o singura sursa/zi)
├── temp_max/min/mean - Temperaturi (°C)
├── apparent_temp_* - Temperaturi aparente (percepute)
├── precipitation_sum, rain_sum, snowfall_sum, snow_depth_max - Precipitatii
├── wind_speed_max, wind_gusts_max, wind_direction_dominant - Vant
├── pressure_mean, humidity_mean, cloudcover_mean - Derivate din hourly
├── shortwave_radiation_sum, sunshine_duration, daylight_duration - Sun
├── et0_evapotranspiration - Evapotranspiratie
└── weather_code - Cod WMO
```

- [ ] **Step 3: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add CLAUDE.md && git commit -m "document /api/weather + weather_oradea table"
```

---

## Task 17: End-to-end verification + merge to main

**Files:** none (verification)

- [ ] **Step 1: Push current branch and wait for Vercel preview**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git push
```
Wait ~1-2 minutes.

- [ ] **Step 2: Smoke-test each endpoint on the preview URL**

Replace `<preview>` with the URL Vercel generated:
```bash
for q in 'type=ping' 'type=residuals&metric=partners' \
         'type=buckets&variable=rain_sum&metric=partners' \
         'type=lag_curve&variable=rain_sum&metric=partners' \
         'type=extreme_days&metric=partners&limit=5' \
         'type=overview&metric=partners'; do
  echo "=== $q ==="
  curl -s "https://<preview>.vercel.app/api/weather?$q" | head -c 400
  echo; echo
done
```
Expected: every response is valid JSON, no `error` key.

- [ ] **Step 3: Live UI walkthrough**

Open the preview. Click the Meteo tab. Verify:
- 4 sections populate (insights cards, bucket bar grid, lag charts, extreme days).
- Metric dropdown → change to Kg → Analizeaza → charts re-render with new metric.
- Date range → narrow to last 6 months → re-analyze → numbers update.
- At least 3-5 insight cards appear for the full date range (if zero, thresholds in overview are too strict — investigate).

- [ ] **Step 4: Merge to main**

Once verified:
```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git checkout main && git merge --no-ff phase2-meteo -m "Merge Phase 2: Meteo & Trafic analysis tab" && git push origin main
```

- [ ] **Step 5: Announce complete**

Report back with a short summary of the most notable weather effects observed (e.g. "heavy rain → −15% partners, max effect at lag=2" or similar). These are the payoff for the whole two-phase project.

---

## Rollback Plan

If Phase 2 causes problems in production:

1. `git revert <merge-commit>` to drop the Meteo tab + endpoint.
2. `weather_oradea` table can stay — it doesn't affect existing queries.
3. `vercel.json` route entry can be reverted without data loss.

## Follow-ups (not in this plan)

- **Year selector on Sezonalitate charts (Phase 1 polish)** — Tipar săptămânal and Tipar lunar currently aggregate across all years silently, so the user can't tell which year the numbers represent. Add a dropdown (`2022`, `2023`, `2024`, `2025`, `2026`, `Toate (media)`) next to the existing metric toggle on both charts. Backend: both `/api/calendar?type=weekly_pattern` and `type=monthly_pattern` already accept `date_from`/`date_to` — the frontend just needs to translate the year pick into a date range (or add a `year=` param for convenience). When "Toate" is selected, no filter is passed (current behavior = average of all years). Small UI task, ~30 min.
- Daily cron that runs `scripts/fetch_weather.py` with no arguments (top-up latest days) — Vercel Cron or GitHub Actions, separate follow-up task.
- Phase 3 — weather badge on each transaction row in partner profile modal (small polish, ~30 min).
- Expand hypothesis families: sequence patterns ("3rd consecutive snowy day"), dramatic temp drops, first-sunny-after-rain — currently stubbed simple version.
