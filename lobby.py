import uuid
from typing import Dict, List
from .game_api import run_player_race

# Простые лобби в памяти процесса
LOBBIES: Dict[str, Dict] = {}


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
    track_id = lobby["track_id"]
    results = []
    for p in lobby["players"]:
        uid = p["user_id"]
        name = p["name"]
        try:
            res = run_player_race(uid, name, track_id=track_id, laps=laps)
            results.append({"user_id": uid, "name": name, "result": res})
        except Exception as e:
            results.append({"user_id": uid, "name": name, "error": str(e)})
    return results
