"""Import .xls transaction files into the PAJU DB.

File structure expected:
  Row = one transaction (one partner, one day)
  First 9 columns: Nume, CNP, Nr. APP (doc id), Tip plata, IBAN,
                   Valoare (gross), Fond mediu (env tax), Impozit, Achitat (net)
  Columns 10+ = waste types like "Deseu Fier (0.80)" where (X) = price per kg

Usage:
  python scripts/import_xls.py 2020               # all months in folder
  python scripts/import_xls.py 2020/01_ianuarie   # one month
  python scripts/import_xls.py --file 2020/01_ianuarie/07.01.2020.xls
  python scripts/import_xls.py --dry-run 2026     # parse but don't write DB
"""
import argparse
import os
import re
import sys
import traceback
from datetime import date
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

# ==== Romanian county code → name (positions 8-9 of CNP) ====
COUNTY_BY_CODE = {
    "01": "Alba", "02": "Arad", "03": "Arges", "04": "Bacau", "05": "Bihor",
    "06": "Bistrita-Nasaud", "07": "Botosani", "08": "Brasov", "09": "Braila",
    "10": "Buzau", "11": "Caras-Severin", "12": "Cluj", "13": "Constanta",
    "14": "Covasna", "15": "Dambovita", "16": "Dolj", "17": "Galati",
    "18": "Gorj", "19": "Harghita", "20": "Hunedoara", "21": "Ialomita",
    "22": "Iasi", "23": "Ilfov", "24": "Maramures", "25": "Mehedinti",
    "26": "Mures", "27": "Neamt", "28": "Olt", "29": "Prahova",
    "30": "Satu Mare", "31": "Salaj", "32": "Sibiu", "33": "Suceava",
    "34": "Teleorman", "35": "Timis", "36": "Tulcea", "37": "Vaslui",
    "38": "Valcea", "39": "Vrancea", "40": "Bucuresti",
    "41": "Bucuresti S1", "42": "Bucuresti S2", "43": "Bucuresti S3",
    "44": "Bucuresti S4", "45": "Bucuresti S5", "46": "Bucuresti S6",
    "51": "Calarasi", "52": "Giurgiu",
}


def load_env_local():
    env = Path(__file__).parent.parent / ".env.local"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip().strip('"').strip("'"))


def parse_cnp(cnp_raw):
    """Parse a Romanian CNP (13 digits). Returns (cnp_str, birth_year, sex,
    county_code, county_name). Returns (None, ...) if invalid."""
    if cnp_raw is None:
        return None, None, None, None, None
    try:
        if isinstance(cnp_raw, float):
            if pd.isna(cnp_raw):
                return None, None, None, None, None
            cnp = str(int(cnp_raw))
        else:
            cnp = str(cnp_raw).strip()
    except (ValueError, OverflowError):
        return None, None, None, None, None
    cnp = cnp.lstrip("'").strip()
    if not cnp.isdigit() or len(cnp) != 13:
        return None, None, None, None, None

    s = int(cnp[0])
    yy = int(cnp[1:3])
    mm = int(cnp[3:5])
    dd = int(cnp[5:7])
    county_code = cnp[7:9]

    # Century + sex
    if s in (1, 2):
        century = 1900
    elif s in (3, 4):
        century = 1800
    elif s in (5, 6):
        century = 2000
    elif s in (7, 8):
        # Foreign resident
        century = 1900
    else:
        return cnp, None, None, county_code, COUNTY_BY_CODE.get(county_code)
    birth_year = century + yy
    sex = "M" if s in (1, 3, 5, 7) else "F"

    # Basic date sanity check
    if not (1 <= mm <= 12 and 1 <= dd <= 31 and 1900 <= birth_year <= 2030):
        birth_year = None

    return cnp, birth_year, sex, county_code, COUNTY_BY_CODE.get(county_code)


FILENAME_RE = re.compile(r"^(\d{2})\.?(\d{2})\.?(\d{4})\.xls$", re.IGNORECASE)


def parse_date_from_filename(filename, folder_year=None, folder_month=None):
    """E.g. '07.01.2020.xls' -> date(2020, 1, 7). Handles weird variants like
    '29.0102020.xls' (missing dot) by falling back to folder context."""
    m = FILENAME_RE.match(filename)
    if m:
        dd, mm, yy = m.group(1), m.group(2), m.group(3)
        try:
            d = date(int(yy), int(mm), int(dd))
            # Sanity: if the parsed year disagrees with folder_year by more
            # than 1, something is wrong — prefer folder hint.
            if folder_year and abs(d.year - folder_year) > 1:
                raise ValueError("year mismatch with folder")
            return d
        except ValueError:
            pass
    # Fallback using folder hint: extract DD from the start of filename
    stem = Path(filename).stem.replace(".", "")
    if folder_year and folder_month and len(stem) >= 2 and stem[:2].isdigit():
        try:
            return date(int(folder_year), int(folder_month), int(stem[:2]))
        except ValueError:
            pass
    # Old-fallback: DDMMYYYY interpretation
    if len(stem) == 8 and stem.isdigit():
        try:
            return date(int(stem[4:8]), int(stem[2:4]), int(stem[0:2]))
        except ValueError:
            pass
    return None


