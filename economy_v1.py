import os, json, tempfile
from dataclasses import dataclass, asdict, field
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

# upgrade system constants
UPGRADE_CLASSES = {
    "starter": 5,
    "club": 4,
    "sport": 3,
    "gt": 2,
    "hyper": 1,
}
UPGRADE_BASE_COST_MULT = 0.1  # fraction of car price per part at level 0

# individual upgrade effects per installed part
# values represent fractional change applied multiplicatively
UPGRADE_EFFECTS: Dict[str, Dict[str, float]] = {
    "engine": {"power": 0.06, "engine_volume": 0.02, "mass": 0.005},
    "turbo": {"power": 0.08, "engine_volume": 0.01, "mass": 0.01},
    "exhaust": {"power": 0.03, "mass": -0.004},
    "intake": {"power": 0.02, "engine_volume": 0.01},
    "ecu": {"power": 0.04},
    "fuel": {"power": 0.03, "mass": 0.002},
    "cooling": {"power": 0.02, "mass": 0.004},
    "transmission": {"power": 0.02, "mass": -0.003},
    "suspension": {"tire_grip": 0.02, "mass": 0.003},
    "tires": {"tire_grip": 0.03, "mass": 0.002},
    "aero": {"tire_grip": 0.01, "mass": -0.002},
    "weight": {"mass": -0.01},
    "custom": {"power": 0.05, "tire_grip": 0.02, "mass": -0.01},
}

def fmt_money(v: int) -> str:
    """Format integer value with spaces for thousands."""
    return f"{v:,}".replace(",", " ")


