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
            elif analysis_type == 'tops':
                result = self.get_top_stats(cur)
            elif analysis_type == 'holidays':
                result = self.get_holiday_analysis(cur)
            elif analysis_type == 'waste_by_region':
                category = params.get('category', [None])[0]
                result = self.get_waste_by_region(cur, category)
            elif analysis_type == 'city_details':
                city = params.get('city', [None])[0]
                result = self.get_city_details(cur, city)
            elif analysis_type == 'all_cities':
                result = self.get_all_cities(cur)
            else:
                result = {
                    'error': 'Unknown analysis type',
                    'available': ['overview', 'monthly', 'yearly', 'county', 'city', 'weekday', 'age', 'trends', 'tops', 'holidays', 'waste_by_region', 'city_details', 'all_cities']
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

    def get_top_stats(self, cur):
        """Get various top statistics for the Statistici tab"""
        # Top by weight per category - get ALL categories
        cur.execute("""
            SELECT wc.name as category, p.name, p.cnp, SUM(ti.weight_kg) as total_kg
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            JOIN partners p ON t.cnp = p.cnp
            GROUP BY wc.name, p.name, p.cnp
            ORDER BY wc.name, total_kg DESC
        """)
        all_by_cat = cur.fetchall()

        # Group by category and get top 1
        top_by_weight = {}
        for row in all_by_cat:
            cat = row['category']
            if cat not in top_by_weight:
                top_by_weight[cat] = {'name': row['name'], 'cnp': row['cnp'], 'total_kg': float(row['total_kg'])}

        # Top by value per category - SORT by value DESC for display
        cur.execute("""
            SELECT wc.name as category, p.name, p.cnp, SUM(ti.value) as total_value
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            JOIN partners p ON t.cnp = p.cnp
            GROUP BY wc.name, p.name, p.cnp
            ORDER BY wc.name, total_value DESC
        """)
        all_val = cur.fetchall()

        top_by_value = {}
        for row in all_val:
            cat = row['category']
            if cat not in top_by_value:
                top_by_value[cat] = {'name': row['name'], 'cnp': row['cnp'], 'total_value': float(row['total_value'])}

        # Sort top_by_value by total_value descending for display
        top_by_value = dict(sorted(top_by_value.items(), key=lambda x: x[1]['total_value'], reverse=True))

        # Bottom by value per category (smallest total among returning partners)
        cur.execute("""
            SELECT wc.name as category, p.name, p.cnp, SUM(ti.value) as total_value, COUNT(DISTINCT t.document_id) as visits
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            JOIN partners p ON t.cnp = p.cnp
            GROUP BY wc.name, p.name, p.cnp
            HAVING COUNT(DISTINCT t.document_id) >= 3
            ORDER BY wc.name, total_value ASC
        """)
        all_bottom = cur.fetchall()

        bottom_by_value = {}
        for row in all_bottom:
            cat = row['category']
            if cat not in bottom_by_value:
                bottom_by_value[cat] = {'name': row['name'], 'cnp': row['cnp'], 'total_value': float(row['total_value']), 'visits': row['visits']}

        # Funny/unusual names - search for Hungarian/Romanian funny patterns
        cur.execute("""
            SELECT name, cnp, city FROM partners
            WHERE name ~* '(futy|fut|fasz|pul|kur|szar|poop|cac|pipi|xxx|zzz|aaa|eee|ooo|uuu|iii)'
               OR name ~* '(buzi|bolond|hulye|prost|nebun|tampla)'
               OR LENGTH(name) <= 4
               OR name ~* '^[A-Z]{1,2} [A-Z]{1,2}$'
               OR name ~* '([a-z])\\1{3,}'
            ORDER BY LENGTH(name), name
            LIMIT 20
        """)
        funny_names = [{'name': r['name'], 'cnp': r['cnp'], 'city': r['city']} for r in cur.fetchall()]

        # Unusual cities
        cur.execute("""
            SELECT DISTINCT city FROM partners
            WHERE city IS NOT NULL
              AND (LENGTH(city) <= 3 OR city ~* '[0-9]' OR city ~* '(xxx|zzz|test|asd)')
            LIMIT 10
        """)
        unusual_cities = [r['city'] for r in cur.fetchall()]

        # Consistent weight partners (low std deviation)
        cur.execute("""
            SELECT p.name, p.cnp,
                   COUNT(DISTINCT t.document_id) as visits,
                   AVG(ti.weight_kg) as avg_weight,
                   STDDEV(ti.weight_kg) as std_weight
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            GROUP BY p.name, p.cnp
            HAVING COUNT(DISTINCT t.document_id) >= 10 AND STDDEV(ti.weight_kg) < 5
            ORDER BY std_weight ASC
            LIMIT 10
        """)
        consistent_partners = [{'name': r['name'], 'cnp': r['cnp'], 'visits': r['visits'], 'avg_weight': float(r['avg_weight']), 'std_weight': float(r['std_weight']) if r['std_weight'] else 0} for r in cur.fetchall()]

        # Best month overall - AVERAGE per day, not total!
        cur.execute("""
            SELECT EXTRACT(MONTH FROM date)::int as month,
                   SUM(gross_value) as total,
                   COUNT(DISTINCT date) as days_count,
                   SUM(gross_value) / COUNT(DISTINCT date) as avg_per_day
            FROM transactions
            GROUP BY EXTRACT(MONTH FROM date)
            ORDER BY avg_per_day DESC
            LIMIT 1
        """)
        best_month = cur.fetchone()
        month_names = ['', 'Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie', 'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie']

        # Best weekday - AVERAGE per day, not total!
        cur.execute("""
            SELECT EXTRACT(DOW FROM date)::int as dow,
                   SUM(gross_value) as total,
                   COUNT(DISTINCT date) as days_count,
                   SUM(gross_value) / COUNT(DISTINCT date) as avg_per_day
            FROM transactions
            GROUP BY EXTRACT(DOW FROM date)
            ORDER BY avg_per_day DESC
            LIMIT 1
        """)
        best_dow = cur.fetchone()
        dow_names = ['Duminica', 'Luni', 'Marti', 'Miercuri', 'Joi', 'Vineri', 'Sambata']

        # Best week (ISO week number)
        cur.execute("""
            SELECT EXTRACT(ISOYEAR FROM date)::int as year,
                   EXTRACT(WEEK FROM date)::int as week,
                   SUM(gross_value) as total,
                   COUNT(DISTINCT date) as days_count,
                   MIN(date) as week_start
            FROM transactions
            GROUP BY EXTRACT(ISOYEAR FROM date), EXTRACT(WEEK FROM date)
            ORDER BY total DESC
            LIMIT 1
        """)
        best_week = cur.fetchone()

        return {
            'top_by_weight': top_by_weight,
            'top_by_value': top_by_value,
            'bottom_by_value': bottom_by_value,
            'consistent_partners': consistent_partners,
            'best_month': {'month': month_names[best_month['month']], 'value': float(best_month['total']), 'avg_per_day': float(best_month['avg_per_day']), 'days': best_month['days_count']} if best_month else None,
            'best_weekday': {'day': dow_names[best_dow['dow']], 'value': float(best_dow['total']), 'avg_per_day': float(best_dow['avg_per_day']), 'days': best_dow['days_count']} if best_dow else None,
            'best_week': {'year': best_week['year'], 'week': best_week['week'], 'value': float(best_week['total']), 'days': best_week['days_count'], 'week_start': str(best_week['week_start'])} if best_week else None
        }

    def get_holiday_analysis(self, cur):
        """Analyze performance around holidays with before/after comparison"""
        # Orthodox Easter 2024: May 5, 2025: April 20
        # Christmas: Dec 25
        # St Nicholas: Dec 6
        from datetime import datetime, timedelta

        holidays = {
            'paste_2024': {'start': '2024-04-28', 'end': '2024-05-12', 'name': 'Paste 2024',
                          'before_start': '2024-04-14', 'before_end': '2024-04-27',
                          'after_start': '2024-05-13', 'after_end': '2024-05-26'},
            'paste_2025': {'start': '2025-04-13', 'end': '2025-04-27', 'name': 'Paste 2025',
                          'before_start': '2025-03-30', 'before_end': '2025-04-12',
                          'after_start': '2025-04-28', 'after_end': '2025-05-11'},
            'craciun_2024': {'start': '2024-12-20', 'end': '2024-12-31', 'name': 'Craciun 2024',
                            'before_start': '2024-12-06', 'before_end': '2024-12-19',
                            'after_start': '2025-01-01', 'after_end': '2025-01-14'},
            'mos_nicolae_2024': {'start': '2024-12-01', 'end': '2024-12-08', 'name': 'Mos Nicolae 2024',
                                'before_start': '2024-11-17', 'before_end': '2024-11-30',
                                'after_start': '2024-12-09', 'after_end': '2024-12-16'}
        }

        results = {}
        for key, h in holidays.items():
            # Get data for holiday period
            cur.execute("""
                SELECT COUNT(*) as transactions,
                       COALESCE(SUM(gross_value), 0) as total_value,
                       COUNT(DISTINCT cnp) as partners
                FROM transactions
                WHERE date BETWEEN %s AND %s
            """, (h['start'], h['end']))
            data = cur.fetchone()

            # Get data for BEFORE period
            cur.execute("""
                SELECT COUNT(*) as transactions,
                       COALESCE(SUM(gross_value), 0) as total_value,
                       COUNT(DISTINCT cnp) as partners
                FROM transactions
                WHERE date BETWEEN %s AND %s
            """, (h['before_start'], h['before_end']))
            before_data = cur.fetchone()

            # Get data for AFTER period
            cur.execute("""
                SELECT COUNT(*) as transactions,
                       COALESCE(SUM(gross_value), 0) as total_value,
                       COUNT(DISTINCT cnp) as partners
                FROM transactions
                WHERE date BETWEEN %s AND %s
            """, (h['after_start'], h['after_end']))
            after_data = cur.fetchone()

            # Get top category during this period
            cur.execute("""
                SELECT wc.name, SUM(ti.weight_kg) as total_kg, SUM(ti.value) as total_value
                FROM transactions t
                JOIN transaction_items ti ON t.document_id = ti.document_id
                JOIN waste_types wt ON ti.waste_type_id = wt.id
                JOIN waste_categories wc ON wt.category_id = wc.id
                WHERE t.date BETWEEN %s AND %s
                GROUP BY wc.name
                ORDER BY total_kg DESC
                LIMIT 3
            """, (h['start'], h['end']))
            top_cats = cur.fetchall()

            # Calculate differences
            before_val = float(before_data['total_value']) if before_data['total_value'] else 0
            holiday_val = float(data['total_value']) if data['total_value'] else 0
            after_val = float(after_data['total_value']) if after_data['total_value'] else 0

            diff_before_pct = ((holiday_val - before_val) / before_val * 100) if before_val > 0 else 0
            diff_after_pct = ((holiday_val - after_val) / after_val * 100) if after_val > 0 else 0

            # Generate explanation
            if diff_before_pct > 10 and diff_after_pct > 10:
                explanation = "Sarbatoarea creste vanzarile! Inainte si dupa sunt mai slabe."
            elif diff_before_pct < -10 and diff_after_pct < -10:
                explanation = "Sarbatoarea scade vanzarile - lumea nu vine in perioada asta."
            elif diff_before_pct > 10:
                explanation = "Creste fata de inainte, dar dupa sarbatoare e similar."
            elif diff_after_pct > 10:
                explanation = "Dupa sarbatoare scad vanzarile semnificativ."
            else:
                explanation = "Fara impact semnificativ al sarbatorii."

            results[key] = {
                'name': h['name'],
                'period': f"{h['start']} - {h['end']}",
                'transactions': data['transactions'],
                'total_value': holiday_val,
                'partners': data['partners'],
                'top_categories': [{'name': c['name'], 'kg': float(c['total_kg']), 'value': float(c['total_value'])} for c in top_cats],
                'vs_before': {
                    'period': f"{h['before_start']} - {h['before_end']}",
                    'value': before_val,
                    'diff_pct': diff_before_pct
                },
                'vs_after': {
                    'period': f"{h['after_start']} - {h['after_end']}",
                    'value': after_val,
                    'diff_pct': diff_after_pct
                },
                'explanation': explanation
            }

        return {'holidays': results}

    def get_waste_by_region(self, cur, category=None):
        """Get waste breakdown by county, city, and age group"""
        category_filter = ""
        params = []
        if category:
            category_filter = "AND wc.name ILIKE %s"
            params.append(f'%{category}%')

        # By County
        cur.execute(f"""
            SELECT p.county, SUM(ti.weight_kg) as total_kg, SUM(ti.value) as total_value,
                   COUNT(DISTINCT p.cnp) as partners
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE p.county IS NOT NULL {category_filter}
            GROUP BY p.county
            ORDER BY total_kg DESC
            LIMIT 15
        """, params)
        by_county = [{'county': r['county'], 'total_kg': float(r['total_kg']), 'total_value': float(r['total_value']), 'partners': r['partners']} for r in cur.fetchall()]

        # By City
        cur.execute(f"""
            SELECT p.city, p.county, SUM(ti.weight_kg) as total_kg, SUM(ti.value) as total_value,
                   COUNT(DISTINCT p.cnp) as partners
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE p.city IS NOT NULL {category_filter}
            GROUP BY p.city, p.county
            ORDER BY total_kg DESC
            LIMIT 15
        """, params)
        by_city = [{'city': r['city'], 'county': r['county'], 'total_kg': float(r['total_kg']), 'total_value': float(r['total_value']), 'partners': r['partners']} for r in cur.fetchall()]

        # By Age Group
        cur.execute(f"""
            SELECT
                CASE
                    WHEN 2025 - p.birth_year < 25 THEN '18-24'
                    WHEN 2025 - p.birth_year < 35 THEN '25-34'
                    WHEN 2025 - p.birth_year < 45 THEN '35-44'
                    WHEN 2025 - p.birth_year < 55 THEN '45-54'
                    WHEN 2025 - p.birth_year < 65 THEN '55-64'
                    ELSE '65+'
                END as age_group,
                SUM(ti.weight_kg) as total_kg, SUM(ti.value) as total_value,
                COUNT(DISTINCT p.cnp) as partners
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE p.birth_year IS NOT NULL {category_filter}
            GROUP BY age_group
            ORDER BY total_kg DESC
        """, params)
        by_age = [{'age_group': r['age_group'], 'total_kg': float(r['total_kg']), 'total_value': float(r['total_value']), 'partners': r['partners']} for r in cur.fetchall()]

        # Get all categories for dropdown
        cur.execute("SELECT name FROM waste_categories ORDER BY name")
        categories = [r['name'] for r in cur.fetchall()]

        return {
            'category': category,
            'by_county': by_county,
            'by_city': by_city,
            'by_age': by_age,
            'categories': categories
        }

    def get_all_cities(self, cur):
        """Get list of all cities with stats - normalized to avoid duplicates"""
        # First, normalize city names by removing prefixes like "Com.", "Oras", "Sat", "Mun."
        # and group by the normalized name, picking the most common county
        cur.execute("""
            WITH normalized_cities AS (
                SELECT
                    p.cnp,
                    TRIM(REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(
                                    REGEXP_REPLACE(p.city, '^(Com\\.?|Comuna)\\s*', '', 'i'),
                                    '^(Oras|Or\\.?)\\s*', '', 'i'),
                                '^(Sat|S\\.?)\\s*', '', 'i'),
                            '^(Mun\\.?|Municipiul)\\s*', '', 'i'),
                        '^\\s+|\\s+$', '', 'g')
                    ) as normalized_city,
                    p.county
                FROM partners p
                WHERE p.city IS NOT NULL
            ),
            city_counties AS (
                SELECT normalized_city, county, COUNT(*) as cnt
                FROM normalized_cities
                WHERE county IS NOT NULL
                GROUP BY normalized_city, county
            ),
            best_county AS (
                SELECT DISTINCT ON (normalized_city) normalized_city, county
                FROM city_counties
                ORDER BY normalized_city, cnt DESC
            )
            SELECT nc.normalized_city as city,
                   bc.county,
                   COUNT(DISTINCT nc.cnp) as partners,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value
            FROM normalized_cities nc
            JOIN transactions t ON nc.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            LEFT JOIN best_county bc ON nc.normalized_city = bc.normalized_city
            GROUP BY nc.normalized_city, bc.county
            ORDER BY total_value DESC
        """)
        cities = [{'city': r['city'], 'county': r['county'], 'partners': r['partners'],
                   'total_kg': float(r['total_kg']), 'total_value': float(r['total_value'])} for r in cur.fetchall()]
        return {'cities': cities, 'count': len(cities)}

    def get_city_details(self, cur, city):
        """Get detailed breakdown for a specific city - handles normalized city names"""
        if not city:
            return {'error': 'City parameter required'}

        # Create a normalized city match pattern - match both exact and with prefixes
        # This handles cases like "Simleul Silvaniei" matching "Com. Simleul Silvaniei", "Oras Simleul Silvaniei", etc.
        city_pattern = f'%{city}%'

        # Basic stats - use pattern matching to find all variations
        cur.execute("""
            SELECT COUNT(DISTINCT p.cnp) as partners,
                   COUNT(DISTINCT t.document_id) as transactions,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            WHERE p.city ILIKE %s
               OR TRIM(REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(p.city, '^(Com\\.?|Comuna)\\s*', '', 'i'),
                                '^(Oras|Or\\.?)\\s*', '', 'i'),
                            '^(Sat|S\\.?)\\s*', '', 'i'),
                        '^(Mun\\.?|Municipiul)\\s*', '', 'i'),
                    '^\\s+|\\s+$', '', 'g')
                  ) ILIKE %s
        """, (city_pattern, city))
        basic = cur.fetchone()

        # Get the county (most common one for this city)
        cur.execute("""
            SELECT p.county, COUNT(*) as cnt
            FROM partners p
            WHERE (p.city ILIKE %s
               OR TRIM(REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(p.city, '^(Com\\.?|Comuna)\\s*', '', 'i'),
                                '^(Oras|Or\\.?)\\s*', '', 'i'),
                            '^(Sat|S\\.?)\\s*', '', 'i'),
                        '^(Mun\\.?|Municipiul)\\s*', '', 'i'),
                    '^\\s+|\\s+$', '', 'g')
                  ) ILIKE %s)
              AND p.county IS NOT NULL
            GROUP BY p.county
            ORDER BY cnt DESC
            LIMIT 1
        """, (city_pattern, city))
        county_row = cur.fetchone()
        county = county_row['county'] if county_row else None

        if not basic or basic['partners'] == 0:
            return {'error': f'City {city} not found'}

        # Breakdown by waste category
        cur.execute("""
            SELECT wc.name as category,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE p.city ILIKE %s
               OR TRIM(REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(p.city, '^(Com\\.?|Comuna)\\s*', '', 'i'),
                                '^(Oras|Or\\.?)\\s*', '', 'i'),
                            '^(Sat|S\\.?)\\s*', '', 'i'),
                        '^(Mun\\.?|Municipiul)\\s*', '', 'i'),
                    '^\\s+|\\s+$', '', 'g')
                  ) ILIKE %s
            GROUP BY wc.name
            ORDER BY total_kg DESC
        """, (city_pattern, city))
        by_category = [{'category': r['category'], 'total_kg': float(r['total_kg']), 'total_value': float(r['total_value'])} for r in cur.fetchall()]

        # Top partners by visits
        cur.execute("""
            SELECT p.cnp, p.name, COUNT(t.document_id) as visits, SUM(t.gross_value) as total_value
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            WHERE p.city ILIKE %s
               OR TRIM(REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(p.city, '^(Com\\.?|Comuna)\\s*', '', 'i'),
                                '^(Oras|Or\\.?)\\s*', '', 'i'),
                            '^(Sat|S\\.?)\\s*', '', 'i'),
                        '^(Mun\\.?|Municipiul)\\s*', '', 'i'),
                    '^\\s+|\\s+$', '', 'g')
                  ) ILIKE %s
            GROUP BY p.cnp, p.name
            ORDER BY visits DESC
            LIMIT 20
        """, (city_pattern, city))
        top_by_visits = [{'cnp': r['cnp'], 'name': r['name'], 'visits': r['visits'], 'total_value': float(r['total_value'])} for r in cur.fetchall()]

        # Top partners by value
        cur.execute("""
            SELECT p.cnp, p.name, COUNT(t.document_id) as visits, SUM(t.gross_value) as total_value
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            WHERE p.city ILIKE %s
               OR TRIM(REGEXP_REPLACE(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                REGEXP_REPLACE(p.city, '^(Com\\.?|Comuna)\\s*', '', 'i'),
                                '^(Oras|Or\\.?)\\s*', '', 'i'),
                            '^(Sat|S\\.?)\\s*', '', 'i'),
                        '^(Mun\\.?|Municipiul)\\s*', '', 'i'),
                    '^\\s+|\\s+$', '', 'g')
                  ) ILIKE %s
            GROUP BY p.cnp, p.name
            ORDER BY total_value DESC
            LIMIT 20
        """, (city_pattern, city))
        top_by_value = [{'cnp': r['cnp'], 'name': r['name'], 'visits': r['visits'], 'total_value': float(r['total_value'])} for r in cur.fetchall()]

        return {
            'city': city,
            'county': county,
            'partners': basic['partners'],
            'transactions': basic['transactions'],
            'total_kg': float(basic['total_kg']) if basic['total_kg'] else 0,
            'total_value': float(basic['total_value']) if basic['total_value'] else 0,
            'by_category': by_category,
            'top_by_visits': top_by_visits,
            'top_by_value': top_by_value
        }
