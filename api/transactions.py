"""
Transactions API - Tranzakciók lekérdezése
Endpoints:
  GET /api/transactions?date_from=2024-01-01&date_to=2024-12-31
  GET /api/transactions?cnp=1234567890123
  GET /api/transactions?document_id=PJ-123456
  GET /api/transactions?category=Cupru&date_from=2024-01-01
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

            # Get specific transaction by document_id
            if 'document_id' in params:
                doc_id = params['document_id'][0]
                result = self.get_transaction_details(cur, doc_id)

            # Get transactions for a partner
            elif 'cnp' in params:
                cnp = params['cnp'][0]
                date_from = params.get('date_from', [None])[0]
                date_to = params.get('date_to', [None])[0]
                limit = int(params.get('limit', [100])[0])
                result = self.get_partner_transactions(cur, cnp, date_from, date_to, limit)

            # Get transactions by date range and optional filters
            elif 'date_from' in params or 'date_to' in params:
                date_from = params.get('date_from', ['2022-01-01'])[0]
                date_to = params.get('date_to', ['2099-12-31'])[0]
                category = params.get('category', [None])[0]
                min_value = params.get('min_value', [None])[0]
                limit = int(params.get('limit', [500])[0])
                result = self.get_transactions_by_date(cur, date_from, date_to, category, min_value, limit)

            # Get daily summary
            elif 'daily' in params:
                date = params['daily'][0]
                result = self.get_daily_summary(cur, date)

            else:
                result = {
                    'error': 'Specify query params',
                    'examples': [
                        '?document_id=PJ-123456',
                        '?cnp=1234567890123',
                        '?date_from=2024-01-01&date_to=2024-12-31',
                        '?daily=2024-10-15',
                        '?date_from=2024-01-01&category=Cupru&min_value=1000'
                    ]
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

    def get_transaction_details(self, cur, doc_id):
        """Get full details of a specific transaction"""
        cur.execute("""
            SELECT t.*, p.name as partner_name, p.city, p.county
            FROM transactions t
            LEFT JOIN partners p ON t.cnp = p.cnp
            WHERE t.document_id = %s
        """, (doc_id,))
        trans = cur.fetchone()

        if not trans:
            return {'error': 'Transaction not found'}

        # Get items
        cur.execute("""
            SELECT ti.*, wt.name as waste_type, wc.name as category
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE ti.document_id = %s
            ORDER BY ti.value DESC
        """, (doc_id,))
        items = cur.fetchall()

        return {
            'transaction': {
                'document_id': trans['document_id'],
                'date': str(trans['date']),
                'cnp': trans['cnp'],
                'partner_name': trans['partner_name'],
                'city': trans['city'],
                'county': trans['county'],
                'payment_type': trans['payment_type'],
                'iban': trans['iban'],
                'gross_value': float(trans['gross_value']),
                'env_tax': float(trans['env_tax']) if trans['env_tax'] else 0,
                'income_tax': float(trans['income_tax']) if trans['income_tax'] else 0,
                'net_paid': float(trans['net_paid']) if trans['net_paid'] else 0
            },
            'items': [{
                'category': i['category'],
                'waste_type': i['waste_type'],
                'price_per_kg': float(i['price_per_kg']) if i['price_per_kg'] else 0,
                'weight_kg': float(i['weight_kg']),
                'value': float(i['value']) if i['value'] else 0
            } for i in items]
        }

    def get_partner_transactions(self, cur, cnp, date_from, date_to, limit):
        """Get all transactions for a partner"""
        query = """
            SELECT t.document_id, t.date, t.gross_value, t.net_paid, t.payment_type
            FROM transactions t
            WHERE t.cnp = %s
        """
        params = [cnp]

        if date_from:
            query += " AND t.date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND t.date <= %s"
            params.append(date_to)

        query += " ORDER BY t.date DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        transactions = cur.fetchall()

        return {
            'cnp': cnp,
            'count': len(transactions),
            'transactions': [{
                'document_id': t['document_id'],
                'date': str(t['date']),
                'gross_value': float(t['gross_value']),
                'net_paid': float(t['net_paid']) if t['net_paid'] else 0,
                'payment_type': t['payment_type']
            } for t in transactions]
        }

    def get_transactions_by_date(self, cur, date_from, date_to, category, min_value, limit):
        """Get transactions by date range with optional filters"""
        if category:
            query = """
                SELECT DISTINCT t.document_id, t.date, t.cnp, p.name as partner_name,
                       t.gross_value, t.payment_type
                FROM transactions t
                LEFT JOIN partners p ON t.cnp = p.cnp
                JOIN transaction_items ti ON t.document_id = ti.document_id
                JOIN waste_types wt ON ti.waste_type_id = wt.id
                JOIN waste_categories wc ON wt.category_id = wc.id
                WHERE t.date >= %s AND t.date <= %s
                  AND wc.name ILIKE %s
            """
            params = [date_from, date_to, f'%{category}%']
        else:
            query = """
                SELECT t.document_id, t.date, t.cnp, p.name as partner_name,
                       t.gross_value, t.payment_type
                FROM transactions t
                LEFT JOIN partners p ON t.cnp = p.cnp
                WHERE t.date >= %s AND t.date <= %s
            """
            params = [date_from, date_to]

        if min_value:
            query += " AND t.gross_value >= %s"
            params.append(float(min_value))

        query += " ORDER BY t.date DESC, t.gross_value DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        transactions = cur.fetchall()

        # Get summary
        cur.execute("""
            SELECT COUNT(*) as count,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COUNT(DISTINCT cnp) as unique_partners
            FROM transactions
            WHERE date >= %s AND date <= %s
        """, (date_from, date_to))
        summary = cur.fetchone()

        return {
            'date_range': {'from': date_from, 'to': date_to},
            'filters': {'category': category, 'min_value': min_value},
            'summary': {
                'total_transactions': summary['count'],
                'total_value': float(summary['total_value']),
                'unique_partners': summary['unique_partners']
            },
            'showing': len(transactions),
            'transactions': [{
                'document_id': t['document_id'],
                'date': str(t['date']),
                'cnp': t['cnp'],
                'partner_name': t['partner_name'],
                'gross_value': float(t['gross_value']),
                'payment_type': t['payment_type']
            } for t in transactions]
        }

    def get_daily_summary(self, cur, date):
        """Get detailed summary for a specific day"""
        # Overall stats
        cur.execute("""
            SELECT COUNT(*) as transactions,
                   COALESCE(SUM(gross_value), 0) as total_value,
                   COALESCE(SUM(net_paid), 0) as total_paid,
                   COUNT(DISTINCT cnp) as unique_partners
            FROM transactions
            WHERE date = %s
        """, (date,))
        stats = cur.fetchone()

        # By category
        cur.execute("""
            SELECT wc.name as category,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value
            FROM transactions t
            JOIN transaction_items ti ON t.document_id = ti.document_id
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            WHERE t.date = %s
            GROUP BY wc.name
            ORDER BY total_kg DESC
        """, (date,))
        categories = cur.fetchall()

        # Top transactions
        cur.execute("""
            SELECT t.document_id, p.name, t.gross_value
            FROM transactions t
            LEFT JOIN partners p ON t.cnp = p.cnp
            WHERE t.date = %s
            ORDER BY t.gross_value DESC
            LIMIT 10
        """, (date,))
        top = cur.fetchall()

        return {
            'date': date,
            'summary': {
                'transactions': stats['transactions'],
                'total_value': float(stats['total_value']),
                'total_paid': float(stats['total_paid']),
                'unique_partners': stats['unique_partners']
            },
            'by_category': [{
                'category': c['category'],
                'total_kg': float(c['total_kg']),
                'total_value': float(c['total_value']) if c['total_value'] else 0
            } for c in categories],
            'top_transactions': [{
                'document_id': t['document_id'],
                'partner_name': t['name'],
                'gross_value': float(t['gross_value'])
            } for t in top]
        }
