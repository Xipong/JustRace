import os, json
from typing import Optional, Dict, Callable
from pathlib import Path
from datetime import date
from .models_v2 import Car, Track, TrackSegment, DriverProfile, run_race
from .economy_v1 import (
    load_player,
    save_player,
    list_catalog,
    payout_for_race,
    reward_player,
    UPGRADE_POWER_BONUS,
    UPGRADE_CLASSES,
    PARTS_PER_CLASS,
    installed_parts,
    buy_upgrade,
    upgrade_status,
    list_upgrade_parts,
)

DATA_DIR = Path(os.getenv("GAME_DATA_DIR", "./data"))
MAX_RACES_PER_DAY = 5

def load_track(path: Path) -> Track:
    data = json.loads(path.read_text(encoding="utf-8"))
    segs = [TrackSegment(**s) for s in data["segments"]]
    return Track(data.get("id", path.stem), data.get("name", path.stem), segs)

def load_car_by_id(car_id: str) -> Car:
    p = DATA_DIR / "cars" / f"{car_id}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    allowed = {"id","name","power","mass","cd","area","tire_grip"}
    data = {k: v for k, v in data.items() if k in allowed}
    data.setdefault("id", car_id)
    data.setdefault("name", car_id)
    return Car(**data)

def ensure_driver(p) -> DriverProfile:
    if p.driver_json:
        try:
            return DriverProfile.from_json(p.driver_json)
        except Exception:
            pass
    return DriverProfile.default(p.user_id, p.name)

def save_driver(p, d: DriverProfile):
    p.driver_json = d.to_json()
    save_player(p)


def _check_daily_limit(p):
    today = date.today().isoformat()
    if p.last_race_day != today:
        p.last_race_day = today
        p.races_today = 0
    if p.races_today >= MAX_RACES_PER_DAY:
        raise RuntimeError(f"Лимит гонок на сегодня исчерпан ({MAX_RACES_PER_DAY}).")
    p.races_today += 1
    save_player(p)
def get_upgrade_parts() -> Dict[str, str]:
    """Return available upgrade part identifiers and their names."""
    return list_upgrade_parts()


def buy_car_upgrade(user_id: str, name: str, car_id: str, part_id: str) -> str:
    """Purchase a factory upgrade part for the player's car."""
    p = load_player(user_id, name)
    return buy_upgrade(p, car_id, part_id)


def get_upgrade_status(user_id: str, name: str, car_id: str) -> str:
    """Report current upgrade progress for the player's car."""
    p = load_player(user_id, name)
    return upgrade_status(p, car_id)

def run_player_race(user_id: str, name: str, track_id: Optional[str]=None, laps: int=1,
                    on_event: Optional[Callable[[Dict], None]] = None) -> Dict:
    p = load_player(user_id, name)
    d = ensure_driver(p)
    if not p.current_car:
        raise RuntimeError("У тебя нет текущей машины. Купи или выбери из гаража.")
    car = load_car_by_id(p.current_car)
    cat = list_catalog()
    item = cat["cars"].get(car.id)
    tier = item.get("tier", "starter") if item else "starter"
    progress = p.upgrades.get(car.id)
    if progress:
        max_parts = UPGRADE_CLASSES.get(tier, 0) * PARTS_PER_CLASS
        total_parts = min(installed_parts(progress), max_parts)
        if total_parts:
            car.power *= 1.0 + UPGRADE_POWER_BONUS * total_parts

    tid = track_id or p.current_track
    if not tid:
        raise RuntimeError("Не выбрана трасса. Используй /track и /settrack <id>.")
    tpath = (DATA_DIR / "tracks" / f"{tid}.json")
    if not tpath.exists():
        raise RuntimeError(f"Файл трассы не найден: {tpath}")
    track = load_track(tpath)

    _check_daily_limit(p)

    summary, gains = run_race(car, track, laps=laps, driver=d, on_event=on_event)
    reward = payout_for_race(tier, laps, summary["incidents"], clean=(summary["incidents"] == 0))
    reward_player(p, reward)
    save_driver(p, d)

    return {
        "time_s": round(summary["total_time_s"], 2),
        "incidents": summary["incidents"],
        "reward": reward,
        "penalties": summary["penalties"],
        "skill_gains": gains,
    }
