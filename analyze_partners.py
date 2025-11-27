import win32com.client
import os
import json
from collections import defaultdict
from datetime import date, datetime
import re

excel = win32com.client.Dispatch('Excel.Application')
excel.Visible = False
excel.DisplayAlerts = False

base_path = r'C:\Users\INTEL\Desktop\paju'

# CNP county codes (Romania)
county_codes = {
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

def parse_cnp(cnp_str):
    """Extract info from CNP"""
    if not cnp_str:
        return None
    cnp = str(int(float(cnp_str))) if isinstance(cnp_str, float) else str(cnp_str)
    cnp = cnp.replace('.0', '').strip()

    if len(cnp) != 13:
        return None

    try:
        sex_code = cnp[0]
        year_suffix = cnp[1:3]
        month = cnp[3:5]
        day = cnp[5:7]
        county = cnp[7:9]

        # Determine birth year
        if sex_code in ['1', '2']:
            year = 1900 + int(year_suffix)
        elif sex_code in ['3', '4']:
            year = 1800 + int(year_suffix)
        elif sex_code in ['5', '6']:
            year = 2000 + int(year_suffix)
        elif sex_code in ['7', '8']:  # Foreign residents
            year = 1900 + int(year_suffix)  # Approximation
        else:
            year = 1900 + int(year_suffix)

        return {
            'sex': 'M' if sex_code in ['1', '3', '5', '7'] else 'F',
            'birth_year': year,
            'birth_month': int(month),
            'county_code': county,
            'county_name': county_codes.get(county, 'Ismeretlen')
        }
    except:
        return None

def detect_structure(headers):
    """Detect file structure"""
    for i, h in enumerate(headers):
        if h and 'tip plata' in h.lower():
            return 'new', 5, 8, 9
        if h and 'valoare' in h.lower():
            if i == 3:
                return 'old', 3, 6, 7
            elif i == 5:
                return 'new', 5, 8, 9
    return 'old', 3, 6, 7

def categorize(header):
    h = header.lower()
    if 'acumulator' in h:
        return 'Akkumulator'
    elif 'fier' in h:
        return 'Vas'
    elif 'cupru' in h and 'cablu' not in h:
        return 'Rez'
    elif 'cablu' in h:
        return 'Kabel'
    elif 'aluminiu' in h:
        return 'Aluminiu'
    elif 'alama' in h:
        return 'Sargarez'
    elif 'inox' in h:
        return 'Inox'
    elif 'plumb' in h:
        return 'Olom'
    elif 'carton' in h or 'hartie' in h:
        return 'Karton'
    elif 'deee' in h or 'placi' in h:
        return 'DEEE'
    elif 'sticla' in h:
        return 'Uveg'
    else:
        return 'Egyeb'

# Process all files and collect partner data
partners = defaultdict(lambda: {
    'name': '',
    'cnp': '',
    'cnp_info': None,
    'first_visit': None,
    'last_visit': None,
    'total_visits': 0,
    'total_value': 0,
    'total_paid': 0,
    'visits_by_month': defaultdict(int),
    'value_by_month': defaultdict(float),
    'categories': defaultdict(float),
    'all_visits': []
})

# Month folders
all_months = []
for year in ['2024', '2025']:
    year_path = os.path.join(base_path, year)
    if os.path.exists(year_path):
        for folder in sorted(os.listdir(year_path)):
            folder_path = os.path.join(year_path, folder)
            if os.path.isdir(folder_path):
                all_months.append((year, folder, folder_path))

print(f"Feldolgozando: {len(all_months)} honap")

total_transactions = 0
daily_stats = defaultdict(lambda: {'value': 0, 'trans': 0, 'categories': defaultdict(float)})
monthly_category_trends = defaultdict(lambda: defaultdict(float))

for year, folder, folder_path in all_months:
    files = [f for f in os.listdir(folder_path) if f.endswith('.xls')]
    print(f"  {year}/{folder}: {len(files)} nap...")

    for filename in files:
        date_str = filename.replace('.xls', '')
        try:
            day, month, y = date_str.split('.')
            date_key = f'{y}-{month}-{day}'
            month_key = f'{y}-{month}'
        except:
            continue

        file_path = os.path.abspath(os.path.join(folder_path, filename))

        try:
            wb = excel.Workbooks.Open(file_path)
            ws = wb.Sheets(1)

            headers = []
            col = 1
            while col < 200:
                val = ws.Cells(1, col).Value
                if val:
                    headers.append(str(val))
                else:
                    if col > 10:
                        break
                col += 1

            structure, value_col, paid_col, waste_start = detect_structure(headers)

            last_row = ws.UsedRange.Rows.Count
            last_col = min(len(headers), 200)

            data_range = ws.Range(ws.Cells(2, 1), ws.Cells(last_row, last_col))
            data = data_range.Value

            if data is None:
                wb.Close(False)
                continue

            if not isinstance(data[0], tuple):
                data = [data]

            for row_data in data:
                if not row_data[0]:
                    continue

                name = str(row_data[0]).strip()
                cnp = str(int(float(row_data[1]))) if row_data[1] else ''

                # Get value
                try:
                    val_raw = row_data[value_col]
                    value = float(val_raw) if isinstance(val_raw, (int, float)) else 0
                    paid_raw = row_data[paid_col] if paid_col < len(row_data) else value
                    paid = float(paid_raw) if isinstance(paid_raw, (int, float)) else value
                except:
                    continue

                if value <= 0:
                    continue

                total_transactions += 1

                # Partner key (CNP or name)
                partner_key = cnp if cnp and len(cnp) == 13 else name

                p = partners[partner_key]
                p['name'] = name
                p['cnp'] = cnp
                if not p['cnp_info'] and cnp:
                    p['cnp_info'] = parse_cnp(cnp)

                if p['first_visit'] is None or date_key < p['first_visit']:
                    p['first_visit'] = date_key
                if p['last_visit'] is None or date_key > p['last_visit']:
                    p['last_visit'] = date_key

                p['total_visits'] += 1
                p['total_value'] += value
                p['total_paid'] += paid
                p['visits_by_month'][month_key] += 1
                p['value_by_month'][month_key] += value
                p['all_visits'].append({'date': date_key, 'value': value})

                # Daily stats
                daily_stats[date_key]['value'] += value
                daily_stats[date_key]['trans'] += 1

                # Categories
                for i, header in enumerate(headers[waste_start:], start=waste_start):
                    if i < len(row_data) and row_data[i]:
                        try:
                            kg = float(row_data[i])
                            if kg > 0:
                                cat = categorize(header)
                                p['categories'][cat] += kg
                                daily_stats[date_key]['categories'][cat] += kg
                                monthly_category_trends[month_key][cat] += kg
                        except:
                            pass

            wb.Close(False)
        except Exception as e:
            print(f"    HIBA: {filename}: {e}")

excel.Quit()

print(f"\nOssz tranzakcio: {total_transactions:,}")
print(f"Egyedi partnerek: {len(partners):,}")

# Analyze partners
today = date.today()
today_str = today.strftime('%Y-%m-%d')

# Convert to serializable format
partners_list = []
for key, p in partners.items():
    # Calculate days since last visit
    if p['last_visit']:
        last_date = datetime.strptime(p['last_visit'], '%Y-%m-%d').date()
        days_inactive = (today - last_date).days
    else:
        days_inactive = 999

    partners_list.append({
        'key': key,
        'name': p['name'],
        'cnp': p['cnp'],
        'cnp_info': p['cnp_info'],
        'first_visit': p['first_visit'],
        'last_visit': p['last_visit'],
        'days_inactive': days_inactive,
        'total_visits': p['total_visits'],
        'total_value': round(p['total_value'], 2),
        'avg_value': round(p['total_value'] / p['total_visits'], 2) if p['total_visits'] > 0 else 0,
        'visits_by_month': dict(p['visits_by_month']),
        'value_by_month': {k: round(v, 2) for k, v in p['value_by_month'].items()},
        'categories': {k: round(v, 1) for k, v in sorted(p['categories'].items(), key=lambda x: -x[1])[:5]}
    })

# Sort by total value
partners_list.sort(key=lambda x: -x['total_value'])

# Stats
returning = [p for p in partners_list if p['total_visits'] > 1]
one_time = [p for p in partners_list if p['total_visits'] == 1]
vip = [p for p in partners_list if p['total_visits'] >= 10]
inactive_30 = [p for p in partners_list if 30 <= p['days_inactive'] < 60]
inactive_60 = [p for p in partners_list if 60 <= p['days_inactive'] < 90]
inactive_90 = [p for p in partners_list if p['days_inactive'] >= 90]

print(f"\n=== PARTNER STATISZTIKAK ===")
print(f"Visszatero (2+ alkalom): {len(returning):,} ({len(returning)/len(partners_list)*100:.1f}%)")
print(f"Egyszeri: {len(one_time):,} ({len(one_time)/len(partners_list)*100:.1f}%)")
print(f"VIP (10+ alkalom): {len(vip):,}")
print(f"Elaludt 30-60 nap: {len(inactive_30):,}")
print(f"Elaludt 60-90 nap: {len(inactive_60):,}")
print(f"Elaludt 90+ nap: {len(inactive_90):,}")

# County analysis
county_stats = defaultdict(lambda: {'count': 0, 'value': 0, 'visits': 0})
for p in partners_list:
    if p['cnp_info']:
        county = p['cnp_info']['county_name']
        county_stats[county]['count'] += 1
        county_stats[county]['value'] += p['total_value']
        county_stats[county]['visits'] += p['total_visits']

print(f"\n=== TOP 10 MEGYE ===")
for county, stats in sorted(county_stats.items(), key=lambda x: -x[1]['value'])[:10]:
    print(f"  {county}: {stats['count']} partner, {stats['value']:,.0f} RON, {stats['visits']} latogatas")

# Age analysis
age_groups = defaultdict(lambda: {'count': 0, 'value': 0})
for p in partners_list:
    if p['cnp_info']:
        age = 2024 - p['cnp_info']['birth_year']
        if age < 25:
            group = '18-24'
        elif age < 35:
            group = '25-34'
        elif age < 45:
            group = '35-44'
        elif age < 55:
            group = '45-54'
        elif age < 65:
            group = '55-64'
        else:
            group = '65+'
        age_groups[group]['count'] += 1
        age_groups[group]['value'] += p['total_value']

print(f"\n=== KORCSOPORT ===")
for group in ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']:
    if group in age_groups:
        print(f"  {group}: {age_groups[group]['count']} fo, {age_groups[group]['value']:,.0f} RON")

# Save comprehensive analytics data
analytics = {
    'generated': today_str,
    'summary': {
        'total_transactions': total_transactions,
        'unique_partners': len(partners_list),
        'returning_partners': len(returning),
        'one_time_partners': len(one_time),
        'vip_partners': len(vip),
        'inactive_30_60': len(inactive_30),
        'inactive_60_90': len(inactive_60),
        'inactive_90_plus': len(inactive_90)
    },
    'top_100_partners': partners_list[:100],
    'inactive_partners': {
        '30_60_days': [{'name': p['name'], 'last_visit': p['last_visit'], 'total_value': p['total_value'], 'visits': p['total_visits']} for p in sorted(inactive_30, key=lambda x: -x['total_value'])[:50]],
        '60_90_days': [{'name': p['name'], 'last_visit': p['last_visit'], 'total_value': p['total_value'], 'visits': p['total_visits']} for p in sorted(inactive_60, key=lambda x: -x['total_value'])[:50]],
        '90_plus_days': [{'name': p['name'], 'last_visit': p['last_visit'], 'total_value': p['total_value'], 'visits': p['total_visits']} for p in sorted(inactive_90, key=lambda x: -x['total_value'])[:50]]
    },
    'county_stats': {k: v for k, v in sorted(county_stats.items(), key=lambda x: -x[1]['value'])},
    'age_groups': dict(age_groups),
    'monthly_category_trends': {k: dict(v) for k, v in sorted(monthly_category_trends.items())},
    'daily_stats': {k: {'value': v['value'], 'trans': v['trans'], 'top_cat': dict(sorted(v['categories'].items(), key=lambda x: -x[1])[:3])} for k, v in sorted(daily_stats.items())}
}

with open(os.path.join(base_path, 'analytics.json'), 'w', encoding='utf-8') as f:
    json.dump(analytics, f, ensure_ascii=False, indent=2)

print(f"\nMentve: analytics.json")