def _folder_hints(filepath):
    """Extract (year, month) from folder names like .../2020/01_ianuarie/."""
    year = month = None
    for part in filepath.parts:
        if re.fullmatch(r"\d{4}", part):
            try: year = int(part)
            except ValueError: pass
        m = re.match(r"^(\d{2})_", part)
        if m:
            try: month = int(m.group(1))
            except ValueError: pass
    return year, month


WASTE_COL_RE = re.compile(r"^(.+?)\s*\(([\d,.]+)\)\s*$")


def parse_waste_column(col):
    """'Deseu Fier (0.80)' -> ('Deseu Fier', 0.80). None if not a waste col."""
    if not isinstance(col, str):
        return None
    m = WASTE_COL_RE.match(col)
    if not m:
        return None
    name = m.group(1).strip()
    price_str = m.group(2).replace(",", ".")
    try:
        price = float(price_str)
    except ValueError:
        return None
    return name, price


def load_reference_data(cur):
    """Return maps for waste_types and waste_categories."""
    cur.execute("SELECT id, name FROM waste_types")
    waste_types = {r["name"]: r["id"] for r in cur.fetchall()}
    cur.execute("SELECT id, name FROM waste_categories")
    categories = {r["name"]: r["id"] for r in cur.fetchall()}
    return waste_types, categories


def guess_category_for_waste(waste_name, categories):
    """Guess category id from waste type name. Falls back to 'Neferos Mix'."""
    wl = waste_name.lower()
    for key, cat in (
        ("acumulat", "Acumulatori"),
        ("alama", "Alama"),
        ("aluminiu radiator cu cupru", "Aluminiu"),
        ("aluminiu", "Aluminiu"),
        ("cablu aluminiu", "Cablu Aluminiu"),
        ("cablu cupru", "Cablu Cupru"),
        ("cupru junkers", "Cupru"),
        ("cupru", "Cupru"),
        ("doze aluminiu", "Aluminiu"),
        ("fier", "Fier"),
        ("ambalaj metalic", "Fier"),
        ("carton", "Carton"),
        ("pet", "Plastic"),
        ("plastic", "Plastic"),
        ("folie", "Plastic"),
        ("ambalaj plastic", "Plastic"),
        ("sticla", "Sticla"),
        ("inox", "Inox"),
        ("plumb", "Plumb"),
        ("zamac", "Zamac"),
        ("zinc", "Zinc"),
        ("neferos", "Neferos Mix"),
        ("deee", "DEEE"),
    ):
        if key in wl:
            return categories.get(cat, categories.get("Neferos Mix"))
    return categories.get("Neferos Mix")


def ensure_waste_type(cur, name, waste_types, categories):
    """Return waste_type_id, creating it if missing."""
    if name in waste_types:
        return waste_types[name]
    cat_id = guess_category_for_waste(name, categories)
    cur.execute(
        "INSERT INTO waste_types (name, category_id) VALUES (%s, %s) RETURNING id",
        (name, cat_id),
    )
    new_id = cur.fetchone()["id"]
    waste_types[name] = new_id
    return new_id


def num(val):
    """Safe numeric conversion returning None for NaN/invalid."""
    if val is None:
        return None
    try:
        if isinstance(val, float) and pd.isna(val):
            return None
        f = float(val)
        return f
    except (ValueError, TypeError):
        return None


def _try_excel_com_convert(filepath):
    """Last-resort fallback for corrupted .xls files: open in real Excel via
    COM automation and save as .xlsx. Returns the new path, or None on failure."""
    try:
        import pythoncom
        from win32com.client import Dispatch
    except Exception:
        return None
    tmp_path = filepath.with_suffix(".converted.xlsx")
    try:
        pythoncom.CoInitialize()
        excel = Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = excel.Workbooks.Open(str(filepath.resolve()))
        wb.SaveAs(str(tmp_path.resolve()), FileFormat=51)  # xlOpenXMLWorkbook
        wb.Close(SaveChanges=False)
        excel.Quit()
        return tmp_path
    except Exception:
        try:
            excel.Quit()
        except Exception:
            pass
        return None


