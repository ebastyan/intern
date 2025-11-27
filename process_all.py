import win32com.client
import os
import json
from collections import defaultdict
from datetime import date

excel = win32com.client.Dispatch('Excel.Application')
excel.Visible = False
excel.DisplayAlerts = False

base_path = r'C:\Users\INTEL\Desktop\paju'

# Month folders mapping
months_2024 = [
    ('01_Ianuarie', '2024-01'), ('02_Februarie', '2024-02'), ('03_Martie', '2024-03'),
    ('04_Aprilie', '2024-04'), ('05_Mai', '2024-05'), ('06_Iunie', '2024-06'),
    ('07_Iulie', '2024-07'), ('08_August', '2024-08'), ('09_Septembrie', '2024-09'),
    ('10_Octombrie', '2024-10'), ('11_Noiembrie', '2024-11'), ('12_Decembrie', '2024-12')
]

months_2025 = [
    ('01_ianuarie', '2025-01'), ('02_februarie', '2025-02'), ('03_martie', '2025-03'),
    ('04_aprilie', '2025-04'), ('05_mai', '2025-05'), ('06_iunie', '2025-06'),
    ('07_iulie', '2025-07'), ('08_august', '2025-08'), ('09_septembrie', '2025-09'),
    ('10_octombrie', '2025-10'), ('11_noiembrie', '2025-11')
]

day_names_ro = ['Luni', 'Marti', 'Miercuri', 'Joi', 'Vineri', 'Sambata', 'Duminica']
day_names_short = ['L', 'Ma', 'Mi', 'J', 'V', 'S', 'D']

def categorize(header):
    h = header.lower()
    if 'acumulator' in h:
        return 'Akkumulator'
    elif 'fier' in h:
        return 'Vas (Fier)'
    elif 'cupru' in h and 'cablu' not in h and 'junkers' not in h and 'radiator' not in h:
        return 'Rez (Cupru)'
    elif 'cupru' in h and 'junkers' in h:
        return 'Rez Junkers'
    elif 'cablu' in h and 'cupru' in h:
        return 'Kabel Rez'
    elif 'cablu' in h and 'aluminiu' in h:
        return 'Kabel Alu'
    elif 'aluminiu' in h and 'radiator' in h and 'cupru' in h:
        return 'Alu-Rez Radiator'
    elif 'aluminiu' in h and 'radiator' in h:
        return 'Alu Radiator'
    elif 'aluminiu' in h and 'jenti' in h:
        return 'Alu Felni'
    elif 'aluminiu' in h and 'premium' in h:
        return 'Alu Premium'
    elif 'aluminiu' in h and 'span' in h:
        return 'Alu Forgacs'
    elif 'aluminiu' in h and 'doze' in h:
        return 'Alu Doboz'
    elif 'aluminiu' in h:
        return 'Aluminiu'
    elif 'alama' in h and 'radiator' in h:
        return 'Sargarez Radiator'
    elif 'alama' in h and 'span' in h:
        return 'Sargarez Forgacs'
    elif 'alama' in h:
        return 'Sargarez (Alama)'
    elif 'inox' in h:
        return 'Inox'
    elif 'plumb' in h:
        return 'Olom (Plumb)'
    elif 'zinc' in h:
        return 'Cink'
    elif 'zamac' in h:
        return 'Zamak'
    elif 'carton' in h or 'hartie' in h:
        return 'Karton/Papir'
    elif 'pet' in h or 'plastic' in h or 'folie' in h:
        return 'Muanyag'
    elif 'sticla' in h:
        return 'Uveg'
    elif 'deee' in h or 'placi' in h:
        return 'Elektronika (DEEE)'
    elif 'neferos' in h:
        return 'Neferos Mix'
    elif 'motor' in h:
        return 'Motor'
    elif 'caroserie' in h or 'tabla' in h:
        return 'Tabla/Karosszeria'
    elif 'capace' in h:
        return 'Capace'
    else:
        return 'Egyeb'

