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
                month_from = params.get('month_from', [None])[0]
                month_to = params.get('month_to', [None])[0]
                tip_deseu = params.get('tip_deseu', [None])[0]
                result = self.get_deseuri_summary(cur, year, month_from, month_to, tip_deseu)
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

    def get_deseuri_summary(self, cur, year=None, month_from=None, month_to=None, tip_deseu=None):
        """Get waste type summary from sumar_deseuri table (monthly summaries from Excel)"""
        # Build filter conditions
        conditions = ["tip_deseu IS NOT NULL"]
        params = []

        if year:
            conditions.append("year = %s")
            params.append(int(year))
        if month_from:
            conditions.append("month >= %s")
            params.append(int(month_from))
        if month_to:
            conditions.append("month <= %s")
            params.append(int(month_to))
        if tip_deseu:
            conditions.append("tip_deseu ILIKE %s")
            params.append(f"%{tip_deseu}%")

        where_clause = " AND ".join(conditions)

        # First get totals for percentage calculation
        total_query = f"""
            SELECT COALESCE(SUM(valoare_ron), 0) as total_val,
                   COALESCE(SUM(adaos_ron), 0) as total_profit
            FROM sumar_deseuri WHERE {where_clause}
        """

        cur.execute(total_query, params)
        totals = cur.fetchone()
        grand_total_val = float(totals['total_val']) if totals['total_val'] else 1
        grand_total_profit = float(totals['total_profit']) if totals['total_profit'] else 1

        # Now get breakdown by tip_deseu
        query = """
            SELECT tip_deseu,
                   COALESCE(SUM(cantitate_kg), 0) as total_kg,
                   COALESCE(SUM(valoare_ron), 0) as total_valoare,
                   COALESCE(SUM(adaos_ron), 0) as total_profit
            FROM sumar_deseuri
            WHERE tip_deseu IS NOT NULL AND tip_deseu != ''
        """

        detail_params = []
        if year:
            query += " AND year = %s"
            detail_params.append(int(year))
        if month_from:
            query += " AND month >= %s"
            detail_params.append(int(month_from))
        if month_to:
            query += " AND month <= %s"
            detail_params.append(int(month_to))
        if tip_deseu:
            query += " AND tip_deseu ILIKE %s"
            detail_params.append(f"%{tip_deseu}%")

        query += " GROUP BY tip_deseu ORDER BY total_valoare DESC"

        cur.execute(query, detail_params)
        deseuri = cur.fetchall()

        # Get available years for filter
        cur.execute("SELECT DISTINCT year FROM sumar_deseuri ORDER BY year")
        available_years = [r['year'] for r in cur.fetchall()]

        # Get available waste types for filter
        cur.execute("SELECT DISTINCT tip_deseu FROM sumar_deseuri WHERE tip_deseu IS NOT NULL ORDER BY tip_deseu")
        available_types = [r['tip_deseu'] for r in cur.fetchall()]

        return {
            'filters': {'year': year, 'month_from': month_from, 'month_to': month_to, 'tip_deseu': tip_deseu},
            'available_years': available_years,
            'available_types': available_types,
            'totals': {
                'total_valoare': grand_total_val,
                'total_profit': grand_total_profit
            },
            'deseuri': [{
                'tip_deseu': d['tip_deseu'],
                'total_kg': float(d['total_kg']) if d['total_kg'] else 0,
                'total_valoare': float(d['total_valoare']) if d['total_valoare'] else 0,
                'total_profit': float(d['total_profit']) if d['total_profit'] else 0,
                'procent_vanzari': round(float(d['total_valoare']) / grand_total_val * 100, 2) if grand_total_val else 0,
                'procent_profit': round(float(d['total_profit']) / grand_total_profit * 100, 2) if grand_total_profit else 0
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
        """Get transport costs from vanzari table (transport_ron column)"""
        # Monthly summary from vanzari.transport_ron
        query = """
            SELECT year, month,
                   COUNT(*) as nr_vanzari,
                   COUNT(transport_ron) as nr_with_transport,
                   COALESCE(SUM(transport_ron), 0) as transport_total,
                   COALESCE(SUM(valoare_ron), 0) as valoare_total
            FROM vanzari
        """
        params = []
        if year:
            query += " WHERE year = %s"
            params.append(int(year))
        query += " GROUP BY year, month ORDER BY year, month"

        cur.execute(query, params)
        monthly = cur.fetchall()

        # Yearly summary
        year_query = """
            SELECT year,
                   COUNT(*) as nr_vanzari,
                   COUNT(transport_ron) as nr_with_transport,
                   COALESCE(SUM(transport_ron), 0) as transport_total,
                   COALESCE(SUM(valoare_ron), 0) as valoare_total
            FROM vanzari
        """
        year_params = []
        if year:
            year_query += " WHERE year = %s"
            year_params.append(int(year))
        year_query += " GROUP BY year ORDER BY year"

        cur.execute(year_query, year_params)
        by_year = cur.fetchall()

        # By firma (top transporters)
        firma_query = """
            SELECT f.name as firma_name,
                   COUNT(*) as nr_vanzari,
                   COALESCE(SUM(v.transport_ron), 0) as transport_total,
                   COALESCE(SUM(v.valoare_ron), 0) as valoare_total
            FROM vanzari v
            JOIN firme f ON v.firma_id = f.id
            WHERE v.transport_ron > 0
        """
        firma_params = []
        if year:
            firma_query += " AND v.year = %s"
            firma_params.append(int(year))
        firma_query += " GROUP BY f.name ORDER BY transport_total DESC LIMIT 20"

        cur.execute(firma_query, firma_params)
        by_firma = cur.fetchall()

        # Calculate totals
        total_transport = sum(float(m['transport_total'] or 0) for m in monthly)
        total_valoare = sum(float(m['valoare_total'] or 0) for m in monthly)
        total_vanzari = sum(m['nr_vanzari'] for m in monthly)
        total_with_transport = sum(m['nr_with_transport'] for m in monthly)

        # Get available years
        cur.execute("SELECT DISTINCT year FROM vanzari ORDER BY year")
        available_years = [r['year'] for r in cur.fetchall()]

        month_names = ['', 'Ian', 'Feb', 'Mar', 'Apr', 'Mai', 'Iun',
                       'Iul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        return {
            'year_filter': year,
            'available_years': available_years,
            'summary': {
                'total_transport': total_transport,
                'total_valoare': total_valoare,
                'total_vanzari': total_vanzari,
                'total_with_transport': total_with_transport,
                'transport_percent': round(total_transport / total_valoare * 100, 2) if total_valoare else 0
            },
            'by_year': [{
                'year': y['year'],
                'nr_vanzari': y['nr_vanzari'],
                'nr_with_transport': y['nr_with_transport'],
                'transport_total': float(y['transport_total']) if y['transport_total'] else 0,
                'valoare_total': float(y['valoare_total']) if y['valoare_total'] else 0,
                'transport_percent': round(float(y['transport_total'] or 0) / float(y['valoare_total']) * 100, 2) if y['valoare_total'] else 0
            } for y in by_year],
            'by_firma': [{
                'firma_name': f['firma_name'],
                'nr_vanzari': f['nr_vanzari'],
                'transport_total': float(f['transport_total']) if f['transport_total'] else 0,
                'valoare_total': float(f['valoare_total']) if f['valoare_total'] else 0
            } for f in by_firma],
            'monthly': [{
                'year': m['year'],
                'month': m['month'],
                'month_name': month_names[m['month']],
                'nr_vanzari': m['nr_vanzari'],
                'nr_with_transport': m['nr_with_transport'],
                'transport_total': float(m['transport_total']) if m['transport_total'] else 0,
                'valoare_total': float(m['valoare_total']) if m['valoare_total'] else 0,
                'transport_percent': round(float(m['transport_total'] or 0) / float(m['valoare_total']) * 100, 2) if m['valoare_total'] else 0
            } for m in monthly],
            'details_2024': self._get_transport_details_2024(cur, year)
        }

    def _get_transport_details_2024(self, cur, year_filter):
        """Get detailed transport stats (drivers, vehicles, countries) - only 2024 has data"""
        # By country
        cur.execute("""
            SELECT tara_destinatie, COUNT(*) as fuvarok,
                   COALESCE(SUM(transport_ron), 0) as transport_total,
                   COALESCE(SUM(cantitate_livrata), 0) as kg_total
            FROM vanzari
            WHERE year = 2024 AND tara_destinatie IS NOT NULL
            GROUP BY tara_destinatie
            ORDER BY fuvarok DESC
        """)
        by_country = [{
            'tara': r['tara_destinatie'],
            'fuvarok': r['fuvarok'],
            'transport_ron': float(r['transport_total']) if r['transport_total'] else 0,
            'kg_total': float(r['kg_total']) if r['kg_total'] else 0
        } for r in cur.fetchall()]

        # By transporter company
        cur.execute("""
            SELECT transportator, COUNT(*) as fuvarok,
                   COALESCE(SUM(transport_ron), 0) as transport_total,
                   COALESCE(SUM(cantitate_livrata), 0) as kg_total
            FROM vanzari
            WHERE year = 2024 AND transportator IS NOT NULL
            GROUP BY transportator
            ORDER BY fuvarok DESC
        """)
        by_transporter = [{
            'transportator': r['transportator'],
            'fuvarok': r['fuvarok'],
            'transport_ron': float(r['transport_total']) if r['transport_total'] else 0,
            'kg_total': float(r['kg_total']) if r['kg_total'] else 0
        } for r in cur.fetchall()]

        # By driver (top 15)
        cur.execute("""
            SELECT nume_sofer, COUNT(*) as fuvarok,
                   COALESCE(SUM(transport_ron), 0) as transport_total,
                   COALESCE(SUM(cantitate_livrata), 0) as kg_total
            FROM vanzari
            WHERE year = 2024 AND nume_sofer IS NOT NULL
            GROUP BY nume_sofer
            ORDER BY fuvarok DESC
            LIMIT 15
        """)
        by_driver = [{
            'sofer': r['nume_sofer'],
            'fuvarok': r['fuvarok'],
            'transport_ron': float(r['transport_total']) if r['transport_total'] else 0,
            'kg_total': float(r['kg_total']) if r['kg_total'] else 0
        } for r in cur.fetchall()]

        # Unique counts
        cur.execute("SELECT COUNT(DISTINCT numar_auto) as cnt FROM vanzari WHERE year = 2024 AND numar_auto IS NOT NULL")
        unique_vehicles = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(DISTINCT nume_sofer) as cnt FROM vanzari WHERE year = 2024 AND nume_sofer IS NOT NULL")
        unique_drivers = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(DISTINCT tara_destinatie) as cnt FROM vanzari WHERE year = 2024 AND tara_destinatie IS NOT NULL")
        unique_countries = cur.fetchone()['cnt']

        cur.execute("SELECT COUNT(DISTINCT transportator) as cnt FROM vanzari WHERE year = 2024 AND transportator IS NOT NULL")
        unique_transporters = cur.fetchone()['cnt']

        return {
            'has_details': True,
            'year': 2024,
            'unique_vehicles': unique_vehicles,
            'unique_drivers': unique_drivers,
            'unique_countries': unique_countries,
            'unique_transporters': unique_transporters,
            'by_country': by_country,
            'by_transporter': by_transporter,
            'by_driver': by_driver
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
