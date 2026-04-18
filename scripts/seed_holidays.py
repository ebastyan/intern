# scripts/seed_holidays.py
"""Seed the holidays table for a year range. Computes Catholic and Orthodox Easter.

Usage:
  python scripts/seed_holidays.py --self-test              # just run algorithm checks
  python scripts/seed_holidays.py --year-from 2022 --year-to 2030
"""
import argparse, os, sys
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

def self_test():
    for y, expected in KNOWN_CATHOLIC_EASTER.items():
        got = catholic_easter(y)
        assert got == expected, f"catholic_easter({y}) -> {got}, expected {expected}"
    print(f"Catholic Easter OK for {len(KNOWN_CATHOLIC_EASTER)} years")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--year-from', type=int, default=2022)
    parser.add_argument('--year-to', type=int, default=2030)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        sys.exit(0)
    print("Seeding not yet implemented in this task; run --self-test for now.")
