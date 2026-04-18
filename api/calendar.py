"""
Calendar API - Sarbatori, zile lucratoare, inchideri companie
Endpoints:
  GET  /api/calendar?type=holidays&year=YYYY
  GET  /api/calendar?type=closures
  GET  /api/calendar?type=closure_candidates
  GET  /api/calendar?type=working_days&date_from=X&date_to=Y
  GET  /api/calendar?type=weekly_pattern&date_from=X&date_to=Y
  GET  /api/calendar?type=monthly_pattern&year=YYYY
  GET  /api/calendar?type=holiday_effect&window=3
  GET  /api/calendar?type=bridge_days
  GET  /api/calendar?type=illegal_workdays
  POST /api/calendar?action=confirm_closure   body: {date_from, date_to, reason}
  POST /api/calendar?action=ignore_closure    body: {date_from, date_to}
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse, parse_qs
from decimal import Decimal
from datetime import date, datetime

def get_db():
    db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL_NO_SSL')
    if not db_url:
        raise Exception("No database URL configured")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Not serializable: {type(obj)}")

class handler(BaseHTTPRequestHandler):
    def _send(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload, default=json_default).encode('utf-8'))

    def list_holidays(self, cur, year):
        if year:
            cur.execute(
                "SELECT date, name, type, is_official FROM holidays WHERE EXTRACT(year FROM date) = %s ORDER BY date",
                (int(year),),
            )
        else:
            cur.execute("SELECT date, name, type, is_official FROM holidays ORDER BY date")
        return [dict(r) for r in cur.fetchall()]

    def list_closures(self, cur):
        cur.execute(
            """
            SELECT date, reason, detected_automatically, validated_at
            FROM company_closures
            WHERE reason IS DISTINCT FROM '__ignored__'
            ORDER BY date
            """
        )
        return [dict(r) for r in cur.fetchall()]

    def closure_candidates(self, cur):
        """Detect contiguous closure periods. A closure day = Sunday OR official
        holiday OR a Mon-Sat non-holiday with zero transactions. Merge consecutive
        closure days into islands (so a summer vacation that spans Sundays stays
        one block). For each island that contains at least one actual company
        closure (zero-tx working day), report the span of those working days and
        the count."""
        cur.execute(
            """
            WITH bounds AS (SELECT MIN(date) AS dmin, MAX(date) AS dmax FROM transactions),
            days AS (
              SELECT generate_series(b.dmin, b.dmax, '1 day'::interval)::date AS d FROM bounds b
            ),
            tx_set AS (SELECT DISTINCT date FROM transactions),
            official AS (SELECT DISTINCT date FROM holidays WHERE is_official),
            marked AS (
              SELECT d,
                     (EXTRACT(ISODOW FROM d) = 7
                       OR d IN (SELECT date FROM official)
                       OR d NOT IN (SELECT date FROM tx_set)) AS is_closed,
                     (EXTRACT(ISODOW FROM d) <> 7
                       AND d NOT IN (SELECT date FROM official)
                       AND d NOT IN (SELECT date FROM tx_set)) AS is_company_closure
              FROM days
            ),
            grouped AS (
              SELECT d, is_closed, is_company_closure,
                     SUM(CASE WHEN NOT is_closed THEN 1 ELSE 0 END)
                       OVER (ORDER BY d ROWS UNBOUNDED PRECEDING) AS grp
              FROM marked
            )
            SELECT
              MIN(d) FILTER (WHERE is_company_closure) AS date_from,
              MAX(d) FILTER (WHERE is_company_closure) AS date_to,
              SUM(CASE WHEN is_company_closure THEN 1 ELSE 0 END) AS working_days,
              COUNT(*) AS calendar_days
            FROM grouped
            WHERE is_closed
            GROUP BY grp
            HAVING SUM(CASE WHEN is_company_closure THEN 1 ELSE 0 END) > 0
            ORDER BY date_from
            """
        )
        runs = [dict(r) for r in cur.fetchall()]
        total = sum(r['working_days'] for r in runs)
        return {'runs': runs, 'total_days': total}

    def weekly_pattern(self, cur, date_from, date_to):
        where = []
        args = []
        if date_from: where.append("t.date >= %s"); args.append(date_from)
        if date_to:   where.append("t.date <= %s"); args.append(date_to)
        where_sql = (' AND '.join(where)) if where else 'TRUE'
        cur.execute(
            f"""
            WITH daily AS (
              SELECT t.date,
                     EXTRACT(ISODOW FROM t.date)::int AS dow,
                     COUNT(DISTINCT t.cnp) AS partners,
                     COUNT(*) AS tx_count,
                     COALESCE(SUM(i.weight_kg), 0) AS kg,
                     COALESCE(SUM(t.gross_value), 0) AS ron
              FROM transactions t
              LEFT JOIN transaction_items i ON i.document_id = t.document_id
              WHERE {where_sql}
                AND EXTRACT(ISODOW FROM t.date) <> 7
                AND t.date NOT IN (SELECT date FROM holidays WHERE is_official)
                AND t.date NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
              GROUP BY t.date
            )
            SELECT dow,
                   CASE dow WHEN 1 THEN 'Luni' WHEN 2 THEN 'Marti' WHEN 3 THEN 'Miercuri'
                            WHEN 4 THEN 'Joi' WHEN 5 THEN 'Vineri' WHEN 6 THEN 'Sambata' END AS dow_label,
                   CASE WHEN dow = 6 THEN 5.0 ELSE 9.0 END AS hours_open,
                   COUNT(*) AS working_days,
                   ROUND(AVG(partners)::numeric, 1) AS avg_partners,
                   ROUND(AVG(tx_count)::numeric, 1) AS avg_transactions,
                   ROUND(AVG(kg)::numeric, 1) AS avg_kg,
                   ROUND(AVG(ron)::numeric, 2) AS avg_ron,
                   ROUND((AVG(partners) / (CASE WHEN dow = 6 THEN 5.0 ELSE 9.0 END))::numeric, 2) AS avg_partners_per_hour,
                   ROUND((AVG(tx_count) / (CASE WHEN dow = 6 THEN 5.0 ELSE 9.0 END))::numeric, 2) AS avg_transactions_per_hour,
                   ROUND((AVG(kg) / (CASE WHEN dow = 6 THEN 5.0 ELSE 9.0 END))::numeric, 2) AS avg_kg_per_hour,
                   ROUND((AVG(ron) / (CASE WHEN dow = 6 THEN 5.0 ELSE 9.0 END))::numeric, 2) AS avg_ron_per_hour
            FROM daily
            GROUP BY dow
            ORDER BY dow
            """,
            args,
        )
        return [dict(r) for r in cur.fetchall()]

    def monthly_pattern(self, cur, year):
        year = int(year) if year else None
        where = ["EXTRACT(ISODOW FROM t.date) <> 7",
                 "t.date NOT IN (SELECT date FROM holidays WHERE is_official)",
                 "t.date NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')"]
        args = []
        if year:
            where.append("EXTRACT(year FROM t.date) = %s")
            args.append(year)
        cur.execute(
            f"""
            WITH daily AS (
              SELECT t.date,
                     EXTRACT(month FROM t.date)::int AS month,
                     COUNT(DISTINCT t.cnp) AS partners,
                     COUNT(*) AS tx_count,
                     COALESCE(SUM(i.weight_kg), 0) AS kg,
                     COALESCE(SUM(t.gross_value), 0) AS ron
              FROM transactions t
              LEFT JOIN transaction_items i ON i.document_id = t.document_id
              WHERE {' AND '.join(where)}
              GROUP BY t.date
            )
            SELECT month,
                   COUNT(*) AS working_days,
                   ROUND(AVG(partners)::numeric, 1) AS avg_partners_per_day,
                   ROUND(AVG(tx_count)::numeric, 1) AS avg_transactions_per_day,
                   ROUND(AVG(kg)::numeric, 1) AS avg_kg_per_day,
                   ROUND(AVG(ron)::numeric, 2) AS avg_ron_per_day,
                   ROUND(SUM(partners)::numeric, 0) AS total_partners,
                   SUM(tx_count) AS total_transactions,
                   ROUND(SUM(kg)::numeric, 1) AS total_kg,
                   ROUND(SUM(ron)::numeric, 2) AS total_ron
            FROM daily
            GROUP BY month
            ORDER BY month
            """,
            args,
        )
        return [dict(r) for r in cur.fetchall()]

    def working_days(self, cur, date_from, date_to):
        cur.execute(
            """
            WITH days AS (
              SELECT generate_series(%s::date, %s::date, '1 day'::interval)::date AS d
            )
            SELECT
              COUNT(*) FILTER (
                WHERE EXTRACT(ISODOW FROM d) <> 7
                  AND d NOT IN (SELECT date FROM holidays WHERE is_official)
                  AND d NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
              ) AS working_days,
              COUNT(*) FILTER (WHERE EXTRACT(ISODOW FROM d) = 7) AS sundays,
              COUNT(*) FILTER (WHERE d IN (SELECT date FROM holidays WHERE is_official)) AS official_holidays,
              COUNT(*) FILTER (WHERE d IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')) AS company_closed
            FROM days
            """,
            (date_from, date_to),
        )
        return dict(cur.fetchone())

    def holiday_effect(self, cur, window):
        """Group consecutive official holidays (spanning Sundays and other
        closed days) into a single holiday BLOCK, then compare traffic on the
        N nearest open days before the block vs after the block. Avoids showing
        the same before/after data three times for holidays like Easter that
        naturally fall in a multi-day closure."""
        window = int(window) if window else 3
        cur.execute(
            f"""
            WITH tx_bounds AS (SELECT MIN(date) AS dmin, MAX(date) AS dmax FROM transactions),
            tx_days AS (SELECT t.date, COUNT(DISTINCT t.cnp) AS partners FROM transactions t GROUP BY t.date),
            official AS (
              SELECT DISTINCT h.date, h.name
              FROM holidays h, tx_bounds b
              WHERE h.is_official AND h.date BETWEEN b.dmin AND b.dmax
            ),
            days AS (
              SELECT generate_series(b.dmin, b.dmax, '1 day'::interval)::date AS d FROM tx_bounds b
            ),
            marked AS (
              SELECT d,
                (d IN (SELECT date FROM tx_days)
                 AND EXTRACT(ISODOW FROM d) <> 7
                 AND d NOT IN (SELECT date FROM official)) AS is_open
              FROM days
            ),
            numbered AS (
              SELECT d, is_open,
                SUM(CASE WHEN is_open THEN 1 ELSE 0 END) OVER (ORDER BY d ROWS UNBOUNDED PRECEDING) AS grp
              FROM marked
            ),
            closure_blocks AS (
              SELECT grp, MIN(d) AS block_start, MAX(d) AS block_end
              FROM numbered WHERE NOT is_open
              GROUP BY grp
            ),
            holiday_blocks AS (
              SELECT cb.grp, cb.block_start, cb.block_end,
                     STRING_AGG(o.name, ' + ' ORDER BY o.date) AS block_name,
                     CASE
                       WHEN EXTRACT(year FROM cb.block_start) = EXTRACT(year FROM cb.block_end)
                         THEN EXTRACT(year FROM cb.block_start)::text
                       ELSE EXTRACT(year FROM cb.block_start)::text || '/' ||
                            RIGHT(EXTRACT(year FROM cb.block_end)::text, 2)
                     END AS year_label
              FROM official o
              JOIN closure_blocks cb ON o.date BETWEEN cb.block_start AND cb.block_end
              GROUP BY cb.grp, cb.block_start, cb.block_end
            ),
            before_ranked AS (
              SELECT hb.block_name, hb.year_label, t.partners,
                     ROW_NUMBER() OVER (PARTITION BY hb.grp ORDER BY t.date DESC) AS rn
              FROM holiday_blocks hb
              JOIN tx_days t ON t.date < hb.block_start
            ),
            after_ranked AS (
              SELECT hb.block_name, hb.year_label, t.partners,
                     ROW_NUMBER() OVER (PARTITION BY hb.grp ORDER BY t.date ASC) AS rn
              FROM holiday_blocks hb
              JOIN tx_days t ON t.date > hb.block_end
            ),
            slots AS (
              SELECT block_name, year_label, -rn::int AS offset_days, partners
              FROM before_ranked WHERE rn <= {window}
              UNION ALL
              SELECT block_name, year_label, rn::int AS offset_days, partners
              FROM after_ranked WHERE rn <= {window}
            )
            SELECT block_name AS holiday_name,
                   year_label,
                   offset_days,
                   partners
            FROM slots
            ORDER BY block_name, year_label, offset_days
            """
        )
        return [dict(r) for r in cur.fetchall()]

    def bridge_days(self, cur):
        cur.execute(
            """
            WITH bounds AS (SELECT MIN(date) AS dmin, MAX(date) AS dmax FROM transactions),
            days AS (
              SELECT generate_series(b.dmin, b.dmax, '1 day'::interval)::date AS d FROM bounds b
            ),
            closed AS (
              SELECT d FROM days
              WHERE EXTRACT(ISODOW FROM d) = 7
                 OR d IN (SELECT date FROM holidays WHERE is_official)
                 OR d IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
            ),
            bridges AS (
              SELECT d.d AS bridge_date
              FROM days d
              WHERE EXTRACT(ISODOW FROM d.d) <> 7
                AND d.d NOT IN (SELECT date FROM holidays WHERE is_official)
                AND d.d NOT IN (SELECT date FROM company_closures WHERE reason IS DISTINCT FROM '__ignored__')
                AND (d.d - INTERVAL '1 day')::date IN (SELECT d FROM closed)
                AND (d.d + INTERVAL '1 day')::date IN (SELECT d FROM closed)
            )
            SELECT b.bridge_date,
                   COALESCE(COUNT(DISTINCT t.cnp), 0) AS partners,
                   COALESCE(COUNT(t.document_id), 0) AS transactions
            FROM bridges b
            LEFT JOIN transactions t ON t.date = b.bridge_date
            GROUP BY b.bridge_date
            ORDER BY b.bridge_date
            """
        )
        return [dict(r) for r in cur.fetchall()]

    def illegal_workdays(self, cur):
        cur.execute(
            """
            SELECT t.date,
                   STRING_AGG(DISTINCT h.name, ', ') AS holiday_names,
                   COUNT(*) AS tx_count,
                   COUNT(DISTINCT t.cnp) AS partners,
                   ROUND(SUM(t.gross_value)::numeric, 2) AS ron
            FROM transactions t
            JOIN holidays h ON h.date = t.date AND h.is_official = true
            GROUP BY t.date
            ORDER BY t.date
            """
        )
        return [dict(r) for r in cur.fetchall()]

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            query_type = params.get('type', [''])[0]

            conn = get_db()
            cur = conn.cursor()

            if query_type == 'ping':
                result = {'ok': True, 'endpoint': 'calendar'}
            elif query_type == 'holidays':
                year = params.get('year', [None])[0]
                result = {'holidays': self.list_holidays(cur, year)}
            elif query_type == 'closures':
                result = {'closures': self.list_closures(cur)}
            elif query_type == 'closure_candidates':
                result = self.closure_candidates(cur)
            elif query_type == 'weekly_pattern':
                df = params.get('date_from', [None])[0]
                dt = params.get('date_to', [None])[0]
                result = {'weekly_pattern': self.weekly_pattern(cur, df, dt)}
            elif query_type == 'monthly_pattern':
                year = params.get('year', [None])[0]
                result = {'monthly_pattern': self.monthly_pattern(cur, year)}
            elif query_type == 'working_days':
                df = params.get('date_from', [None])[0]
                dt = params.get('date_to', [None])[0]
                if not df or not dt:
                    result = {'error': 'date_from and date_to required'}
                else:
                    result = self.working_days(cur, df, dt)
            elif query_type == 'holiday_effect':
                win = params.get('window', ['3'])[0]
                result = {'holiday_effect': self.holiday_effect(cur, win)}
            elif query_type == 'bridge_days':
                result = {'bridge_days': self.bridge_days(cur)}
            elif query_type == 'illegal_workdays':
                result = {'illegal_workdays': self.illegal_workdays(cur)}
            else:
                result = {'error': 'Unknown query type', 'got': query_type}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {'error': str(e)})

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            action = params.get('action', [''])[0]

            length = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(length).decode('utf-8') if length else '{}'
            data = json.loads(body) if body else {}

            conn = get_db()
            cur = conn.cursor()

            if action in ('confirm_closure', 'ignore_closure'):
                df = data.get('date_from'); dt = data.get('date_to')
                if not df or not dt:
                    conn.close(); self._send(400, {'error': 'date_from and date_to required'}); return
                reason = data.get('reason') or ('' if action == 'confirm_closure' else '__ignored__')
                if action == 'ignore_closure':
                    reason = '__ignored__'
                cur.execute(
                    """
                    INSERT INTO company_closures (date, reason, detected_automatically)
                    SELECT generate_series(%s::date, %s::date, '1 day'::interval)::date, %s, true
                    ON CONFLICT (date) DO UPDATE SET reason = EXCLUDED.reason, validated_at = now()
                    """,
                    (df, dt, reason),
                )
                conn.commit()
                result = {'ok': True, 'action': action, 'date_from': df, 'date_to': dt}
            else:
                result = {'error': 'Unknown action', 'got': action}

            conn.close()
            self._send(200, result)
        except Exception as e:
            self._send(500, {'error': str(e)})
