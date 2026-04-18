# Meteo & Trafic + Sezonalitate — Design Spec

**Date:** 2026-04-17
**Author:** pap.sebastian@gmail.com (ebastyan)
**Repo:** ebastyan/intern (paju dashboard)

## 1. Overview

Add two new analytical capabilities to the Persoane Fizice dashboard:

1. **Sezonalitate** — calendar-aware baseline showing how traffic varies by day of week, month, holidays, and company closures. Establishes the "normal" against which any external influence can be measured.
2. **Meteo & Trafic** — correlates Oradea historical weather (2022-01-03 → present) with daily traffic metrics, generating narrative hypothesis statements (e.g. "Esős napokon 14%-kal kevesebb partner jön; eső után 2 nappal pedig +8% visszapattanás látható").

The two are deliberately split because the weather analysis is only meaningful once the seasonal / calendar baseline is correct. Weather effects must be measured as deviations from the seasonal norm, not from raw numbers.

A third optional phase adds a small weather badge to each transaction row in the partner profile modal.

## 2. Motivation

- Business planning: staffing, opening hours, promotions can be informed by knowing **why** a day was slow/busy.
- Weather effects are currently hidden inside seasonal averages ("January is cold and slow") rather than isolated ("today was 6°C colder than the January norm, and we saw a 12% drop").
- Holiday compliance audit falls out for free: the algorithm lists any official non-working day that had transactions.

## 3. Scope

In scope:
- Two new tables (`holidays`, `company_closures`) + one weather table (`weather_oradea`).
- One-off weather ingestion script (rerunnable / idempotent, for backfill and periodic top-up).
- Two new API endpoints (`/api/calendar`, `/api/weather-analysis`).
- Two new frontend tabs (**Sezonalitate**, **Meteo & Trafic**) added to `index.html`.
- Romanian national holidays 2022-2030 + Catholic Easter (algorithmic) + Orthodox Easter/Pentecost (algorithmic).
- Company closure auto-detection workflow: propose candidates → user validates → seed into DB.

Out of scope (explicitly):
- Firme B2B weather analysis (separate dashboard, fewer rows, deferred).
- Hourly/sub-daily weather granularity (transactions only have dates, not times).
- Real-time weather forecast integration (historical only).
- Predictive models / ML — statistics only, no learned models.
- Weather effects on waste-type *prices* (separate question, different design).

## 4. Working Day Definition

Core definition used everywhere:

> A **working day** is any date where: `day_of_week ≠ Sunday` AND `date ∉ holidays WHERE is_official = true` AND `date ∉ company_closures`.

Note: **Saturday is a working day** at Paju (opening hours Monday-Saturday). Only Sunday is a natural closed day.

All seasonality baselines, per-weekday comparisons, and weather-effect deltas are computed **only on working days**, unless explicitly labelled otherwise.

---

## 5. Phase 1 — Sezonalitate

### 5.1 Data Model

```sql
CREATE TABLE holidays (
  date DATE NOT NULL,
  name VARCHAR(100) NOT NULL,
  type VARCHAR(20) NOT NULL,        -- 'national' | 'catholic' | 'orthodox'
  is_official BOOLEAN NOT NULL,     -- Romanian public holiday ("piros nap")
  PRIMARY KEY (date, type)
);
CREATE INDEX idx_holidays_date ON holidays(date);

CREATE TABLE company_closures (
  date DATE PRIMARY KEY,
  reason VARCHAR(200),              -- free-text, e.g. 'Concediu de vară', 'Prelungire Crăciun'
  detected_automatically BOOLEAN DEFAULT true,
  validated_at TIMESTAMP DEFAULT now()
);
```

Composite primary key on `holidays` allows both Catholic and Orthodox Easter on the rare years they coincide, or an Orthodox holiday that falls on a national holiday being represented twice.

### 5.2 Holiday Seeding

A single-run script `scripts/seed_holidays.py` populates 2022-2030:

