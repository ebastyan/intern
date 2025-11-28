import json
import re
from collections import defaultdict
from datetime import date

with open(r'C:\Users\INTEL\Desktop\paju\all_persons.json', 'r', encoding='utf-8') as f:
    all_data = json.load(f)

today = date(2025, 11, 26)

def normalize_locality(name):
    if not name:
        return ''
    name = str(name).strip()
    name_lower = name.lower()

    # Remove prefixes
    prefixes = [
        r'^com\.?\s*', r'^mun\.?\s*', r'^oras\.?\s*', r'^ors\.?\s*',
        r'^sat\.?\s*', r'^comuna\.?\s*', r'^municipiul\.?\s*',
    ]
    for p in prefixes:
        name_lower = re.sub(p, '', name_lower, flags=re.IGNORECASE)

    # Clean up
    name_lower = re.sub(r'\s+', ' ', name_lower).strip()
    name_lower = re.sub(r'[\\/:*?"<>|]', '', name_lower)

    # Fix common typos
    typo_fixes = {
        'oradsea': 'oradea', 'oradaea': 'oradea', 'oradae': 'oradea',
        'orade': 'oradea', 'oradera': 'oradea', 'oradrea': 'oradea',
        'oradxea': 'oradea',
        'simlu silvaniei': 'simleul silvaniei',
        'simleul sivaniei': 'simleul silvaniei',
        'simleul silvaniaei': 'simleul silvaniei',
        'simleul ilvaniei': 'simleul silvaniei',
        'simleul silaniei': 'simleul silvaniei',
        'simleulsilvaniei': 'simleul silvaniei',
        'simleu sivaniei': 'simleul silvaniei',
        'simleul  silvaniei': 'simleul silvaniei',
        'simleul silvaneii': 'simleul silvaniei',
        'simleu silvanies': 'simleul silvaniei',
        'simlaul silvaniei': 'simleul silvaniei',
        'simleu silvaniei': 'simleul silvaniei',
        'simleul silvaniei': 'simleul silvaniei',
        'sacuieni': 'sacueni', 'sacuinei': 'sacueni', 'sacuieu': 'sacueni',
        'sinmartin': 'sanmartin', 'sin,martin': 'sanmartin',
    }

    for typo, fix in typo_fixes.items():
        if name_lower == typo:
            name_lower = fix
            break

    return name_lower.title()

def parse_cnp(cnp):
    if not cnp or len(cnp) < 13:
        return None, None, None, None
    try:
        s = int(cnp[0])
        yy = int(cnp[1:3])
        mm = int(cnp[3:5])
        dd = int(cnp[5:7])
        jj = cnp[7:9]

        if s == 1:
            gender = 'Barbat'
            year = 1900 + yy
        elif s == 2:
            gender = 'Femeie'
            year = 1900 + yy
        elif s == 5:
            gender = 'Barbat'
            year = 2000 + yy
        elif s == 6:
            gender = 'Femeie'
            year = 2000 + yy
        elif s in [7, 8, 9]:
            gender = 'Strain'
            year = 1900 + yy
        else:
            return None, None, None, None

        birth_date = date(year, mm, dd)
        age = (today - birth_date).days // 365

        return gender, year, age, jj
    except:
        return None, None, None, None

# CNP county codes
cnp_county_map = {
    '01': 'Alba', '02': 'Arad', '03': 'Arges', '04': 'Bacau', '05': 'Bihor',
    '06': 'Bistrita-Nasaud', '07': 'Botosani', '08': 'Brasov', '09': 'Braila',
    '10': 'Buzau', '11': 'Caras-Severin', '12': 'Cluj', '13': 'Constanta',
    '14': 'Covasna', '15': 'Dambovita', '16': 'Dolj', '17': 'Galati',
    '18': 'Gorj', '19': 'Harghita', '20': 'Hunedoara', '21': 'Ialomita',
    '22': 'Iasi', '23': 'Ilfov', '24': 'Maramures', '25': 'Mehedinti',
    '26': 'Mures', '27': 'Neamt', '28': 'Olt', '29': 'Prahova',
    '30': 'Salaj', '31': 'Satu Mare', '32': 'Sibiu', '33': 'Suceava',
    '34': 'Teleorman', '35': 'Timis', '36': 'Tulcea', '37': 'Vaslui',
    '38': 'Valcea', '39': 'Vrancea', '40': 'Bucuresti', '41': 'Bucuresti S1',
    '42': 'Bucuresti S2', '43': 'Bucuresti S3', '44': 'Bucuresti S4',
    '45': 'Bucuresti S5', '46': 'Bucuresti S6', '51': 'Calarasi', '52': 'Giurgiu'
}

