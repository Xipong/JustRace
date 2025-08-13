import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from lobby import reset_lobbies, create_lobby, join_lobby, LOBBIES


def test_join_lobby_stores_car():
    reset_lobbies()
    lid = create_lobby("track1")
    join_lobby(lid, "u1", "Alice", chat_id="1", car="Matiz")
    assert LOBBIES[lid]["players"][0]["car"] == "Matiz"
