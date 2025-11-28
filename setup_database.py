"""
PAJU - Complete Database Setup and Import
==========================================
Ez a script:
1. Létrehozza a normalizált táblákat NeonDB-ben
2. Importálja a partnereket (persoanefizice.xls)
3. Importálja az összes tranzakciót (napi XLS fájlok)
4. Tisztítja az adatokat (whitespace, kis/nagybetű)
"""

import win32com.client
import psycopg2
from psycopg2.extras import execute_values
import os
import re
import time
from datetime import datetime, date
from collections import defaultdict

# NeonDB connection
DATABASE_URL = "postgresql://neondb_owner:npg_L2AyrcXul8km@ep-ancient-firefly-a47vk6i8-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require"
BASE_PATH = r'C:\Users\INTEL\Desktop\paju'

def get_connection():
    """Get a new database connection"""
    return psycopg2.connect(DATABASE_URL)

def execute_with_retry(cur, conn, query, data, max_retries=3):
    """Execute query with retry on connection failure"""
    for attempt in range(max_retries):
        try:
            execute_values(cur, query, data)
            conn.commit()
            return True
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            print(f"      Connection error, retry {attempt+1}/{max_retries}...")
            time.sleep(2)
            try:
                conn.close()
            except:
                pass
            conn = get_connection()
            cur = conn.cursor()
    return False

# CNP county codes (Romania)
COUNTY_CODES = {
    '01': 'Alba', '02': 'Arad', '03': 'Arges', '04': 'Bacau', '05': 'Bihor',
    '06': 'Bistrita-Nasaud', '07': 'Botosani', '08': 'Brasov', '09': 'Braila',
    '10': 'Buzau', '11': 'Caras-Severin', '12': 'Cluj', '13': 'Constanta',
    '14': 'Covasna', '15': 'Dambovita', '16': 'Dolj', '17': 'Galati',
    '18': 'Gorj', '19': 'Harghita', '20': 'Hunedoara', '21': 'Ialomita',
    '22': 'Iasi', '23': 'Ilfov', '24': 'Maramures', '25': 'Mehedinti',
    '26': 'Mures', '27': 'Neamt', '28': 'Olt', '29': 'Prahova', '30': 'Satu Mare',
    '31': 'Salaj', '32': 'Sibiu', '33': 'Suceava', '34': 'Teleorman',
    '35': 'Timis', '36': 'Tulcea', '37': 'Vaslui', '38': 'Valcea', '39': 'Vrancea',
    '40': 'Bucuresti', '41': 'Bucuresti S1', '42': 'Bucuresti S2',
    '43': 'Bucuresti S3', '44': 'Bucuresti S4', '45': 'Bucuresti S5',
    '46': 'Bucuresti S6', '51': 'Calarasi', '52': 'Giurgiu'
}

def normalize_string(s):
    """Normalize string: strip whitespace, consistent casing for proper nouns"""
    if not s:
        return None
    s = str(s).strip()
    # Remove extra whitespace
    s = re.sub(r'\s+', ' ', s)
    return s if s else None

def normalize_county(county):
    """Normalize county name: Bihor = BIHOR = bihor"""
    if not county:
        return None
    county = normalize_string(county)
    if not county:
        return None
    # Title case for counties
    return county.title()

def normalize_city(city):
    """Normalize city name"""
    if not city:
        return None
    city = normalize_string(city)
    if not city:
        return None
    return city.title()

def normalize_name(name):
    """Normalize person name"""
    if not name:
        return None
    name = normalize_string(name)
    if not name:
        return None
    # Title case for names
    return name.title()

def parse_cnp(cnp_str):
    """Extract info from CNP"""
    if not cnp_str:
        return None, None, None

    # Clean CNP
    cnp = str(int(float(cnp_str))) if isinstance(cnp_str, float) else str(cnp_str)
    cnp = cnp.replace('.0', '').strip()

    if len(cnp) != 13:
        return None, None, None

    try:
        sex_code = cnp[0]
        year_suffix = cnp[1:3]
        county_code = cnp[7:9]

        # Determine birth year
        if sex_code in ['1', '2']:
            year = 1900 + int(year_suffix)
        elif sex_code in ['3', '4']:
            year = 1800 + int(year_suffix)
        elif sex_code in ['5', '6']:
            year = 2000 + int(year_suffix)
        else:
            year = 1900 + int(year_suffix)

        sex = 'M' if sex_code in ['1', '3', '5', '7'] else 'F'

        return sex, year, county_code
    except:
        return None, None, None

