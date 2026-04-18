"""
Weather API - Meteo & Trafic analysis
Endpoints:
  GET /api/weather?type=ping
  GET /api/weather?type=residuals&metric=partners&date_from=X&date_to=Y
  GET /api/weather?type=buckets&variable=rain_sum&metric=partners
  GET /api/weather?type=lag_curve&variable=rain_sum&metric=partners
  GET /api/weather?type=extreme_days&metric=partners&limit=20
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

class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload, default=json_default).encode("utf-8"))

    def residuals(self, cur, metric_name, date_from, date_to):
        agg_sql, label = resolve_metric(metric_name)
        where = ["EXTRACT(ISODOW FROM t.date) <> 7"]
        args = []
        if date_from: where.append("t.date >= %s"); args.append(date_from)
        if date_to:   where.append("t.date <= %s"); args.append(date_to)
        where_sql = " AND ".join(where)

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

    def buckets(self, cur, metric_name, variable, date_from, date_to):
        if variable not in BUCKET_SPECS:
            return {"error": f"No bucket spec for variable {variable}",
                    "available": list(BUCKET_SPECS.keys())}
        data = self.residuals(cur, metric_name, date_from, date_to)
        rows = [r for r in data["residuals"] if r["residual"] is not None and r.get(variable) is not None]
        out = []
        for lo, hi, label in BUCKET_SPECS[variable]:
            in_bucket_res = []
            in_bucket_base = []
            for r in rows:
                v = float(r[variable])
                if lo is not None and v < lo: continue
                if hi is not None and v >= hi: continue
                in_bucket_res.append(r["residual"])
                if r["baseline"] is not None:
                    in_bucket_base.append(float(r["baseline"]))
            if not in_bucket_res:
                out.append({"bucket": label, "lo": lo, "hi": hi, "n": 0,
                            "mean_residual": None, "mean_residual_pct": None})
                continue
            mean = sum(in_bucket_res) / len(in_bucket_res)
            mean_b = sum(in_bucket_base) / len(in_bucket_base) if in_bucket_base else None
            pct = (mean / mean_b * 100.0) if mean_b else None
            out.append({"bucket": label, "lo": lo, "hi": hi, "n": len(in_bucket_res),
                        "mean_residual": round(mean, 2),
                        "mean_residual_pct": round(pct, 2) if pct is not None else None})
        return {"metric": data["metric"], "variable": variable, "buckets": out}

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            qtype = params.get("type", [""])[0]

            conn = get_db()
            cur = conn.cursor()

            if qtype == "ping":
                result = {"ok": True, "endpoint": "weather"}
            elif qtype == "residuals":
                metric = params.get("metric", ["partners"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.residuals(cur, metric, df, dt)
            elif qtype == "buckets":
                metric = params.get("metric", ["partners"])[0]
                variable = params.get("variable", ["rain_sum"])[0]
                df = params.get("date_from", [None])[0]
                dt = params.get("date_to", [None])[0]
                result = self.buckets(cur, metric, variable, df, dt)
            else:
                result = {"error": "Unknown query type", "got": qtype}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        self._send(405, {"error": "POST not supported on /api/weather"})
