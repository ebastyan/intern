"""
Analytics API - Összesítések és statisztikák
Endpoints:
  GET /api/analytics?type=overview
  GET /api/analytics?type=monthly&year=2024
  GET /api/analytics?type=county
  GET /api/analytics?type=weekday
  GET /api/analytics?type=yearly
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
        raise Exception("No database URL configured. Set POSTGRES_URL or DATABASE_URL environment variable.")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)

            conn = get_db()
            cur = conn.cursor()

            analysis_type = params.get('type', ['overview'])[0]

            if analysis_type == 'overview':
                result = self.get_overview(cur)
            elif analysis_type == 'monthly':
                year = params.get('year', [None])[0]
                result = self.get_monthly_summary(cur, year)
            elif analysis_type == 'yearly':
                result = self.get_yearly_summary(cur)
            elif analysis_type == 'county':
                result = self.get_county_analysis(cur)
            elif analysis_type == 'city':
                county = params.get('county', [None])[0]
                result = self.get_city_analysis(cur, county)
            elif analysis_type == 'weekday':
                year = params.get('year', [None])[0]
                month = params.get('month', [None])[0]
                result = self.get_weekday_patterns(cur, year, month)
            elif analysis_type == 'age':
                result = self.get_age_analysis(cur)
            elif analysis_type == 'trends':
                result = self.get_trends(cur)
            else:
                result = {
                    'error': 'Unknown analysis type',
                    'available': ['overview', 'monthly', 'yearly', 'county', 'city', 'weekday', 'age', 'trends']
                }

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

    def get_overview(self, cur):
        """Get overall business overview"""
        # Total stats
        cur.execute("""
            SELECT COUNT(*) as transactions,
                   COUNT(DISTINCT cnp) as unique_partners,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COALESCE(SUM(net_paid), 0) as total_paid,
                   MIN(date) as first_date,
                   MAX(date) as last_date,
                   COUNT(DISTINCT date) as working_days
            FROM transactions
        """)
        totals = cur.fetchone()

        # Partner stats
        cur.execute("SELECT COUNT(*) as count FROM partners")
        total_partners = cur.fetchone()['count']

        # Category totals
        cur.execute("""
            SELECT wc.name, SUM(ti.weight_kg) as total_kg
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            GROUP BY wc.name
            ORDER BY total_kg DESC
        """)
        categories = cur.fetchall()

        # Recent activity (last 30 days)
        cur.execute("""
            SELECT COUNT(*) as transactions,
                   COALESCE(SUM(gross_value), 0) as value,
                   COUNT(DISTINCT cnp) as partners
            FROM transactions
            WHERE date >= CURRENT_DATE - 30
        """)
        recent = cur.fetchone()

        return {
            'overview': {
                'total_transactions': totals['transactions'],
                'unique_partners': totals['unique_partners'],
                'registered_partners': total_partners,
                'total_value': float(totals['total_value']),
                'total_paid': float(totals['total_paid']),
                'date_range': {
                    'from': str(totals['first_date']),
                    'to': str(totals['last_date'])
                },
                'working_days': totals['working_days'],
                'avg_per_day': float(totals['total_value']) / totals['working_days'] if totals['working_days'] > 0 else 0
            },
            'last_30_days': {
                'transactions': recent['transactions'],
                'value': float(recent['value']),
                'unique_partners': recent['partners']
            },
            'by_category': [{
                'category': c['name'],
                'total_kg': float(c['total_kg'])
            } for c in categories]
        }

    def get_yearly_summary(self, cur):
        """Get year-by-year summary"""
        cur.execute("""
            SELECT EXTRACT(YEAR FROM date)::int as year,
                   COUNT(*) as transactions,
                   COUNT(DISTINCT cnp) as unique_partners,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COALESCE(SUM(net_paid), 0) as total_paid,
                   COUNT(DISTINCT date) as working_days
            FROM transactions
            GROUP BY EXTRACT(YEAR FROM date)
            ORDER BY year
        """)
        years = cur.fetchall()

        return {
            'years': [{
                'year': y['year'],
                'transactions': y['transactions'],
                'unique_partners': y['unique_partners'],
                'total_value': float(y['total_value']),
                'total_paid': float(y['total_paid']),
                'working_days': y['working_days'],
                'avg_per_day': float(y['total_value']) / y['working_days'] if y['working_days'] > 0 else 0
            } for y in years]
        }

    def get_monthly_summary(self, cur, year=None):
        """Get monthly breakdown"""
        query = """
            SELECT EXTRACT(YEAR FROM date)::int as year,
                   EXTRACT(MONTH FROM date)::int as month,
                   COUNT(*) as transactions,
                   COUNT(DISTINCT cnp) as unique_partners,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COUNT(DISTINCT date) as working_days,
                   MIN(date) as first_day,
                   MAX(date) as last_day
            FROM transactions
        """
        params = []
        if year:
            query += " WHERE EXTRACT(YEAR FROM date) = %s"
            params.append(int(year))

        query += """
            GROUP BY EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date)
            ORDER BY year, month
        """

        cur.execute(query, params)
        months = cur.fetchall()

        return {
            'year_filter': year,
            'months': [{
                'year': m['year'],
                'month': m['month'],
                'transactions': m['transactions'],
                'unique_partners': m['unique_partners'],
                'total_value': float(m['total_value']),
                'working_days': m['working_days'],
                'avg_per_day': float(m['total_value']) / m['working_days'] if m['working_days'] > 0 else 0,
                'date_range': f"{m['first_day']} - {m['last_day']}"
            } for m in months]
        }

    def get_county_analysis(self, cur):
        """Get analysis by county"""
        cur.execute("""
            SELECT p.county,
                   COUNT(DISTINCT p.cnp) as partner_count,
                   COUNT(t.document_id) as transaction_count,
                   COALESCE(SUM(t.gross_value), 0) as total_value
            FROM partners p
            LEFT JOIN transactions t ON p.cnp = t.cnp
            WHERE p.county IS NOT NULL
            GROUP BY p.county
            ORDER BY total_value DESC
        """)
        counties = cur.fetchall()

        return {
            'by_county': [{
                'county': c['county'],
                'partner_count': c['partner_count'],
                'transaction_count': c['transaction_count'],
                'total_value': float(c['total_value']),
                'avg_per_partner': float(c['total_value']) / c['partner_count'] if c['partner_count'] > 0 else 0
            } for c in counties]
        }

    def get_city_analysis(self, cur, county=None):
        """Get analysis by city, optionally filtered by county"""
        query = """
            SELECT p.city, p.county,
                   COUNT(DISTINCT p.cnp) as partner_count,
                   COUNT(t.document_id) as transaction_count,
                   COALESCE(SUM(t.gross_value), 0) as total_value
            FROM partners p
            LEFT JOIN transactions t ON p.cnp = t.cnp
            WHERE p.city IS NOT NULL
        """
        params = []
        if county:
            query += " AND p.county ILIKE %s"
            params.append(f'%{county}%')

        query += " GROUP BY p.city, p.county ORDER BY total_value DESC LIMIT 100"

        cur.execute(query, params)
        cities = cur.fetchall()

        return {
            'county_filter': county,
            'by_city': [{
                'city': c['city'],
                'county': c['county'],
                'partner_count': c['partner_count'],
                'transaction_count': c['transaction_count'],
                'total_value': float(c['total_value'])
            } for c in cities]
        }

    def get_weekday_patterns(self, cur, year=None, month=None):
        """Get patterns by day of week"""
        query = """
            SELECT TO_CHAR(date, 'Day') as weekday,
                   EXTRACT(DOW FROM date)::int as dow,
                   COUNT(*) as transactions,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COUNT(DISTINCT date) as days_count,
                   COUNT(DISTINCT cnp) as unique_partners
            FROM transactions
            WHERE 1=1
        """
        params = []
        if year:
            query += " AND EXTRACT(YEAR FROM date) = %s"
            params.append(int(year))
        if month:
            query += " AND EXTRACT(MONTH FROM date) = %s"
            params.append(int(month))

        query += """
            GROUP BY TO_CHAR(date, 'Day'), EXTRACT(DOW FROM date)
            ORDER BY dow
        """

        cur.execute(query, params)
        weekdays = cur.fetchall()

        return {
            'filters': {'year': year, 'month': month},
            'weekday_patterns': [{
                'weekday': w['weekday'].strip(),
                'transactions': w['transactions'],
                'total_value': float(w['total_value']),
                'days_count': w['days_count'],
                'avg_per_day': float(w['total_value']) / w['days_count'] if w['days_count'] > 0 else 0,
                'avg_transactions': w['transactions'] // w['days_count'] if w['days_count'] > 0 else 0
            } for w in weekdays]
        }

    def get_age_analysis(self, cur):
        """Get analysis by partner age groups"""
        cur.execute("""
            SELECT
                CASE
                    WHEN 2024 - p.birth_year < 25 THEN '18-24'
                    WHEN 2024 - p.birth_year < 35 THEN '25-34'
                    WHEN 2024 - p.birth_year < 45 THEN '35-44'
                    WHEN 2024 - p.birth_year < 55 THEN '45-54'
                    WHEN 2024 - p.birth_year < 65 THEN '55-64'
                    ELSE '65+'
                END as age_group,
                COUNT(DISTINCT p.cnp) as partner_count,
                COUNT(t.document_id) as transaction_count,
                COALESCE(SUM(t.gross_value), 0) as total_value
            FROM partners p
            LEFT JOIN transactions t ON p.cnp = t.cnp
            WHERE p.birth_year IS NOT NULL
            GROUP BY age_group
            ORDER BY age_group
        """)
        ages = cur.fetchall()

        # Sex breakdown
        cur.execute("""
            SELECT p.sex,
                   COUNT(DISTINCT p.cnp) as partner_count,
                   COUNT(t.document_id) as transaction_count,
                   COALESCE(SUM(t.gross_value), 0) as total_value
            FROM partners p
            LEFT JOIN transactions t ON p.cnp = t.cnp
            WHERE p.sex IS NOT NULL
            GROUP BY p.sex
        """)
        sex = cur.fetchall()

        return {
            'by_age_group': [{
                'age_group': a['age_group'],
                'partner_count': a['partner_count'],
                'transaction_count': a['transaction_count'],
                'total_value': float(a['total_value'])
            } for a in ages],
            'by_sex': [{
                'sex': 'Barbat' if s['sex'] == 'M' else 'Femeie',
                'partner_count': s['partner_count'],
                'transaction_count': s['transaction_count'],
                'total_value': float(s['total_value'])
            } for s in sex]
        }

    def get_trends(self, cur):
        """Get recent trends and comparisons"""
        # Last 7 days vs previous 7
        cur.execute("""
            SELECT
                SUM(CASE WHEN date >= CURRENT_DATE - 7 THEN gross_value ELSE 0 END) as last_7,
                SUM(CASE WHEN date >= CURRENT_DATE - 14 AND date < CURRENT_DATE - 7 THEN gross_value ELSE 0 END) as prev_7,
                COUNT(CASE WHEN date >= CURRENT_DATE - 7 THEN 1 END) as trans_last_7,
                COUNT(CASE WHEN date >= CURRENT_DATE - 14 AND date < CURRENT_DATE - 7 THEN 1 END) as trans_prev_7
            FROM transactions
        """)
        weekly = cur.fetchone()

        # Last 30 days vs previous 30
        cur.execute("""
            SELECT
                SUM(CASE WHEN date >= CURRENT_DATE - 30 THEN gross_value ELSE 0 END) as last_30,
                SUM(CASE WHEN date >= CURRENT_DATE - 60 AND date < CURRENT_DATE - 30 THEN gross_value ELSE 0 END) as prev_30
            FROM transactions
        """)
        monthly = cur.fetchone()

        # Top growing cities (by transaction count increase)
        cur.execute("""
            WITH recent AS (
                SELECT p.city, COUNT(*) as cnt
                FROM transactions t
                JOIN partners p ON t.cnp = p.cnp
                WHERE t.date >= CURRENT_DATE - 30
                GROUP BY p.city
            ),
            previous AS (
                SELECT p.city, COUNT(*) as cnt
                FROM transactions t
                JOIN partners p ON t.cnp = p.cnp
                WHERE t.date >= CURRENT_DATE - 60 AND t.date < CURRENT_DATE - 30
                GROUP BY p.city
            )
            SELECT r.city,
                   r.cnt as recent_count,
                   COALESCE(p.cnt, 0) as previous_count,
                   r.cnt - COALESCE(p.cnt, 0) as growth
            FROM recent r
            LEFT JOIN previous p ON r.city = p.city
            WHERE r.city IS NOT NULL
            ORDER BY growth DESC
            LIMIT 10
        """)
        growing = cur.fetchall()

        return {
            'weekly_comparison': {
                'last_7_days': float(weekly['last_7'] or 0),
                'previous_7_days': float(weekly['prev_7'] or 0),
                'change_percent': round((float(weekly['last_7'] or 0) - float(weekly['prev_7'] or 1)) / float(weekly['prev_7'] or 1) * 100, 1) if weekly['prev_7'] else 0,
                'transactions_last_7': weekly['trans_last_7'],
                'transactions_prev_7': weekly['trans_prev_7']
            },
            'monthly_comparison': {
                'last_30_days': float(monthly['last_30'] or 0),
                'previous_30_days': float(monthly['prev_30'] or 0),
                'change_percent': round((float(monthly['last_30'] or 0) - float(monthly['prev_30'] or 1)) / float(monthly['prev_30'] or 1) * 100, 1) if monthly['prev_30'] else 0
            },
            'growing_cities': [{
                'city': g['city'],
                'recent_transactions': g['recent_count'],
                'previous_transactions': g['previous_count'],
                'growth': g['growth']
            } for g in growing]
        }
