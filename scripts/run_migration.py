# scripts/run_migration.py
"""Run a SQL migration file against POSTGRES_URL. Usage: python scripts/run_migration.py scripts/migrations/NNN_name.sql"""
import os, sys, psycopg2
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

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_migration.py <path-to-sql-file>")
        sys.exit(1)
    load_env_local()
    sql_path = Path(sys.argv[1])
    if not sql_path.exists():
        print(f"Missing: {sql_path}"); sys.exit(1)
    sql = sql_path.read_text()
    url = os.environ.get('POSTGRES_URL')
    if not url:
        print("POSTGRES_URL not set"); sys.exit(1)
    conn = psycopg2.connect(url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.close()
    print(f"Applied: {sql_path.name}")

if __name__ == '__main__':
    main()
