import os, json, tempfile
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from pathlib import Path

DATA_DIR = Path(os.getenv("GAME_DATA_DIR", "./data"))
USERS_DIR = DATA_DIR / "users"
USERS_DIR.mkdir(parents=True, exist_ok=True)
CARS_DIR = DATA_DIR / "cars"
TRACKS_DIR = DATA_DIR / "tracks"

DEFAULT_START_BALANCE = 20000
RACE_BASE_REWARD = {
    "starter": 150,
    "club": 220,
    "sport": 360,
    "gt": 600,
    "hyper": 1200,
}
CLEAN_BONUS = 0.25
PENALTY_TAX = 0.08

@dataclass
class Player:
    user_id: str
    name: str
    balance: int = DEFAULT_START_BALANCE
    garage: List[str] = None
    current_car: Optional[str] = None
    current_track: Optional[str] = None
    driver_json: Optional[str] = None

    def __post_init__(self):
        if self.garage is None:
            self.garage = []

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

def _user_path(uid: str) -> Path:
    return USERS_DIR / f"{uid}.json"

def load_player(uid: str, name: str) -> Player:
    pth = _user_path(uid)
    if pth.exists():
        try:
            data = json.loads(pth.read_text(encoding="utf-8"))
            data.setdefault("name", name)
            data.setdefault("balance", DEFAULT_START_BALANCE)
            data.setdefault("garage", [])
            return Player(**data)
        except Exception:
            pass
    p = Player(user_id=uid, name=name)
    pth.write_text(p.to_json(), encoding="utf-8")
    return p

def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def save_player(p: Player) -> None:
    _atomic_write(_user_path(p.user_id), p.to_json())

def _price_tier(car: Dict) -> (int, str):
    mass = max(car.get("mass", 1), 1)
    power = max(car.get("power", 0), 0)
    pw = power / mass  # kW/kg
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

def list_catalog() -> Dict:
    out = {"cars": {}}
    for p in CARS_DIR.glob("*.json"):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            price, tier = _price_tier(j)
            cid = j.get("id") or p.stem
            name = j.get("name") or p.stem
            out["cars"][cid] = {"name": name, "price": price, "tier": tier}
        except Exception:
            continue
    return out

def list_tracks() -> Dict[str, str]:
    out = {}
    for p in TRACKS_DIR.glob("*.json"):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            tid = j.get("id") or p.stem
            name = j.get("name") or p.stem
            out[tid] = name
        except Exception:
            continue
    return out

def buy_car(p: Player, car_id: str) -> str:
    cat = list_catalog()
    if car_id not in cat["cars"]:
        return "🚫 Такой машины нет."
    item = cat["cars"][car_id]
    price = item["price"]
    if p.balance < price:
        return f"💸 Не хватает средств: нужно {price}, на счету {p.balance}."
    p.balance -= price
    p.garage.append(car_id)
    if p.current_car is None:
        p.current_car = car_id
    save_player(p)
    return f"✅ Покупка: {item['name']} за {price}. Баланс: {p.balance}."

def set_current_car(p: Player, car_id: str) -> str:
    if car_id not in p.garage:
        return "🚫 Сначала купи эту машину."
    p.current_car = car_id
    save_player(p)
    return f"🚗 Текущая машина: {car_id}"

def set_current_track(p: Player, track_id: str) -> str:
    tracks = list_tracks()
    if track_id not in tracks:
        return "🚫 Такой трассы нет."
    p.current_track = track_id
    save_player(p)
    return f"🏁 Текущая трасса: {tracks[track_id]} (`{track_id}`)"

def payout_for_race(car_tier: str, laps: int, incidents: int, clean: bool) -> int:
    base = RACE_BASE_REWARD.get(car_tier, 300) * max(1, laps)
    mult = 1.0 + (CLEAN_BONUS if clean else 0.0)
    mult *= max(0.5, 1.0 - PENALTY_TAX * max(0, incidents))
    return max(0, int(base * mult))

def reward_player(p: Player, amount: int) -> None:
    p.balance += int(amount)
    save_player(p)
