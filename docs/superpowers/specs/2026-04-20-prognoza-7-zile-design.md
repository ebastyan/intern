# Prognoza 7-zile — Design Spec

**Date:** 2026-04-20
**Author:** pap.sebastian@gmail.com (ebastyan)
**Follows from:** Phase 2 Meteo & Trafic (live in `main`)

## 1. Overview

Given that Phase 2 quantifies how each weather category moves traffic against a weekday-matched baseline, the next natural step is forward-looking: **show the user what the next 7 days are likely to look like**. Turn the existing hindcast engine into a forecast.

Two surfaces:
- **Sumar tab widget** — compact 7-day strip, single-glance morning overview.
- **Meteo tab card** (top of tab) — full detail per day with breakdown of why the estimate landed where it did.

Both surfaces share one backend endpoint; same metric dropdown as existing Meteo UI (partners / transactions / kg / RON).

## 2. Motivation

- Current dashboard is 100% backward-looking. User wants actionable forward info: "how many staff tomorrow?", "how much cash to keep on hand?".
- All the ingredients exist: baseline computation, weather-category effects, a 2,299-day historical weather table. Just need to plug forecast data in.
- Open-Meteo's `/v1/forecast` endpoint is the forecast counterpart to `/v1/archive` we already use. Free, no key, same coordinates, same response shape as daily/hourly archive data.

## 3. Scope

In scope:
- New `GET /api/weather?type=forecast&metric=partners` endpoint returning 7 days forward.
- New `scripts/fetch_forecast.py` (reuses logic from `fetch_weather.py` but talks to `/v1/forecast`). Called directly from the API endpoint on each request — no DB caching in MVP.
- Sumar widget — one compact card, responsive layout, 7 day columns.
- Meteo tab top card — 7 expandable/inline day blocks with full breakdown.

Out of scope (not in this plan):
- Caching forecast in DB (revisit if API becomes slow or rate-limited).
- Forecast accuracy tracking over time (comparing past predictions vs actuals).
- Longer forecast horizon (> 7 days) — Open-Meteo supports up to 16, but accuracy drops fast; keep 7 for MVP.
- Alerts / notifications ("tomorrow will be very bad — warn the user").
- Manual weather override ("what if it rains 20mm tomorrow?") — scenario simulator is a separate feature.

## 4. Prediction Model

For each forecast day `D` with weekday `W` and forecast weather `F`:

```
baseline(D) = median(actual[W] over last 28 calendar days of real data)
```

(identical to the formula already used by `/api/weather?type=residuals`.)