def clean_cnp(cnp_val):
    """Clean CNP value to string"""
    if not cnp_val:
        return None
    cnp = str(int(float(cnp_val))) if isinstance(cnp_val, float) else str(cnp_val)
    cnp = cnp.replace('.0', '').strip()
    if len(cnp) == 13 and cnp.isdigit():
        return cnp
    return None

def normalize_waste_name(name):
    """Normalize common typos in waste type names"""
    # Common typos/variations
    typo_map = {
        'JENTI': 'JANTE',  # JENTI -> JANTE
        'HARTTIE': 'HARTIE',
        'ALUMINUI': 'ALUMINIU',
    }
    result = name
    for typo, correct in typo_map.items():
        result = re.sub(typo, correct, result, flags=re.IGNORECASE)
    return result

def extract_category(header):
    """Extract category and subtype from header like 'Deseu Cupru (36.00)'"""
    # Remove price part
    name = re.sub(r'\s*\([0-9.]+\)\s*$', '', header).strip()
    # Normalize typos
    name = normalize_waste_name(name)
    name_upper = name.upper()

    # Determine category
    if 'FIER' in name_upper:
        return 'Fier', name
    elif 'CUPRU' in name_upper and 'CABLU' not in name_upper and 'ALUMINIU' not in name_upper:
        return 'Cupru', name
    elif 'CABLU' in name_upper and 'CUPRU' in name_upper:
        return 'Cablu Cupru', name
    elif 'CABLU' in name_upper and 'ALUMINIU' in name_upper:
        return 'Cablu Aluminiu', name
    elif 'ALAMA' in name_upper:
        return 'Alama', name
    elif 'ALUMINIU' in name_upper:
        return 'Aluminiu', name
    elif 'ACUMULATOR' in name_upper:
        return 'Acumulatori', name
    elif 'INOX' in name_upper:
        return 'Inox', name
    elif 'PLUMB' in name_upper:
        return 'Plumb', name
    elif 'ZINC' in name_upper:
        return 'Zinc', name
    elif 'ZAMAC' in name_upper:
        return 'Zamac', name
    elif 'DEEE' in name_upper or 'PLACI ELECTRONICE' in name_upper:
        return 'DEEE', name
    elif 'CARTON' in name_upper or 'HARTIE' in name_upper:
        return 'Carton', name
    elif 'STICLA' in name_upper:
        return 'Sticla', name
    elif 'PLASTIC' in name_upper or 'PET' in name_upper or 'FOLIE' in name_upper:
        return 'Plastic', name
    elif 'NEFEROS' in name_upper:
        return 'Neferos Mix', name
    else:
        return 'Altele', name

def extract_price(header):
    """Extract price from header like 'Deseu Cupru (36.00)'"""
    match = re.search(r'\(([0-9.]+)\)', header)
    if match:
        return float(match.group(1))
    return None

