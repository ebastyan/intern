"""
Data API - Dashboard adatok (éves/havi összesítések)
Ez a régi API formátumot tartja a dashboard kompatibilitás érdekében
GET /api/data - Éves és havi összefoglalók
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            conn = get_db()
            cur = conn.cursor()

            result = {'years': {}}

            # Get yearly summaries
            cur.execute("""
                SELECT EXTRACT(YEAR FROM date)::int as year,
                       COUNT(*) as transactions,
                       COUNT(DISTINCT date) as working_days,
                       COALESCE(SUM(gross_value), 0) as total_value,
                       COALESCE(SUM(net_paid), 0) as total_paid
                FROM transactions
                GROUP BY EXTRACT(YEAR FROM date)
                ORDER BY year
            """)
            yearly = cur.fetchall()

            for y in yearly:
                year = str(y['year'])
                months_in_year = 12 if y['year'] < 2025 else 11  # Adjust for current year
                result['years'][year] = {
                    'summary': {
                        'total_value': float(y['total_value']),
                        'total_paid': float(y['total_paid']),
                        'transactions': y['transactions'],
                        'working_days': y['working_days'],
                        'avg_per_day': float(y['total_value']) / y['working_days'] if y['working_days'] > 0 else 0,
                        'avg_per_month': float(y['total_value']) / months_in_year
                    },
                    'months': {},
                    'total_by_category': {}
                }

            # Get monthly summaries
            cur.execute("""
                SELECT EXTRACT(YEAR FROM date)::int as year,
                       EXTRACT(MONTH FROM date)::int as month,
                       COUNT(*) as transactions,
                       COUNT(DISTINCT date) as working_days,
                       COUNT(DISTINCT cnp) as unique_partners,
                       COALESCE(SUM(gross_value), 0) as total_value,
                       COALESCE(SUM(net_paid), 0) as total_paid,
                       MIN(date) as first_day,
                       MAX(date) as last_day
                FROM transactions
                GROUP BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)
                ORDER BY year, month
            """)
            monthly = cur.fetchall()

            # Month names in Romanian
            month_names = {
                1: 'Ianuarie', 2: 'Februarie', 3: 'Martie', 4: 'Aprilie',
                5: 'Mai', 6: 'Iunie', 7: 'Iulie', 8: 'August',
                9: 'Septembrie', 10: 'Octombrie', 11: 'Noiembrie', 12: 'Decembrie'
            }

            for m in monthly:
                year = str(m['year'])
                month = str(m['month']).zfill(2)

                # Get best and worst day for this month
                cur.execute("""
                    SELECT date, SUM(gross_value) as day_value
                    FROM transactions
                    WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s
                    GROUP BY date
                    ORDER BY day_value DESC
                    LIMIT 1
                """, (m['year'], m['month']))
                best = cur.fetchone()

                cur.execute("""
                    SELECT date, SUM(gross_value) as day_value
                    FROM transactions
                    WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s
                    GROUP BY date
                    ORDER BY day_value ASC
                    LIMIT 1
                """, (m['year'], m['month']))
                worst = cur.fetchone()

                result['years'][year]['months'][month] = {
                    'period': f"{month_names[m['month']]} {m['year']}",
                    'summary': {
                        'total_value': float(m['total_value']),
                        'total_paid': float(m['total_paid']),
                        'transactions': m['transactions'],
                        'working_days': m['working_days'],
                        'unique_partners': m['unique_partners'],
                        'avg_per_day': float(m['total_value']) / m['working_days'] if m['working_days'] > 0 else 0,
                        'avg_per_trans': float(m['total_value']) / m['transactions'] if m['transactions'] > 0 else 0,
                        'best_day': {
                            'date': str(best['date']) if best else None,
                            'value': float(best['day_value']) if best else 0
                        },
                        'worst_day': {
                            'date': str(worst['date']) if worst else None,
                            'value': float(worst['day_value']) if worst else 0
                        }
                    },
                    'weekday_patterns': {}
                }

            # Get weekday patterns for each month
            cur.execute("""
                SELECT EXTRACT(YEAR FROM date)::int as year,
                       EXTRACT(MONTH FROM date)::int as month,
                       TO_CHAR(date, 'Day') as weekday_name,
                       COUNT(*) as transactions,
                       COALESCE(SUM(gross_value), 0) as total_value,
                       COUNT(DISTINCT date) as days_count
                FROM transactions
                GROUP BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date), TO_CHAR(date, 'Day')
            """)
            weekdays = cur.fetchall()

            for w in weekdays:
                year = str(w['year'])
                month = str(w['month']).zfill(2)
                weekday = w['weekday_name'].strip()
                if year in result['years'] and month in result['years'][year]['months']:
                    result['years'][year]['months'][month]['weekday_patterns'][weekday] = {
                        'avg_value': float(w['total_value']) / w['days_count'] if w['days_count'] > 0 else 0,
                        'avg_transactions': w['transactions'] // w['days_count'] if w['days_count'] > 0 else 0,
                        'days_count': w['days_count']
                    }

            # Get category totals by year
            cur.execute("""
                SELECT EXTRACT(YEAR FROM t.date)::int as year,
                       wc.name as category,
                       COALESCE(SUM(ti.weight_kg), 0) as total_kg
                FROM transaction_items ti
                JOIN waste_types wt ON ti.waste_type_id = wt.id
                JOIN waste_categories wc ON wt.category_id = wc.id
                JOIN transactions t ON ti.document_id = t.document_id
                GROUP BY EXTRACT(YEAR FROM t.date), wc.name
                ORDER BY year, total_kg DESC
            """)
            categories = cur.fetchall()

            for c in categories:
                year = str(c['year'])
                if year in result['years']:
                    result['years'][year]['total_by_category'][c['category']] = float(c['total_kg'])

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
