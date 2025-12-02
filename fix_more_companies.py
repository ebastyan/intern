# -*- coding: utf-8 -*-
"""
Fix more duplicate company names
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

db_url = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_db():
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

def run():
    conn = get_db()
    cur = conn.cursor()

    print("=" * 60)
    print("MORE COMPANY NORMALIZATION")
    print("=" * 60)

    # Get all companies with ID
    cur.execute("SELECT id, name FROM firme ORDER BY name")
    companies = cur.fetchall()

    print(f"\nCurrent companies ({len(companies)}):")
    name_to_id = {}
    for c in companies:
        print(f"  {c['id']}: {c['name']}")
        name_to_id[c['name'].upper()] = c['id']

    # Define more merges based on the list
    # Map: keep_name -> [merge_names]
    name_merges = {
        # I need to look at the actual list first
    }

    print("\n\nLooking for similar names...")

    # Group by similarity
    groups = {}
    for c in companies:
        name = c['name'].upper()
        # Get first significant word
        words = name.replace('-', ' ').split()
        if words:
            key = words[0]
            if key not in groups:
                groups[key] = []
            groups[key].append(c)

    # Show groups with multiple entries
    for key, items in sorted(groups.items()):
        if len(items) > 1:
            print(f"\n{key}:")
            for item in items:
                print(f"    {item['id']}: {item['name']}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