def detect_structure(headers):
    """
    Detect file structure based on headers.
    OLD format (before Sept 2024): Nume, CNP, Nr.APP, Valoare, Fond mediu, Impozit, Achitat, ...waste columns
    NEW format (from Sept 2024): Nume, CNP, Nr.APP, Tip plata, Cont IBAN, Valoare, Fond mediu, Impozit, Achitat, ...waste columns
    """
    for i, h in enumerate(headers):
        if h and 'tip plata' in h.lower():
            return 'new', 5, 8, 9  # value_col=5 (0-indexed), paid_col=8, waste_start=9
        if h and 'valoare' in h.lower():
            if i == 3:  # Old format: Valoare at index 3
                return 'old', 3, 6, 7  # value_col=3, paid_col=6, waste_start=7
            elif i == 5:  # New format: Valoare at index 5
                return 'new', 5, 8, 9
    return 'old', 3, 6, 7  # Default to old format

def process_month(year_folder, month_folder, period_key):
    """Process a single month and return the data"""
    folder_path = os.path.join(base_path, year_folder, month_folder)

    if not os.path.exists(folder_path):
        print(f"  [!] Mappa nem letezik: {folder_path}")
        return None

    files = [f for f in os.listdir(folder_path) if f.endswith('.xls')]
    files.sort()

    if not files:
        print(f"  [!] Nincs XLS file: {folder_path}")
        return None

    print(f"  Feldolgozas: {len(files)} nap...")

    daily_detailed = {}
    all_waste_totals = defaultdict(float)
    month_total_value = 0
    month_total_trans = 0
    month_total_paid = 0
    partners = set()

    for filename in files:
        date_str = filename.replace('.xls', '')
        try:
            day, month, year = date_str.split('.')
            date_obj = date(int(year), int(month), int(day))
            weekday = date_obj.weekday()
            date_key = f'{year}-{month}-{day}'
        except:
            print(f"    [!] Rossz fajlnev: {filename}")
            continue

        file_path = os.path.abspath(os.path.join(folder_path, filename))

        try:
            wb = excel.Workbooks.Open(file_path)
            ws = wb.Sheets(1)

            headers = []
            col = 1
            while col < 250:
                val = ws.Cells(1, col).Value
                if val:
                    headers.append(str(val))
                else:
                    if col > 10:
                        break
                col += 1

            # Detect structure and get column indices
            structure, value_col, paid_col, waste_start = detect_structure(headers)

            last_row = ws.UsedRange.Rows.Count
            last_col = len(headers)
            if last_col > 200:
                last_col = 200

            data_range = ws.Range(ws.Cells(2, 1), ws.Cells(last_row, last_col))
            data = data_range.Value

            if data is None:
                wb.Close(False)
                continue

            if not isinstance(data[0], tuple):
                data = [data]

            day_waste_cat = defaultdict(float)
            day_waste_detailed = defaultdict(float)
            day_total = 0
            day_paid = 0
            day_trans = 0

            for row_data in data:
                if not row_data[0]:
                    continue

                # Partner name
                name = str(row_data[0]).strip() if row_data[0] else ''
                if name:
                    partners.add(name)

                # Get value and paid based on structure
                try:
                    value = float(row_data[value_col]) if row_data[value_col] and str(row_data[value_col]).replace('.','').replace('-','').isdigit() == False else 0
                    # More robust conversion
                    val_raw = row_data[value_col]
                    if val_raw is not None:
                        if isinstance(val_raw, (int, float)):
                            value = float(val_raw)
                        else:
                            try:
                                value = float(str(val_raw).replace(',', '.'))
                            except:
                                value = 0
                    else:
                        value = 0

                    paid_raw = row_data[paid_col] if paid_col < len(row_data) else value
                    if paid_raw is not None:
                        if isinstance(paid_raw, (int, float)):
                            paid = float(paid_raw)
                        else:
                            try:
                                paid = float(str(paid_raw).replace(',', '.'))
                            except:
                                paid = value
                    else:
                        paid = value
                except Exception as e:
                    continue

                day_total += value
                day_paid += paid
                day_trans += 1

                # Process waste columns
                for i, header in enumerate(headers[waste_start:], start=waste_start):
                    if i < len(row_data) and row_data[i]:
                        try:
                            kg_raw = row_data[i]
                            if isinstance(kg_raw, (int, float)):
                                kg = float(kg_raw)
                            else:
                                kg = float(str(kg_raw).replace(',', '.'))
                            if kg > 0:
                                cat = categorize(header)
                                day_waste_cat[cat] += kg
                                day_waste_detailed[header] += kg
                                all_waste_totals[cat] += kg
                        except:
                            pass

            month_total_value += day_total
            month_total_trans += day_trans
            month_total_paid += day_paid

            sorted_cat = sorted(day_waste_cat.items(), key=lambda x: -x[1])[:5]
            sorted_detailed = sorted(day_waste_detailed.items(), key=lambda x: -x[1])[:3]

            daily_detailed[date_key] = {
                'day': int(day),
                'weekday': weekday,
                'weekday_name': day_names_ro[weekday],
                'weekday_short': day_names_short[weekday],
                'total_value': round(day_total, 2),
                'total_paid': round(day_paid, 2),
                'transactions': day_trans,
                'avg_per_trans': round(day_total / day_trans, 2) if day_trans > 0 else 0,
                'top3_detailed': [{'name': n.replace('Deseu ', '').replace('Deseuri ', ''), 'kg': round(k, 1)} for n, k in sorted_detailed],
                'top5_categories': [{'cat': c, 'kg': round(k, 1)} for c, k in sorted_cat],
                'all_categories': {k: round(v, 1) for k, v in day_waste_cat.items()}
            }

            wb.Close(False)

        except Exception as e:
            print(f"    [!] HIBA {filename}: {e}")

    # Weekly patterns
    weekday_stats = defaultdict(lambda: {'total_value': 0, 'transactions': 0, 'days': 0, 'categories': defaultdict(float)})

    for date_key, d in daily_detailed.items():
        wd = d['weekday']
        weekday_stats[wd]['total_value'] += d['total_value']
        weekday_stats[wd]['transactions'] += d['transactions']
        weekday_stats[wd]['days'] += 1
        for cat, kg in d['all_categories'].items():
            weekday_stats[wd]['categories'][cat] += kg

    weekday_patterns = {}
    for wd in range(7):
        if weekday_stats[wd]['days'] > 0:
            top_cats = sorted(weekday_stats[wd]['categories'].items(), key=lambda x: -x[1])[:3]
            weekday_patterns[day_names_ro[wd]] = {
                'days_count': weekday_stats[wd]['days'],
                'avg_value': round(weekday_stats[wd]['total_value'] / weekday_stats[wd]['days'], 0),
                'avg_transactions': round(weekday_stats[wd]['transactions'] / weekday_stats[wd]['days'], 0),
                'top3_categories': [{'cat': c, 'avg_kg': round(k / weekday_stats[wd]['days'], 0)} for c, k in top_cats]
            }

    # Best/worst days
    if daily_detailed:
        best_day = max(daily_detailed.items(), key=lambda x: x[1]['total_value'])
        worst_day = min(daily_detailed.items(), key=lambda x: x[1]['total_value'])
    else:
        best_day = worst_day = (None, {'total_value': 0})

    return {
        'period': period_key,
        'summary': {
            'total_value': round(month_total_value, 0),
            'total_paid': round(month_total_paid, 0),
            'transactions': month_total_trans,
            'working_days': len(daily_detailed),
            'unique_partners': len(partners),
            'avg_per_day': round(month_total_value / len(daily_detailed), 0) if daily_detailed else 0,
            'avg_per_trans': round(month_total_value / month_total_trans, 0) if month_total_trans else 0,
            'best_day': {'date': best_day[0], 'value': round(best_day[1]['total_value'], 0)} if best_day[0] else None,
            'worst_day': {'date': worst_day[0], 'value': round(worst_day[1]['total_value'], 0)} if worst_day[0] else None
        },
        'total_by_category': {k: round(v, 0) for k, v in sorted(all_waste_totals.items(), key=lambda x: -x[1])},
        'weekday_patterns': weekday_patterns,
        'daily': dict(sorted(daily_detailed.items()))
    }

