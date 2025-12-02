# -*- coding: utf-8 -*-
"""
Fix duplicate company names by merging them
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

# Database connection
db_url = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_db():
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

# Company merge mappings: keep_id -> [merge_ids]
# Based on the company list analysis
COMPANY_MERGES = {
    # ABS ACCIAIERIE variants -> keep ID 4 (ABS-ACCIAIERIE BERTOLI SAFAU)
    4: [2, 3],  # Merge ID 2,3 into ID 4

    # ACCIAIERIE BELTRAME variants -> keep ID 7 (AFV-ACCIAIERIE BELTRAME)
    7: [5, 6],

    # AK METAL variants
    9: [10],  # AK METAL <- AK METAL B.V.

    # ALKU variants
    11: [12],  # ALKU <- ALKU GMBH KABEL UND METALLE

    # ALPIN RECYCLING variants
    14: [15],  # ALPIN RECYCLING <- ALPIN REYCLING (typo)

    # AS METAL variants
    18: [19],  # AS METAL <- AS METAL COM

    # BYRMETALS variants -> keep one
    24: [21, 22, 23, 25],  # BYRMETALS SCRAP TRADE <- others

    # CANPACK variants
    29: [26, 27, 28],  # CANPACK RECYCLING <- others

    # CHEMICAL variants
    34: [32, 33],  # CHEMICAL WORLDWIDE BUSINESS <- others
}

def run():
    conn = get_db()
    cur = conn.cursor()

    print("=" * 60)
    print("COMPANY NAME NORMALIZATION")
    print("=" * 60)

    # Get current companies
    cur.execute("SELECT id, name FROM firme ORDER BY id")
    companies = {c['id']: c['name'] for c in cur.fetchall()}
    print(f"\nTotal companies before: {len(companies)}")

    # Also get more duplicate patterns from the actual names
    cur.execute("SELECT id, name FROM firme")
    all_companies = cur.fetchall()

    # Create automatic merge mappings based on name similarity
    name_to_ids = {}
    for c in all_companies:
        # Normalize for matching
        name = c['name'].upper().strip()
        # Remove common suffixes and variations
        name = name.replace(' SRL', '').replace(' S.R.L.', '').replace(' S.R.L', '')
        name = name.replace(' B.V.', '').replace(' B.V', '').replace('B.V.', '')
        name = name.replace(' GMBH', '').replace(' SP ZOO', '').replace(' SP. Z O.O.', '')
        name = name.replace(' SPOLKA Z OGRANICZONA', '').replace(' SPOLKA', '')
        name = name.replace('-', ' ').replace('  ', ' ').strip()

        base_name = name.split()[0] if name else ''  # First word as key

        if base_name not in name_to_ids:
            name_to_ids[base_name] = []
        name_to_ids[base_name].append(c['id'])

    # Show potential duplicates
    print("\nPotential duplicates by first word:")
    for name, ids in sorted(name_to_ids.items()):
        if len(ids) > 1:
            names = [companies.get(i, 'N/A') for i in ids if i in companies]
            print(f"  {name}: {ids} -> {names}")

    # Do the manual merges
    print("\n" + "=" * 60)
    print("EXECUTING MERGES")
    print("=" * 60)

    for keep_id, merge_ids in COMPANY_MERGES.items():
        if keep_id not in companies:
            print(f"  WARNING: Keep ID {keep_id} not found, skipping...")
            continue

        keep_name = companies[keep_id]
        print(f"\n  Keeping: '{keep_name}' (ID {keep_id})")

        for merge_id in merge_ids:
            if merge_id not in companies:
                print(f"    - ID {merge_id} not found, skipping...")
                continue

            merge_name = companies[merge_id]

            # Update vanzari to point to keep_id
            cur.execute("UPDATE vanzari SET firma_id = %s WHERE firma_id = %s", (keep_id, merge_id))
            vanzari_count = cur.rowcount

            # Update sumar_firme to point to keep_id
            cur.execute("UPDATE sumar_firme SET firma_id = %s WHERE firma_id = %s", (keep_id, merge_id))
            sumar_count = cur.rowcount

            # Delete the merged company
            cur.execute("DELETE FROM firme WHERE id = %s", (merge_id,))

            print(f"    <- Merged '{merge_name}' (ID {merge_id}): {vanzari_count} vanzari, {sumar_count} sumar")

    conn.commit()

    # Final count
    cur.execute("SELECT COUNT(*) as count FROM firme")
    final_count = cur.fetchone()['count']
    print(f"\n\nTotal companies after: {final_count}")

    # Show data by year
    print("\n" + "=" * 60)
    print("DATA VERIFICATION")
    print("=" * 60)

    cur.execute("""
        SELECT year, COUNT(*) as vanzari,
               SUM(valoare_ron) as valoare,
               SUM(adaos_final) as profit,
               COUNT(DISTINCT firma_id) as firme
        FROM vanzari
        GROUP BY year ORDER BY year
    """)
    print("\nVanzari per year:")
    for r in cur.fetchall():
        print(f"  {r['year']}: {r['vanzari']} vanzari, {r['valoare']:,.0f} RON, {r['profit']:,.0f} profit, {r['firme']} firme")

    # Show top companies
    print("\nTop 10 companies by value:")
    cur.execute("""
        SELECT f.name, SUM(v.valoare_ron) as total, COUNT(*) as cnt
        FROM vanzari v
        JOIN firme f ON v.firma_id = f.id
        GROUP BY f.id, f.name
        ORDER BY total DESC
        LIMIT 10
    """)
    for r in cur.fetchall():
        print(f"  {r['name']}: {r['total']:,.0f} RON ({r['cnt']} vanzari)")

    cur.close()
    conn.close()

    print("\n\nDone!")

if __name__ == '__main__':
    run()
