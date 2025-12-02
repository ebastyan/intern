# -*- coding: utf-8 -*-
"""
Merge SPIZ companies as requested by user
"""
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

sys.stdout.reconfigure(encoding='utf-8')

db_url = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def run():
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    print("Merging SPIZ companies...")
    print("  PW SPIZ SPOLKA (ID 91) -> SPIZ (ID 110)")

    # Update vanzari
    cur.execute("UPDATE vanzari SET firma_id = 110 WHERE firma_id = 91")
    print(f"    Updated {cur.rowcount} vanzari records")

    # Update sumar_firme
    cur.execute("UPDATE sumar_firme SET firma_id = 110 WHERE firma_id = 91")
    print(f"    Updated {cur.rowcount} sumar_firme records")

    # Delete duplicate
    cur.execute("DELETE FROM firme WHERE id = 91")
    print(f"    Deleted PW SPIZ SPOLKA from firme")

    # Rename to simpler name
    cur.execute("UPDATE firme SET name = 'SPIZ' WHERE id = 110")
    print(f"    Renamed to SPIZ")

    conn.commit()

    # Verify
    cur.execute("SELECT id, name FROM firme WHERE name LIKE '%SPIZ%'")
    for r in cur.fetchall():
        print(f"    Remaining: {r['id']}: {r['name']}")

    cur.close()
    conn.close()
    print("Done!")

if __name__ == '__main__':
    run()
