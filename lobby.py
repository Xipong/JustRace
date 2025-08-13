import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Barrier
from typing import Dict, List, Optional, Callable

from game_api import run_player_race

# Простые лобби в памяти процесса
LOBBIES: Dict[str, Dict] = {}
MAX_PLAYERS = 8


def reset_lobbies() -> None:
    """Очистить все активные лобби.

    Полезно для тестов или при перезапуске сервиса, чтобы убедиться, что
    в памяти не осталось старых записей.
    """
    LOBBIES.clear()


def create_lobby(track_id: str) -> str:
    """Создать лобби и вернуть его ID."""
    lid = uuid.uuid4().hex[:6]
    LOBBIES[lid] = {"track_id": track_id, "players": []}
    return lid


def find_user_lobby(user_id: str) -> Optional[str]:
    """Вернуть ID лобби, в котором состоит пользователь, если есть."""
    for lid, info in LOBBIES.items():
        if any(p["user_id"] == user_id for p in info["players"]):
            return lid
    return None


def join_lobby(
    lobby_id: str,
    user_id: str,
    name: str,
    *,
    chat_id: str,
    mass: float = 0.0,
    power: float = 0.0,
    car: str = "",
) -> None:
    lobby = LOBBIES.get(lobby_id)
    if not lobby:
        raise RuntimeError("Лобби не найдено")

    other = find_user_lobby(user_id)
    if other and other != lobby_id:
        raise RuntimeError(f"Сначала выйди из лобби {other}")

    if len(lobby["players"]) >= MAX_PLAYERS:
        raise RuntimeError("Лобби заполнено (макс 8)")
    if user_id not in [p["user_id"] for p in lobby["players"]]:
        lobby["players"].append(
            {
                "user_id": user_id,
                "name": name,
                "chat_id": chat_id,
                "mass": mass,
                "power": power,
                "car": car,
            }
        )


def leave_lobby(lobby_id: str, user_id: str) -> None:
    lobby = LOBBIES.get(lobby_id)
    if not lobby:
        return
    lobby["players"] = [p for p in lobby["players"] if p["user_id"] != user_id]
    if not lobby["players"]:
        del LOBBIES[lobby_id]


_last_tick: Dict[str, float] = defaultdict(float)


def _log_event(evt: Dict) -> None:
    uid = evt.get("user_id", "?")
    name = evt.get("name", "?")
    etype = evt.get("type")
    if etype == "penalty":
        print(
            f"🚫 {name} penalty {evt.get('severity', '')}+{evt['delta_s']:.2f}s on {evt['segment']}"
        )
    elif etype == "segment_tick":
        now = time.time()
        if now - _last_tick[uid] >= 20.0:
            _last_tick[uid] = now
            print(
                "\n".join(
                    [
                        f"JustRace: {name}",
                        f"🏎 Круг {evt['lap']}/{evt['laps']}",
                        f"📏 Участок: {evt['segment']} (ID: {evt['segment_id']})",
                        f"🚀 Скорость: {evt['speed']:.1f} км/ч",
                        f"⏱ Время: {evt['time_s']:.1f} сек",
                        f"🏁 Пройдено: {evt['distance']:.0f}/{evt['segment_length']:.0f}м",
                    ]
                )
            )
    elif etype == "segment_change":
        print(
            f"➡️ {name}: Новый участок {evt['segment']} 🚀{evt['speed']:.1f} км/ч ⏱{evt['time_s']:.1f} сек"
        )


def start_lobby_race(
    lobby_id: str, laps: int = 1, *, on_event: Optional[Callable[[Dict], None]] = None
) -> List[Dict]:
    lobby = LOBBIES.get(lobby_id)
    if not lobby:
        raise RuntimeError("Лобби не найдено")
    players = list(lobby["players"])
    if len(players) < 2:
        raise RuntimeError("В лобби должно быть минимум 2 игрока")
    track_id = lobby["track_id"]
    results: List[Dict] = []
    barrier = Barrier(len(players))

    def _runner(p: Dict) -> Dict:
        def wrapper(evt: Dict) -> None:
            evt = dict(evt)
            evt["user_id"] = p["user_id"]
            evt["name"] = p["name"]
            if on_event:
                on_event(evt)
            else:
                _log_event(evt)

        barrier.wait()
        return run_player_race(
            p["user_id"], p["name"], track_id=track_id, laps=laps, on_event=wrapper
        )

    with ThreadPoolExecutor() as pool:
        fut_map = {pool.submit(_runner, p): p for p in players}
        for fut in as_completed(fut_map):
            p = fut_map[fut]
            try:
                res = fut.result()
                results.append({"user_id": p["user_id"], "name": p["name"], "result": res})
            except Exception as e:
                results.append({"user_id": p["user_id"], "name": p["name"], "error": str(e)})
    return results