**Fixed national holidays (is_official=true):**
- Jan 1, Jan 2 — Anul Nou
- Jan 24 — Ziua Unirii Principatelor Române
- May 1 — Ziua Muncii
- Jun 1 — Ziua Copilului
- Aug 15 — Adormirea Maicii Domnului (Sf. Maria Mare)
- Nov 30 — Sf. Andrei
- Dec 1 — Ziua Națională
- Dec 25, Dec 26 — Crăciunul

**Computed Catholic (type='catholic', is_official=false):**
- Good Friday — Vinerea Mare (Easter - 2)
- Easter Sunday — Paștele catolic
- Easter Monday — A doua zi de Paști (catolic)
- Whit Sunday — Rusalii catolice (Easter + 49)
- Whit Monday — A doua zi de Rusalii catolice (Easter + 50)

Catholic Easter via Butcher/Meeus Gregorian algorithm.

**Computed Orthodox (type='orthodox', is_official=true for the Romanian-recognized ones):**
- Good Friday — Vinerea Mare ortodoxă (is_official=true since 2018)
- Easter Sunday — Paștele ortodox (is_official=true)
- Easter Monday — A doua zi de Paști ortodox (is_official=true)
- Whit Sunday — Rusalii ortodoxe (is_official=true)
- Whit Monday — A doua zi de Rusalii ortodoxe (is_official=true)

Orthodox Easter via Meeus Julian algorithm + 13-day Julian→Gregorian shift.

The script is idempotent (INSERT ... ON CONFLICT DO UPDATE).

### 5.3 Company Closure Detection

Algorithm (run once, surfaced via the Sezonalitate tab UI):

```
For each date D in [min(transactions.date), max(transactions.date)]:
  If dow(D) == Sunday: skip
  If D ∈ holidays WHERE is_official=true: skip
  If no transactions on D: emit as "closure candidate"
```

Candidates are grouped into contiguous runs (e.g. "2024-08-05 → 2024-08-18 — 12 working days") and displayed in the Sezonalitate tab under a **"Zile fără tranzacții (de validat)"** section. Each row has three buttons:

- **Confirmă** — insert into `company_closures` with a reason (optional text input).
- **Ignoră** — mark as "noise" (stored as `company_closures` with `reason = '__ignored__'`).
- **Editează** — change the proposed date range before confirming.

A separate section lists detected **"Tranzacții pe zile oficial nelucrătoare"** — any row where `transactions.date` coincides with `holidays WHERE is_official=true`. This is purely informational (audit). No action required.

### 5.4 API — `/api/calendar`

| Parameter | Purpose |
|-----------|---------|
| `type=holidays&year=YYYY` | List holidays for a year (all types). |
| `type=closures` | List all validated company closures. |
| `type=closure_candidates` | List auto-detected candidate runs not yet validated or ignored. |
| `type=working_days&date_from=X&date_to=Y` | Return working-day count + list for a range. |
| `type=weekly_pattern&date_from=X&date_to=Y` | Per-weekday aggregates (partners, transactions, kg, value) averaged over working days. |
| `type=monthly_pattern&year=YYYY` | Per-month aggregates for the year, normalized per working day. |
| `type=holiday_effect&window=N` | For each official holiday in the data range, returns traffic on day-N, day-(N-1), ..., day+N compared to the 4 previous weeks' same-weekday baseline. Default N=3. |
| `type=bridge_days` | Lists detected "bridge" patterns: a single working day sandwiched between a weekend/holiday and another weekend/holiday. Shows actual traffic vs expected baseline. |
| `type=illegal_workdays` | Lists transactions on `is_official=true` days (audit). |

POST endpoints for closure validation:
- `POST /api/calendar?action=confirm_closure` body `{date_from, date_to, reason}`
- `POST /api/calendar?action=ignore_closure` body `{date_from, date_to}`

### 5.5 UI — Sezonalitate tab

Tab position in the top nav: `Sumar | Comparatie | Parteneri | Deseuri | Reguni | Predictii | Statistice | **Sezonalitate**` (inserted before or after Statistice).

Sections (top to bottom):