# Process
stats = {
    'gender': defaultdict(int),
    'age_groups': defaultdict(int),
    'birth_decades': defaultdict(int),
    'birth_years': defaultdict(int),
    'localities': defaultdict(int),
    'counties': defaultdict(int),
    'cnp_counties': defaultdict(int),
    'ages': [],
    'migration': defaultdict(int),  # Birth county vs current county
}

duplicates_by_cnp = defaultdict(list)

for p in all_data:
    loc = normalize_locality(p['localitate'])
    if loc:
        stats['localities'][loc] += 1

    current_county = p['judet'] if p['judet'] else ''
    if current_county:
        stats['counties'][current_county] += 1

    gender, year, age, jj = parse_cnp(p['cnp'])
    birth_county = cnp_county_map.get(jj, '') if jj else ''

    if gender:
        stats['gender'][gender] += 1
    if year:
        stats['birth_decades'][(year // 10) * 10] += 1
        stats['birth_years'][year] += 1
    if age is not None and 0 <= age < 150:
        stats['ages'].append(age)
        if age < 18: stats['age_groups']['0-17 (Minori)'] += 1
        elif age < 25: stats['age_groups']['18-24'] += 1
        elif age < 35: stats['age_groups']['25-34'] += 1
        elif age < 45: stats['age_groups']['35-44'] += 1
        elif age < 55: stats['age_groups']['45-54'] += 1
        elif age < 65: stats['age_groups']['55-64'] += 1
        else: stats['age_groups']['65+'] += 1

    if birth_county:
        stats['cnp_counties'][birth_county] += 1
        # Migration analysis
        if current_county and birth_county:
            if 'Bucuresti' in birth_county:
                birth_county_normalized = 'Bucuresti'
            else:
                birth_county_normalized = birth_county
            if birth_county_normalized != current_county:
                stats['migration'][f'{birth_county_normalized} -> {current_county}'] += 1

    if p['cnp']:
        duplicates_by_cnp[p['cnp']].append(p)

# Find duplicates
duplicate_cnps = {cnp: entries for cnp, entries in duplicates_by_cnp.items() if len(entries) > 1}

print('=== NORMALIZALT TELEPULESEK TOP 30 ===')
sorted_locs = sorted(stats['localities'].items(), key=lambda x: -x[1])
for loc, cnt in sorted_locs[:30]:
    print(f'{loc}: {cnt}')

print(f'\n=== DUPLIKALT CNP-K ===')
print(f'Osszesen {len(duplicate_cnps)} CNP tobbszor szerepel')

print(f'\n=== SZULETESI HELY (CNP alapjan) TOP 15 ===')
sorted_birth = sorted(stats['cnp_counties'].items(), key=lambda x: -x[1])
for county, cnt in sorted_birth[:15]:
    print(f'{county}: {cnt}')

print(f'\n=== MIGRACIO (honnan hova koltoztek) TOP 20 ===')
sorted_migration = sorted(stats['migration'].items(), key=lambda x: -x[1])
for route, cnt in sorted_migration[:20]:
    print(f'{route}: {cnt}')

print(f'\n=== ELETKOR STATISZTIKAK ===')
ages = stats['ages']
print(f'Atlag eletkor: {sum(ages)/len(ages):.1f} ev')
print(f'Median eletkor: {sorted(ages)[len(ages)//2]} ev')
print(f'Legfiatalabb: {min(ages)} ev')
print(f'Legidosebb: {max(ages)} ev')

# Save
output = {
    'localities_normalized': dict(sorted_locs),
    'gender': dict(stats['gender']),
    'age_groups': dict(stats['age_groups']),
    'birth_decades': dict(sorted(stats['birth_decades'].items())),
    'birth_years': dict(sorted(stats['birth_years'].items())),
    'cnp_birth_counties': dict(sorted_birth),
    'current_counties': dict(sorted(stats['counties'].items(), key=lambda x: -x[1])),
    'migration_routes': dict(sorted_migration[:50]),
    'avg_age': round(sum(ages)/len(ages), 1),
    'median_age': sorted(ages)[len(ages)//2],
    'min_age': min(ages),
    'max_age': max(ages),
    'duplicate_cnp_count': len(duplicate_cnps),
    'total_records': len(all_data)
}

with open(r'C:\Users\INTEL\Desktop\paju\normalized_stats.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('\nMentve: normalized_stats.json')
