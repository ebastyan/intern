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
            params = parse_qs(parsed.query)

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

            else:
                result = {'error': 'Specify ?q=search, ?cnp=XXX, ?inactive=days, ?top=N, or ?onetime'}

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
