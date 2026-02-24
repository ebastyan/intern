"""
Waste API - Hulladék típusok és statisztikák
Endpoints:
  GET /api/waste?type=categories
  GET /api/waste?type=types
  GET /api/waste?type=prices&category=Cupru
  GET /api/waste?type=top&category=Fier&limit=20
  GET /api/waste?type=monthly&category=Aluminiu
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

            query_type = params.get('type', ['categories'])[0]

            if query_type == 'categories':
                result = self.get_categories(cur)
            elif query_type == 'types':
                category = params.get('category', [None])[0]
                result = self.get_types(cur, category)
            elif query_type == 'prices':
                category = params.get('category', [None])[0]
                result = self.get_price_history(cur, category)
            elif query_type == 'top':
                category = params.get('category', [None])[0]
                limit = int(params.get('limit', [20])[0])
                date_from = params.get('date_from', [None])[0]
                date_to = params.get('date_to', [None])[0]
                result = self.get_top_by_category(cur, category, limit, date_from, date_to)
            elif query_type == 'monthly':
                category = params.get('category', [None])[0]
                year = params.get('year', [None])[0]
                result = self.get_monthly_by_category(cur, category, year)
            elif query_type == 'search':
                # Find who brought specific waste type at specific price range
                waste_type = params.get('waste', [None])[0]
                min_price = params.get('min_price', [None])[0]
                max_price = params.get('max_price', [None])[0]
                date_from = params.get('date_from', [None])[0]
                date_to = params.get('date_to', [None])[0]
                limit = int(params.get('limit', [100])[0])
                result = self.search_waste_transactions(cur, waste_type, min_price, max_price, date_from, date_to, limit)
            elif query_type == 'analysis':
                waste_type_ids = params.get('waste_type_ids', [None])[0]
                categories = params.get('categories', [None])[0]
                date_from = params.get('date_from', [None])[0]
                date_to = params.get('date_to', [None])[0]
                aggregation = params.get('aggregation', ['monthly'])[0]
                result = self.get_waste_analysis(cur, waste_type_ids, categories, date_from, date_to, aggregation)
            else:
                result = {
                    'error': 'Unknown query type',
                    'available': ['categories', 'types', 'prices', 'top', 'monthly', 'search', 'analysis']
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

    def get_categories(self, cur):
        """Get all waste categories with totals"""
        cur.execute("""
            SELECT wc.id, wc.name,
                   COUNT(DISTINCT wt.id) as type_count,
                   COALESCE(SUM(ti.weight_kg), 0) as total_kg,
                   COALESCE(SUM(ti.value), 0) as total_value,
                   COUNT(DISTINCT t.document_id) as transaction_count
            FROM waste_categories wc
            LEFT JOIN waste_types wt ON wc.id = wt.category_id
            LEFT JOIN transaction_items ti ON wt.id = ti.waste_type_id
            LEFT JOIN transactions t ON ti.document_id = t.document_id
            GROUP BY wc.id, wc.name
            ORDER BY total_kg DESC
        """)
        categories = cur.fetchall()

        return {
            'categories': [{
                'id': c['id'],
                'name': c['name'],
                'type_count': c['type_count'],
                'total_kg': float(c['total_kg']),
                'total_value': float(c['total_value']),
                'transaction_count': c['transaction_count']
            } for c in categories]
        }

    def get_types(self, cur, category=None):
        """Get all waste types, optionally filtered by category"""
        query = """
            SELECT wt.id, wt.name, wc.name as category,
                   COALESCE(SUM(ti.weight_kg), 0) as total_kg,
                   COALESCE(SUM(ti.value), 0) as total_value,
                   COUNT(DISTINCT ti.document_id) as transaction_count,
                   MIN(ti.price_per_kg) as min_price,
                   MAX(ti.price_per_kg) as max_price,
                   AVG(ti.price_per_kg) as avg_price
            FROM waste_types wt
            JOIN waste_categories wc ON wt.category_id = wc.id
            LEFT JOIN transaction_items ti ON wt.id = ti.waste_type_id
        """
        params = []
        if category:
            query += " WHERE wc.name ILIKE %s"
            params.append(f'%{category}%')

        query += " GROUP BY wt.id, wt.name, wc.name ORDER BY total_kg DESC"

        cur.execute(query, params)
        types = cur.fetchall()

        return {
            'category_filter': category,
            'types': [{
                'id': t['id'],
                'name': t['name'],
                'category': t['category'],
                'total_kg': float(t['total_kg']),
                'total_value': float(t['total_value']),
                'transaction_count': t['transaction_count'],
                'price_range': {
                    'min': float(t['min_price']) if t['min_price'] else None,
                    'max': float(t['max_price']) if t['max_price'] else None,
                    'avg': round(float(t['avg_price']), 2) if t['avg_price'] else None
                }
            } for t in types]
        }

    def get_price_history(self, cur, category):
        """Get price variations by month for a category"""
        if not category:
            return {'error': 'Specify category parameter'}

        cur.execute("""
            SELECT TO_CHAR(t.date, 'YYYY-MM') as month,
                   wt.name as waste_type,
                   MIN(ti.price_per_kg) as min_price,
                   MAX(ti.price_per_kg) as max_price,
                   AVG(ti.price_per_kg) as avg_price,
                   SUM(ti.weight_kg) as total_kg
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            WHERE wc.name ILIKE %s
            GROUP BY TO_CHAR(t.date, 'YYYY-MM'), wt.name
            ORDER BY month, waste_type
        """, (f'%{category}%',))
        data = cur.fetchall()

        # Organize by month
        by_month = {}
        for d in data:
            month = d['month']
            if month not in by_month:
                by_month[month] = []
            by_month[month].append({
                'waste_type': d['waste_type'],
                'min_price': float(d['min_price']) if d['min_price'] else None,
                'max_price': float(d['max_price']) if d['max_price'] else None,
                'avg_price': round(float(d['avg_price']), 2) if d['avg_price'] else None,
                'total_kg': float(d['total_kg'])
            })

        return {
            'category': category,
            'price_history': by_month
        }

    def get_top_by_category(self, cur, category, limit, date_from, date_to):
        """Get top partners/transactions for a specific category"""
        if not category:
            return {'error': 'Specify category parameter'}

        query = """
            SELECT p.cnp, p.name, p.city, p.county,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value,
                   COUNT(DISTINCT t.document_id) as transaction_count
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            JOIN partners p ON t.cnp = p.cnp
            WHERE wc.name ILIKE %s
        """
        params = [f'%{category}%']

        if date_from:
            query += " AND t.date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND t.date <= %s"
            params.append(date_to)

        query += """
            GROUP BY p.cnp, p.name, p.city, p.county
            ORDER BY total_kg DESC
            LIMIT %s
        """
        params.append(limit)

        cur.execute(query, params)
        top = cur.fetchall()

        return {
            'category': category,
            'date_range': {'from': date_from, 'to': date_to},
            'top_partners': [{
                'cnp': t['cnp'],
                'name': t['name'],
                'city': t['city'],
                'county': t['county'],
                'total_kg': float(t['total_kg']),
                'total_value': float(t['total_value']),
                'transaction_count': t['transaction_count']
            } for t in top]
        }

    def get_monthly_by_category(self, cur, category, year):
        """Get monthly totals for a category"""
        if not category:
            return {'error': 'Specify category parameter'}

        query = """
            SELECT EXTRACT(YEAR FROM t.date)::int as year,
                   EXTRACT(MONTH FROM t.date)::int as month,
                   SUM(ti.weight_kg) as total_kg,
                   SUM(ti.value) as total_value,
                   COUNT(DISTINCT t.document_id) as transaction_count,
                   COUNT(DISTINCT t.cnp) as unique_partners,
                   AVG(ti.price_per_kg) as avg_price
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            WHERE wc.name ILIKE %s
        """
        params = [f'%{category}%']

        if year:
            query += " AND EXTRACT(YEAR FROM t.date) = %s"
            params.append(int(year))

        query += """
            GROUP BY EXTRACT(YEAR FROM t.date), EXTRACT(MONTH FROM t.date)
            ORDER BY year, month
        """

        cur.execute(query, params)
        months = cur.fetchall()

        return {
            'category': category,
            'year_filter': year,
            'monthly': [{
                'year': m['year'],
                'month': m['month'],
                'total_kg': float(m['total_kg']),
                'total_value': float(m['total_value']),
                'transaction_count': m['transaction_count'],
                'unique_partners': m['unique_partners'],
                'avg_price': round(float(m['avg_price']), 2) if m['avg_price'] else None
            } for m in months]
        }

    def search_waste_transactions(self, cur, waste_type, min_price, max_price, date_from, date_to, limit):
        """Search for transactions with specific waste type and price range"""
        if not waste_type:
            return {'error': 'Specify waste parameter (e.g., waste=Cupru)'}

        query = """
            SELECT t.document_id, t.date, p.name, p.city, p.county,
                   wt.name as waste_type, wc.name as category,
                   ti.price_per_kg, ti.weight_kg, ti.value
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            LEFT JOIN partners p ON t.cnp = p.cnp
            WHERE (wt.name ILIKE %s OR wc.name ILIKE %s)
        """
        params = [f'%{waste_type}%', f'%{waste_type}%']

        if min_price:
            query += " AND ti.price_per_kg >= %s"
            params.append(float(min_price))
        if max_price:
            query += " AND ti.price_per_kg <= %s"
            params.append(float(max_price))
        if date_from:
            query += " AND t.date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND t.date <= %s"
            params.append(date_to)

        query += " ORDER BY t.date DESC, ti.value DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, params)
        results = cur.fetchall()

        return {
            'search_params': {
                'waste_type': waste_type,
                'price_range': {'min': min_price, 'max': max_price},
                'date_range': {'from': date_from, 'to': date_to}
            },
            'count': len(results),
            'transactions': [{
                'document_id': r['document_id'],
                'date': str(r['date']),
                'partner_name': r['name'],
                'city': r['city'],
                'county': r['county'],
                'category': r['category'],
                'waste_type': r['waste_type'],
                'price_per_kg': float(r['price_per_kg']) if r['price_per_kg'] else None,
                'weight_kg': float(r['weight_kg']),
                'value': float(r['value']) if r['value'] else None
            } for r in results]
        }

    def get_waste_analysis(self, cur, waste_type_ids, categories, date_from, date_to, aggregation):
        """Detailed waste analysis by type with time aggregation.
        Supports waste_type_ids (individual types) and/or categories (whole categories).
        Categories are grouped as a single series per category name."""
        ids = []
        cat_names = []

        if waste_type_ids:
            ids = [int(x.strip()) for x in waste_type_ids.split(',') if x.strip().isdigit()]
        if categories:
            cat_names = [c.strip() for c in categories.split(',') if c.strip()]

        if not ids and not cat_names:
            return {'error': 'Specify waste_type_ids and/or categories parameter'}

        # Resolve categories: find which type IDs belong to selected categories
        cat_type_ids = {}  # cat_name -> set of type IDs
        if cat_names:
            cat_ph = ','.join(['%s'] * len(cat_names))
            cur.execute(f"""
                SELECT wt.id, wc.name as category
                FROM waste_types wt
                JOIN waste_categories wc ON wt.category_id = wc.id
                WHERE wc.name IN ({cat_ph})
            """, cat_names)
            for row in cur.fetchall():
                cat = row['category']
                if cat not in cat_type_ids:
                    cat_type_ids[cat] = set()
                cat_type_ids[cat].add(row['id'])

        # Build mapping: type_id -> group_key (either type_id for individual, or "cat:CatName" for category)
        type_to_group = {}
        for cat, type_ids_in_cat in cat_type_ids.items():
            for tid in type_ids_in_cat:
                type_to_group[tid] = f"cat:{cat}"

        # Individual type IDs override category grouping
        for tid in ids:
            type_to_group[tid] = f"type:{tid}"

        # All type IDs to query
        all_ids = set(ids)
        for type_ids_in_cat in cat_type_ids.values():
            all_ids.update(type_ids_in_cat)

        if not all_ids:
            return {'error': 'No matching waste types found'}

        # Period grouping
        if aggregation == 'daily':
            period_expr = "TO_CHAR(t.date, 'YYYY-MM-DD')"
        elif aggregation == 'yearly':
            period_expr = "TO_CHAR(t.date, 'YYYY')"
        else:
            period_expr = "TO_CHAR(t.date, 'YYYY-MM')"

        id_list = list(all_ids)
        placeholders = ','.join(['%s'] * len(id_list))
        query = f"""
            SELECT {period_expr} as period,
                   wt.id as waste_type_id,
                   wt.name as waste_name,
                   wc.name as category,
                   COALESCE(SUM(ti.weight_kg), 0) as total_kg,
                   COALESCE(SUM(ti.value), 0) as total_value,
                   COUNT(DISTINCT t.document_id) as transaction_count,
                   AVG(ti.price_per_kg) as avg_price
            FROM transaction_items ti
            JOIN waste_types wt ON ti.waste_type_id = wt.id
            JOIN waste_categories wc ON wt.category_id = wc.id
            JOIN transactions t ON ti.document_id = t.document_id
            WHERE wt.id IN ({placeholders})
        """
        params = list(id_list)

        if date_from:
            query += " AND t.date >= %s"
            params.append(date_from)
        if date_to:
            query += " AND t.date <= %s"
            params.append(date_to)

        query += f"""
            GROUP BY {period_expr}, wt.id, wt.name, wc.name
            ORDER BY period, wt.name
        """

        cur.execute(query, params)
        rows = cur.fetchall()

        # Collect unique periods and build series, merging by group key
        periods = []
        series_map = {}  # group_key -> series data
        for r in rows:
            p = r['period']
            if p not in periods:
                periods.append(p)

            wid = r['waste_type_id']
            group_key = type_to_group.get(wid, f"type:{wid}")

            if group_key not in series_map:
                if group_key.startswith('cat:'):
                    display_name = group_key[4:]  # category name
                else:
                    display_name = r['waste_name']
                series_map[group_key] = {
                    'waste_type_id': wid,
                    'name': display_name,
                    'category': r['category'],
                    'data': {},
                    'totals': {'kg': 0, 'value': 0, 'transactions': 0}
                }

            s = series_map[group_key]
            kg = float(r['total_kg'])
            val = float(r['total_value'])
            trans = r['transaction_count']

            if p in s['data']:
                s['data'][p]['kg'] += kg
                s['data'][p]['value'] += val
                s['data'][p]['transactions'] += trans
            else:
                s['data'][p] = {
                    'kg': kg,
                    'value': val,
                    'transactions': trans,
                    'avg_price': round(float(r['avg_price']), 2) if r['avg_price'] else None
                }
            s['totals']['kg'] += kg
            s['totals']['value'] += val
            s['totals']['transactions'] += trans

        periods.sort()

        # Build final series with ordered data arrays
        series = []
        total_kg = 0
        total_value = 0
        for wid, s in series_map.items():
            ordered_data = []
            for p in periods:
                ordered_data.append(s['data'].get(p, {'kg': 0, 'value': 0, 'transactions': 0, 'avg_price': None}))
            s['data'] = ordered_data
            s['totals']['kg'] = round(s['totals']['kg'], 2)
            s['totals']['value'] = round(s['totals']['value'], 2)
            total_kg += s['totals']['kg']
            total_value += s['totals']['value']
            series.append(s)

        period_count = len(periods) if periods else 1

        return {
            'aggregation': aggregation,
            'periods': periods,
            'series': series,
            'summary': {
                'total_kg': round(total_kg, 2),
                'total_value': round(total_value, 2),
                'period_count': len(periods),
                'avg_kg_per_period': round(total_kg / period_count, 2)
            }
        }
