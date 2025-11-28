import win32com.client
import os
import json
from collections import defaultdict
from datetime import date

excel = win32com.client.Dispatch('Excel.Application')
excel.Visible = False
excel.DisplayAlerts = False

januar_path = r'2024\01_Ianuarie'
files = [f for f in os.listdir(januar_path) if f.endswith('.xls')]
files.sort()

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
    else:
        return 'Egyeb'

daily_detailed = {}
all_waste_totals = defaultdict(float)

for filename in files:
    date_str = filename.replace('.xls', '')
    day, month, year = date_str.split('.')
    date_obj = date(int(year), int(month), int(day))
    weekday = date_obj.weekday()
    date_key = f'{year}-{month}-{day}'

    file_path = os.path.abspath(os.path.join(januar_path, filename))

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

        last_row = ws.UsedRange.Rows.Count
        last_col = len(headers)
        # Max 200 oszlop
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
        day_trans = 0

        for row_data in data:
            if not row_data[0]:
                continue

            value = float(row_data[3]) if row_data[3] else 0
            day_total += value
            day_trans += 1

            for i, header in enumerate(headers[7:], start=7):
                if i < len(row_data) and row_data[i]:
                    kg = float(row_data[i])
                    if kg > 0:
                        cat = categorize(header)
                        day_waste_cat[cat] += kg
                        day_waste_detailed[header] += kg
                        all_waste_totals[cat] += kg

        sorted_cat = sorted(day_waste_cat.items(), key=lambda x: -x[1])[:5]
        sorted_detailed = sorted(day_waste_detailed.items(), key=lambda x: -x[1])[:3]

        daily_detailed[date_key] = {
            'day': int(day),
            'weekday': weekday,
            'weekday_name': day_names_ro[weekday],
            'weekday_short': day_names_short[weekday],
            'total_value': round(day_total, 2),
            'transactions': day_trans,
            'avg_per_trans': round(day_total / day_trans, 2) if day_trans > 0 else 0,
            'top3_detailed': [{'name': n.replace('Deseu ', '').replace('Deseuri ', ''), 'kg': round(k, 1)} for n, k in sorted_detailed],
            'top5_categories': [{'cat': c, 'kg': round(k, 1)} for c, k in sorted_cat],
            'all_categories': {k: round(v, 1) for k, v in day_waste_cat.items()}
        }

        wb.Close(False)

    except Exception as e:
        print(f'HIBA {filename}: {e}')

excel.Quit()

# Heti mintak
weekday_stats = defaultdict(lambda: {'total_value': 0, 'transactions': 0, 'days': 0, 'categories': defaultdict(float)})

for date_key, d in daily_detailed.items():
    wd = d['weekday']
    weekday_stats[wd]['total_value'] += d['total_value']
    weekday_stats[wd]['transactions'] += d['transactions']
    weekday_stats[wd]['days'] += 1
    for cat, kg in d['all_categories'].items():
        weekday_stats[wd]['categories'][cat] += kg

# Output
output = {
    'period': '2024-01',
    'total_by_category': {k: round(v, 0) for k, v in sorted(all_waste_totals.items(), key=lambda x: -x[1])},
    'daily': dict(sorted(daily_detailed.items())),
    'weekday_patterns': {}
}

for wd in range(7):
    if weekday_stats[wd]['days'] > 0:
        top_cats = sorted(weekday_stats[wd]['categories'].items(), key=lambda x: -x[1])[:3]
        output['weekday_patterns'][day_names_ro[wd]] = {
            'days_count': weekday_stats[wd]['days'],
            'avg_value': round(weekday_stats[wd]['total_value'] / weekday_stats[wd]['days'], 0),
            'avg_transactions': round(weekday_stats[wd]['transactions'] / weekday_stats[wd]['days'], 0),
            'top3_categories': [{'cat': c, 'avg_kg': round(k / weekday_stats[wd]['days'], 0)} for c, k in top_cats]
        }

with open('2024_01_detailed.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('=== OSSZES KATEGORIA (januar) ===')
for cat, kg in sorted(all_waste_totals.items(), key=lambda x: -x[1]):
    print(f'{cat:25} {kg:>12,.0f} kg')

print()
print('=== HETI MINTAK ===')
for wd in range(7):
    if weekday_stats[wd]['days'] > 0:
        s = weekday_stats[wd]
        avg_v = s['total_value'] / s['days']
        avg_t = s['transactions'] / s['days']
        top = sorted(s['categories'].items(), key=lambda x: -x[1])[:2]
        top_str = ', '.join([f'{c}:{int(k/s["days"])}kg' for c,k in top])
        print(f'{day_names_ro[wd]:10} | {avg_v:>10,.0f} RON | {avg_t:>3.0f} tranz | Top: {top_str}')

print()
print('Mentve: 2024_01_detailed.json')
