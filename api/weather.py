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
            else:
                result = {"error": "Unknown query type", "got": qtype}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        self._send(405, {"error": "POST not supported on /api/weather"})
