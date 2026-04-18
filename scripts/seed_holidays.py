# scripts/seed_holidays.py
"""Seed the holidays table for a year range. Computes Catholic and Orthodox Easter.

Usage:
  python scripts/seed_holidays.py --self-test              # just run algorithm checks
  python scripts/seed_holidays.py --year-from 2022 --year-to 2030
"""
import argparse, os, sys
import psycopg2
from datetime import date, timedelta
from pathlib import Path

def load_env_local():
    env = Path(__file__).parent.parent / '.env.local'
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))

def catholic_easter(year: int) -> date:
    """Butcher's Gregorian Easter algorithm (returns Sunday)."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

# Known Catholic Easter Sunday dates, hand-verified.
KNOWN_CATHOLIC_EASTER = {
    2022: date(2022, 4, 17),
    2023: date(2023, 4, 9),
    2024: date(2024, 3, 31),
    2025: date(2025, 4, 20),
    2026: date(2026, 4, 5),
    2027: date(2027, 3, 28),
    2028: date(2028, 4, 16),
    2029: date(2029, 4, 1),
    2030: date(2030, 4, 21),
}

def orthodox_easter(year: int) -> date:
    """Meeus' Julian Easter algorithm, then Julian -> Gregorian shift (+13 days for 1900-2099)."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month_julian = (d + e + 114) // 31
    day_julian = ((d + e + 114) % 31) + 1
    julian_date = date(year, month_julian, day_julian)
    return julian_date + timedelta(days=13)

# Known Orthodox Easter Sunday dates, hand-verified.
KNOWN_ORTHODOX_EASTER = {
    2022: date(2022, 4, 24),
    2023: date(2023, 4, 16),
    2024: date(2024, 5, 5),
    2025: date(2025, 4, 20),
    2026: date(2026, 4, 12),
    2027: date(2027, 5, 2),
    2028: date(2028, 4, 16),
    2029: date(2029, 4, 8),
    2030: date(2030, 4, 28),
}

def generate_holidays(year_from: int, year_to: int):
    """Yield (date, name, type, is_official) tuples for all holidays in the year range."""
    for year in range(year_from, year_to + 1):
        # Fixed national holidays (is_official=True)
        yield (date(year, 1, 1), 'Anul Nou', 'national', True)
        yield (date(year, 1, 2), 'Anul Nou (a doua zi)', 'national', True)
        yield (date(year, 1, 24), 'Ziua Unirii Principatelor Romane', 'national', True)
        yield (date(year, 5, 1), 'Ziua Muncii', 'national', True)
        yield (date(year, 6, 1), 'Ziua Copilului', 'national', True)
        yield (date(year, 8, 15), 'Adormirea Maicii Domnului', 'national', True)
        yield (date(year, 11, 30), 'Sfantul Andrei', 'national', True)
        yield (date(year, 12, 1), 'Ziua Nationala', 'national', True)
        yield (date(year, 12, 25), 'Craciunul', 'national', True)
        yield (date(year, 12, 26), 'Craciunul (a doua zi)', 'national', True)

        # Catholic (is_official=False — cultural, not a Romanian public holiday)
        ce = catholic_easter(year)
        yield (ce - timedelta(days=2), 'Vinerea Mare (catolica)', 'catholic', False)
        yield (ce, 'Pastele catolic', 'catholic', False)
        yield (ce + timedelta(days=1), 'A doua zi de Pasti (catolic)', 'catholic', False)
        yield (ce + timedelta(days=49), 'Rusalii catolice', 'catholic', False)
        yield (ce + timedelta(days=50), 'A doua zi de Rusalii (catolic)', 'catholic', False)

        # Orthodox (is_official=True for Good Friday since 2018, Easter and Pentecost always)
        oe = orthodox_easter(year)
        yield (oe - timedelta(days=2), 'Vinerea Mare (ortodoxa)', 'orthodox', year >= 2018)
        yield (oe, 'Pastele ortodox', 'orthodox', True)
        yield (oe + timedelta(days=1), 'A doua zi de Pasti (ortodox)', 'orthodox', True)
        yield (oe + timedelta(days=49), 'Rusalii ortodoxe', 'orthodox', True)
        yield (oe + timedelta(days=50), 'A doua zi de Rusalii (ortodoxe)', 'orthodox', True)

def upsert_holidays(year_from: int, year_to: int):
    url = os.environ.get('POSTGRES_URL')
    if not url:
        raise RuntimeError('POSTGRES_URL not set (check .env.local)')
    conn = psycopg2.connect(url)
    conn.autocommit = False
    rows = list(generate_holidays(year_from, year_to))
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO holidays (date, name, type, is_official)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (date, type) DO UPDATE
              SET name = EXCLUDED.name,
                  is_official = EXCLUDED.is_official
            """,
            rows,
        )
    conn.commit()
    conn.close()
    return len(rows)

def self_test():
    for y, expected in KNOWN_CATHOLIC_EASTER.items():
        assert catholic_easter(y) == expected
    for y, expected in KNOWN_ORTHODOX_EASTER.items():
        assert orthodox_easter(y) == expected
    print(f"Easter algorithms OK ({len(KNOWN_CATHOLIC_EASTER)} + {len(KNOWN_ORTHODOX_EASTER)} years)")

    rows = list(generate_holidays(2024, 2024))
    # 10 fixed national + 5 catholic + 5 orthodox = 20 per year
    assert len(rows) == 20, f"Expected 20 entries for 2024, got {len(rows)}"
    by_type = {}
    for _, _, t, _ in rows:
        by_type[t] = by_type.get(t, 0) + 1
    assert by_type == {'national': 10, 'catholic': 5, 'orthodox': 5}, by_type

    # Spot-check: Romanian National Day 2024 is Dec 1
    dates_2024 = {name: d for d, name, *_ in rows}
    assert dates_2024['Ziua Nationala'] == date(2024, 12, 1)
    # Spot-check: Orthodox Easter Monday 2024 = May 6 (Easter was May 5)
    assert dates_2024['A doua zi de Pasti (ortodox)'] == date(2024, 5, 6)

    print(f"generate_holidays() OK: 20 entries/year, correct type split, known dates match")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--year-from', type=int, default=2022)
    parser.add_argument('--year-to', type=int, default=2030)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        sys.exit(0)
    load_env_local()
    n = upsert_holidays(args.year_from, args.year_to)
    print(f"Upserted {n} holidays for {args.year_from}-{args.year_to}")
