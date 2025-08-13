import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List
from threading import Barrier

from game_api import run_player_race

# Простые лобби в памяти процесса
LOBBIES: Dict[str, Dict] = {}


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


def join_lobby(lobby_id: str, user_id: str, name: str) -> None:
    lobby = LOBBIES.get(lobby_id)
    if not lobby:
        raise RuntimeError("Лобби не найдено")
    if user_id not in [p["user_id"] for p in lobby["players"]]:
        lobby["players"].append({"user_id": user_id, "name": name})


def leave_lobby(lobby_id: str, user_id: str) -> None:
    lobby = LOBBIES.get(lobby_id)
    if not lobby:
        return
    lobby["players"] = [p for p in lobby["players"] if p["user_id"] != user_id]
    if not lobby["players"]:
        del LOBBIES[lobby_id]


def start_lobby_race(lobby_id: str, laps: int = 1) -> List[Dict]:
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
        barrier.wait()
        return run_player_race(p["user_id"], p["name"], track_id=track_id, laps=laps)

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
