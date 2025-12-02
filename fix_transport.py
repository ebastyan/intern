# -*- coding: utf-8 -*-
"""
Fix transport data where destinatie and firma are swapped
"""
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

sys.stdout.reconfigure(encoding='utf-8')

db_url = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

# Known cities/places (destinatii)
KNOWN_CITIES = {
    'SLATINA', 'VITTUONE', 'VARPALOTA', 'CASTENDOLO', 'SPISSKE VLACHY',
    'BUCURESTI', 'CZESTOCHOWA', 'TOMASZOW', 'CLUJ', 'ORSOVA', 'KONIN',
    'SANTIMBRU', 'TIMIS', 'HUNEDOARA', 'OLANDA', 'UNGARIA', 'RESITA',
    'ORADEA', 'BRASOV', 'MARAMURES', 'ALBA', 'SIBIU', 'ARAD', 'BIHOR',
    'ITALIA', 'CEHIA', 'POLONIA', 'SLOVACIA', 'AUSTRIA', 'GERMANIA'
}

# Known company names
KNOWN_COMPANIES = {
    'REIF', 'CRONIMET', 'EUMETRA', 'RUMET', 'HENEKEN', 'RAGMET RAFFINERIA',
    'SPIZ', 'SYNTOM', 'REMAT BRASOV', 'TEHNOINVEST', 'FEVA', 'CHEMICAL',
    'REMAT PLUS', 'MGG', 'GUARDO', 'CALITEX', 'AK METAL', 'APEX', 'TRIMMO',
    'RECIMAT', 'VESNA', 'GLETOS', 'ZLATCUP', 'CANPACK', 'AS METAL'
}

def run():
    conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    print("=" * 60)
    print("FIXING SWAPPED TRANSPORT DATA")
    print("=" * 60)

    # Get all transport records
    cur.execute("SELECT id, destinatie, firma_name FROM transporturi_firme")
    records = cur.fetchall()

    fix_count = 0
    for r in records:
        dest = (r['destinatie'] or '').upper().strip()
        firma = (r['firma_name'] or '').upper().strip()

        # Check if swapped: destinatie looks like company, firma looks like city
        dest_is_company = any(c in dest for c in KNOWN_COMPANIES)
        firma_is_city = any(c in firma for c in KNOWN_CITIES)

        if dest_is_company or firma_is_city:
            print(f"  Swapping: Dest '{r['destinatie']}' <-> Firma '{r['firma_name']}'")
            cur.execute("""
                UPDATE transporturi_firme
                SET destinatie = %s, firma_name = %s
                WHERE id = %s
            """, (r['firma_name'], r['destinatie'], r['id']))
            fix_count += 1

    conn.commit()
    print(f"\nFixed {fix_count} records")

    # Verify
    print("\n" + "=" * 60)
    print("VERIFICATION - Sample after fix:")
    cur.execute("SELECT * FROM transporturi_firme LIMIT 10")
    for r in cur.fetchall():
        print(f"  Dest: {r['destinatie']}, Firma: {r['firma_name']}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
