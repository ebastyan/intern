# scripts/fetch_weather.py
"""Fetch historical daily weather for Oradea and upsert into weather_oradea.

Usage:
  python scripts/fetch_weather.py --self-test
  python scripts/fetch_weather.py
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

def _get_json(url):
    req = Request(url, headers={"User-Agent": "paju-dashboard/1.0"})
    with urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def fetch_range(date_from, date_to):
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

    d_dates = daily_resp["daily"]["time"]
    per_day = {}
    for api_field, col in COLUMN_MAP.items():
        arr = daily_resp["daily"].get(api_field, [None] * len(d_dates))
        for i, dstr in enumerate(d_dates):
            per_day.setdefault(dstr, {})[col] = arr[i] if i < len(arr) else None

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
    d = date.today() - timedelta(days=14)
    rows = fetch_range(d, d)
    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    r = rows[0]
    assert r["date"] == d.isoformat()
    assert r.get("temp_max") is not None, "temp_max missing"
    assert r.get("precipitation_sum") is not None, "precipitation_sum missing"
    print(f"Self-test OK: {d} -> temp_max={r['temp_max']}, precip_sum={r['precipitation_sum']}, wind_max={r.get('wind_speed_max')}, pressure_mean={r.get('pressure_mean')}")

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
