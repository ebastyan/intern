# -*- coding: utf-8 -*-
"""
Check data issues
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
    print("SUMAR_DESEURI TABLE CHECK")
    print("=" * 60)

    # Check sumar_deseuri by year
    cur.execute("""
        SELECT year, COUNT(*) as records,
               SUM(cantitate_kg) as kg,
               SUM(valoare_ron) as valoare,
               SUM(adaos_ron) as profit
        FROM sumar_deseuri
        GROUP BY year ORDER BY year
    """)
    for r in cur.fetchall():
        print(f"  {r['year']}: {r['records']} records, {r['kg']:,.0f} kg, {r['valoare']:,.0f} valoare, {r['profit']:,.0f} profit")

    # Check if 2022 has any records
    cur.execute("SELECT * FROM sumar_deseuri WHERE year = 2022 LIMIT 5")
    rows = cur.fetchall()
    print(f"\n2022 records sample: {len(rows)}")
    for r in rows:
        print(f"  {r}")

    # Check 2024 profit - is it really 15M?
    print("\n" + "=" * 60)
    print("2024 PROFIT CHECK")
    print("=" * 60)

    cur.execute("""
        SELECT SUM(adaos_final) as profit_from_vanzari
        FROM vanzari WHERE year = 2024
    """)
    r = cur.fetchone()
    print(f"  Profit from vanzari table: {r['profit_from_vanzari']:,.0f} RON")

    cur.execute("""
        SELECT SUM(adaos_ron) as profit_from_sumar
        FROM sumar_deseuri WHERE year = 2024
    """)
    r = cur.fetchone()
    print(f"  Profit from sumar_deseuri table: {r['profit_from_sumar']:,.0f} RON")

    # Transport data check
    print("\n" + "=" * 60)
    print("TRANSPORT DATA CHECK")
    print("=" * 60)

    cur.execute("""
        SELECT year, COUNT(*) as records, SUM(total) as total_cost
        FROM transporturi_firme
        GROUP BY year ORDER BY year
    """)
    for r in cur.fetchall():
        print(f"  {r['year']}: {r['records']} records, total cost: {r['total_cost']:,.0f} RON" if r['total_cost'] else f"  {r['year']}: {r['records']} records, total cost: N/A")

    # Check destinations - foreign vs domestic
    cur.execute("SELECT DISTINCT destinatie FROM transporturi_firme WHERE destinatie IS NOT NULL ORDER BY destinatie")
    dests = [r['destinatie'] for r in cur.fetchall()]
    print(f"\n  All destinations: {dests}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
