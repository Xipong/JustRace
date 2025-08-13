import os, sys, pytest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import lobby


def test_lobby_create_join_start(monkeypatch):
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    lobby.join_lobby(lid, "u1", "A")
    lobby.join_lobby(lid, "u2", "B")

    def fake_run(uid, name, track_id=None, laps=1):
        return {"time_s": 1.23, "incidents": 0, "reward": 0}

    monkeypatch.setattr(lobby, "run_player_race", fake_run)
    res = lobby.start_lobby_race(lid, laps=1)
    assert {r["user_id"] for r in res} == {"u1", "u2"}


def test_lobby_requires_two_players():
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    lobby.join_lobby(lid, "u1", "A")
    with pytest.raises(RuntimeError):
        lobby.start_lobby_race(lid)
