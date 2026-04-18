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

    def list_holidays(self, cur, year):
        if year:
            cur.execute(
                "SELECT date, name, type, is_official FROM holidays WHERE EXTRACT(year FROM date) = %s ORDER BY date",
                (int(year),),
            )
        else:
            cur.execute("SELECT date, name, type, is_official FROM holidays ORDER BY date")
        return [dict(r) for r in cur.fetchall()]

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            query_type = params.get('type', [''])[0]

            conn = get_db()
            cur = conn.cursor()

            if query_type == 'ping':
                result = {'ok': True, 'endpoint': 'calendar'}
            elif query_type == 'holidays':
                year = params.get('year', [None])[0]
                result = {'holidays': self.list_holidays(cur, year)}
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
