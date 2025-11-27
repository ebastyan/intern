from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qs

def get_db():
    return psycopg2.connect(
        os.environ.get('POSTGRES_URL'),
        cursor_factory=RealDictCursor
    )

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Parse query params
            query = parse_qs(urlparse(self.path).query)
            year = query.get('year', [None])[0]
            month = query.get('month', [None])[0]

            conn = get_db()
            cur = conn.cursor()

            if year and month:
                # Get specific month data including daily
                cur.execute("""
                    SELECT * FROM monthly_summary
                    WHERE year = %s AND month = %s
                """, (int(year), int(month)))
                monthly = cur.fetchone()

                cur.execute("""
                    SELECT * FROM daily_data
                    WHERE year = %s AND month = %s
                    ORDER BY day
                """, (int(year), int(month)))
                daily = cur.fetchall()

                cur.execute("""
                    SELECT * FROM weekday_patterns
                    WHERE year = %s AND month = %s
                """, (int(year), int(month)))
                weekday = cur.fetchall()

                cur.execute("""
                    SELECT category, total_kg FROM category_totals
                    WHERE year = %s AND month = %s
                    ORDER BY total_kg DESC
                """, (int(year), int(month)))
                categories = cur.fetchall()

                result = {
                    'period': f'{year}-{month.zfill(2)}',
                    'summary': {
                        'total_value': float(monthly['total_value']),
                        'transactions': monthly['transactions'],
                        'working_days': monthly['working_days']
                    } if monthly else None,
                    'daily': {d['date_key']: {
                        'day': d['day'],
                        'weekday': d['weekday'],
                        'weekday_short': d['weekday_short'],
                        'total_value': float(d['total_value']),
                        'transactions': d['transactions'],
                        'top5_categories': d['top5_categories']
                    } for d in daily},
                    'weekday_patterns': {w['weekday_name']: {
                        'days_count': w['days_count'],
                        'avg_value': float(w['avg_value']),
                        'avg_transactions': w['avg_transactions']
                    } for w in weekday},
                    'total_by_category': {c['category']: float(c['total_kg']) for c in categories}
                }
            else:
                # Get all months summary
                cur.execute("""
                    SELECT year, month, period, total_value, transactions, working_days
                    FROM monthly_summary
                    ORDER BY year, month
                """)
                result = {'months': cur.fetchall()}

            cur.close()
            conn.close()

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result, default=str).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