def parse_date(date_str):
    """Parse date from various formats"""
    if not date_str:
        return None

    if isinstance(date_str, datetime):
        return date_str.date()

    date_str = str(date_str).strip()

    # Try different formats
    formats = ['%Y/%m/%d %H:%M', '%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str.split()[0] if ' ' in date_str else date_str, fmt.split()[0]).date()
        except:
            pass
    return None

def detect_file_structure(headers):
    """Detect file structure by header positions

    Old structure (2024 Jan-Aug):
      Col 1: Nume, Col 2: CNP, Col 3: Nr.APP, Col 4: Valoare, Col 5: Fond, Col 6: Impozit, Col 7: Achitat, Col 8+: Waste

    New structure A (some Sept+ files):
      Col 1: Nume, Col 2: CNP, Col 3: Nr.APP, Col 4: Tip plata, Col 5: IBAN, Col 6: Valoare, Col 7: Fond, Col 8: Impozit, Col 9: Achitat, Col 10+: Waste

    New structure B (some files have different order):
      Col 1: Nume, Col 2: CNP, Col 3: Tip plata, Col 4: IBAN, Col 5: Nr.APP, Col 6: Valoare, Col 7: Fond, Col 8: Impozit, Col 9: Achitat, Col 10+: Waste

    Returns: (structure_type, doc_id_col, tip_plata_col, iban_col, value_col, paid_col, waste_start)
    """
    tip_plata_col = None
    nr_app_col = None
    valoare_col = None
    iban_col = None

    for i, h in enumerate(headers):
        if h:
            h_lower = str(h).lower()
            if 'tip plata' in h_lower:
                tip_plata_col = i
            elif 'nr. app' in h_lower or 'nr.app' in h_lower:
                nr_app_col = i
            elif h_lower == 'valoare':
                valoare_col = i
            elif 'iban' in h_lower or 'cont' in h_lower:
                iban_col = i

    # Old structure - no Tip plata column
    if tip_plata_col is None:
        # Old: doc_id at idx 2, no tip_plata, no iban, value at idx 3, paid at idx 6, waste from idx 7
        return 'old', 2, None, None, 3, 6, 7

    # New structure - find actual positions
    if nr_app_col is not None and valoare_col is not None:
        # Paid column is typically valoare + 3 (Fond, Impozit, then Achitat)
        paid_col = valoare_col + 3
        waste_start = valoare_col + 4  # After Achitat
        return 'new', nr_app_col, tip_plata_col, iban_col, valoare_col, paid_col, waste_start

    # Fallback for new structure
    if tip_plata_col == 2:  # Col 3 is Tip plata -> Nr.APP is at col 5 (idx 4)
        return 'new', 4, 2, 3, 5, 8, 9
    else:  # Col 3 is Nr.APP (idx 2), Tip plata at col 4 (idx 3)
        return 'new', 2, 3, 4, 5, 8, 9

# =============================================================================
# MAIN SCRIPT
# =============================================================================

print("=" * 60)
print("PAJU Database Setup and Import")
print("=" * 60)

# Connect to database
print("\n[1] Conectare la NeonDB...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
print("    OK!")

# =============================================================================
# CREATE TABLES
# =============================================================================
print("\n[2] Creare tabele...")

cur.execute("""
-- Drop existing tables
DROP TABLE IF EXISTS transaction_items CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS waste_types CASCADE;
DROP TABLE IF EXISTS waste_categories CASCADE;
DROP TABLE IF EXISTS partners CASCADE;

-- Partners table (from persoanefizice.xls)
CREATE TABLE partners (
    cnp VARCHAR(13) PRIMARY KEY,
    name VARCHAR(200),
    id_series VARCHAR(100),
    id_expiry DATE,
    street VARCHAR(500),
    city VARCHAR(150),
    county VARCHAR(100),
    country VARCHAR(100) DEFAULT 'Romania',
    phone VARCHAR(100),
    email VARCHAR(150),
    birth_year INTEGER,
    sex CHAR(1),
    county_code_cnp VARCHAR(2),
    county_from_cnp VARCHAR(50),
    created_at TIMESTAMP,
    modified_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);
CREATE INDEX idx_partners_county ON partners(county);
CREATE INDEX idx_partners_city ON partners(city);
CREATE INDEX idx_partners_name ON partners(name);

-- Waste categories (main categories: Fier, Cupru, etc.)
CREATE TABLE waste_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL
);

-- Waste types (subtypes: Deseu Cupru, Deseu Cupru Junkers, etc.)
CREATE TABLE waste_types (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES waste_categories(id),
    name VARCHAR(150) NOT NULL,
    UNIQUE(category_id, name)
);
CREATE INDEX idx_waste_types_category ON waste_types(category_id);

-- Transactions (each document/visit)
CREATE TABLE transactions (
    document_id VARCHAR(50) PRIMARY KEY,
    date DATE NOT NULL,
    cnp VARCHAR(13) REFERENCES partners(cnp),
    payment_type VARCHAR(100),
    iban VARCHAR(100),
    gross_value DECIMAL(12,2),
    env_tax DECIMAL(10,2),
    income_tax DECIMAL(10,2),
    net_paid DECIMAL(12,2)
);
CREATE INDEX idx_transactions_date ON transactions(date);
CREATE INDEX idx_transactions_cnp ON transactions(cnp);
CREATE INDEX idx_transactions_date_cnp ON transactions(date, cnp);

-- Transaction items (each waste type in a transaction)
CREATE TABLE transaction_items (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(50) REFERENCES transactions(document_id),
    waste_type_id INTEGER REFERENCES waste_types(id),
    price_per_kg DECIMAL(8,2),
    weight_kg DECIMAL(10,2),
    value DECIMAL(12,2)
);
CREATE INDEX idx_items_document ON transaction_items(document_id);
CREATE INDEX idx_items_waste_type ON transaction_items(waste_type_id);
CREATE INDEX idx_items_price ON transaction_items(price_per_kg);
""")

conn.commit()
print("    Tabele create!")

# =============================================================================
# IMPORT PARTNERS FROM PERSOANEFIZICE.XLS
# =============================================================================
print("\n[3] Import parteneri din persoanefizice.xls...")

excel = win32com.client.Dispatch('Excel.Application')
excel.Visible = False
excel.DisplayAlerts = False

partners_file = os.path.join(BASE_PATH, 'persoanefizice.xls')
wb = excel.Workbooks.Open(partners_file)
ws = wb.Sheets(1)

last_row = ws.UsedRange.Rows.Count
last_col = 30  # We need columns up to 29
print(f"    Gasit {last_row} randuri, citire range...")

# Read ALL data at once - MUCH faster!
data_range = ws.Range(ws.Cells(2, 1), ws.Cells(last_row, last_col))
all_data = data_range.Value
print(f"    Date citite, procesare...")

partners_data = []
partners_seen = set()
skipped = 0

if all_data:
    # Handle single row case
    if not isinstance(all_data[0], tuple):
        all_data = [all_data]

    for idx, row in enumerate(all_data):
        if idx % 5000 == 0 and idx > 0:
            print(f"    Procesat {idx}/{len(all_data)}...")

        if not row or len(row) < 10:
            skipped += 1
            continue

        cnp = clean_cnp(row[3])  # Column 4 = index 3
        if not cnp or cnp in partners_seen:
            skipped += 1
            continue

        partners_seen.add(cnp)

        name = normalize_name(row[1])  # Column 2
        id_series = normalize_string(row[4])  # Column 5
        id_expiry = parse_date(row[5])  # Column 6
        street = normalize_string(row[6])  # Column 7
        city = normalize_city(row[7])  # Column 8
        county = normalize_county(row[8])  # Column 9
        country = normalize_string(row[9]) if len(row) > 9 else 'Romania'  # Column 10
        country = country or 'Romania'
        phone = normalize_string(row[14]) if len(row) > 14 else None  # Column 15
        email = normalize_string(row[11]) if len(row) > 11 else None  # Column 12
        created_at = parse_date(row[26]) if len(row) > 26 else None  # Column 27
        modified_at = parse_date(row[28]) if len(row) > 28 else None  # Column 29
        is_active = row[24] if len(row) > 24 else True  # Column 25
        is_active = True if is_active in [True, 1, '1', 'Da', 'Yes'] else False

        # Parse CNP for extra info
        sex, birth_year, county_code = parse_cnp(cnp)
        county_from_cnp = COUNTY_CODES.get(county_code) if county_code else None

        partners_data.append((
            cnp, name, id_series, id_expiry, street, city, county, country,
            phone, email, birth_year, sex, county_code, county_from_cnp,
            created_at, modified_at, is_active
        ))

wb.Close(False)

# Bulk insert partners in smaller batches with retry
PARTNER_BATCH = 100  # Very small batches for stability
print(f"    Inserare {len(partners_data)} parteneri in batch-uri de {PARTNER_BATCH}...")
partner_insert_query = """
    INSERT INTO partners (cnp, name, id_series, id_expiry, street, city, county, country,
                         phone, email, birth_year, sex, county_code_cnp, county_from_cnp,
                         created_at, modified_at, is_active)
    VALUES %s
    ON CONFLICT (cnp) DO UPDATE SET
        name = EXCLUDED.name,
        modified_at = EXCLUDED.modified_at
"""

for i in range(0, len(partners_data), PARTNER_BATCH):
    batch = partners_data[i:i+PARTNER_BATCH]
    for attempt in range(3):
        try:
            execute_values(cur, partner_insert_query, batch)
            conn.commit()
            break
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
            print(f"      Retry {attempt+1}/3 at batch {i}...")
            time.sleep(2)
            try:
                cur.close()
                conn.close()
            except:
                pass
            conn = get_connection()
            cur = conn.cursor()

    if (i + PARTNER_BATCH) % 3000 == 0:
        print(f"      Inserat {min(i+PARTNER_BATCH, len(partners_data))}/{len(partners_data)}...")

print(f"    Importat {len(partners_data)} parteneri (skip: {skipped} duplicat/invalid)")

# =============================================================================
# SCAN ALL XLS FILES FOR WASTE TYPES
# =============================================================================
print("\n[4] Scanare tipuri de deseuri din toate fisierele...")

all_waste_headers = set()
all_months = []

for year in ['2024', '2025']:
    year_path = os.path.join(BASE_PATH, year)
    if os.path.exists(year_path):
        for folder in sorted(os.listdir(year_path)):
            folder_path = os.path.join(year_path, folder)
            if os.path.isdir(folder_path):
                all_months.append((year, folder, folder_path))

print(f"    Gasit {len(all_months)} luni de procesat")

# Scan headers from first file of each month
for year, folder, folder_path in all_months:
    files = [f for f in os.listdir(folder_path) if f.endswith('.xls')]
    if files:
        file_path = os.path.join(folder_path, files[0])
        try:
            wb = excel.Workbooks.Open(os.path.abspath(file_path))
            ws = wb.Sheets(1)
            for col in range(1, 300):
                val = ws.Cells(1, col).Value
                if val and ('Deseu' in str(val) or 'Deseuri' in str(val)):
                    all_waste_headers.add(str(val))
            wb.Close(False)
        except Exception as e:
            print(f"    EROARE la {file_path}: {e}")

print(f"    Gasit {len(all_waste_headers)} tipuri de deseuri unice")

# =============================================================================
# INSERT WASTE CATEGORIES AND TYPES
# =============================================================================
print("\n[5] Inserare categorii si tipuri deseuri...")

categories_map = {}  # name -> id
waste_types_map = {}  # (category_id, subtype_name) -> id

for header in sorted(all_waste_headers):
    cat_name, subtype_name = extract_category(header)

    # Insert category if new
    if cat_name not in categories_map:
        cur.execute("""
            INSERT INTO waste_categories (name) VALUES (%s)
            ON CONFLICT (name) DO NOTHING
            RETURNING id
        """, (cat_name,))
        result = cur.fetchone()
        if result:
            categories_map[cat_name] = result[0]
        else:
            cur.execute("SELECT id FROM waste_categories WHERE name = %s", (cat_name,))
            categories_map[cat_name] = cur.fetchone()[0]

    # Insert waste type if new
    cat_id = categories_map[cat_name]
    key = (cat_id, subtype_name)
    if key not in waste_types_map:
        cur.execute("""
            INSERT INTO waste_types (category_id, name) VALUES (%s, %s)
            ON CONFLICT (category_id, name) DO NOTHING
            RETURNING id
        """, (cat_id, subtype_name))
        result = cur.fetchone()
        if result:
            waste_types_map[key] = result[0]
        else:
            cur.execute("SELECT id FROM waste_types WHERE category_id = %s AND name = %s", (cat_id, subtype_name))
            waste_types_map[key] = cur.fetchone()[0]

conn.commit()
print(f"    Inserat {len(categories_map)} categorii, {len(waste_types_map)} subtipuri")

# =============================================================================
# IMPORT ALL TRANSACTIONS
# =============================================================================
print("\n[6] Import tranzactii din toate fisierele XLS...")

total_transactions = 0
total_items = 0
missing_partners = set()
transactions_batch = []
items_batch = []
BATCH_SIZE = 200  # Smaller batches to avoid SSL timeout

for year, folder, folder_path in all_months:
    files = [f for f in os.listdir(folder_path) if f.endswith('.xls')]
    print(f"    {year}/{folder}: {len(files)} fisiere...")

    for filename in files:
        # Parse date from filename
        date_str = filename.replace('.xls', '')
        try:
            day, month_num, y = date_str.split('.')
            trans_date = date(int(y), int(month_num), int(day))
        except:
            continue

        file_path = os.path.abspath(os.path.join(folder_path, filename))

        try:
            wb = excel.Workbooks.Open(file_path)
            ws = wb.Sheets(1)

            # Get headers (read row 1 as range - MUCH faster)
            last_col = ws.UsedRange.Columns.Count
            header_range = ws.Range(ws.Cells(1, 1), ws.Cells(1, last_col)).Value
            if header_range:
                headers = [str(h) if h else None for h in header_range[0]] if isinstance(header_range[0], tuple) else [str(header_range[0]) if header_range[0] else None]
            else:
                headers = []

            # Detect structure from headers
            structure, doc_id_col, tip_plata_col, iban_col, value_col, paid_col, waste_start = detect_file_structure(headers)

            # Read ALL data at once (MUCH faster than cell-by-cell!)
            last_row = ws.UsedRange.Rows.Count
            if last_row < 2:
                wb.Close(False)
                continue

            data_range = ws.Range(ws.Cells(2, 1), ws.Cells(last_row, last_col))
            all_data = data_range.Value

            if all_data is None:
                wb.Close(False)
                continue

            # Handle single row case
            if not isinstance(all_data[0], tuple):
                all_data = [all_data]

            for row_data in all_data:
                if not row_data or not row_data[0]:
                    continue

                name = row_data[0]
                cnp = clean_cnp(row_data[1])

                # Document ID position is determined by header detection
                doc_id = normalize_string(row_data[doc_id_col]) if len(row_data) > doc_id_col else None

                # Get payment type and IBAN from detected positions
                if tip_plata_col is not None:
                    payment_type = normalize_string(row_data[tip_plata_col]) if len(row_data) > tip_plata_col else None
                else:
                    payment_type = None

                if iban_col is not None:
                    iban = normalize_string(row_data[iban_col]) if len(row_data) > iban_col else None
                else:
                    iban = None

                # Get financial values from detected positions
                gross_value = row_data[value_col] if len(row_data) > value_col else None
                env_tax = row_data[value_col + 1] if len(row_data) > value_col + 1 else None
                income_tax = row_data[value_col + 2] if len(row_data) > value_col + 2 else None
                net_paid = row_data[paid_col] if len(row_data) > paid_col else None

                # Skip if no valid document ID
                if not doc_id:
                    continue

                # Clean numeric values
                try:
                    gross_value = float(gross_value) if gross_value else 0
                    env_tax = float(env_tax) if env_tax else 0
                    income_tax = float(income_tax) if income_tax else 0
                    net_paid = float(net_paid) if net_paid else 0
                except:
                    continue

                if gross_value <= 0:
                    continue

                # Check if partner exists, if not add to missing
                if cnp and cnp not in partners_seen:
                    missing_partners.add((cnp, normalize_name(name)))

                # Add transaction
                transactions_batch.append((
                    doc_id, trans_date, cnp, payment_type, iban,
                    gross_value, env_tax, income_tax, net_paid
                ))
                total_transactions += 1

                # Process waste items
                for col_idx in range(waste_start, min(len(headers), len(row_data))):
                    header = headers[col_idx]
                    if not header or ('Deseu' not in header and 'Deseuri' not in header):
                        continue

                    weight = row_data[col_idx]
                    if not weight:
                        continue

                    try:
                        weight = float(weight)
                        if weight <= 0:
                            continue
                    except:
                        continue

                    # Get waste type info
                    cat_name, subtype_name = extract_category(header)
                    price = extract_price(header)

                    cat_id = categories_map.get(cat_name)
                    waste_type_id = waste_types_map.get((cat_id, subtype_name))

                    if waste_type_id:
                        item_value = weight * price if price else 0
                        items_batch.append((doc_id, waste_type_id, price, weight, item_value))
                        total_items += 1

                # Batch insert
                if len(transactions_batch) >= BATCH_SIZE:
                    try:
                        execute_values(cur, """
                            INSERT INTO transactions (document_id, date, cnp, payment_type, iban,
                                                     gross_value, env_tax, income_tax, net_paid)
                            VALUES %s
                            ON CONFLICT (document_id) DO NOTHING
                        """, transactions_batch)

                        execute_values(cur, """
                            INSERT INTO transaction_items (document_id, waste_type_id, price_per_kg, weight_kg, value)
                            VALUES %s
                        """, items_batch)

                        conn.commit()
                    except Exception as batch_err:
                        print(f"      Batch hiba: {batch_err}")
                        conn.rollback()
                    transactions_batch = []
                    items_batch = []

            wb.Close(False)

        except Exception as e:
            print(f"      EROARE: {filename}: {e}")
            try:
                conn.rollback()
            except:
                pass

# Insert remaining
if transactions_batch:
    try:
        execute_values(cur, """
            INSERT INTO transactions (document_id, date, cnp, payment_type, iban,
                                     gross_value, env_tax, income_tax, net_paid)
            VALUES %s
            ON CONFLICT (document_id) DO NOTHING
        """, transactions_batch)

        execute_values(cur, """
            INSERT INTO transaction_items (document_id, waste_type_id, price_per_kg, weight_kg, value)
            VALUES %s
        """, items_batch)

        conn.commit()
    except Exception as e:
        print(f"    Vegso batch hiba: {e}")
        conn.rollback()

# Insert missing partners (found in transactions but not in persoanefizice.xls)
if missing_partners:
    print(f"\n[7] Inserare {len(missing_partners)} parteneri noi (din tranzactii)...")
    for cnp, name in missing_partners:
        sex, birth_year, county_code = parse_cnp(cnp)
        county_from_cnp = COUNTY_CODES.get(county_code) if county_code else None
        try:
            cur.execute("""
                INSERT INTO partners (cnp, name, birth_year, sex, county_code_cnp, county_from_cnp)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (cnp) DO NOTHING
            """, (cnp, name, birth_year, sex, county_code, county_from_cnp))
        except:
            pass
    conn.commit()

excel.Quit()

# =============================================================================
# FINAL STATISTICS
# =============================================================================
print("\n" + "=" * 60)
print("STATISTICI FINALE")
print("=" * 60)

cur.execute("SELECT COUNT(*) FROM partners")
print(f"  Parteneri: {cur.fetchone()[0]:,}")

cur.execute("SELECT COUNT(*) FROM waste_categories")
print(f"  Categorii deseuri: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM waste_types")
print(f"  Subtipuri deseuri: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM transactions")
print(f"  Tranzactii: {cur.fetchone()[0]:,}")

cur.execute("SELECT COUNT(*) FROM transaction_items")
print(f"  Itemuri tranzactie: {cur.fetchone()[0]:,}")

cur.execute("SELECT MIN(date), MAX(date) FROM transactions")
date_range = cur.fetchone()
print(f"  Perioada: {date_range[0]} - {date_range[1]}")

cur.execute("SELECT SUM(gross_value) FROM transactions")
total = cur.fetchone()[0]
print(f"  Valoare totala: {total:,.2f} RON")

print("\n--- Top 5 categorii (dupa greutate) ---")
cur.execute("""
    SELECT wc.name, SUM(ti.weight_kg) as total_kg
    FROM transaction_items ti
    JOIN waste_types wt ON ti.waste_type_id = wt.id
    JOIN waste_categories wc ON wt.category_id = wc.id
    GROUP BY wc.name
    ORDER BY total_kg DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,.0f} kg")

print("\n--- Top 5 judete (dupa parteneri) ---")
cur.execute("""
    SELECT county, COUNT(*) as cnt
    FROM partners
    WHERE county IS NOT NULL
    GROUP BY county
    ORDER BY cnt DESC
    LIMIT 5
""")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]:,} parteneri")

cur.close()
conn.close()

print("\n" + "=" * 60)
print("IMPORT COMPLET!")
print("=" * 60)
