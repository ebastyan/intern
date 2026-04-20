# Prognoza 7-zile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the forward-looking prognoza: backend endpoint pulls Open-Meteo forecast and maps each of the next 7 days into the existing hindcast engine; frontend exposes it as a compact Sumar widget and a detailed Meteo-tab card.

**Architecture:** New `type=forecast` branch in the existing `api/weather.py`. Same per-dimension category matching used by `overview`, but applied to forecast weather plus a weekday-matched baseline from the historical residuals query. No DB caching in MVP — forecast fetched fresh per request (~500ms via `urllib`).

**Tech Stack:** Python 3.12 stdlib (`urllib` for Open-Meteo forecast), psycopg2 for DB, vanilla JS + existing Chart.js patterns. No new dependencies.

**Source spec:** `docs/superpowers/specs/2026-04-20-prognoza-7-zile-design.md`

**Working branch:** `main` is fine (small focused feature, merge when green). If anything looks risky on preview, we can rebase behind a feature branch mid-flight.

---

## File Structure

**Modified:**
- `api/weather.py` — new module-level `fetch_open_meteo_forecast()` helper, new `forecast()` method on `handler` class, new `elif qtype == "forecast":` route.
- `index.html` — one new card in the Sumar section (widget) + one new card at the top of `section-meteo` (detailed block) + their JS loaders at the end of the main script block.
- `CLAUDE.md` — document the new endpoint and its parameters.

**No new files**, no schema changes. Keeps the footprint minimal.

---

## Task 1: Backend — Open-Meteo forecast fetcher helper

**Files:**
- Modify: `api/weather.py`

The existing `scripts/fetch_weather.py` talks to `/v1/archive`. We need the same transformation logic inline in the API module for `/v1/forecast`. Copy-adapt rather than import the script (Vercel serverless has no `scripts/` on path).

- [ ] **Step 1: Add the forecast fetcher helper at module level**

Open `api/weather.py`. Immediately below the existing `def find_threshold(...)` helper (search for `def find_threshold`) and above `class handler(...)`, add:

```python
# ============================================================================
# Open-Meteo forecast (Phase 3 — Prognoza 7-zile)
# ============================================================================
import json as _json
from urllib.parse import urlencode as _urlencode
from urllib.request import urlopen as _urlopen, Request as _Request

FORECAST_LAT = 47.0722
FORECAST_LON = 21.9217
FORECAST_TZ = "Europe/Bucharest"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

FORECAST_DAILY_FIELDS = [
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
    "apparent_temperature_max", "apparent_temperature_min",
    "precipitation_sum", "rain_sum", "snowfall_sum", "snow_depth_max",
    "precipitation_hours", "windspeed_10m_max", "windgusts_10m_max",
    "winddirection_10m_dominant", "weather_code",
]
FORECAST_HOURLY_FIELDS = ["pressure_msl", "relativehumidity_2m", "cloudcover"]

# Maps Open-Meteo daily field names to our internal column names
FORECAST_DAILY_MAP = {
    "temperature_2m_max": "temp_max",
    "temperature_2m_min": "temp_min",
    "temperature_2m_mean": "temp_mean",
    "apparent_temperature_max": "apparent_temp_max",
    "apparent_temperature_min": "apparent_temp_min",
    "precipitation_sum": "precipitation_sum",
    "rain_sum": "rain_sum",
    "snowfall_sum": "snowfall_sum",
    "snow_depth_max": "snow_depth_max",
    "precipitation_hours": "precipitation_hours",
    "windspeed_10m_max": "wind_speed_max",
    "windgusts_10m_max": "wind_gusts_max",
    "winddirection_10m_dominant": "wind_direction_dominant",
    "weather_code": "weather_code",
}
FORECAST_HOURLY_MAP = {
    "pressure_msl": "pressure_mean",
    "relativehumidity_2m": "humidity_mean",
    "cloudcover": "cloudcover_mean",
}


def _open_meteo_forecast(forecast_days=7, timeout=10):
    """Fetch forecast from Open-Meteo, return dict: {date -> {col: value}}.
    Returns None on network/API failure. No retries — caller decides."""
    daily_q = {
        "latitude": FORECAST_LAT, "longitude": FORECAST_LON,
        "timezone": FORECAST_TZ, "forecast_days": forecast_days,
        "daily": ",".join(FORECAST_DAILY_FIELDS),
    }
    hourly_q = {
        "latitude": FORECAST_LAT, "longitude": FORECAST_LON,
        "timezone": FORECAST_TZ, "forecast_days": forecast_days,
        "hourly": ",".join(FORECAST_HOURLY_FIELDS),
    }
    try:
        daily = _fetch_json(FORECAST_URL + "?" + _urlencode(daily_q), timeout)
        hourly = _fetch_json(FORECAST_URL + "?" + _urlencode(hourly_q), timeout)
    except Exception:
        return None

    per_day = {}
    d_times = daily.get("daily", {}).get("time", [])
    for api_field, col in FORECAST_DAILY_MAP.items():
        arr = daily["daily"].get(api_field, [None] * len(d_times))
        for i, dstr in enumerate(d_times):
            per_day.setdefault(dstr, {})[col] = arr[i] if i < len(arr) else None

    h_times = hourly.get("hourly", {}).get("time", [])
    h_by_day = {}
    for api_field in FORECAST_HOURLY_FIELDS:
        arr = hourly["hourly"].get(api_field, [None] * len(h_times))
        for i, tstr in enumerate(h_times):
            day = tstr[:10]
            if arr[i] is None:
                continue
            h_by_day.setdefault(day, {}).setdefault(api_field, []).append(arr[i])
    for dstr, fields in h_by_day.items():
        target = per_day.setdefault(dstr, {})
        for api_field, col in FORECAST_HOURLY_MAP.items():
            vals = fields.get(api_field, [])
            if vals:
                target[col] = round(sum(vals) / len(vals), 2)

    return per_day


def _fetch_json(url, timeout):
    req = _Request(url, headers={"User-Agent": "paju-dashboard/1.0"})
    with _urlopen(req, timeout=timeout) as r:
        return _json.loads(r.read().decode("utf-8"))
```

