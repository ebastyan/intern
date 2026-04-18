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
