# -*- coding: utf-8 -*-
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect('postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require')
cur = conn.cursor(cursor_factory=RealDictCursor)

print('=== Check: Document ID problems ===')
cur.execute("""
    SELECT document_id, date, gross_value
    FROM transactions
    WHERE document_id NOT LIKE 'PJ-%'
    LIMIT 10
""")
bad_docs = cur.fetchall()
if bad_docs:
    print(f'PROBLEMA: {len(bad_docs)} bad document_id found:')
    for r in bad_docs:
        print(f'  {r}')
else:
    print('OK - All document_id have PJ-xxx format!')

print()
print('=== Check: Aluminiu JENTI vs JANTE ===')
cur.execute("""
    SELECT name FROM waste_types WHERE name ILIKE '%JENTI%'
""")
jenti = cur.fetchall()
if jenti:
    print(f'PROBLEMA: Found JENTI type: {jenti}')
else:
    print('OK - No JENTI type, normalization successful!')

cur.execute("""
    SELECT name FROM waste_types WHERE name ILIKE '%JANTE%'
""")
jante = cur.fetchall()
print(f'JANTE types: {[r["name"] for r in jante]}')

print()
print('=== All Waste Types ===')
cur.execute("""
    SELECT wc.name as category, wt.name as subtype
    FROM waste_types wt
    JOIN waste_categories wc ON wt.category_id = wc.id
    ORDER BY wc.name, wt.name
""")
for r in cur.fetchall():
    print(f'  {r["category"]}: {r["subtype"]}')

print()
print('=== Sample transactions from October 2024 ===')
cur.execute("""
    SELECT document_id, date, payment_type, gross_value, net_paid
    FROM transactions
    WHERE date >= '2024-10-01' AND date < '2024-10-05'
    ORDER BY date, document_id
    LIMIT 10
""")
for r in cur.fetchall():
    print(f'  {r["document_id"]}: {r["date"]} | {r["payment_type"]} | {r["gross_value"]} RON')

print()
print('=== Sample transactions from November 2025 ===')
cur.execute("""
    SELECT document_id, date, payment_type, gross_value, net_paid
    FROM transactions
    WHERE date >= '2025-11-01'
    ORDER BY date DESC
    LIMIT 10
""")
for r in cur.fetchall():
    print(f'  {r["document_id"]}: {r["date"]} | {r["payment_type"]} | {r["gross_value"]} RON')

conn.close()