- [ ] **Step 2: Syntax check**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "import ast; ast.parse(open('api/weather.py', encoding='utf-8').read()); print('SYNTAX OK')"
```

Expected: `SYNTAX OK`

- [ ] **Step 3: Live sanity test the fetcher**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "
import sys; sys.path.insert(0, 'api')
from weather import _open_meteo_forecast
data = _open_meteo_forecast(forecast_days=3)
assert data is not None, 'fetch returned None'
print(f'Got {len(data)} days')
first_day = sorted(data.keys())[0]
print('First day:', first_day)
print('Columns:', sorted(data[first_day].keys()))
print('Sample values:', {k: data[first_day][k] for k in ['temp_max','precipitation_sum','wind_gusts_max','pressure_mean','humidity_mean']})
"
```

Expected: `Got 3 days` with a date close to today, columns including at least `temp_max`, `precipitation_sum`, `wind_gusts_max`, `pressure_mean`, `humidity_mean`, and sample values that look plausible for Oradea.

If the script fails because the network / API is unreachable from this machine, proceed anyway — the helper is trivial and the live test in the next task will catch real issues.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "Add Open-Meteo forecast fetcher helper (Phase 3)"
```

---

## Task 2: Backend — category-effect computation (all-history)

**Files:**
- Modify: `api/weather.py`

The forecast needs to match each forecast day's weather to the global effect for each category across the full dataset (not user-filtered like `overview`). Reuse the existing `buckets` method, call it with `date_from=None, date_to=None`, and iterate across the same `CATEGORIES` used by `overview`.

- [ ] **Step 1: Add a small helper method `_all_time_category_effects` inside `class handler`**

Open `api/weather.py`, find the existing `overview()` method (search `def overview`). **Immediately before** `def overview`, add this new method (inside the class, same indentation level):

```python
    def _all_time_category_effects(self, cur, metric_name):
        """Return {category_name: {effect_pct, n, range, emoji}} for all
        ranking categories, computed across the entire dataset. Used by
        forecast to look up per-dimension effects without repeating per
        request."""
        # Reuse the same CATEGORIES list used in overview.
        CATS = _RANKING_CATEGORIES
        # Compute once across all history (no date filter).
        data = self.residuals(cur, metric_name, None, None)
        rows = [r for r in data["residuals"] if r["residual"] is not None]
        out = {}
        for emoji, name, range_str, fn in CATS:
            matching = [r for r in rows if fn(r) and r.get("residual_pct") is not None]
            if len(matching) < 5:
                # Not enough samples — skip so forecast doesn't rely on it
                continue
            avg_pct = sum(float(r["residual_pct"]) for r in matching) / len(matching)
            out[name] = {
                "emoji": emoji,
                "name": name,
                "range": range_str,
                "effect_pct": round(avg_pct, 2),
                "n": len(matching),
                "fn": fn,
            }
        return out