def round_price(value: float) -> int:
    """Round monetary value to the nearest multiple of ten, halves rounding up."""
    return int((value + 5) // 10 * 10)


# default upgrade cost multipliers now live in each car definition
UPGRADE_PART_MULT: Dict[str, float] = {}


_CAR_UPGRADE_MULT_CACHE: Dict[str, Dict[str, float]] = {}


def _car_upgrade_mults(car_id: str) -> Dict[str, float]:
    """Return part multiplier overrides for a specific car."""
    if car_id not in _CAR_UPGRADE_MULT_CACHE:
        try:
            data = json.loads((CARS_DIR / f"{car_id}.json").read_text(encoding="utf-8"))
            _CAR_UPGRADE_MULT_CACHE[car_id] = data.get("upgrade_multipliers", {})
        except Exception:
            _CAR_UPGRADE_MULT_CACHE[car_id] = {}
    return _CAR_UPGRADE_MULT_CACHE[car_id]


def part_cost_multiplier(part_id: str, car_id: Optional[str]) -> float:
    """Get cost multiplier for a part, considering car-specific overrides."""
    if car_id:
        mults = _car_upgrade_mults(car_id)
        if part_id in mults:
            return mults[part_id]
    return UPGRADE_PART_MULT.get(part_id, 1.0)


def upgrade_cost(
    car_price: int, level: int, part_id: str, car_id: Optional[str] = None
) -> int:
    """Return integer cost for an upgrade part at the given level."""
    mult = part_cost_multiplier(part_id, car_id)
    base = car_price * UPGRADE_BASE_COST_MULT * mult * (level + 1)
    return round_price(base)

# available upgrade parts
UPGRADE_PARTS = {
    "engine": "Двигатель",
    "turbo": "Турбина",
    "exhaust": "Выпуск",
    "intake": "Впуск",
    "ecu": "ЭБУ",
    "fuel": "Топливная система",
    "cooling": "Охлаждение",
    "transmission": "Трансмиссия",
    "suspension": "Подвеска",
    "tires": "Шины",
    "aero": "Аэродинамика",
    "weight": "Облегчение",
}
# descriptions for upgrade parts
UPGRADE_DESCRIPTIONS = {
    "engine": "Повышает базовую мощность мотора.",
    "turbo": "Устанавливает турбонаддув для прироста тяги.",
    "exhaust": "Уменьшает сопротивление выпускной системы.",
    "intake": "Улучшает поступление воздуха в двигатель.",
    "ecu": "Перепрошивка блока управления для оптимальной работы.",
    "fuel": "Повышает эффективность подачи топлива.",
    "cooling": "Снижает температуру двигателя под нагрузкой.",
    "transmission": "Ускоряет переключение передач.",
    "suspension": "Улучшает управляемость на трассе.",
    "tires": "Повышает сцепление с дорогой.",
    "aero": "Снижает аэродинамическое сопротивление.",
    "weight": "Облегчает автомобиль для лучшей динамики.",
}
PARTS_PER_CLASS = 12
assert len(UPGRADE_PARTS) == PARTS_PER_CLASS, "UPGRADE_PARTS must contain exactly 12 items"

def list_upgrade_parts() -> Dict[str, str]:
    """Return a mapping of available upgrade part ids to their names."""
    return dict(UPGRADE_PARTS)

@dataclass
class UpgradeProgress:
    """State of upgrades for a single car."""
    level: int = 0
    parts: List[str] = field(default_factory=list)
    custom_done: bool = False


def installed_parts(progress: UpgradeProgress) -> int:
    """Return total installed upgrade parts across all completed classes."""
    return progress.level * PARTS_PER_CLASS + len(progress.parts)


def all_installed_parts(progress: UpgradeProgress) -> List[str]:
    """Return list of part ids installed across all levels."""
    parts: List[str] = []
    full = ["custom"] + list(UPGRADE_PARTS.keys())
    for _ in range(progress.level):
        parts.extend(full)
    if progress.custom_done:
        parts.append("custom")
    parts.extend(progress.parts)
    return parts


def custom_upgrade_info(car: Dict, level: int) -> Dict[str, str]:
    """Generate a custom upgrade name/description for a car and level."""
    name = f"Спецтюнинг {car['name']}"
    desc = f"Уникальный пакет для перехода на класс {level}"
    return {"id": "custom", "name": name, "desc": desc}


def available_parts(p: "Player", car_id: str) -> list:
    """Return list of available upgrade parts for current car level.

    Each item is a dict with keys: id, name, desc.
    """
    cat = list_catalog()
    if car_id not in p.garage or car_id not in cat["cars"]:
        return []
    item = cat["cars"][car_id]
    tier = item["tier"]
    max_classes = UPGRADE_CLASSES.get(tier, 0)
    progress = p.upgrades.get(car_id, UpgradeProgress())
    if progress.level >= max_classes:
        return []
    if not progress.custom_done:
        info = custom_upgrade_info(item, progress.level + 1)
        return [info]
    parts = []
    for pid, name in UPGRADE_PARTS.items():
        if pid not in progress.parts:
            parts.append({"id": pid, "name": name, "desc": UPGRADE_DESCRIPTIONS[pid]})
    return parts


@dataclass
class Player:
    user_id: str
    name: str
    balance: int = DEFAULT_START_BALANCE
    garage: List[str] = field(default_factory=list)
    current_car: Optional[str] = None
    current_track: Optional[str] = None
    driver_json: Optional[str] = None
    races_today: int = 0
    last_race_day: Optional[str] = None
    upgrades: Dict[str, UpgradeProgress] = field(default_factory=dict)  # car_id -> progress

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

            data.setdefault("races_today", 0)
            data.setdefault("last_race_day", None)

            data.setdefault("upgrades", {})
            upg: Dict[str, UpgradeProgress] = {}
            for cid, val in data["upgrades"].items():
                if isinstance(val, dict):
                    lvl = int(val.get("level", 0))
                    parts = list(val.get("parts", []))
                    custom = bool(val.get("custom_done", False))
                    upg[cid] = UpgradeProgress(level=lvl, parts=parts, custom_done=custom)
                elif isinstance(val, list):
                    upg[cid] = UpgradeProgress(level=0, parts=list(val))
                elif isinstance(val, int):
                    upg[cid] = UpgradeProgress(level=val, parts=[])
                else:
                    upg[cid] = UpgradeProgress()

            data["upgrades"] = upg
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

def list_catalog() -> Dict:
    out = {"cars": {}}
    for p in CARS_DIR.glob("*.json"):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            price = j["price"]
            tier = j["tier"]
            cid = j.get("id") or p.stem
            name = j.get("name") or p.stem
            out["cars"][cid] = {
                "name": name,
                "price": price,
                "tier": tier,
                "classes": UPGRADE_CLASSES.get(tier, 0),
            }
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
        return f"💸 Не хватает средств: нужно {fmt_money(price)}, на счету {fmt_money(p.balance)}."
    p.balance -= price
    p.garage.append(car_id)
    if p.current_car is None:
        p.current_car = car_id
    save_player(p)
    stats = car_stats(p, car_id)
    power = int(stats["base_power"])
    mass = int(stats["base_mass"])
    volume = stats.get("base_engine_volume", 0)
    vol_txt = f", Объем: {volume:.2f} л" if volume else ""
    return (
        f"✅ Покупка: {item['name']} за {fmt_money(price)}. "
        f"Мощность: {power} л.с., Вес: {mass} кг{vol_txt}. Баланс: {fmt_money(p.balance)}."
    )

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
    """Compute race payout without penalizing incidents."""
    base = RACE_BASE_REWARD.get(car_tier, 300) * max(1, laps)
    mult = 1.0 + (CLEAN_BONUS if clean else 0.0)
    return max(0, int(base * mult))

def reward_player(p: Player, amount: int) -> None:
    p.balance += int(amount)
    save_player(p)


def redeem_bonus_code(p: Player, code: str) -> str:
    """Apply a bonus code reward for the player."""
    if code == "TestNewBounty":
        reward_player(p, 100_000)
        return f"🎁 Начислено 100000. Баланс: {p.balance}."
    return "🚫 Неверный код."


def car_stats(p: Player, car_id: str) -> Dict[str, float]:
    """Return base and upgraded stats for a player's car."""
    cat = list_catalog()
    if car_id not in cat["cars"]:
        return {
            "power": 0,
            "mass": 0,
            "tire_grip": 0,
            "engine_volume": 0,
            "base_power": 0,
            "base_mass": 0,
            "base_tire_grip": 0,
            "base_engine_volume": 0,
        }
    data = json.loads((DATA_DIR / "cars" / f"{car_id}.json").read_text(encoding="utf-8"))
    base_power = data.get("power", 0)
    base_mass = data.get("mass", 0)
    base_grip = data.get("tire_grip", 0.0)
    base_volume = data.get("engine_volume", 0.0)
    item = cat["cars"][car_id]
    tier = item.get("tier", "starter")
    progress = p.upgrades.get(car_id, UpgradeProgress())
    max_parts = UPGRADE_CLASSES.get(tier, 0) * PARTS_PER_CLASS
    applied = all_installed_parts(progress)[:max_parts]
    power = base_power
    mass = base_mass
    grip = base_grip
    volume = base_volume
    for pid in applied:
        eff = UPGRADE_EFFECTS.get(pid, {})
        power *= 1 + eff.get("power", 0.0)
        mass *= 1 + eff.get("mass", 0.0)
        grip *= 1 + eff.get("tire_grip", 0.0)
        volume *= 1 + eff.get("engine_volume", 0.0)
    return {
        "power": power,
        "mass": mass,
        "tire_grip": grip,
        "engine_volume": volume,
        "base_power": base_power,
        "base_mass": base_mass,
        "base_tire_grip": base_grip,
        "base_engine_volume": base_volume,
    }


def buy_upgrade(p: Player, car_id: str, part_id: str) -> str:
    """Purchase a specific factory upgrade part improving car power."""
    cat = list_catalog()
    if car_id not in p.garage:
        return "🚫 Сначала купи эту машину."
    if car_id not in cat["cars"]:
        return "🚫 Такой машины нет."
    item = cat["cars"][car_id]
    tier = item["tier"]
    max_classes = UPGRADE_CLASSES.get(tier, 0)
    progress = p.upgrades.get(car_id, UpgradeProgress())
    if progress.level >= max_classes:
        return "🚫 Достигнут максимум классов."
    if not progress.custom_done:
        if part_id != "custom":
            return "🚫 Сначала установи специальный комплект."
        cost = upgrade_cost(item["price"], progress.level, "custom", car_id)
        if p.balance < cost:
            return f"💸 Не хватает средств: нужно {fmt_money(cost)}, на счету {fmt_money(p.balance)}."
        before = car_stats(p, car_id)
        p.balance -= cost
        progress.custom_done = True
        p.upgrades[car_id] = progress
        save_player(p)
        after = car_stats(p, car_id)
        dp = after["power"] - before["power"]
        dm = after["mass"] - before["mass"]
        dv = after["engine_volume"] - before["engine_volume"]
        info = custom_upgrade_info(item, progress.level + 1)
        return (
            f"✨ {info['name']} для {item['name']} за {fmt_money(cost)}. "
            f"Δмощн {dp:+.0f}, Δвес {dm:+.0f}, Δобъем {dv:+.2f} л. Баланс: {fmt_money(p.balance)}."
        )
    if part_id not in UPGRADE_PARTS:
        return "🚫 Нет такой запчасти."
    if part_id in progress.parts:
        return "🚫 Эта запчасть уже установлена на текущем уровне."
    cost = upgrade_cost(item["price"], progress.level, part_id, car_id)
    if p.balance < cost:
        return f"💸 Не хватает средств: нужно {fmt_money(cost)}, на счету {fmt_money(p.balance)}."
    before = car_stats(p, car_id)
    p.balance -= cost
    progress.parts.append(part_id)
    parts_count = len(progress.parts)
    if parts_count == PARTS_PER_CLASS:
        progress.level += 1
        progress.parts = []
        progress.custom_done = False
        msg_end = " Заводская доработка завершена."
        current_level = progress.level
    else:
        msg_end = ""
        current_level = progress.level + 1
    p.upgrades[car_id] = progress
    save_player(p)
    after = car_stats(p, car_id)
    dp = after["power"] - before["power"]
    dm = after["mass"] - before["mass"]
    dv = after["engine_volume"] - before["engine_volume"]
    name = UPGRADE_PARTS[part_id]
    display_count = parts_count if not msg_end else PARTS_PER_CLASS
    return (
        f"🔧 {name} {display_count}/{PARTS_PER_CLASS} уровня {current_level}/{max_classes} "
        f"для {item['name']} за {fmt_money(cost)}. Δмощн {dp:+.0f}, Δвес {dm:+.0f}, Δобъем {dv:+.2f} л. Баланс: {fmt_money(p.balance)}." + msg_end
    )


def upgrade_status(p: Player, car_id: str) -> str:
    """Show current upgrade progress for a car."""
    cat = list_catalog()
    if car_id not in p.garage:
        return "🚫 Сначала купи эту машину."
    if car_id not in cat["cars"]:
        return "🚫 Такой машины нет."
    item = cat["cars"][car_id]
    tier = item["tier"]
    progress = p.upgrades.get(car_id, UpgradeProgress())
    max_classes = UPGRADE_CLASSES.get(tier, 0)
    if not progress.custom_done and progress.level < max_classes:
        info = custom_upgrade_info(item, progress.level + 1)
        return (
            f"🔩 {item['name']}: классы {progress.level}/{max_classes}. "
            f"Требуется {info['name']}"
        )
    parts_names = [UPGRADE_PARTS.get(pid, pid) for pid in progress.parts]
    installed = ", ".join(parts_names) if parts_names else "нет"
    return (
        f"🔩 {item['name']}: классы {progress.level}/{max_classes}, "
        f"детали уровня: {installed}"
    )
