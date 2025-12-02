"""
Firme API - Vanzari catre firme (B2B)
=====================================
Endpoints:
  GET /api/firme?type=overview - Sumar general
  GET /api/firme?type=list - Lista firme
  GET /api/firme?type=firma&id=X - Detalii firma
  GET /api/firme?type=vanzari&firma_id=X - Vanzari firma
  GET /api/firme?type=monthly&year=2024 - Date lunare
  GET /api/firme?type=deseuri&year=2024 - Sumar deseuri
  GET /api/firme?type=top - Top firme
  GET /api/firme?type=transporturi - Transporturi
  GET /api/firme?type=yearly - Comparatie anuala
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qs
from decimal import Decimal

def get_db():
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

            query_type = params.get('type', ['overview'])[0]

            if query_type == 'overview':
                year = params.get('year', [None])[0]
                result = self.get_overview(cur, year)
            elif query_type == 'list':
                year = params.get('year', [None])[0]
                search = params.get('search', [None])[0]
                result = self.get_firme_list(cur, year, search)
            elif query_type == 'firma':
                firma_id = params.get('id', [None])[0]
                result = self.get_firma_details(cur, firma_id)
            elif query_type == 'vanzari':
                firma_id = params.get('firma_id', [None])[0]
                year = params.get('year', [None])[0]
                month = params.get('month', [None])[0]
                result = self.get_vanzari(cur, firma_id, year, month)
            elif query_type == 'monthly':
                year = params.get('year', [None])[0]
                result = self.get_monthly_summary(cur, year)
            elif query_type == 'deseuri':
                year = params.get('year', [None])[0]
                month = params.get('month', [None])[0]
                result = self.get_deseuri_summary(cur, year, month)
            elif query_type == 'top':
                year = params.get('year', [None])[0]
                limit = int(params.get('limit', [10])[0])
                result = self.get_top_firme(cur, year, limit)
            elif query_type == 'transporturi':
                year = params.get('year', [None])[0]
                result = self.get_transporturi(cur, year)
            elif query_type == 'yearly':
                result = self.get_yearly_comparison(cur)
            else:
                result = {
                    'error': 'Unknown query type',
                    'available': ['overview', 'list', 'firma', 'vanzari', 'monthly', 'deseuri', 'top', 'transporturi', 'yearly']
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

    def get_overview(self, cur, year=None):
        """Get overall B2B business overview"""
        # Total stats
        if year:
            cur.execute("""
                SELECT COUNT(*) as total_vanzari,
                       COUNT(DISTINCT firma_id) as firme_active,
                       COALESCE(SUM(valoare_ron), 0) as total_valoare,
                       COALESCE(SUM(adaos_final), 0) as total_profit,
                       COALESCE(SUM(cantitate_receptionata), 0) as total_kg,
                       MIN(data) as first_date,
                       MAX(data) as last_date
                FROM vanzari
                WHERE year = %s
            """, (int(year),))
        else:
            cur.execute("""
                SELECT COUNT(*) as total_vanzari,
                       COUNT(DISTINCT firma_id) as firme_active,
                       COALESCE(SUM(valoare_ron), 0) as total_valoare,
                       COALESCE(SUM(adaos_final), 0) as total_profit,
                       COALESCE(SUM(cantitate_receptionata), 0) as total_kg,
                       MIN(data) as first_date,
                       MAX(data) as last_date
                FROM vanzari
            """)
        totals = cur.fetchone()

        # Total firme
        cur.execute("SELECT COUNT(*) as count FROM firme")
        total_firme = cur.fetchone()['count']

        # By year
        cur.execute("""
            SELECT year,
                   COUNT(*) as vanzari,
                   COALESCE(SUM(valoare_ron), 0) as valoare,
                   COALESCE(SUM(adaos_final), 0) as profit,
                   COALESCE(SUM(cantitate_receptionata), 0) as kg
            FROM vanzari
            GROUP BY year
            ORDER BY year
        """)
        by_year = cur.fetchall()

        # Recent month
        cur.execute("""
            SELECT COALESCE(SUM(valoare_ron), 0) as valoare,
                   COALESCE(SUM(adaos_final), 0) as profit,
                   COUNT(*) as vanzari
            FROM vanzari
            WHERE data >= CURRENT_DATE - INTERVAL '30 days'
        """)
        recent = cur.fetchone()

        return {
            'overview': {
                'total_firme': total_firme,
                'firme_active': totals['firme_active'],
                'total_vanzari': totals['total_vanzari'],
                'total_valoare_ron': float(totals['total_valoare']),
                'total_profit_ron': float(totals['total_profit']),
                'total_kg': float(totals['total_kg']),
                'profit_margin': round(float(totals['total_profit']) / float(totals['total_valoare']) * 100, 2) if totals['total_valoare'] else 0,
                'date_range': {
                    'from': str(totals['first_date']),
                    'to': str(totals['last_date'])
                }
            },
            'by_year': [{
                'year': y['year'],
                'vanzari': y['vanzari'],
                'valoare_ron': float(y['valoare']),
                'profit_ron': float(y['profit']),
                'kg': float(y['kg'])
            } for y in by_year],
            'last_30_days': {
                'valoare_ron': float(recent['valoare']),
                'profit_ron': float(recent['profit']),
                'vanzari': recent['vanzari']
            }
        }

    def get_firme_list(self, cur, year=None, search=None):
        """Get list of all companies with stats, optionally filtered by year"""
        query = """
            SELECT f.id, f.name,
                   COUNT(v.id) as nr_vanzari,
                   COALESCE(SUM(v.valoare_ron), 0) as total_valoare,
                   COALESCE(SUM(v.adaos_final), 0) as total_profit,
                   COALESCE(SUM(v.cantitate_receptionata), 0) as total_kg,
                   MIN(v.data) as first_sale,
                   MAX(v.data) as last_sale
            FROM firme f
            LEFT JOIN vanzari v ON f.id = v.firma_id
        """
        conditions = []
        params = []

        if year:
            conditions.append("v.year = %s")
            params.append(int(year))

        if search:
            conditions.append("LOWER(f.name) LIKE %s")
            params.append(f"%{search.lower()}%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " GROUP BY f.id, f.name HAVING COUNT(v.id) > 0 ORDER BY total_valoare DESC"

        cur.execute(query, params)
        firme = cur.fetchall()

        return {
            'count': len(firme),
            'filters': {'year': year, 'search': search},
            'firme': [{
                'id': f['id'],
                'name': f['name'],
                'nr_vanzari': f['nr_vanzari'],
                'total_valoare': float(f['total_valoare']),
                'total_profit': float(f['total_profit']),
                'total_kg': float(f['total_kg']),
                'first_sale': str(f['first_sale']) if f['first_sale'] else None,
                'last_sale': str(f['last_sale']) if f['last_sale'] else None
            } for f in firme]
        }

    def get_firma_details(self, cur, firma_id):
        """Get detailed info about a specific company"""
        if not firma_id:
            return {'error': 'firma_id required'}

        # Basic info
        cur.execute("""
            SELECT f.*,
                   COUNT(v.id) as nr_vanzari,
                   COALESCE(SUM(v.valoare_ron), 0) as total_valoare,
                   COALESCE(SUM(v.adaos_final), 0) as total_profit,
                   COALESCE(SUM(v.cantitate_receptionata), 0) as total_kg,
                   MIN(v.data) as first_sale,
                   MAX(v.data) as last_sale
            FROM firme f
            LEFT JOIN vanzari v ON f.id = v.firma_id
            WHERE f.id = %s
            GROUP BY f.id
        """, (firma_id,))
        firma = cur.fetchone()

        if not firma:
            return {'error': 'Firma not found'}

        # Monthly breakdown
        cur.execute("""
            SELECT year, month,
                   COUNT(*) as nr_vanzari,
                   COALESCE(SUM(valoare_ron), 0) as valoare,
                   COALESCE(SUM(adaos_final), 0) as profit,
                   COALESCE(SUM(cantitate_receptionata), 0) as kg
            FROM vanzari
            WHERE firma_id = %s
            GROUP BY year, month
            ORDER BY year, month
        """, (firma_id,))
        monthly = cur.fetchall()

        # Recent vanzari
        cur.execute("""
            SELECT data, numar_aviz, cantitate_livrata, cantitate_receptionata,
                   pret_achizitie, pret_vanzare, valoare_ron, adaos_final, tip_deseu
            FROM vanzari
            WHERE firma_id = %s
            ORDER BY data DESC
            LIMIT 50
        """, (firma_id,))
        recent = cur.fetchall()

        return {
            'firma': {
                'id': firma['id'],
                'name': firma['name'],
                'nr_vanzari': firma['nr_vanzari'],
                'total_valoare': float(firma['total_valoare']),
                'total_profit': float(firma['total_profit']),
                'total_kg': float(firma['total_kg']),
                'profit_margin': round(float(firma['total_profit']) / float(firma['total_valoare']) * 100, 2) if firma['total_valoare'] else 0,
                'first_sale': str(firma['first_sale']) if firma['first_sale'] else None,
                'last_sale': str(firma['last_sale']) if firma['last_sale'] else None
            },
            'monthly': [{
                'year': m['year'],
                'month': m['month'],
                'nr_vanzari': m['nr_vanzari'],
                'valoare': float(m['valoare']),
                'profit': float(m['profit']),
                'kg': float(m['kg'])
            } for m in monthly],
            'recent_vanzari': [{
                'data': str(v['data']),
                'numar_aviz': v['numar_aviz'],
                'cantitate_livrata': float(v['cantitate_livrata']) if v['cantitate_livrata'] else 0,
                'cantitate_receptionata': float(v['cantitate_receptionata']) if v['cantitate_receptionata'] else 0,
                'pret_achizitie': float(v['pret_achizitie']) if v['pret_achizitie'] else 0,
                'pret_vanzare': float(v['pret_vanzare']) if v['pret_vanzare'] else 0,
                'valoare_ron': float(v['valoare_ron']) if v['valoare_ron'] else 0,
                'adaos_final': float(v['adaos_final']) if v['adaos_final'] else 0,
                'tip_deseu': v['tip_deseu']
            } for v in recent]
        }

    def get_vanzari(self, cur, firma_id=None, year=None, month=None):
        """Get vanzari with filters"""
        query = """
            SELECT v.*, f.name as firma_name
            FROM vanzari v
            JOIN firme f ON v.firma_id = f.id
            WHERE 1=1
        """
        params = []

        if firma_id:
            query += " AND v.firma_id = %s"
            params.append(firma_id)
        if year:
            query += " AND v.year = %s"
            params.append(int(year))
        if month:
            query += " AND v.month = %s"
            params.append(int(month))

        query += " ORDER BY v.data DESC LIMIT 500"

        cur.execute(query, params)
        vanzari = cur.fetchall()

        return {
            'count': len(vanzari),
            'filters': {'firma_id': firma_id, 'year': year, 'month': month},
            'vanzari': [{
                'id': v['id'],
                'firma_name': v['firma_name'],
                'data': str(v['data']),
                'numar_aviz': v['numar_aviz'],
                'tip_deseu': v['tip_deseu'],
                'cantitate_livrata': float(v['cantitate_livrata']) if v['cantitate_livrata'] else 0,
                'cantitate_receptionata': float(v['cantitate_receptionata']) if v['cantitate_receptionata'] else 0,
                'valoare_ron': float(v['valoare_ron']) if v['valoare_ron'] else 0,
                'adaos_final': float(v['adaos_final']) if v['adaos_final'] else 0
            } for v in vanzari]
        }

    def get_monthly_summary(self, cur, year=None):
        """Get monthly summary"""
        query = """
            SELECT year, month,
                   COUNT(*) as nr_vanzari,
                   COUNT(DISTINCT firma_id) as nr_firme,
                   COALESCE(SUM(valoare_ron), 0) as total_valoare,
                   COALESCE(SUM(adaos_final), 0) as total_profit,
                   COALESCE(SUM(cantitate_receptionata), 0) as total_kg
            FROM vanzari
        """
        params = []
        if year:
            query += " WHERE year = %s"
            params.append(int(year))

        query += " GROUP BY year, month ORDER BY year, month"

        cur.execute(query, params)
        months = cur.fetchall()

        month_names = ['', 'Ianuarie', 'Februarie', 'Martie', 'Aprilie', 'Mai', 'Iunie',
                       'Iulie', 'August', 'Septembrie', 'Octombrie', 'Noiembrie', 'Decembrie']

        return {
            'year_filter': year,
            'months': [{
                'year': m['year'],
                'month': m['month'],
                'month_name': month_names[m['month']],
                'nr_vanzari': m['nr_vanzari'],
                'nr_firme': m['nr_firme'],
                'total_valoare': float(m['total_valoare']),
                'total_profit': float(m['total_profit']),
                'total_kg': float(m['total_kg']),
                'profit_margin': round(float(m['total_profit']) / float(m['total_valoare']) * 100, 2) if m['total_valoare'] else 0
            } for m in months]
        }

    def get_deseuri_summary(self, cur, year=None, month=None):
        """Get waste type summary"""
        query = """
            SELECT tip_deseu,
                   SUM(cantitate_kg) as total_kg,
                   SUM(valoare_ron) as total_valoare,
                   SUM(adaos_ron) as total_profit,
                   AVG(procent_vanzari) as avg_procent_vanzari,
                   AVG(procent_profit) as avg_procent_profit
            FROM sumar_deseuri
            WHERE 1=1
        """
        params = []
        if year:
            query += " AND year = %s"
            params.append(int(year))
        if month:
            query += " AND month = %s"
            params.append(int(month))

        query += " GROUP BY tip_deseu ORDER BY total_valoare DESC"

        cur.execute(query, params)
        deseuri = cur.fetchall()

        return {
            'filters': {'year': year, 'month': month},
            'deseuri': [{
                'tip_deseu': d['tip_deseu'],
                'total_kg': float(d['total_kg']) if d['total_kg'] else 0,
                'total_valoare': float(d['total_valoare']) if d['total_valoare'] else 0,
                'total_profit': float(d['total_profit']) if d['total_profit'] else 0,
                'procent_vanzari': float(d['avg_procent_vanzari']) if d['avg_procent_vanzari'] else 0,
                'procent_profit': float(d['avg_procent_profit']) if d['avg_procent_profit'] else 0
            } for d in deseuri]
        }

    def get_top_firme(self, cur, year=None, limit=10):
        """Get top companies by value"""
        query = """
            SELECT f.id, f.name,
                   COUNT(v.id) as nr_vanzari,
                   COALESCE(SUM(v.valoare_ron), 0) as total_valoare,
                   COALESCE(SUM(v.adaos_final), 0) as total_profit,
                   COALESCE(SUM(v.cantitate_receptionata), 0) as total_kg
            FROM firme f
            JOIN vanzari v ON f.id = v.firma_id
        """
        params = []
        if year:
            query += " WHERE v.year = %s"
            params.append(int(year))

        query += f" GROUP BY f.id, f.name ORDER BY total_valoare DESC LIMIT {limit}"

        cur.execute(query, params)
        top = cur.fetchall()

        # Also get top by profit
        query2 = query.replace('ORDER BY total_valoare', 'ORDER BY total_profit')
        cur.execute(query2, params)
        top_profit = cur.fetchall()

        # Top by kg
        query3 = query.replace('ORDER BY total_valoare', 'ORDER BY total_kg')
        cur.execute(query3, params)
        top_kg = cur.fetchall()

        def format_firma(f):
            return {
                'id': f['id'],
                'name': f['name'],
                'nr_vanzari': f['nr_vanzari'],
                'total_valoare': float(f['total_valoare']),
                'total_profit': float(f['total_profit']),
                'total_kg': float(f['total_kg'])
            }

        return {
            'year_filter': year,
            'top_by_value': [format_firma(f) for f in top],
            'top_by_profit': [format_firma(f) for f in top_profit],
            'top_by_kg': [format_firma(f) for f in top_kg]
        }

    def get_transporturi(self, cur, year=None):
        """Get transport costs"""
        query = """
            SELECT year, month, destinatie, firma_name, descriere,
                   suma_fara_tva, tva, total, transportator
            FROM transporturi_firme
        """
        params = []
        if year:
            query += " WHERE year = %s"
            params.append(int(year))

        query += " ORDER BY year DESC, month DESC"

        cur.execute(query, params)
        transporturi = cur.fetchall()

        # Summary by year/month
        cur.execute("""
            SELECT year, month, COALESCE(SUM(total), 0) as total_cost
            FROM transporturi_firme
            GROUP BY year, month
            ORDER BY year, month
        """)
        summary = cur.fetchall()

        return {
            'year_filter': year,
            'count': len(transporturi),
            'transporturi': [{
                'year': t['year'],
                'month': t['month'],
                'destinatie': t['destinatie'],
                'firma_name': t['firma_name'],
                'descriere': t['descriere'],
                'suma_fara_tva': float(t['suma_fara_tva']) if t['suma_fara_tva'] else 0,
                'tva': float(t['tva']) if t['tva'] else 0,
                'total': float(t['total']) if t['total'] else 0,
                'transportator': t['transportator']
            } for t in transporturi],
            'monthly_totals': [{
                'year': s['year'],
                'month': s['month'],
                'total_cost': float(s['total_cost'])
            } for s in summary]
        }

    def get_yearly_comparison(self, cur):
        """Get yearly comparison for trends"""
        cur.execute("""
            SELECT year,
                   COUNT(*) as nr_vanzari,
                   COUNT(DISTINCT firma_id) as nr_firme,
                   COALESCE(SUM(valoare_ron), 0) as total_valoare,
                   COALESCE(SUM(adaos_final), 0) as total_profit,
                   COALESCE(SUM(cantitate_receptionata), 0) as total_kg,
                   COUNT(DISTINCT month) as months_active
            FROM vanzari
            GROUP BY year
            ORDER BY year
        """)
        years = cur.fetchall()

        # Monthly comparison per year
        cur.execute("""
            SELECT year, month,
                   COALESCE(SUM(valoare_ron), 0) as valoare,
                   COALESCE(SUM(adaos_final), 0) as profit
            FROM vanzari
            GROUP BY year, month
            ORDER BY year, month
        """)
        monthly = cur.fetchall()

        # Organize monthly data by year
        monthly_by_year = {}
        for m in monthly:
            if m['year'] not in monthly_by_year:
                monthly_by_year[m['year']] = {}
            monthly_by_year[m['year']][m['month']] = {
                'valoare': float(m['valoare']),
                'profit': float(m['profit'])
            }

        return {
            'years': [{
                'year': y['year'],
                'nr_vanzari': y['nr_vanzari'],
                'nr_firme': y['nr_firme'],
                'total_valoare': float(y['total_valoare']),
                'total_profit': float(y['total_profit']),
                'total_kg': float(y['total_kg']),
                'months_active': y['months_active'],
                'avg_per_month': float(y['total_valoare']) / y['months_active'] if y['months_active'] else 0,
                'profit_margin': round(float(y['total_profit']) / float(y['total_valoare']) * 100, 2) if y['total_valoare'] else 0
            } for y in years],
            'monthly_by_year': monthly_by_year
        }