```

- [ ] **Step 2: Pull the `CATEGORIES` definition out to module level as `_RANKING_CATEGORIES`**

Find the line `CATEGORIES = [` inside `def overview()`. Cut the entire list assignment (from `CATEGORIES = [` through its closing `]`) and move it to module level, just below the existing `BUCKET_SPECS = {...}` dict. Rename to `_RANKING_CATEGORIES`.

The result: module-level has
```python
_RANKING_CATEGORIES = [
    ("🌧️", "Ploaie torentiala", ">20mm",
     lambda r: r.get("precipitation_sum") is not None and float(r["precipitation_sum"]) > 20),
    # ... all existing entries unchanged ...
]
```

And inside `overview()` replace the old `CATEGORIES = [...]` block with:
```python
        CATEGORIES = _RANKING_CATEGORIES
```
(one line, preserves every existing reference to `CATEGORIES` below it.)

- [ ] **Step 3: Syntax check**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "import ast; ast.parse(open('api/weather.py', encoding='utf-8').read()); print('SYNTAX OK')"
```

Expected: `SYNTAX OK`

- [ ] **Step 4: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "Extract ranking categories to module level + add all-time effects helper"
```

---

## Task 3: Backend — `forecast` method + endpoint routing

**Files:**
- Modify: `api/weather.py`

This is the core: combine the forecast fetch, all-time effects, and per-day baselines into the response shape from the spec.

- [ ] **Step 1: Add the `forecast` method inside `class handler`**

Right after the `_all_time_category_effects` method you added in Task 2, add:

```python
    def forecast(self, cur, metric_name):
        """Return a 7-day traffic prognoza for Oradea. See spec
        docs/superpowers/specs/2026-04-20-prognoza-7-zile-design.md."""
        from datetime import datetime, timedelta
        forecast_data = _open_meteo_forecast(forecast_days=7)
        if forecast_data is None:
            return {"error": "forecast_unavailable", "retry_after_seconds": 300}

        effects = self._all_time_category_effects(cur, metric_name)

        DOW_NAMES = ["Luni", "Marti", "Miercuri", "Joi", "Vineri", "Sambata", "Duminica"]
        METRIC_UNIT = {"partners": "parteneri", "transactions": "tranzactii",
                       "kg": "kg", "ron": "RON"}

        agg_sql, metric_label = resolve_metric(metric_name)

        # One SQL round-trip: pull weekday-matched baseline for each forecast date.
        forecast_dates = sorted(forecast_data.keys())
        baselines = self._forecast_baselines(cur, metric_name, forecast_dates)

        days_out = []
        for dstr in forecast_dates:
            weather = forecast_data.get(dstr, {})
            d_obj = datetime.strptime(dstr, "%Y-%m-%d").date()
            dow_idx = d_obj.weekday()  # Mon=0..Sun=6
            dow = DOW_NAMES[dow_idx]
            is_closed = dow == "Duminica"
            if is_closed:
                days_out.append({
                    "date": dstr, "dow": dow, "is_closed": True,
                    "weather": weather, "weather_desc": "inchis",
                    "baseline": None, "predicted": None,
                    "pct_vs_baseline": None, "confidence": None,
                    "min_n": None, "breakdown": [],
                })
                continue

            baseline = baselines.get(dstr)
            matched = []
            for name, e in effects.items():
                try:
                    if e["fn"](weather):
                        matched.append({
                            "category": name,
                            "emoji": e["emoji"],
                            "range": e["range"],
                            "effect_pct": e["effect_pct"],
                            "n": e["n"],
                        })
                except Exception:
                    continue

            total_pct = sum(m["effect_pct"] for m in matched) if matched else 0.0
            predicted = (baseline * (1 + total_pct / 100)) if baseline is not None else None
            min_n = min((m["n"] for m in matched), default=0)

            if min_n >= 100:
                confidence = "high"
            elif min_n >= 30 or not matched:
                confidence = "ok"
            else:
                confidence = "low"

            days_out.append({
                "date": dstr, "dow": dow, "is_closed": False,
                "weather": weather,
                "weather_desc": _forecast_desc(weather),
                "baseline": round(baseline, 1) if baseline is not None else None,
                "predicted": round(predicted, 1) if predicted is not None else None,
                "pct_vs_baseline": round(total_pct, 1),
                "confidence": confidence,
                "min_n": min_n,
                "breakdown": matched,
            })

        return {
            "metric": metric_label,
            "metric_unit": METRIC_UNIT.get(metric_name, ""),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "days": days_out,
        }

    def _forecast_baselines(self, cur, metric_name, dates):
        """For each forecast date, compute the weekday-matched baseline
        (median of same-weekday values in the last 28 calendar days of
        historical data). Returns {date_str: float}."""
        if not dates:
            return {}
        agg_sql, _ = resolve_metric(metric_name)
        cur.execute(f"""
            WITH daily AS (
              SELECT t.date,
                     EXTRACT(ISODOW FROM t.date)::int AS dow,
                     {agg_sql} AS value
              FROM transactions t
              LEFT JOIN transaction_items i ON i.document_id = t.document_id
              WHERE EXTRACT(ISODOW FROM t.date) <> 7
              GROUP BY t.date
            ),
            targets AS (
              SELECT unnest(%s::date[]) AS d
            )
            SELECT targets.d,
                   (SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d2.value)
                    FROM daily d2
                    WHERE d2.dow = EXTRACT(ISODOW FROM targets.d)::int
                      AND d2.date BETWEEN targets.d - INTERVAL '28 days' AND targets.d - INTERVAL '1 day'
                   ) AS baseline
            FROM targets
        """, (dates,))
        out = {}
        for row in cur.fetchall():
            d = row["d"]
            b = row["baseline"]
            out[d.isoformat() if hasattr(d, "isoformat") else str(d)] = float(b) if b is not None else None
        return out
```

- [ ] **Step 2: Add the `_forecast_desc` module-level helper**

Right below the `_open_meteo_forecast` helper (the one from Task 1), add:

```python
def _forecast_desc(w):
    """Compact human-readable summary of a forecast day's weather."""
    bits = []
    tmax = w.get("temp_max"); tmin = w.get("temp_min")
    if tmax is not None and tmin is not None:
        bits.append(f"{float(tmin):.0f}..{float(tmax):.0f}°C")
    elif tmax is not None:
        bits.append(f"{float(tmax):.0f}°C")
    ps = w.get("precipitation_sum")
    if ps is not None and float(ps) >= 0.5:
        bits.append(f"{float(ps):.1f}mm ploaie")
    ss = w.get("snowfall_sum")
    if ss is not None and float(ss) >= 0.5:
        bits.append(f"{float(ss):.1f}cm zapada")
    wg = w.get("wind_gusts_max")
    if wg is not None and float(wg) >= 40:
        bits.append(f"vant {float(wg):.0f}km/h")
    cc = w.get("cloudcover_mean")
    if cc is not None:
        if float(cc) >= 85:
            bits.append("nori inchisi")
        elif float(cc) <= 20:
            bits.append("senin")
    return ", ".join(bits) if bits else "vreme calma"
```

- [ ] **Step 3: Wire into `do_GET` routing**

Search for the existing dispatch block in `do_GET` (around the line `elif qtype == "overview":`). Add a new branch **above** the final `else` clause:

```python
            elif qtype == "forecast":
                metric = params.get("metric", ["partners"])[0]
                result = self.forecast(cur, metric)
```

- [ ] **Step 4: Syntax check**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "import ast; ast.parse(open('api/weather.py', encoding='utf-8').read()); print('SYNTAX OK')"
```

Expected: `SYNTAX OK`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add api/weather.py && git commit -m "Add /api/weather?type=forecast endpoint (Phase 3)"
```

---

## Task 4: Backend — push + live smoke test

**Files:** (none changed in this task — verification only)

- [ ] **Step 1: Push to main and wait for Vercel**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git push
```

Wait ~90s for Vercel to rebuild.

- [ ] **Step 2: Hit the new endpoint live**

```bash
curl -s "https://internpaju.vercel.app/api/weather?type=forecast&metric=partners" | python -m json.tool | head -60
```

Expected: JSON with `metric: "partners"`, `days` array of 7 objects. First day should be today or tomorrow in `Europe/Bucharest` time. Each non-Sunday day has numeric `baseline`, `predicted`, `pct_vs_baseline`, `confidence`, `breakdown`.

Sunday in the range has `is_closed: true`, `predicted: null`.

If the endpoint returns `{"error": "forecast_unavailable"}`: Open-Meteo was unreachable from Vercel at request time — retry in 30s. If it persists after 2-3 minutes, something is wrong with the fetch helper — stop and debug.

If the endpoint returns a Python exception message: something is broken in the SQL or the dispatch — stop and debug the specific error.

- [ ] **Step 3: Sanity-check the values**

Pick any non-Sunday `day` in the response. Manually verify:
```
predicted ≈ baseline × (1 + pct_vs_baseline / 100)
```

Within ±0.1 (rounding). If this fails, the math in `forecast()` has a bug.

Also check that at least one day has a non-empty `breakdown` — meaning weather is matching some categories. If all `breakdown` arrays are empty, either all 7 days have unusually normal weather or the category-matching is broken.

---

## Task 5: Frontend — Sumar tab widget

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add the widget card in the Sumar section**

Open `index.html` and find the Sumar section (search for `id="section-overview"` — Sumar is called `overview` internally). Find the closing of the 6-card stat grid, then the "Top 10 parteneri" table. Insert this **between them**:

```html
            <div class="card" id="sumarForecastCard">
                <h2><span class="icon">🔮</span> Prognoza urmatoarele 7 zile</h2>
                <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;">
                    <label style="color:#888;font-size:0.85em;">Metrica:</label>
                    <select id="sumarForecastMetric" style="background:#1a1a2e;color:#fff;border:1px solid #333;padding:5px 8px;border-radius:4px;">
                        <option value="partners">Parteneri</option>
                        <option value="transactions">Tranzactii</option>
                        <option value="kg">Kg</option>
                        <option value="ron">RON</option>
                    </select>
                    <span style="color:#555;font-size:0.82em;margin-left:8px;">Bazat pe Open-Meteo + tiparele detectate</span>
                </div>
                <div id="sumarForecast"></div>
            </div>
```

- [ ] **Step 2: Add the loader + renderer at the end of the main `<script>` block**

Find the placeholder spot at the bottom of the main `<script>` block — after `loadMeteoExtreme` and before the closing `</script>`. Add:

```javascript

        // === Prognoza 7-zile — Sumar widget ===
        const METEO_EMOJI = {
            clear: "☀️", partly: "🌤️", cloudy: "☁️", rain: "🌧️",
            snow: "❄️", storm: "⛈️", fog: "🌫️", closed: "🔒",
        };
        function forecastEmoji(w) {
            if (w == null) return "❓";
            const code = w.weather_code;
            if (w.snowfall_sum != null && Number(w.snowfall_sum) >= 0.5) return METEO_EMOJI.snow;
            if (w.precipitation_sum != null && Number(w.precipitation_sum) >= 2) return METEO_EMOJI.rain;
            if (w.precipitation_sum != null && Number(w.precipitation_sum) >= 0.5) return "🌦️";
            if (w.cloudcover_mean != null && Number(w.cloudcover_mean) >= 80) return METEO_EMOJI.cloudy;
            if (w.cloudcover_mean != null && Number(w.cloudcover_mean) <= 25) return METEO_EMOJI.clear;
            return METEO_EMOJI.partly;
        }

        async function loadSumarForecast() {
            const host = document.getElementById('sumarForecast');
            if (!host) return;
            const metric = document.getElementById('sumarForecastMetric').value;
            host.innerHTML = '<p style="color:#888">Se incarca...</p>';
            try {
                const res = await fetch(`/api/weather?type=forecast&metric=${encodeURIComponent(metric)}`);
                const data = await res.json();
                if (data.error) {
                    host.innerHTML = `<p style="color:#ff9f40">Prognoza temporar nedisponibila. Reincarca pagina in cateva minute.</p>`;
                    return;
                }
                const unit = data.metric_unit || '';
                let html = '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:6px;">';
                data.days.forEach(d => {
                    const dayNum = d.date.slice(8,10);
                    if (d.is_closed) {
                        html += `<div style="padding:10px 6px;text-align:center;background:rgba(255,255,255,0.02);border-radius:6px;border:1px solid rgba(255,255,255,0.06);">
                            <div style="color:#aaa;font-size:0.8em;">${d.dow.slice(0,2)}</div>
                            <div style="color:#ccc;font-weight:600;">${dayNum}</div>
                            <div style="font-size:1.5em;margin:4px 0;">🔒</div>
                            <div style="color:#666;font-size:0.75em;">INCHIS</div>
                        </div>`;
                        return;
                    }
                    const pct = d.pct_vs_baseline ?? 0;
                    const color = pct > 5 ? '#00ff88' : (pct < -5 ? '#ff6b6b' : '#aaa');
                    const sign = pct >= 0 ? '+' : '';
                    const predicted = d.predicted != null ? Math.round(d.predicted) : '—';
                    const tmax = d.weather?.temp_max != null ? Math.round(d.weather.temp_max) : '';
                    const emoji = forecastEmoji(d.weather || {});
                    const tooltip = d.breakdown.slice(0,2).map(b => `${b.emoji} ${b.category}: ${b.effect_pct>=0?'+':''}${b.effect_pct}%`).join(' · ') || 'fara ajustare';
                    html += `<div title="${tooltip}" style="padding:10px 6px;text-align:center;background:rgba(0,217,255,0.04);border-radius:6px;border:1px solid rgba(0,217,255,0.1);cursor:pointer;" onclick="showSection('meteo')">
                        <div style="color:#aaa;font-size:0.8em;">${d.dow.slice(0,2)}</div>
                        <div style="color:#ccc;font-weight:600;">${dayNum}</div>
                        <div style="font-size:1.5em;margin:4px 0;">${emoji}</div>
                        <div style="color:#888;font-size:0.75em;">${tmax}${tmax !== '' ? '°' : ''}</div>
                        <div style="color:#fff;font-weight:600;font-size:1em;margin-top:4px;">${predicted}</div>
                        <div style="color:${color};font-size:0.82em;font-weight:600;">${sign}${pct.toFixed(0)}%</div>
                    </div>`;
                });
                html += '</div>';
                html += `<div style="color:#555;font-size:0.75em;margin-top:8px;">Generat: ${new Date(data.generated_at).toLocaleString('ro-RO')}</div>`;
                host.innerHTML = html;
            } catch (e) {
                host.innerHTML = `<p style="color:#ff6b6b">Eroare: ${e.message}</p>`;
            }
        }
```

- [ ] **Step 3: Wire the metric dropdown and initial load**

Search for `loadAllData` in the script. After `loadAllData()` fills everything else, append a call to `loadSumarForecast()`. Also wire the dropdown's `onchange` to reload.

Find `function loadAllData(` (or similar). At its end (just before the closing brace of the function), add:
```javascript
            loadSumarForecast();
            const m = document.getElementById('sumarForecastMetric');
            if (m && !m.dataset.bound) { m.dataset.bound = '1'; m.onchange = () => loadSumarForecast(); }
```

If `loadAllData` is async and returns from a try/catch, add this inside the try block right before it exits.

- [ ] **Step 4: Verify HTML/JS has everything**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "
with open('index.html','r',encoding='utf-8') as f: html = f.read()
for k in ['sumarForecastCard','sumarForecastMetric','sumarForecast','loadSumarForecast','forecastEmoji']:
    assert k in html, f'{k} missing'
print('Sumar widget wiring OK')
"
```

Expected: `Sumar widget wiring OK`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add index.html && git commit -m "Add Prognoza 7-zile widget to Sumar tab"
```

---

## Task 6: Frontend — Meteo tab detailed card

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add the card at the top of `section-meteo`**

Find `<div id="section-meteo" class="section">` (from Phase 2). Inside, **as the first child** (before the existing "🌦️ Meteo & Trafic" intro card), insert:

```html
            <div class="card" id="meteoForecastCard">
                <h2><span class="icon">🔮</span> Prognoza 7 zile — trafic estimat</h2>
                <p style="color:#888;font-size:0.85em;margin-bottom:10px;">
                    Bazat pe forecast meteo Open-Meteo + tiparele detectate in datele tale istorice. Fiecare efect se aduna independent. Duminica = inchis (fara program).
                </p>
                <div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;">
                    <label style="color:#888;font-size:0.85em;">Metrica:</label>
                    <select id="meteoForecastMetric" style="background:#1a1a2e;color:#fff;border:1px solid #333;padding:5px 8px;border-radius:4px;">
                        <option value="partners">Parteneri</option>
                        <option value="transactions">Tranzactii</option>
                        <option value="kg">Kg</option>
                        <option value="ron">RON</option>
                    </select>
                </div>
                <div id="meteoForecast"></div>
            </div>
```

- [ ] **Step 2: Add the detailed loader/renderer**

At the end of the main `<script>` block (right after `loadSumarForecast`), add:

```javascript

        // === Prognoza 7-zile — Meteo tab detailed card ===
        async function loadMeteoForecast() {
            const host = document.getElementById('meteoForecast');
            if (!host) return;
            const metric = document.getElementById('meteoForecastMetric').value;
            host.innerHTML = '<p style="color:#888">Se incarca...</p>';
            try {
                const res = await fetch(`/api/weather?type=forecast&metric=${encodeURIComponent(metric)}`);
                const data = await res.json();
                if (data.error) {
                    host.innerHTML = '<p style="color:#ff9f40">Prognoza temporar nedisponibila. Reincarca in cateva minute.</p>';
                    return;
                }
                const unit = data.metric_unit || '';
                let html = '';
                data.days.forEach(d => {
                    if (d.is_closed) {
                        html += `<div style="padding:12px 16px;margin-bottom:10px;background:rgba(255,255,255,0.03);border-left:3px solid #555;border-radius:4px;">
                            <div style="color:#aaa;font-size:0.95em;">📅 <strong>${d.dow} ${d.date}</strong> · 🔒 INCHIS (fara program Duminica)</div>
                        </div>`;
                        return;
                    }
                    const pct = d.pct_vs_baseline ?? 0;
                    const color = pct > 2 ? '#00ff88' : (pct < -2 ? '#ff6b6b' : '#aaa');
                    const sign = pct >= 0 ? '+' : '';
                    const predicted = d.predicted != null ? Math.round(d.predicted) : '—';
                    const baseline = d.baseline != null ? Math.round(d.baseline) : '—';
                    const emoji = forecastEmoji(d.weather || {});
                    const confColor = d.confidence === 'high' ? '#00ff88' : (d.confidence === 'low' ? '#ff9f40' : '#888');
                    const confLabel = d.confidence === 'high' ? 'mare' : (d.confidence === 'low' ? 'scazuta' : 'ok');
                    let brHtml = '';
                    if (d.breakdown.length) {
                        d.breakdown.forEach(b => {
                            const bc = b.effect_pct > 2 ? '#00ff88' : (b.effect_pct < -2 ? '#ff6b6b' : '#888');
                            const bs = b.effect_pct >= 0 ? '+' : '';
                            brHtml += `<div style="display:grid;grid-template-columns:1fr 80px 70px;gap:8px;color:#bbb;padding:2px 0;">
                                <span>${b.emoji} ${b.category} <span style="color:#666;font-size:0.85em;">(${b.range})</span></span>
                                <span style="color:${bc};text-align:right;font-weight:600;">${bs}${b.effect_pct.toFixed(1)}%</span>
                                <span style="color:#555;text-align:right;font-size:0.85em;">${b.n} zile</span>
                            </div>`;
                        });
                        brHtml += `<div style="display:grid;grid-template-columns:1fr 80px 70px;gap:8px;padding-top:6px;margin-top:6px;border-top:1px solid rgba(255,255,255,0.06);color:#eee;font-weight:600;">
                            <span>Total ajustare</span>
                            <span style="color:${color};text-align:right;">${sign}${pct.toFixed(1)}%</span><span></span>
                        </div>`;
                    } else {
                        brHtml = '<div style="color:#666;font-style:italic;">Nicio categorie meteo semnificativa — vreme "normala".</div>';
                    }
                    html += `<div style="padding:14px 16px;margin-bottom:12px;background:rgba(0,217,255,0.03);border-left:3px solid ${color};border-radius:4px;">
                        <div style="font-size:1.05em;color:#fff;font-weight:600;margin-bottom:3px;">📅 ${d.dow} ${d.date} · ${emoji} ${d.weather_desc}</div>
                        <div style="color:#ddd;margin-bottom:8px;">Estimat: <strong style="color:#fff;">~${predicted}</strong> ${unit} · <strong style="color:${color};">${sign}${pct.toFixed(1)}%</strong> vs ${d.dow} normal (baseline ${baseline}) · <span style="color:${confColor};">confidence ${confLabel}</span> <span style="color:#555;font-size:0.85em;">(min ${d.min_n} zile similare)</span></div>
                        <div style="font-size:0.9em;">Cauze:</div>
                        ${brHtml}
                    </div>`;
                });
                host.innerHTML = html;
            } catch (e) {
                host.innerHTML = `<p style="color:#ff6b6b">Eroare: ${e.message}</p>`;
            }
        }
```

- [ ] **Step 3: Wire into Meteo tab's initial load**

Find `loadMeteo()` (the Phase 2 function). At its end (inside the existing body), add:

```javascript
            loadMeteoForecast();
            const mfm = document.getElementById('meteoForecastMetric');
            if (mfm && !mfm.dataset.bound) { mfm.dataset.bound = '1'; mfm.onchange = () => loadMeteoForecast(); }
```

- [ ] **Step 4: Verify**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && python -c "
with open('index.html','r',encoding='utf-8') as f: html = f.read()
for k in ['meteoForecastCard','meteoForecastMetric','meteoForecast','loadMeteoForecast']:
    assert k in html, f'{k} missing'
print('Meteo forecast card OK')
"
```

Expected: `Meteo forecast card OK`

- [ ] **Step 5: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add index.html && git commit -m "Add Prognoza 7-zile detailed card to Meteo tab"
```

---

## Task 7: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add the new endpoint to the `/api/weather` table**

Find the `/api/weather` section (inserted in Phase 2). At the bottom of its endpoint table, add a new row:

```markdown
| `type=forecast&metric=X` | Prognoza 7 zile (Open-Meteo + pattern lookup) |
```

- [ ] **Step 2: Commit**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git add CLAUDE.md && git commit -m "Document /api/weather?type=forecast in CLAUDE.md"
```

---

## Task 8: Push, live verification, no merge (already on main)

**Files:** (none — verification only)

- [ ] **Step 1: Push all remaining commits**

```bash
cd C:/Users/INTEL/Desktop/Projektek/Vercelek/paju && git push
```

- [ ] **Step 2: Wait for Vercel deploy and visit live**

Wait ~90s. Then open the deployed URL in a browser.

- [ ] **Step 3: Verify Sumar widget**

Visit `https://internpaju.vercel.app/`. Log in if prompted. On the **Sumar** tab, the new "🔮 Prognoza urmatoarele 7 zile" card should appear between the stat cards and the Top 10 table. Check:
- 7 columns visible (Luni through Duminica for the upcoming week)
- Each column shows a weekday abbrev, day number, weather emoji, temperature, predicted value, percent delta
- Sunday column shows 🔒 INCHIS
- Metric dropdown switches numbers

- [ ] **Step 4: Verify Meteo card**

Click the **Meteo** tab. At the very top, above the Clasament, a new card "🔮 Prognoza 7 zile — trafic estimat" should appear. Check:
- 7 day blocks shown, one per row
- Each non-Sunday block has: date + weather desc, estimated value, percent vs baseline, confidence, breakdown table summing to the total
- Sunday block has a muted "🔒 INCHIS" line only
- Metric dropdown switches all numbers

- [ ] **Step 5: Quality check**

Pick one visible day from the Meteo card. Do the math manually:
- Read `baseline`, `breakdown` entries and `Total ajustare`
- `sum(breakdown effect_pct) ≈ Total ajustare` — off by at most 0.1 due to rounding
- `predicted ≈ baseline × (1 + Total ajustare / 100)` — same tolerance

If this matches, the feature is working.

- [ ] **Step 6: Done**

This feature lives on `main`. No merge needed (we worked on `main` directly per the simpler flow).

---

## Rollback Plan

If the forecast endpoint breaks the page (e.g. API outage causes repeated failures):
```bash
git revert HEAD~N..HEAD   # N = number of commits in this plan
git push
```
Vercel redeploys within 1-2 minutes. The dashboard returns to its pre-forecast state cleanly because all changes are additive (new endpoint, new HTML card, new JS functions).

## Follow-ups (not in this plan)

- DB cache for forecast (new `weather_forecast` table refreshed nightly) if Open-Meteo rate-limits us.
- Prediction accuracy tracking (store each day's prediction, compare 48h later against actual, surface cumulative error %).
- Scenario simulator ("what if it rains 20mm tomorrow?") with editable weather inputs.
- Morning email summary using the same endpoint.
