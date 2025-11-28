"""
Monthly API - Részletes havi adatok
GET /api/monthly?year=2024&month=10 - Specifikus hónap részletei
GET /api/monthly - Összes hónap összefoglalója
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qs
from decimal import Decimal

def get_db():
    # Try multiple environment variable names
    db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL_NO_SSL')
    if not db_url:
        raise Exception("No database URL configured")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

# Romanian weekday names
WEEKDAY_NAMES = {
    0: 'Duminica',
    1: 'Luni',
    2: 'Marti',
    3: 'Miercuri',
    4: 'Joi',
    5: 'Vineri',
    6: 'Sambata'
}

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
                result = self.get_month_details(cur, int(year), int(month))
            else:
                result = self.get_all_months(cur)

            cur.close()
            conn.close()

            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result, default=decimal_default, ensure_ascii=False).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def get_month_details(self, cur, year, month):
        """Get detailed data for a specific month"""
        # Monthly summary
        cur.execute("""
            SELECT COUNT(*) as transactions,
                   COUNT(DISTINCT date) as working_days,
                   COUNT(DISTINCT cnp) as unique_partners,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COALESCE(SUM(net_paid), 0) as total_paid
            FROM transactions
            WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s
        """, (year, month))
        summary = cur.fetchone()

        if summary['transactions'] == 0:
            return {'error': f'No data for {year}-{str(month).zfill(2)}'}

        # Daily breakdown
        cur.execute("""
            SELECT date,
                   EXTRACT(DAY FROM date)::int as day,
                   EXTRACT(DOW FROM date)::int as weekday,
                   COUNT(*) as transactions,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COUNT(DISTINCT cnp) as unique_partners
            FROM transactions
            WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s
            GROUP BY date
            ORDER BY date
        """, (year, month))
        daily_data = cur.fetchall()

        # Weekday patterns
        cur.execute("""
            SELECT EXTRACT(DOW FROM date)::int as weekday,
                   COUNT(*) as transactions,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COUNT(DISTINCT date) as days_count
            FROM transactions
            WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s
            GROUP BY EXTRACT(DOW FROM date)
            ORDER BY weekday
        """, (year, month))
        weekday_data = cur.fetchall()

        # Category breakdown
        cur.execute("""
            SELECT wc.name as category,
                   COALESCE(SUM(ti.weight_kg), 0) as total_kg,
                   COALESCE(SUM(ti.value), 0) as total_value
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            WHERE EXTRACT(YEAR FROM t.date) = %s AND EXTRACT(MONTH FROM t.date) = %s
            GROUP BY wc.name
            ORDER BY total_kg DESC
        """, (year, month))
        categories = cur.fetchall()

        # Top transactions
        cur.execute("""
            SELECT t.document_id, t.date, p.name, t.gross_value
            FROM transactions t
            LEFT JOIN partners p ON t.cnp = p.cnp
            WHERE EXTRACT(YEAR FROM t.date) = %s AND EXTRACT(MONTH FROM t.date) = %s
            ORDER BY t.gross_value DESC
            LIMIT 10
        """, (year, month))
        top = cur.fetchall()

        # Format daily data
        daily = {}
        for d in daily_data:
            date_key = str(d['date'])
            daily[date_key] = {
                'day': d['day'],
                'weekday': WEEKDAY_NAMES.get(d['weekday'], ''),
                'weekday_short': WEEKDAY_NAMES.get(d['weekday'], '')[:2],
                'total_value': float(d['total_value']),
                'transactions': d['transactions'],
                'unique_partners': d['unique_partners']
            }

        # Format weekday patterns
        weekday_patterns = {}
        for w in weekday_data:
            weekday_name = WEEKDAY_NAMES.get(w['weekday'], '')
            weekday_patterns[weekday_name] = {
                'days_count': w['days_count'],
                'avg_value': float(w['total_value']) / w['days_count'] if w['days_count'] > 0 else 0,
                'avg_transactions': w['transactions'] // w['days_count'] if w['days_count'] > 0 else 0
            }

        return {
            'period': f'{year}-{str(month).zfill(2)}',
            'summary': {
                'total_value': float(summary['total_value']),
                'total_paid': float(summary['total_paid']),
                'transactions': summary['transactions'],
                'working_days': summary['working_days'],
                'unique_partners': summary['unique_partners'],
                'avg_per_day': float(summary['total_value']) / summary['working_days'] if summary['working_days'] > 0 else 0
            },
            'daily': daily,
            'weekday_patterns': weekday_patterns,
            'total_by_category': {c['category']: float(c['total_kg']) for c in categories},
            'top_transactions': [{
                'document_id': t['document_id'],
                'date': str(t['date']),
                'partner': t['name'],
                'value': float(t['gross_value'])
            } for t in top]
        }

    def get_all_months(self, cur):
        """Get summary of all months"""
        cur.execute("""
            SELECT EXTRACT(YEAR FROM date)::int as year,
                   EXTRACT(MONTH FROM date)::int as month,
                   COUNT(*) as transactions,
                   COUNT(DISTINCT date) as working_days,
                   COALESCE(SUM(gross_value), 0) as total_value
            FROM transactions
            GROUP BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)
            ORDER BY year, month
        """)
        months = cur.fetchall()

        # Romanian month names
        month_names = {
            1: 'Ianuarie', 2: 'Februarie', 3: 'Martie', 4: 'Aprilie',
            5: 'Mai', 6: 'Iunie', 7: 'Iulie', 8: 'August',
            9: 'Septembrie', 10: 'Octombrie', 11: 'Noiembrie', 12: 'Decembrie'
        }

        return {
            'months': [{
                'year': m['year'],
                'month': m['month'],
                'period': f"{month_names[m['month']]} {m['year']}",
                'total_value': float(m['total_value']),
                'transactions': m['transactions'],
                'working_days': m['working_days']
            } for m in months]
        }