# Process all months
all_data = {
    'generated': str(date.today()),
    'years': {}
}

# 2024
print("=" * 50)
print("2024 FELDOLGOZASA")
print("=" * 50)

all_data['years']['2024'] = {'months': {}}

for folder, period in months_2024:
    print(f"\n[{period}] {folder}")
    month_data = process_month('2024', folder, period)
    if month_data:
        month_num = period.split('-')[1]
        all_data['years']['2024']['months'][month_num] = month_data
        print(f"  OK: {month_data['summary']['total_value']:,.0f} RON, {month_data['summary']['transactions']} tranz")

# 2025
print("\n" + "=" * 50)
print("2025 FELDOLGOZASA")
print("=" * 50)

all_data['years']['2025'] = {'months': {}}

for folder, period in months_2025:
    print(f"\n[{period}] {folder}")
    month_data = process_month('2025', folder, period)
    if month_data:
        month_num = period.split('-')[1]
        all_data['years']['2025']['months'][month_num] = month_data
        print(f"  OK: {month_data['summary']['total_value']:,.0f} RON, {month_data['summary']['transactions']} tranz")

excel.Quit()

# Calculate yearly summaries
for year in ['2024', '2025']:
    year_total = 0
    year_trans = 0
    year_days = 0
    year_categories = defaultdict(float)

    for month_num, month_data in all_data['years'][year]['months'].items():
        year_total += month_data['summary']['total_value']
        year_trans += month_data['summary']['transactions']
        year_days += month_data['summary']['working_days']
        for cat, kg in month_data['total_by_category'].items():
            year_categories[cat] += kg

    all_data['years'][year]['summary'] = {
        'total_value': round(year_total, 0),
        'transactions': year_trans,
        'working_days': year_days,
        'avg_per_day': round(year_total / year_days, 0) if year_days else 0,
        'avg_per_month': round(year_total / len(all_data['years'][year]['months']), 0) if all_data['years'][year]['months'] else 0
    }
    all_data['years'][year]['total_by_category'] = {k: round(v, 0) for k, v in sorted(year_categories.items(), key=lambda x: -x[1])}

# Save combined data
with open(os.path.join(base_path, 'all_data.json'), 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)

# Print summary
print("\n" + "=" * 60)
print("OSSZESITES")
print("=" * 60)

for year in ['2024', '2025']:
    s = all_data['years'][year]['summary']
    months_count = len(all_data['years'][year]['months'])
    print(f"\n{year}: {months_count} honap feldolgozva")
    print(f"  Osszes ertek:  {s['total_value']:>15,.0f} RON")
    print(f"  Tranzakciok:   {s['transactions']:>15,}")
    print(f"  Munkanapok:    {s['working_days']:>15}")
    print(f"  Atlag/nap:     {s['avg_per_day']:>15,.0f} RON")
    print(f"  Atlag/honap:   {s['avg_per_month']:>15,.0f} RON")

    print(f"\n  Top 5 kategoria:")
    for i, (cat, kg) in enumerate(list(all_data['years'][year]['total_by_category'].items())[:5], 1):
        print(f"    {i}. {cat:20} {kg:>12,.0f} kg")

print(f"\n\nMentve: {os.path.join(base_path, 'all_data.json')}")
print(f"JSON meret: {os.path.getsize(os.path.join(base_path, 'all_data.json')) / 1024:.1f} KB")
