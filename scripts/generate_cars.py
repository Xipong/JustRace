import json
import requests
import urllib3
from pathlib import Path

DATASET_URL = "https://raw.githubusercontent.com/vega/vega-datasets/master/data/cars.json"
CARS_DIR = Path("data/cars")
CARS_DIR.mkdir(parents=True, exist_ok=True)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def sanitize(name: str, year: int) -> str:
    out = ''.join(ch.lower() if ch.isalnum() else '_' for ch in name)
    out = '_'.join(filter(None, out.split('_')))
    return f"{out}_{year}"
def estimate_area(mass_kg: int) -> float:
    # rough estimation: heavier cars have larger frontal area
    return round(1.8 + min(0.8, (mass_kg - 700) / 1300), 1)


def compute_price_tier(car: dict):
    pw = car["power"] / car["mass"]
    tiers = {
        "starter": (0.00, 0.09, 8000),
        "club":    (0.09, 0.14, 18000),
        "sport":   (0.14, 0.25, 60000),
        "gt":      (0.25, 0.40, 180000),
        "hyper":   (0.40, 2.00, 900000),
    }
    for name, (lo, hi, base) in tiers.items():
        if lo <= pw < hi:
            grip = float(car.get("tire_grip", 1.0))
            cd = float(car.get("cd", 0.35))
            adj = 1.0 + 0.15 * (grip - 1.0) + 0.10 * (max(0.25, min(0.6, cd)) - 0.35)
            return int(base * adj), name
    return 5000, "starter"


def main():
    data = requests.get(DATASET_URL, verify=False).json()
    existing_ids = {p.stem for p in CARS_DIR.glob('*.json')}
    new_entries = []
    for car in data:
        name = car['Name']
        if name.lower().startswith('amc'):
            continue
        year = int(str(car['Year'])[:4])
        cid = sanitize(name, year)
        if cid in existing_ids:
            continue
        hp = car.get('Horsepower')
        weight = car.get('Weight_in_lbs')
        if hp is None or weight is None:
            continue
        power = int(round(hp * 0.7457))
        mass = int(round(weight * 0.453592))
        pw = power / mass
        cd = 0.45 if year < 1980 else 0.32
        area = estimate_area(mass)
        grip = round(0.9 + min(0.4, pw), 2)
        info = {
            "id": cid,
            "name": f"{name} ({year})",
            "power": power,
            "mass": mass,
            "cd": round(cd, 2),
            "area": area,
            "tire_grip": grip,
        }
        (CARS_DIR / f"{cid}.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
        new_entries.append(info)
        existing_ids.add(cid)
        if len(new_entries) >= 50:
            break

    # update catalog.json
    cat_path = Path('catalog.json')
    if cat_path.exists():
        catalog = json.loads(cat_path.read_text(encoding='utf-8'))
    else:
        catalog = {"tiers": {}, "cars": {}}
    catalog['cars'] = {}
    for p in CARS_DIR.glob('*.json'):
        j = json.loads(p.read_text(encoding='utf-8'))
        price, tier = compute_price_tier(j)
        cid = j['id']
        catalog['cars'][cid] = {
            "path": str(p).replace('\\', '/'),
            "price": price,
            "tier": tier,
            "name": j['name']
        }
    cat_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
