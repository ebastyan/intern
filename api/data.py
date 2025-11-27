from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db():
    return psycopg2.connect(
        os.environ.get('POSTGRES_URL'),
        cursor_factory=RealDictCursor
    )

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            conn = get_db()
            cur = conn.cursor()

            # Get yearly summaries
            cur.execute("SELECT * FROM yearly_summary ORDER BY year")
            yearly = cur.fetchall()

            # Get monthly summaries
            cur.execute("SELECT * FROM monthly_summary ORDER BY year, month")
            monthly = cur.fetchall()

            # Get yearly category totals
            cur.execute("""
                SELECT year, category, total_kg
                FROM category_totals
                WHERE month IS NULL
                ORDER BY year, total_kg DESC
            """)
            categories = cur.fetchall()

            # Organize data
            result = {
                'years': {}
            }

            for y in yearly:
                year = str(y['year'])
                result['years'][year] = {
                    'summary': {
                        'total_value': float(y['total_value']),
                        'transactions': y['transactions'],
                        'working_days': y['working_days'],
                        'avg_per_day': float(y['avg_per_day']),
                        'avg_per_month': float(y['avg_per_month'])
                    },
                    'months': {},
                    'total_by_category': {}
                }

            # Get weekday patterns
            cur.execute("""
                SELECT year, month, weekday_name, avg_value, avg_transactions, days_count
                FROM weekday_patterns
            """)
            weekday_data = cur.fetchall()

            for m in monthly:
                year = str(m['year'])
                month = str(m['month']).zfill(2)
                result['years'][year]['months'][month] = {
                    'period': m['period'],
                    'summary': {
                        'total_value': float(m['total_value']),
                        'total_paid': float(m['total_paid']) if m['total_paid'] else 0,
                        'transactions': m['transactions'],
                        'working_days': m['working_days'],
                        'unique_partners': m['unique_partners'],
                        'avg_per_day': float(m['avg_per_day']),
                        'avg_per_trans': float(m['avg_per_trans']),
                        'best_day': {'date': m['best_day_date'], 'value': float(m['best_day_value'])} if m['best_day_date'] else None,
                        'worst_day': {'date': m['worst_day_date'], 'value': float(m['worst_day_value'])} if m['worst_day_date'] else None
                    },
                    'weekday_patterns': {}
                }

            # Add weekday patterns to months
            for w in weekday_data:
                year = str(w['year'])
                month = str(w['month']).zfill(2)
                if year in result['years'] and month in result['years'][year]['months']:
                    result['years'][year]['months'][month]['weekday_patterns'][w['weekday_name']] = {
                        'avg_value': float(w['avg_value']),
                        'avg_transactions': w['avg_transactions'],
                        'days_count': w['days_count']
                    }

            for c in categories:
                year = str(c['year'])
                result['years'][year]['total_by_category'][c['category']] = float(c['total_kg'])

            cur.close()
            conn.close()

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())