1. **Tipar săptămânal** — horizontal bar chart, Luni-Sâmbătă, 4 metrics (parteneri, tranzacții, kg, RON) as toggle buttons. Computed on working days only. Shows both absolute and % vs weekly average.
2. **Tipar lunar** — 12-month line chart, same 4 metrics. Per-working-day normalized to correct for month length.
3. **Impactul sărbătorilor** — table, one row per holiday, showing the traffic pattern for ±3 days around the holiday averaged across all years in the dataset, vs the same-weekday 4-week baseline. Hover on a row → expanded year-by-year breakdown.
4. **Bridge days** — table of dates where one lone working day sits between two closed days. Shows actual vs baseline.
5. **Zile fără tranzacții (de validat)** — the closure-candidate workflow. Candidate runs with Confirmă/Ignoră/Editează buttons.
6. **Audit: zile oficial nelucrătoare cu tranzacții** — simple table, informational only. Grouped by year.

Color coding: deviations from baseline rendered in `#00ff88` (positive) and `#ff3366` (negative). Dark theme stays consistent.

---

## 6. Phase 2 — Meteo & Trafic

### 6.1 Data Model

```sql
CREATE TABLE weather_oradea (
  date DATE PRIMARY KEY,
  -- Temperature (°C)
  temp_max NUMERIC(5,2),
  temp_min NUMERIC(5,2),
  temp_mean NUMERIC(5,2),
  apparent_temp_max NUMERIC(5,2),
  apparent_temp_min NUMERIC(5,2),
  apparent_temp_mean NUMERIC(5,2),
  -- Precipitation
  precipitation_sum NUMERIC(6,2),      -- mm, rain + snow water equivalent
  rain_sum NUMERIC(6,2),               -- mm
  snowfall_sum NUMERIC(6,2),           -- cm
  snow_depth_max NUMERIC(5,2),         -- m, max during day
  precipitation_hours NUMERIC(4,1),
  -- Wind
  wind_speed_max NUMERIC(5,2),         -- km/h, 10m
  wind_gusts_max NUMERIC(5,2),         -- km/h
  wind_direction_dominant INT,          -- degrees 0-360
  -- Radiation / sun
  shortwave_radiation_sum NUMERIC(6,2), -- MJ/m²
  sunshine_duration NUMERIC(7,1),       -- seconds
  daylight_duration NUMERIC(7,1),
  et0_evapotranspiration NUMERIC(5,2),
  -- Derived (from hourly, averaged to daily)
  pressure_mean NUMERIC(6,2),           -- hPa
  humidity_mean NUMERIC(4,1),           -- %
  cloudcover_mean NUMERIC(4,1),         -- %
  -- WMO weather code (dominant during daylight hours)
  weather_code INT,
  -- Metadata
  fetched_at TIMESTAMP DEFAULT now()
);
CREATE INDEX idx_weather_date ON weather_oradea(date);
```

Rationale for "max complexity": user explicitly asked for the broadest data pull. Storing more than we currently analyze is cheap (~1500 rows × ~20 cols) and future-proofs secondary questions ("do high-pressure days matter?").

### 6.2 Ingestion Script

