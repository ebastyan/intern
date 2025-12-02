# -*- coding: utf-8 -*-
"""
Check transport data structure
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
    print("TRANSPORT DATA CHECK")
    print("=" * 60)

    cur.execute("SELECT * FROM transporturi_firme ORDER BY year, month LIMIT 20")
    rows = cur.fetchall()

    print(f"\nTotal records checked: {len(rows)}")
    for r in rows:
        print(f"\nYear: {r['year']}, Month: {r['month']}")
        print(f"  Destinatie: {r['destinatie']}")
        print(f"  Firma: {r['firma_name']}")
        print(f"  Descriere: {r['descriere']}")
        print(f"  Total: {r['total']}")
        print(f"  Transportator: {r['transportator']}")

    # Check if destinatie looks like company names or cities
    print("\n" + "=" * 60)
    print("UNIQUE DESTINATII:")
    cur.execute("SELECT DISTINCT destinatie FROM transporturi_firme WHERE destinatie IS NOT NULL ORDER BY destinatie")
    for r in cur.fetchall():
        print(f"  {r['destinatie']}")

    print("\n" + "=" * 60)
    print("UNIQUE FIRMA NAMES IN TRANSPORT:")
    cur.execute("SELECT DISTINCT firma_name FROM transporturi_firme WHERE firma_name IS NOT NULL ORDER BY firma_name")
    for r in cur.fetchall():
        print(f"  {r['firma_name']}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
