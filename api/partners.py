"""
Partner API - Keresés CNP/név alapján, partner részletek
Endpoints:
  GET /api/partners?q=keresés&limit=50
  GET /api/partners?cnp=1234567890123
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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query, keep_blank_values=True)

            conn = get_db()
            cur = conn.cursor()

            # Get specific partner by CNP
            if 'cnp' in params:
                cnp = params['cnp'][0]
                result = self.get_partner_details(cur, cnp)

            # Search partners by name or CNP fragment
            elif 'q' in params:
                query = params['q'][0]
                limit = int(params.get('limit', [50])[0])
                result = self.search_partners(cur, query, limit)

            # Get inactive partners
            elif 'inactive' in params:
                days = int(params['inactive'][0])
                limit = int(params.get('limit', [100])[0])
                result = self.get_inactive_partners(cur, days, limit)

            # Get top partners by value
            elif 'top' in params:
                limit = int(params['top'][0])
                category = params.get('category', [None])[0]
                result = self.get_top_partners(cur, limit, category)

            # Get one-time visitors
            elif 'onetime' in params:
                limit = int(params.get('limit', [100])[0])
                result = self.get_onetime_partners(cur, limit)

            # Advanced filter: date range + visit count range
            elif 'filter' in params:
                date_from = params.get('date_from', ['2024-01-01'])[0]
                date_to = params.get('date_to', ['2099-12-31'])[0]
                min_visits = int(params.get('min_visits', [1])[0])
                max_visits = int(params.get('max_visits', [999999])[0])
                category = params.get('category', [None])[0]
                min_kg = float(params.get('min_kg', [0])[0])
                limit = int(params.get('limit', [100])[0])
                result = self.get_filtered_partners(cur, date_from, date_to, min_visits, max_visits, category, min_kg, limit)

            # Regular visitors (weekly/monthly/yearly)
            elif 'regulars' in params:
                frequency = params['regulars'][0]  # weekly, monthly, yearly
                result = self.get_regular_partners(cur, frequency)

            # Same address partners (potential duplicates/family)
            elif 'same_address' in params:
                result = self.get_same_address_partners(cur)

            # Same family name + city
            elif 'same_family' in params:
                result = self.get_same_family_partners(cur)

            # Big suppliers by category with min visits
            elif 'big_suppliers' in params:
                category = params['big_suppliers'][0]
                min_kg = float(params.get('min_kg', [100])[0])
                min_visits = int(params.get('min_visits', [2])[0])
                year = params.get('year', [None])[0]
                result = self.get_big_suppliers(cur, category, min_kg, min_visits, year)

            else:
                result = {'error': 'Specify ?q=search, ?cnp=XXX, ?inactive=days, ?top=N, ?onetime, ?filter, ?regulars, ?same_address, ?same_family, or ?big_suppliers'}

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

    def search_partners(self, cur, query, limit):
        """Search partners by name or CNP"""
        cur.execute("""
            SELECT p.cnp, p.name, p.city, p.county,
                   COUNT(t.document_id) as visit_count,
                   COALESCE(SUM(t.gross_value), 0) as total_value,
                   MAX(t.date) as last_visit
            FROM partners p
            LEFT JOIN transactions t ON p.cnp = t.cnp
            WHERE p.name ILIKE %s OR p.cnp LIKE %s
            GROUP BY p.cnp, p.name, p.city, p.county
            ORDER BY total_value DESC
            LIMIT %s
        """, (f'%{query}%', f'%{query}%', limit))

        partners = cur.fetchall()
        return {
            'count': len(partners),
            'partners': [{
                'cnp': p['cnp'],
                'name': p['name'],
                'city': p['city'],
                'county': p['county'],
                'visit_count': p['visit_count'],
                'total_value': float(p['total_value']),
                'last_visit': str(p['last_visit']) if p['last_visit'] else None
            } for p in partners]
        }

    def get_partner_details(self, cur, cnp):
        """Get detailed info about a specific partner"""
        # Partner info
        cur.execute("""
            SELECT * FROM partners WHERE cnp = %s
        """, (cnp,))
        partner = cur.fetchone()

        if not partner:
            return {'error': 'Partner not found'}

        # Transaction summary
        cur.execute("""
            SELECT COUNT(*) as visit_count,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COALESCE(SUM(net_paid), 0) as total_paid,
                   MIN(date) as first_visit,
                   MAX(date) as last_visit
            FROM transactions
            WHERE cnp = %s
        """, (cnp,))
        summary = cur.fetchone()

        # Recent transactions
        cur.execute("""
            SELECT document_id, date, gross_value, net_paid, payment_type
            FROM transactions
            WHERE cnp = %s
            ORDER BY date DESC
            LIMIT 20
        """, (cnp,))
        transactions = cur.fetchall()

        # Waste type breakdown
        cur.execute("""
            SELECT wc.name as category,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value
            FROM transactions t
            JOIN transaction_items ti ON t.document_id = ti.document_id
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE t.cnp = %s
            GROUP BY wc.name
            ORDER BY total_kg DESC
        """, (cnp,))
        waste_breakdown = cur.fetchall()

        # Monthly pattern
        cur.execute("""
            SELECT TO_CHAR(date, 'YYYY-MM') as month,
                   COUNT(*) as visits,
                   SUM(gross_value) as value
            FROM transactions
            WHERE cnp = %s
            GROUP BY TO_CHAR(date, 'YYYY-MM')
            ORDER BY month DESC
            LIMIT 24
        """, (cnp,))
        monthly = cur.fetchall()

        return {
            'partner': {
                'cnp': partner['cnp'],
                'name': partner['name'],
                'city': partner['city'],
                'county': partner['county'],
                'street': partner['street'],
                'phone': partner['phone'],
                'email': partner['email'],
                'birth_year': partner['birth_year'],
                'sex': partner['sex'],
                'county_from_cnp': partner['county_from_cnp']
            },
            'summary': {
                'visit_count': summary['visit_count'],
                'total_value': float(summary['total_value']),
                'total_paid': float(summary['total_paid']),
                'first_visit': str(summary['first_visit']) if summary['first_visit'] else None,
                'last_visit': str(summary['last_visit']) if summary['last_visit'] else None,
                'days_since_last': None  # Will calculate on frontend
            },
            'recent_transactions': [{
                'document_id': t['document_id'],
                'date': str(t['date']),
                'gross_value': float(t['gross_value']),
                'net_paid': float(t['net_paid']) if t['net_paid'] else 0,
                'payment_type': t['payment_type']
            } for t in transactions],
            'waste_breakdown': [{
                'category': w['category'],
                'total_kg': float(w['total_kg']),
                'total_value': float(w['total_value']) if w['total_value'] else 0
            } for w in waste_breakdown],
            'monthly_pattern': [{
                'month': m['month'],
                'visits': m['visits'],
                'value': float(m['value'])
            } for m in monthly]
        }

    def get_inactive_partners(self, cur, days, limit):
        """Get partners who haven't visited in X days but were active before"""
        cur.execute("""
            SELECT p.cnp, p.name, p.city, p.county,
                   COUNT(t.document_id) as visit_count,
                   SUM(t.gross_value) as total_value,
                   MAX(t.date) as last_visit,
                   CURRENT_DATE - MAX(t.date) as days_inactive
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            GROUP BY p.cnp, p.name, p.city, p.county
            HAVING MAX(t.date) < CURRENT_DATE - %s
               AND COUNT(t.document_id) >= 2
            ORDER BY total_value DESC
            LIMIT %s
        """, (days, limit))

        partners = cur.fetchall()
        return {
            'days_threshold': days,
            'count': len(partners),
            'partners': [{
                'cnp': p['cnp'],
                'name': p['name'],
                'city': p['city'],
                'county': p['county'],
                'visit_count': p['visit_count'],
                'total_value': float(p['total_value']),
                'last_visit': str(p['last_visit']),
                'days_inactive': p['days_inactive']
            } for p in partners]
        }

    def get_top_partners(self, cur, limit, category=None):
        """Get top partners by value, optionally filtered by waste category"""
        if category:
            cur.execute("""
                SELECT p.cnp, p.name, p.city, p.county,
                       COUNT(DISTINCT t.document_id) as visit_count,
                       SUM(ti.weight_kg) as total_kg,
                       SUM(ti.value) as total_value
                FROM partners p
                JOIN transactions t ON p.cnp = t.cnp
                JOIN transaction_items ti ON t.document_id = ti.document_id
                JOIN waste_types wt ON ti.waste_type_id = wt.id
                JOIN waste_categories wc ON wt.category_id = wc.id
                WHERE wc.name ILIKE %s
                GROUP BY p.cnp, p.name, p.city, p.county
                ORDER BY total_kg DESC
                LIMIT %s
            """, (f'%{category}%', limit))
        else:
            cur.execute("""
                SELECT p.cnp, p.name, p.city, p.county,
                       COUNT(t.document_id) as visit_count,
                       SUM(t.gross_value) as total_value,
                       MAX(t.date) as last_visit
                FROM partners p
                JOIN transactions t ON p.cnp = t.cnp
                GROUP BY p.cnp, p.name, p.city, p.county
                ORDER BY total_value DESC
                LIMIT %s
            """, (limit,))

        partners = cur.fetchall()
        return {
            'category_filter': category,
            'count': len(partners),
            'partners': [{
                'cnp': p['cnp'],
                'name': p['name'],
                'city': p['city'],
                'county': p['county'],
                'visit_count': p['visit_count'],
                'total_value': float(p.get('total_value', 0) or 0),
                'total_kg': float(p['total_kg']) if 'total_kg' in p and p['total_kg'] else None,
                'last_visit': str(p['last_visit']) if 'last_visit' in p and p['last_visit'] else None
            } for p in partners]
        }

    def get_onetime_partners(self, cur, limit):
        """Get partners who visited only once"""
        cur.execute("""
            SELECT p.cnp, p.name, p.city, p.county,
                   t.date as visit_date,
                   t.gross_value
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            WHERE p.cnp IN (
                SELECT cnp FROM transactions GROUP BY cnp HAVING COUNT(*) = 1
            )
            ORDER BY t.gross_value DESC
            LIMIT %s
        """, (limit,))

        partners = cur.fetchall()
        return {
            'count': len(partners),
            'partners': [{
                'cnp': p['cnp'],
                'name': p['name'],
                'city': p['city'],
                'county': p['county'],
                'visit_date': str(p['visit_date']),
                'gross_value': float(p['gross_value'])
            } for p in partners]
        }

    def get_filtered_partners(self, cur, date_from, date_to, min_visits, max_visits, category, min_kg, limit):
        """Advanced partner filter with date range, visit count, category and min kg"""
        if category:
            cur.execute("""
                SELECT p.cnp, p.name, p.city, p.county,
                       COUNT(DISTINCT t.document_id) as visit_count,
                       SUM(ti.weight_kg) as total_kg,
                       SUM(ti.value) as total_value,
                       MIN(t.date) as first_visit,
                       MAX(t.date) as last_visit
                FROM partners p
                JOIN transactions t ON p.cnp = t.cnp
                JOIN transaction_items ti ON t.document_id = ti.document_id
                JOIN waste_types wt ON ti.waste_type_id = wt.id
                JOIN waste_categories wc ON wt.category_id = wc.id
                WHERE t.date >= %s AND t.date <= %s
                  AND wc.name ILIKE %s
                GROUP BY p.cnp, p.name, p.city, p.county
                HAVING COUNT(DISTINCT t.document_id) >= %s
                   AND COUNT(DISTINCT t.document_id) <= %s
                   AND SUM(ti.weight_kg) >= %s
                ORDER BY total_kg DESC
                LIMIT %s
            """, (date_from, date_to, f'%{category}%', min_visits, max_visits, min_kg, limit))
        else:
            cur.execute("""
                SELECT p.cnp, p.name, p.city, p.county,
                       COUNT(t.document_id) as visit_count,
                       SUM(t.gross_value) as total_value,
                       SUM(t.net_paid) as total_paid,
                       MIN(t.date) as first_visit,
                       MAX(t.date) as last_visit
                FROM partners p
                JOIN transactions t ON p.cnp = t.cnp
                WHERE t.date >= %s AND t.date <= %s
                GROUP BY p.cnp, p.name, p.city, p.county
                HAVING COUNT(t.document_id) >= %s
                   AND COUNT(t.document_id) <= %s
                ORDER BY total_value DESC
                LIMIT %s
            """, (date_from, date_to, min_visits, max_visits, limit))

        partners = cur.fetchall()
        return {
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
                'min_visits': min_visits,
                'max_visits': max_visits,
                'category': category,
                'min_kg': min_kg
            },
            'count': len(partners),
            'partners': [{
                'cnp': p['cnp'],
                'name': p['name'],
                'city': p['city'],
                'county': p['county'],
                'visit_count': p['visit_count'],
                'total_value': float(p.get('total_value', 0) or 0),
                'total_kg': float(p['total_kg']) if 'total_kg' in p and p['total_kg'] else None,
                'total_paid': float(p['total_paid']) if 'total_paid' in p and p['total_paid'] else None,
                'first_visit': str(p['first_visit']) if p['first_visit'] else None,
                'last_visit': str(p['last_visit']) if p['last_visit'] else None
            } for p in partners]
        }

    def get_regular_partners(self, cur, frequency):
        """Get partners who visit regularly (weekly, monthly, yearly)"""
        if frequency == 'weekly':
            # Partners who visited at least 4 different weeks in both 2024 and 2025
            cur.execute("""
                WITH weekly_visits AS (
                    SELECT cnp,
                           EXTRACT(YEAR FROM date) as year,
                           COUNT(DISTINCT DATE_TRUNC('week', date)) as weeks_visited
                    FROM transactions
                    GROUP BY cnp, EXTRACT(YEAR FROM date)
                )
                SELECT p.cnp, p.name, p.city, p.county,
                       COUNT(t.document_id) as total_visits,
                       SUM(t.gross_value) as total_value
                FROM partners p
                JOIN transactions t ON p.cnp = t.cnp
                WHERE p.cnp IN (
                    SELECT w1.cnp FROM weekly_visits w1
                    JOIN weekly_visits w2 ON w1.cnp = w2.cnp
                    WHERE w1.year = 2024 AND w2.year = 2025
                      AND w1.weeks_visited >= 4 AND w2.weeks_visited >= 4
                )
                GROUP BY p.cnp, p.name, p.city, p.county
                ORDER BY total_visits DESC
                LIMIT 100
            """)
        elif frequency == 'monthly':
            # Partners who visited at least 6 different months in both years
            cur.execute("""
                WITH monthly_visits AS (
                    SELECT cnp,
                           EXTRACT(YEAR FROM date) as year,
                           COUNT(DISTINCT EXTRACT(MONTH FROM date)) as months_visited
                    FROM transactions
                    GROUP BY cnp, EXTRACT(YEAR FROM date)
                )
                SELECT p.cnp, p.name, p.city, p.county,
                       COUNT(t.document_id) as total_visits,
                       SUM(t.gross_value) as total_value
                FROM partners p
                JOIN transactions t ON p.cnp = t.cnp
                WHERE p.cnp IN (
                    SELECT m1.cnp FROM monthly_visits m1
                    JOIN monthly_visits m2 ON m1.cnp = m2.cnp
                    WHERE m1.year = 2024 AND m2.year = 2025
                      AND m1.months_visited >= 6 AND m2.months_visited >= 4
                )
                GROUP BY p.cnp, p.name, p.city, p.county
                ORDER BY total_visits DESC
                LIMIT 100
            """)
        else:  # yearly - visited in both years
            cur.execute("""
                SELECT p.cnp, p.name, p.city, p.county,
                       COUNT(t.document_id) as total_visits,
                       SUM(t.gross_value) as total_value,
                       COUNT(DISTINCT EXTRACT(YEAR FROM t.date)) as years_active
                FROM partners p
                JOIN transactions t ON p.cnp = t.cnp
                GROUP BY p.cnp, p.name, p.city, p.county
                HAVING COUNT(DISTINCT EXTRACT(YEAR FROM t.date)) >= 2
                ORDER BY total_value DESC
                LIMIT 100
            """)

        partners = cur.fetchall()
        return {
            'frequency': frequency,
            'count': len(partners),
            'partners': [{
                'cnp': p['cnp'],
                'name': p['name'],
                'city': p['city'],
                'county': p['county'],
                'total_visits': p['total_visits'],
                'total_value': float(p['total_value'])
            } for p in partners]
        }

    def get_same_address_partners(self, cur):
        """Find partners with same city + street (potential duplicates/family)"""
        cur.execute("""
            SELECT p.city, p.street, p.county,
                   array_agg(p.name) as names,
                   array_agg(p.cnp) as cnps,
                   COUNT(*) as partner_count,
                   SUM(stats.total_value) as combined_value
            FROM partners p
            JOIN (
                SELECT cnp, SUM(gross_value) as total_value
                FROM transactions
                GROUP BY cnp
            ) stats ON p.cnp = stats.cnp
            WHERE p.city IS NOT NULL AND p.street IS NOT NULL
              AND LENGTH(p.street) > 3
            GROUP BY p.city, p.street, p.county
            HAVING COUNT(*) >= 2
            ORDER BY combined_value DESC
            LIMIT 50
        """)

        groups = cur.fetchall()
        return {
            'count': len(groups),
            'groups': [{
                'city': g['city'],
                'street': g['street'],
                'county': g['county'],
                'partner_count': g['partner_count'],
                'names': g['names'],
                'cnps': g['cnps'],
                'combined_value': float(g['combined_value'])
            } for g in groups]
        }

    def get_same_family_partners(self, cur):
        """Find partners with same family name (first word) + same city"""
        cur.execute("""
            WITH family_names AS (
                SELECT cnp, name, city, county, street,
                       SPLIT_PART(name, ' ', 1) as family_name
                FROM partners
                WHERE name IS NOT NULL AND city IS NOT NULL
            )
            SELECT f.family_name, f.city, f.county,
                   array_agg(f.name) as names,
                   array_agg(f.cnp) as cnps,
                   array_agg(f.street) as streets,
                   COUNT(*) as partner_count,
                   SUM(COALESCE(stats.total_value, 0)) as combined_value
            FROM family_names f
            LEFT JOIN (
                SELECT cnp, SUM(gross_value) as total_value
                FROM transactions
                GROUP BY cnp
            ) stats ON f.cnp = stats.cnp
            GROUP BY f.family_name, f.city, f.county
            HAVING COUNT(*) >= 2
            ORDER BY combined_value DESC
            LIMIT 50
        """)

        groups = cur.fetchall()
        return {
            'count': len(groups),
            'groups': [{
                'family_name': g['family_name'],
                'city': g['city'],
                'county': g['county'],
                'partner_count': g['partner_count'],
                'names': g['names'],
                'cnps': g['cnps'],
                'streets': g['streets'],
                'combined_value': float(g['combined_value']) if g['combined_value'] else 0,
                'same_street': len(set([s for s in g['streets'] if s])) == 1 if g['streets'] else False
            } for g in groups]
        }

    def get_big_suppliers(self, cur, category, min_kg, min_visits, year):
        """Get big suppliers for a specific category with minimum kg and visits"""
        year_filter = ""
        params = [f'%{category}%', min_kg, min_visits]

        if year:
            year_filter = "AND EXTRACT(YEAR FROM t.date) = %s"
            params.append(int(year))

        params.append(100)  # limit

        cur.execute(f"""
            SELECT p.cnp, p.name, p.city, p.county,
                   COUNT(DISTINCT t.document_id) as visit_count,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value,
                   MIN(t.date) as first_visit,
                   MAX(t.date) as last_visit,
                   AVG(ti.price_per_kg) as avg_price
            FROM partners p
            JOIN transactions t ON p.cnp = t.cnp
            JOIN transaction_items ti ON t.document_id = ti.document_id
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE wc.name ILIKE %s
              {year_filter}
            GROUP BY p.cnp, p.name, p.city, p.county
            HAVING SUM(ti.weight_kg) >= %s
               AND COUNT(DISTINCT t.document_id) >= %s
            ORDER BY total_kg DESC
            LIMIT %s
        """, params)

        partners = cur.fetchall()
        return {
            'category': category,
            'min_kg': min_kg,
            'min_visits': min_visits,
            'year': year,
            'count': len(partners),
            'partners': [{
                'cnp': p['cnp'],
                'name': p['name'],
                'city': p['city'],
                'county': p['county'],
                'visit_count': p['visit_count'],
                'total_kg': float(p['total_kg']),
                'total_value': float(p['total_value']),
                'avg_price': float(p['avg_price']) if p['avg_price'] else 0,
                'first_visit': str(p['first_visit']),
                'last_visit': str(p['last_visit'])
            } for p in partners]
        }