`scripts/fetch_weather.py`:
- Source: Open-Meteo Historical Weather API (`https://archive-api.open-meteo.com/v1/archive`)
- Coordinates: `latitude=47.0722, longitude=21.9217` (Oradea city center)
- Timezone: `Europe/Bucharest`
- Free tier, no API key, rate-limit generous for one-off backfill.
- Two parallel requests: `daily=...` (primary metrics) and `hourly=pressure_msl,relativehumidity_2m,cloudcover` (averaged to daily for the "derived" columns above).
- Upsert into `weather_oradea` (ON CONFLICT (date) DO UPDATE).
- Default range: `2022-01-01` → yesterday. Configurable via `--date-from` / `--date-to`.
- Idempotent, safe to rerun.
- After Phase 2 ships, a scheduled call keeps it fresh (daily cron or Vercel cron; not in this spec's scope).

### 6.3 Baseline Model

For any date `D` with weekday `W` and month `M`, the **expected** traffic for a metric `m` is:

```
baseline(D, m) = median(m over working days in the 28 calendar days preceding D with weekday=W,
                        excluding D itself and any company_closures or official holidays)
```

A 28-calendar-day lookback normally yields 3-4 matching weekdays. Fallback: if fewer than 3 matching working days exist (early dataset dates, holiday-dense periods, validated closures), widen the lookback to 56 calendar days; if still fewer than 3, use the overall weekday median for the surrounding calendar year.

The **residual** is then `residual(D, m) = actual(D, m) - baseline(D, m)`. All weather statistics operate on residuals, not raw values.

This approach captures weekly and short-term seasonal drift without needing a model fit. It's interpretable and easy to debug.

### 6.4 Hypothesis Engine

Four families of hypothesis are computed automatically; each produces a ranked list of statements.

**A. Single-variable comparison** — for each weather variable, split days into natural buckets and compare residuals:

- Rain: {0mm, 0.1-2mm light, 2-10mm moderate, >10mm heavy}
- Snow: {0cm, 0.1-2cm, 2-10cm, >10cm}
- Temperature max: {<-5, -5-0, 0-10, 10-20, 20-30, >30°C}
- Wind gusts: {<30, 30-50, 50-70, >70 km/h}
- Weather code: clear / cloudy / rain / snow / thunderstorm / fog

Output: per bucket, mean residual + 95% CI (via bootstrap, 1000 resamples), number of days, two-sided t-test p-value against "baseline bucket" (0mm rain, 0cm snow, 10-20°C, <30km/h wind, clear).

**B. Threshold detection** — for continuous variables (temp_max, temp_min, precipitation_sum, wind_speed_max):

- Sort days by variable value.
- Walk through candidate split points in 1% increments of the range.
- At each split, compute mean residual above vs below, with pooled variance.
- Report the split with maximum |t-statistic|, along with the value and the effect size.

Output statement format:
> "Peste X km/h vânt, traficul scade cu Y% față de zilele mai liniștite (n=Z zile, p=P)."

Threshold is only reported if p < 0.05 AND effect size >5%.

**C. Lag detection** — for rain, snow, temperature anomaly, wind:

For each lag ℓ ∈ {-2, -1, 0, +1, +2, +3}, compute the correlation between weather on day `D` and residual on day `D+ℓ`. A lag ℓ is reported as "interesting" if `|corr(ℓ)| > |corr(0)|` AND `|corr(ℓ)|` is highest among lags with p<0.05.

Output statement format:
> "Ploaia are efect maxim după 2 zile, nu în aceeași zi (corelația la lag=2 este -0.31 vs -0.12 la lag=0)."

**D. Interaction / sequence patterns** — a curated set of compound conditions:

- Cold + wet: `temp_max < 5 AND precipitation_sum > 2`
- Hot + dry: `temp_max > 30 AND precipitation_sum < 0.5`
- First sunny day after rain: `precipitation_sum(D-1) > 5 AND precipitation_sum(D) < 0.5`
- Nth consecutive snowy day: counts `snowfall_sum > 0` streak, shows residual vs streak length (1st, 2nd, 3rd+ day of snow).
- Dramatic temperature drop: `temp_max(D-1) - temp_max(D) > 10`

Each compound rule reports effect size + n + p-value. Only statements with p<0.05 and n≥5 are shown.

**Deseasonalization is already baked in via the residual-based baseline (§6.3)**, so no separate step needed. All four families above operate on residuals.

### 6.5 API — `/api/weather-analysis`

| Parameter | Purpose |
|-----------|---------|
| `type=overview&date_from=X&date_to=Y` | Everything: bucket comparisons, thresholds, lags, interactions. Single fat response. |
| `type=buckets&variable=rain&metric=partners&date_from=X&date_to=Y` | Just the bucket table for one variable × metric combo. |
| `type=scatter&variable=temp_max&metric=kg&date_from=X&date_to=Y` | Raw points (day, x, y, residual) for a scatter plot. |
| `type=lag_curve&variable=rain&metric=partners&date_from=X&date_to=Y` | Correlation-vs-lag data for a line chart. |
| `type=extreme_days&date_from=X&date_to=Y&limit=20` | Top-N most-atypical days: largest |residual| and their weather. |

Metric options: `partners`, `transactions`, `kg`, `ron`.

Date filter behavior: **if date_from/date_to are omitted**, analysis covers the full working-day dataset. **If provided**, all computations (including the 28-day baseline windows) are restricted to that period. This matches the user's mental model: "pick a period, analyze only that period".

### 6.6 UI — Meteo & Trafic tab

Sections top to bottom:

1. **Header panel** — date range picker (De la / Pana la), metric selector (Parteneri / Tranzacții / Kg / RON), "Analizează" button. Below it: "Baseline: medianul ultimelor 28 zile lucrătoare cu aceeași zi a săptămânii" (explanation tooltip).
2. **Insights auto-generate** — stack of narrative cards, ranked by effect size × significance. Each card has:
   - One-line Romanian hypothesis statement (bold)
   - Supporting numbers (n, p, effect)
   - Small inline sparkline or mini-chart where appropriate
   - Example: "🌧️ Ploaia >10mm scade traficul cu 14% (n=23 zile, p=0.002). Efect maxim la +2 zile."
3. **Thermometer curve** — scatter of temp_max vs residual (partners), with detected threshold lines overlaid.
4. **Precipitation bucket bars** — grouped bar chart, x=bucket, y=mean residual per metric, with error bars.
5. **Lag analysis** — line charts, one per variable (rain, snow, temp, wind), showing residual correlation at lags -2..+3.
6. **Interaction heatmap** — 2D grid, temp_max × precipitation_sum, cell color = mean residual. Only populated cells shown.
7. **Extreme days table** — top-20 largest-|residual| days with full weather row and computed residual. Clickable → opens the daily summary (reusing existing `/api/transactions?daily=...`).
8. **Raw data explorer** (collapsible) — table of every day in range with weather + actual + baseline + residual. Downloadable as CSV.

Chart.js for everything. Scatters use existing chart patterns from Deseuri → Analiza Detaliata. Heatmap via Chart.js `matrix` plugin or fallback to a hand-rolled CSS grid if the plugin is heavy.

---

## 7. Phase 3 — Weather Badge (optional polish)

If Phase 2 ships cleanly, the partner profile modal (accessible from the Parteneri tab, see `index.html` Szilagyi example) gains a compact weather badge next to each transaction date.

Change:
- `/api/partners?cnp=X` SQL gains `LEFT JOIN weather_oradea w ON t.date = w.date` and returns `temp_mean`, `precipitation_sum`, `snowfall_sum`, `wind_speed_max`, `weather_code` per transaction.
- Frontend renders a small pill: `☀️ 5°C · vânt 15km/h` or `🌧️ 12°C · 8mm` or `❄️ -3°C · 4cm`.
- Emoji mapping derived from `weather_code` (WMO standard codes), with fallback logic: heavy snow > snow > heavy rain > rain > fog > cloudy > clear.

No API schema changes beyond adding the extra columns to the existing partner-profile response. Fail-open: if weather is NULL (pre-2022 or future), badge is omitted silently.

---

## 8. Non-Goals

- No machine learning. Everything is classical statistics (means, t-tests, correlations, bootstrap CIs).
- No predictive forecasting ("what if it rains tomorrow, what will traffic be?"). The analysis is descriptive.
- No air quality / pollution data (would require separate sources, not clearly valuable here).
- No multi-city comparison. Only Oradea weather, tied to Paju's physical location.
- No real-time weather. All data is historical archive.

## 9. Open Questions

None at spec-approval time. Any issues surfaced during implementation should be added here.

## 10. Delivery Order

1. **Phase 1 end-to-end** (holidays seed, closures UI, Sezonalitate tab) — ships first, lets user validate calendar accuracy before weather layer depends on it.
2. **Phase 2 end-to-end** (ingestion, tables, analysis engine, Meteo & Trafic tab) — ships once Phase 1 is validated.
3. **Phase 3** (weather badge in partner modal) — ships only if user confirms it's wanted after seeing Phase 2 live.

Each phase is independently shippable and deployable via the existing Vercel auto-deploy pipeline.
