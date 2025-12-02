# -*- coding: utf-8 -*-
"""
Full data check
"""
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

sys.stdout.reconfigure(encoding='utf-8')

db_url = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def run():
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    print("=" * 60)
    print("TRANSPORT DATA - FULL CHECK")
    print("=" * 60)

    cur.execute("SELECT COUNT(*) as cnt FROM transporturi_firme")
    print(f"Total transport records: {cur.fetchone()['cnt']}")

    cur.execute("SELECT * FROM transporturi_firme ORDER BY year, month")
    rows = cur.fetchall()
    total = 0
    for r in rows:
        total += float(r['total']) if r['total'] else 0
        print(f"  {r['year']}/{r['month']}: {r['destinatie']} -> {r['firma_name']} = {r['total']} RON")

    print(f"\nTotal transport cost: {total:,.0f} RON")

    print("\n" + "=" * 60)
    print("DESEURI - TIP DESEU VALUES")
    print("=" * 60)

    # Check tip_deseu in vanzari
    cur.execute("""
        SELECT DISTINCT tip_deseu, COUNT(*) as cnt
        FROM vanzari
        WHERE tip_deseu IS NOT NULL AND tip_deseu != ''
        GROUP BY tip_deseu
        ORDER BY cnt DESC
    """)
    rows = cur.fetchall()
    print(f"Unique tip_deseu values: {len(rows)}")
    for r in rows:
        print(f"  {r['tip_deseu']}: {r['cnt']} records")

    # Check if tip_deseu has company names
    print("\n" + "=" * 60)
    print("CHECKING IF TIP_DESEU HAS COMPANY NAMES")
    print("=" * 60)

    cur.execute("SELECT name FROM firme")
    firma_names = set(r['name'].upper() for r in cur.fetchall())

    cur.execute("SELECT DISTINCT tip_deseu FROM vanzari WHERE tip_deseu IS NOT NULL")
    tip_deseu_values = [r['tip_deseu'] for r in cur.fetchall()]

    for td in tip_deseu_values:
        if td and td.upper() in firma_names:
            print(f"  WARNING: '{td}' is also a company name!")

    print("\n" + "=" * 60)
    print("YEARLY TOTALS FROM VANZARI")
    print("=" * 60)

    cur.execute("""
        SELECT year,
               COUNT(*) as tranzactii,
               COUNT(DISTINCT firma_id) as firme,
               SUM(valoare_ron) as rulaj,
               SUM(adaos_final) as profit,
               SUM(cantitate_receptionata) as kg
        FROM vanzari
        GROUP BY year ORDER BY year
    """)
    for r in cur.fetchall():
        print(f"  {r['year']}: {r['tranzactii']} tranzactii, {r['firme']} firme, {r['rulaj']:,.0f} RON, {r['profit']:,.0f} profit, {r['kg']:,.0f} kg")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
