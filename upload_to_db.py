import psycopg2
import json
from datetime import date

# NeonDB connection
DATABASE_URL = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("Kapcsolodas OK!")

# Create tables
print("\nTablak letrehozasa...")

cur.execute("""
DROP TABLE IF EXISTS daily_data CASCADE;
DROP TABLE IF EXISTS monthly_summary CASCADE;
DROP TABLE IF EXISTS yearly_summary CASCADE;
DROP TABLE IF EXISTS category_totals CASCADE;
DROP TABLE IF EXISTS weekday_patterns CASCADE;
""")

# Yearly summary
cur.execute("""
CREATE TABLE yearly_summary (
    id SERIAL PRIMARY KEY,
    year INTEGER UNIQUE NOT NULL,
    total_value DECIMAL(15,2),
    transactions INTEGER,
    working_days INTEGER,
    avg_per_day DECIMAL(12,2),
    avg_per_month DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

# Monthly summary
cur.execute("""
CREATE TABLE monthly_summary (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    period VARCHAR(10),
    total_value DECIMAL(15,2),
    total_paid DECIMAL(15,2),
    transactions INTEGER,
    working_days INTEGER,
    unique_partners INTEGER,
    avg_per_day DECIMAL(12,2),
    avg_per_trans DECIMAL(12,2),
    best_day_date VARCHAR(20),
    best_day_value DECIMAL(12,2),
    worst_day_date VARCHAR(20),
    worst_day_value DECIMAL(12,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(year, month)
);
""")

# Daily data
cur.execute("""
CREATE TABLE daily_data (
    id SERIAL PRIMARY KEY,
    date_key VARCHAR(20) NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    day INTEGER NOT NULL,
    weekday INTEGER,
    weekday_name VARCHAR(20),
    weekday_short VARCHAR(5),
    total_value DECIMAL(12,2),
    total_paid DECIMAL(12,2),
    transactions INTEGER,
    avg_per_trans DECIMAL(10,2),
    top3_detailed JSONB,
    top5_categories JSONB,
    all_categories JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date_key)
);
CREATE INDEX idx_daily_year_month ON daily_data(year, month);
CREATE INDEX idx_daily_weekday ON daily_data(weekday);
""")

# Category totals (by year and month)
cur.execute("""
CREATE TABLE category_totals (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER,
    category VARCHAR(50) NOT NULL,
    total_kg DECIMAL(15,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_category_year ON category_totals(year);
""")

# Weekday patterns
cur.execute("""
CREATE TABLE weekday_patterns (
    id SERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    weekday_name VARCHAR(20) NOT NULL,
    days_count INTEGER,
    avg_value DECIMAL(12,2),
    avg_transactions INTEGER,
    top3_categories JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")

conn.commit()
print("Tablak letrehozva!")

# Load JSON data
print("\nJSON betoltese...")
with open('all_data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Insert yearly summaries
print("\nEves osszesitok feltoltese...")
for year_str, year_data in data['years'].items():
    year = int(year_str)
    s = year_data['summary']
    cur.execute("""
        INSERT INTO yearly_summary (year, total_value, transactions, working_days, avg_per_day, avg_per_month)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (year, s['total_value'], s['transactions'], s['working_days'], s['avg_per_day'], s['avg_per_month']))

conn.commit()
print("  2 ev feltoltve")

# Insert monthly summaries and daily data
print("\nHavi es napi adatok feltoltese...")
total_months = 0
total_days = 0

for year_str, year_data in data['years'].items():
    year = int(year_str)

    # Yearly category totals
    if 'total_by_category' in year_data:
        for cat, kg in year_data['total_by_category'].items():
            cur.execute("""
                INSERT INTO category_totals (year, month, category, total_kg)
                VALUES (%s, NULL, %s, %s)
            """, (year, cat, kg))

    for month_str, month_data in year_data['months'].items():
        month = int(month_str)
        s = month_data['summary']

        # Monthly summary
        cur.execute("""
            INSERT INTO monthly_summary
            (year, month, period, total_value, total_paid, transactions, working_days,
             unique_partners, avg_per_day, avg_per_trans, best_day_date, best_day_value,
             worst_day_date, worst_day_value)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            year, month, month_data['period'],
            s['total_value'], s['total_paid'], s['transactions'], s['working_days'],
            s['unique_partners'], s['avg_per_day'], s['avg_per_trans'],
            s['best_day']['date'] if s['best_day'] else None,
            s['best_day']['value'] if s['best_day'] else None,
            s['worst_day']['date'] if s['worst_day'] else None,
            s['worst_day']['value'] if s['worst_day'] else None
        ))
        total_months += 1

        # Monthly category totals
        if 'total_by_category' in month_data:
            for cat, kg in month_data['total_by_category'].items():
                cur.execute("""
                    INSERT INTO category_totals (year, month, category, total_kg)
                    VALUES (%s, %s, %s, %s)
                """, (year, month, cat, kg))

        # Weekday patterns
        if 'weekday_patterns' in month_data:
            for wd_name, wd_data in month_data['weekday_patterns'].items():
                cur.execute("""
                    INSERT INTO weekday_patterns
                    (year, month, weekday_name, days_count, avg_value, avg_transactions, top3_categories)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    year, month, wd_name,
                    wd_data['days_count'], wd_data['avg_value'], wd_data['avg_transactions'],
                    json.dumps(wd_data['top3_categories'])
                ))

        # Daily data
        if 'daily' in month_data:
            for date_key, day_data in month_data['daily'].items():
                cur.execute("""
                    INSERT INTO daily_data
                    (date_key, year, month, day, weekday, weekday_name, weekday_short,
                     total_value, total_paid, transactions, avg_per_trans,
                     top3_detailed, top5_categories, all_categories)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (date_key) DO UPDATE SET
                        total_value = EXCLUDED.total_value,
                        transactions = EXCLUDED.transactions
                """, (
                    date_key, year, month, day_data['day'],
                    day_data['weekday'], day_data['weekday_name'], day_data['weekday_short'],
                    day_data['total_value'], day_data['total_paid'],
                    day_data['transactions'], day_data['avg_per_trans'],
                    json.dumps(day_data['top3_detailed']),
                    json.dumps(day_data['top5_categories']),
                    json.dumps(day_data['all_categories'])
                ))
                total_days += 1

conn.commit()
print(f"  {total_months} honap feltoltve")
print(f"  {total_days} nap feltoltve")

# Verify
print("\nEllenorzes...")
cur.execute("SELECT COUNT(*) FROM yearly_summary")
print(f"  yearly_summary: {cur.fetchone()[0]} rekord")

cur.execute("SELECT COUNT(*) FROM monthly_summary")
print(f"  monthly_summary: {cur.fetchone()[0]} rekord")

cur.execute("SELECT COUNT(*) FROM daily_data")
print(f"  daily_data: {cur.fetchone()[0]} rekord")

cur.execute("SELECT COUNT(*) FROM category_totals")
print(f"  category_totals: {cur.fetchone()[0]} rekord")

cur.execute("SELECT COUNT(*) FROM weekday_patterns")
print(f"  weekday_patterns: {cur.fetchone()[0]} rekord")

# Sample query
print("\n--- Minta lekerdezes: Top 5 honap forgalom szerint ---")
cur.execute("""
    SELECT period, total_value, transactions
    FROM monthly_summary
    ORDER BY total_value DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,.0f} RON ({row[2]} tranz)")

cur.close()
conn.close()

print("\n✅ KESZ! Minden adat feltoltve a NeonDB-be!")