def parse_file(filepath, waste_types, categories, existing_docs, use_com=False):
    """Parse one .xls file. If use_com=True, falls back to Excel COM for
    corrupted files (can hang — use only for opt-in second pass)."""
    filename = filepath.name
    fy, fm = _folder_hints(filepath)
    tx_date = parse_date_from_filename(filename, folder_year=fy, folder_month=fm)
    if tx_date is None:
        raise ValueError(f"Cannot parse date from filename: {filename}")

    df = None
    last_err = None
    try:
        df = pd.read_excel(filepath, engine="xlrd")
    except Exception as e:
        last_err = e
        if use_com:
            converted = _try_excel_com_convert(filepath)
            if converted is not None:
                try:
                    df = pd.read_excel(converted, engine="openpyxl")
                except Exception as e2:
                    last_err = e2
                finally:
                    try:
                        converted.unlink()
                    except Exception:
                        pass
    if df is None:
        raise RuntimeError(f"Failed to read {filepath}: {last_err}")

    if df.empty:
        return [], [], []

    required = {"Nume", "CNP", "Nr. APP"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{filepath}: missing columns {missing}")

    # Identify waste columns (all columns past the first 9 that match the pattern)
    waste_cols = []
    for col in df.columns[9:]:
        parsed = parse_waste_column(col)
        if parsed:
            waste_cols.append((col, parsed[0], parsed[1]))

    partners_up = {}  # cnp -> (name, birth_year, sex, county_code, county_from_cnp)
    txs = []
    items = []

    for _, row in df.iterrows():
        doc_id = row.get("Nr. APP")
        if doc_id is None or (isinstance(doc_id, float) and pd.isna(doc_id)):
            continue
        doc_id = str(doc_id).strip()
        if not doc_id or doc_id in existing_docs:
            continue

        name = row.get("Nume")
        if name is not None and not (isinstance(name, float) and pd.isna(name)):
            name = str(name).strip()
        else:
            name = None

        cnp_raw = row.get("CNP")
        cnp, by, sx, cc, cn = parse_cnp(cnp_raw)
        if cnp is None:
            # Skip rows without a valid CNP (can't attach to a partner)
            continue

        # Track the partner (last seen wins)
        partners_up[cnp] = (name, by, sx, cc, cn)

        payment_type = row.get("Tip plata")
        if isinstance(payment_type, float) and pd.isna(payment_type):
            payment_type = None
        elif payment_type is not None:
            payment_type = str(payment_type).strip()

        iban = row.get("Cont IBAN (plata OP)")
        if isinstance(iban, float) and pd.isna(iban):
            iban = None
        elif iban is not None:
            iban = str(iban).strip()

        gross = num(row.get("Valoare"))
        env_tax = num(row.get("Fond mediu"))
        income_tax = num(row.get("Impozit"))
        net_paid = num(row.get("Achitat"))

        txs.append({
            "document_id": doc_id,
            "date": tx_date,
            "cnp": cnp,
            "payment_type": payment_type,
            "iban": iban,
            "gross_value": gross,
            "env_tax": env_tax,
            "income_tax": income_tax,
            "net_paid": net_paid,
        })
        existing_docs.add(doc_id)

        # Items
        for col, wname, price in waste_cols:
            w = row[col]
            weight = num(w)
            if weight is None or weight == 0:
                continue
            value = round(weight * price, 2)
            items.append({
                "document_id": doc_id,
                "waste_name": wname,
                "price_per_kg": price,
                "weight_kg": weight,
                "value": value,
            })

    return partners_up, txs, items


def upsert_partners(cur, partners_up):
    if not partners_up:
        return 0
    rows = [(cnp, v[0], v[1], v[2], v[3], v[4]) for cnp, v in partners_up.items()]
    execute_values(
        cur,
        """
        INSERT INTO partners (cnp, name, birth_year, sex, county_code_cnp, county_from_cnp)
        VALUES %s
        ON CONFLICT (cnp) DO UPDATE
          SET name = COALESCE(EXCLUDED.name, partners.name),
              birth_year = COALESCE(EXCLUDED.birth_year, partners.birth_year),
              sex = COALESCE(EXCLUDED.sex, partners.sex),
              county_code_cnp = COALESCE(EXCLUDED.county_code_cnp, partners.county_code_cnp),
              county_from_cnp = COALESCE(EXCLUDED.county_from_cnp, partners.county_from_cnp),
              modified_at = now()
        """,
        rows,
        page_size=500,
    )
    return len(rows)


def insert_transactions(cur, txs):
    if not txs:
        return 0
    rows = [(t["document_id"], t["date"], t["cnp"], t["payment_type"], t["iban"],
             t["gross_value"], t["env_tax"], t["income_tax"], t["net_paid"]) for t in txs]
    execute_values(
        cur,
        """
        INSERT INTO transactions
            (document_id, date, cnp, payment_type, iban, gross_value, env_tax, income_tax, net_paid)
        VALUES %s
        ON CONFLICT (document_id) DO NOTHING
        """,
        rows,
        page_size=500,
    )
    return len(rows)


def insert_items(cur, items, waste_types, categories):
    if not items:
        return 0
    rows = []
    for it in items:
        wid = ensure_waste_type(cur, it["waste_name"], waste_types, categories)
        rows.append((it["document_id"], wid, it["price_per_kg"], it["weight_kg"], it["value"]))
    execute_values(
        cur,
        """
        INSERT INTO transaction_items (document_id, waste_type_id, price_per_kg, weight_kg, value)
        VALUES %s
        """,
        rows,
        page_size=1000,
    )
    return len(rows)


def load_existing_docs(cur):
    cur.execute("SELECT document_id FROM transactions")
    return {r["document_id"] for r in cur.fetchall()}


def iter_xls_files(target):
    """Yield .xls files for a folder, month-folder, or single file path."""
    p = Path(target)
    if p.is_file() and p.suffix.lower() == ".xls":
        yield p
        return
    if not p.is_dir():
        return
    # If it contains month-subfolders, recurse
    month_dirs = sorted([x for x in p.iterdir() if x.is_dir() and re.match(r"^\d{2}_", x.name)])
    if month_dirs:
        for md in month_dirs:
            for f in sorted(md.glob("*.xls")):
                yield f
    else:
        for f in sorted(p.glob("*.xls")):
            yield f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="Year folder (e.g. 2020), month folder, or single .xls file")
    ap.add_argument("--dry-run", action="store_true", help="Parse, don't write DB")
    ap.add_argument("--commit-every", type=int, default=1,
                    help="Commit every N files (default 1 = per-file)")
    ap.add_argument("--use-com", action="store_true",
                    help="Try Excel COM fallback for corrupted .xls (can hang — opt-in for second pass)")
    args = ap.parse_args()

    load_env_local()
    url = os.environ.get("POSTGRES_URL")
    if not url:
        print("POSTGRES_URL not set"); sys.exit(1)

    conn = psycopg2.connect(url, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    waste_types, categories = load_reference_data(cur)
    existing_docs = load_existing_docs(cur)
    print(f"Loaded {len(waste_types)} waste types, {len(categories)} categories, "
          f"{len(existing_docs)} existing document_ids")

    total_files = 0
    total_partners = 0
    total_txs = 0
    total_items = 0
    corrupted = []

    pending_commit = 0
    for f in iter_xls_files(args.target):
        total_files += 1
        try:
            rel = str(f.relative_to(Path.cwd()))
        except ValueError:
            rel = str(f)
        try:
            partners_up, txs, items = parse_file(f, waste_types, categories, existing_docs, use_com=args.use_com)
        except Exception as e:
            corrupted.append((rel, str(e)))
            print(f"  [ERROR] {rel}: {e}")
            continue

        if args.dry_run:
            print(f"  [DRY] {rel}: {len(partners_up)} partners, {len(txs)} txs, {len(items)} items")
            total_partners += len(partners_up)
            total_txs += len(txs)
            total_items += len(items)
            continue

        try:
            n_p = upsert_partners(cur, partners_up)
            n_t = insert_transactions(cur, txs)
            n_i = insert_items(cur, items, waste_types, categories)
            total_partners += n_p
            total_txs += n_t
            total_items += n_i
            pending_commit += 1
            if pending_commit >= args.commit_every:
                conn.commit()
                pending_commit = 0
            print(f"  OK {rel}: {n_p} p, {n_t} tx, {n_i} it")
        except Exception as e:
            conn.rollback()
            corrupted.append((rel, str(e)))
            print(f"  [DB ERROR] {rel}: {e}")
            traceback.print_exc(limit=3)

    if pending_commit > 0 and not args.dry_run:
        conn.commit()

    print()
    print("==== SUMMARY ====")
    print(f"Files processed: {total_files}")
    print(f"Partners upserted: {total_partners}")
    print(f"Transactions inserted: {total_txs}")
    print(f"Items inserted: {total_items}")
    print(f"Errors: {len(corrupted)}")
    if corrupted:
        print("Error details:")
        for rel, err in corrupted:
            print(f"  - {rel}: {err[:120]}")
    conn.close()


if __name__ == "__main__":
    main()
