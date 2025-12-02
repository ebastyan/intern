"""
Fix database issues:
1. Normalize company names (merge duplicates)
2. Verify data integrity
3. Check transport data structure
"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Database connection
db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL') or "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_db():
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def analyze_data():
    """Analyze the current state of the database"""
    conn = get_db()
    cur = conn.cursor()

    print("=" * 60)
    print("DATABASE ANALYSIS")
    print("=" * 60)

    # 1. Check vanzari per year
    print("\n1. VANZARI PER YEAR:")
    cur.execute("""
        SELECT year, COUNT(*) as count,
               COALESCE(SUM(valoare_ron), 0) as valoare,
               COUNT(DISTINCT firma_id) as firme
        FROM vanzari GROUP BY year ORDER BY year
    """)
    for r in cur.fetchall():
        print(f"  {r['year']}: {r['count']} vanzari, {r['valoare']:,.0f} RON, {r['firme']} firme")

    # 2. Check all company names
    print("\n2. ALL COMPANY NAMES:")
    cur.execute("SELECT id, name FROM firme ORDER BY name")
    companies = cur.fetchall()
    print(f"  Total: {len(companies)} companies")
    for c in companies:
        print(f"    ID {c['id']}: {c['name']}")

    # 3. Check transport data
    print("\n3. TRANSPORT DATA SAMPLE:")
    cur.execute("SELECT * FROM transporturi_firme LIMIT 5")
    for t in cur.fetchall():
        print(f"  Year: {t['year']}, Month: {t['month']}")
        print(f"    Destinatie: {t['destinatie']}")
        print(f"    Firma: {t['firma_name']}")
        print(f"    Descriere: {t['descriere']}")
        print(f"    Transportator: {t['transportator']}")
        print()

    # 4. Check sumar_deseuri
    print("\n4. SUMAR_DESEURI SAMPLE:")
    cur.execute("SELECT * FROM sumar_deseuri LIMIT 5")
    for d in cur.fetchall():
        print(f"  {d['tip_deseu']}: kg={d['cantitate_kg']}, valoare={d['valoare_ron']}, profit={d['adaos_ron']}")

    cur.close()
    conn.close()

def normalize_company_names():
    """Normalize company names by merging duplicates"""
    conn = get_db()
    cur = conn.cursor()

    # Company name mappings - canonical name -> list of variations
    # The key is the name to KEEP, the values are names to MERGE INTO the key
    mappings = {
        'RECIMAT': ['RECIMAT BIHOR'],
        'SPIZ': ['PW SPIZ SPOLSKA', 'PW SPIZ', 'SPIZ SPOLKA'],
        'CALITEX': ['SC CALITEX', 'CALITEX SRL'],
        'REMAT BIHOR': ['REMAT', 'REMAT BIHOR SRL'],
        'RER': ['RER VEST', 'RER ECOLOGIC'],
        'SOLIDE RECYCLING': ['SOLIDE', 'SOLIDE RECYLCING'],
        'ECO VEST': ['ECOVEST', 'ECO-VEST'],
        'FERMIT': ['FERMIT ORADEA', 'SC FERMIT'],
    }

    print("\n" + "=" * 60)
    print("NORMALIZING COMPANY NAMES")
    print("=" * 60)

    # Get all companies
    cur.execute("SELECT id, name FROM firme")
    companies = {c['name'].upper(): c for c in cur.fetchall()}

    for canonical, variations in mappings.items():
        canonical_upper = canonical.upper()

        # Find canonical company ID
        canonical_id = None
        for name, data in companies.items():
            if canonical_upper in name or name in canonical_upper:
                canonical_id = data['id']
                break

        if not canonical_id:
            print(f"  Warning: Canonical '{canonical}' not found, skipping...")
            continue

        for var in variations:
            var_upper = var.upper()
            for name, data in companies.items():
                if var_upper in name or name == var_upper:
                    if data['id'] != canonical_id:
                        print(f"  Merging '{data['name']}' (ID {data['id']}) into '{canonical}' (ID {canonical_id})")
                        # Update all vanzari references
                        cur.execute("UPDATE vanzari SET firma_id = %s WHERE firma_id = %s",
                                   (canonical_id, data['id']))
                        affected = cur.rowcount
                        print(f"    -> Updated {affected} vanzari records")

                        # Delete the duplicate company
                        try:
                            cur.execute("DELETE FROM firme WHERE id = %s", (data['id'],))
                            print(f"    -> Deleted duplicate company")
                        except Exception as e:
                            print(f"    -> Warning: Could not delete: {e}")

    conn.commit()
    cur.close()
    conn.close()
    print("\nDone!")

def verify_data():
    """Verify data after normalization"""
    conn = get_db()
    cur = conn.cursor()

    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    # Check remaining companies
    cur.execute("SELECT id, name FROM firme ORDER BY name")
    companies = cur.fetchall()
    print(f"\nRemaining companies: {len(companies)}")

    # Check vanzari integrity
    cur.execute("""
        SELECT f.name, COUNT(v.id) as cnt, SUM(v.valoare_ron) as val
        FROM vanzari v
        JOIN firme f ON v.firma_id = f.id
        GROUP BY f.name
        ORDER BY val DESC
        LIMIT 20
    """)
    print("\nTop 20 companies by value:")
    for r in cur.fetchall():
        print(f"  {r['name']}: {r['cnt']} vanzari, {r['val']:,.0f} RON")

    cur.close()
    conn.close()

if __name__ == '__main__':
    analyze_data()
    # Uncomment to run normalization:
    # normalize_company_names()
    # verify_data()