For each weather dimension the forecast provides (temp_max, temp_min, precipitation_sum, snowfall_sum, wind_gusts_max, humidity_mean, cloudcover_mean), look up which category `F` falls into from the existing `CATEGORIES` table in `api/weather.py`. For each matching category, retrieve the previously-computed `effect_pct` (same logic used by the `ranking` in the `overview` endpoint, but computed once across ALL historical data, not filtered to the user's selected range).

Sum the per-dimension effects additively:

```
total_pct = sum(effect_pct for each matching category)
predicted(D) = baseline(D) * (1 + total_pct / 100)
```

### Example

Forecast for a Wednesday: `temp_max=8°C, precipitation_sum=5mm, cloudcover_mean=92%`
- `temp_max=8°C` → `Rece (5..10°C max)` → effect_pct e.g. −1.8%, n=170
- `precipitation_sum=5mm` → `Ploaie moderata (5-10mm)` → e.g. −5.2%, n=48
- `cloudcover_mean=92%` → `Mohorat (nori >90%)` → e.g. −0.5%, n=310

```
total_pct = -1.8 + -5.2 + -0.5 = -7.5%
baseline for a Wednesday = 89 partners (28-day Wednesday median)
predicted = 89 * (1 - 0.075) = 82 partners
```

### Confidence tiers

The **minimum n across the matched categories** drives the confidence label:

- `high`: min_n ≥ 100 — deep sample, solid prediction
- `ok`: 30 ≤ min_n < 100
- `low`: min_n < 30 — warn the user (orange badge); show the prediction but mark it as tentative

### Sundays

Sundays are always closed (no opening hours). Forecast cards for Sunday display `🔒 INCHIS` and no prediction — no baseline, no adjusted figure.

### Missing weather dimensions

Open-Meteo historical covers everything, but the forecast endpoint occasionally omits some (e.g. `sunshine_duration` for very short-range). Missing dimensions are silently skipped — the matching categories simply aren't added to the sum. The UI notes `(based on N dimensions)` if fewer than the full 6 contributed.

## 5. Backend

### 5.1 New endpoint

```
GET /api/weather?type=forecast&metric=partners
```

Parameters:
- `metric` — one of `partners | transactions | kg | ron`. Defaults to `partners`.

No date parameters — always "today + 7 days forward" from server time.

Response shape:
```json
{
  "metric": "partners",
  "generated_at": "2026-04-20T06:31:00+03:00",
  "days": [
    {
      "date": "2026-04-20",
      "dow": "Luni",
      "is_closed": false,
      "weather": {
        "temp_max": 11, "temp_min": 5,
        "precipitation_sum": 2.1, "snowfall_sum": 0,
        "wind_gusts_max": 34, "humidity_mean": 78,
        "cloudcover_mean": 65, "weather_code": 61
      },
      "weather_desc": "5..11°C, 2.1mm ploaie, vant 34km/h",
      "baseline": 92.5,
      "predicted": 85.4,
      "pct_vs_baseline": -7.7,
      "confidence": "ok",
      "min_n": 42,
      "breakdown": [
        { "category": "Rece (5..10°C max)", "effect_pct": -1.8, "n": 170 },
        { "category": "Ploaie usoara (2-5mm)", "effect_pct": -3.4, "n": 118 },
        { "category": "Rafale medii (50-70km/h)", "effect_pct": -2.5, "n": 48 }
      ]
    },
    { "date": "2026-04-21", ... },
    { "date": "2026-04-22", ... },
    ...
    { "date": "2026-04-26", "is_closed": true, "dow": "Duminica", "predicted": null }
  ]
}
```

### 5.2 Implementation notes

- Put the Open-Meteo fetch in `api/weather.py` next to the historical fetch pattern. Use `urllib` (stdlib, already in the project).
- Reuse `CATEGORIES` list from the same file.
- Compute `effect_pct` per category using the existing `buckets` method restricted to all data (no user date range), or precompute once per request (cheap — ~1500 tx-days × 25 categories).
- Baseline per future day: same SQL as `residuals` but using future `d.date`. The subquery for `PERCENTILE_CONT(0.5) ... WHERE d2.date BETWEEN d.date - 28 days AND d.date - 1 day` works naturally for future dates because `d2` covers the full history.

### 5.3 Forecast API shape (Open-Meteo)

```
https://api.open-meteo.com/v1/forecast?
  latitude=47.0722&longitude=21.9217&
  timezone=Europe/Bucharest&
  forecast_days=7&
  daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,
    apparent_temperature_max,apparent_temperature_min,
    precipitation_sum,rain_sum,snowfall_sum,snow_depth_max,
    precipitation_hours,windspeed_10m_max,windgusts_10m_max,
    winddirection_10m_dominant,shortwave_radiation_sum,
    sunshine_duration,daylight_duration,et0_fao_evapotranspiration,
    weather_code&
  hourly=pressure_msl,relativehumidity_2m,cloudcover
```

Same shape as historical, just a different base URL and `forecast_days` instead of `start_date/end_date`. The hourly-derived daily means (pressure, humidity, cloud) are computed on the server side before returning — same code path as `fetch_weather.py`.

### 5.4 Error handling

- Open-Meteo 5xx / network timeout → return `{"error": "forecast_unavailable", "retry_after_seconds": 300}`. Frontend shows a muted retry-later message. No stack trace surfaced.
- Partial response (fewer than 7 days) → return what we have. Frontend fills gaps with "Nedisponibil".

## 6. Frontend

### 6.1 Sumar tab widget

Placement: a new card inside the existing Sumar section. Insert BELOW the big 6 stat cards (so the at-a-glance numbers stay first) but ABOVE the "Top 10 parteneri" table. Collapsible — has its own toggle/close so user can dismiss if they want.

Layout — 7 column horizontal strip:

```
┌────────────────────────────────────────────────────────────────────┐
│  🔮 Prognoza urmatoarele 7 zile          [partners ▾]              │
├────┬────┬────┬────┬────┬────┬──────────────────────────────────────┤
│ Lu │ Ma │ Mi │ Jo │ Vi │ Sa │  Du                                  │
│ 20 │ 21 │ 22 │ 23 │ 24 │ 25 │  26                                  │
│ ☀️ │ 🌧️│ 🌧️│ ☀️ │ ☀️ │ ☁️ │  🔒                                  │
│11° │ 8° │10° │16° │18° │14° │  —                                  │
│ 92 │ 78 │ 82 │110 │115 │ 85 │ INCHIS                               │
│ ≈  │−12%│−8% │+18%│+24%│ +1%│                                      │
└────┴────┴────┴────┴────┴────┴──────────────────────────────────────┘
```

Color coding: green if `pct_vs_baseline > 5`, red if `< -5`, gray otherwise. Hover on a column shows a small popup with the top 2 breakdown contributors. Clicking jumps to the Meteo tab with that day scrolled into view.

Metric dropdown changes all 7 numbers simultaneously (same pattern as existing Meteo tab controls).

Responsive: on narrower screens the 7 columns wrap into two rows, or scroll horizontally.

### 6.2 Meteo tab card

Placement: a new card at the **top** of the Meteo tab (before the existing "🎓 Ce invata datele" card), so whenever the user opens Meteo the first thing they see is the forward-looking view.

Layout — 7 day blocks, each:

```
┌──────────────────────────────────────────────────────┐
│ 📅 Marti 21 Apr · 🌧️ 3..8°C, ploaie 8mm, vant 45km/h │
│                                                       │
│ Estimat: ~78 parteneri                               │
│ −12% fata de o zi Marti normala (baseline 89)        │
│ Confidence: ok (bazat pe 42 zile similare)           │
│                                                       │
│ Cauze:                                                │
│   🌧️ Ploaie moderata (5-10mm)    −5.2%  (48 zile)   │
│   🥶 Frig (0..5°C max)            −4.3%  (128 zile)  │
│   💨 Rafale medii (50-70km/h)     −2.5%  (48 zile)   │
│   ───────────────────────────────────                │
│   Total ajustare                  −12.0%              │
└──────────────────────────────────────────────────────┘
```

Each block is one row in a single-column flex layout (full width). Metric dropdown at the top of the whole card. Low-confidence days get an orange `⚠ low` badge. Sunday shows as `🔒 INCHIS` without any numbers.

A single info line at the top of the card explains the methodology briefly:

> Bazat pe forecast meteo Open-Meteo + tiparele detectate in datele istorice. Fiecare efect se aduna independent. Prognoza pentru Duminica = inchis (program).

## 7. Data Flow Summary

```
User opens dashboard
  │
  ├─ Sumar tab first-load:
  │    loadAllData() runs (existing), appends:
  │    fetch('/api/weather?type=forecast&metric=partners')
  │    → render widget
  │
  └─ Meteo tab first-click:
       loadMeteo() runs (existing), appends:
       fetch('/api/weather?type=forecast&metric=<current>')
       → render top card before calling overview
```

Both surfaces share one fetch per metric per page-load — clicking the metric dropdown on either surface re-fetches that surface only.

## 8. Testing

- Manual: visit the Vercel preview URL, Sumar shows widget, Meteo shows top card.
- Spot-check: for a known day 2 days from now, predicted ≈ baseline × (1 + breakdown_total%). Mental arithmetic, no test framework.
- Edge case: set laptop clock ahead to a Sunday — card should show INCHIS for that day.
- Edge case: disconnect network → graceful degradation (card shows "prognoza nedisponibila").

## 9. Non-goals

- No model retraining or ML — pure lookup into existing hindcast effects.
- No historical forecast-vs-actual tracking (would need a separate `forecast_history` table + cron).
- No email / push notifications on predicted bad days.
- No multi-location forecasts (Oradea only, like everything else in this project).
- No manual scenario simulator ("what if it rains 15mm?") — separate feature if requested.

## 10. Follow-ups

- If user likes the daily feel, add a small morning email summary — reuse the same endpoint.
- Compare prediction vs actual the day after to build trust in the numbers (record prediction, compare 48h later).
- Add a "this exact weather happened on X date, here's what actually happened" deep-link from each breakdown row to the detail of that historical day.
