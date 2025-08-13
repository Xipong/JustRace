import os, sys, pytest
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import lobby
import bot_lobby
import bot
import asyncio


def test_lobby_create_join_start(monkeypatch):
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    lobby.join_lobby(lid, "u1", "A", chat_id="c1", mass=1000, power=100)
    lobby.join_lobby(lid, "u2", "B", chat_id="c1", mass=900, power=110)

    events = []

    def fake_run(uid, name, track_id=None, laps=1, on_event=None):
        if on_event:
            on_event({"type": "penalty", "segment": "S", "delta_s": 1.0})
            on_event(
                {
                    "type": "segment_tick",
                    "segment": "S",
                    "segment_id": 1,
                    "segment_length": 100,
                    "distance": 50,
                    "lap": 1,
                    "laps": 1,
                    "time_s": 5.0,
                    "speed": 50.0,
                }
            )
        return {"time_s": 1.23, "incidents": 0, "reward": 0}

    monkeypatch.setattr(lobby, "run_player_race", fake_run)
    res = lobby.start_lobby_race(lid, laps=1, on_event=events.append)
    assert {r["user_id"] for r in res} == {"u1", "u2"}
    penalties = [e for e in events if e["type"] == "penalty"]
    assert len(penalties) == 2
    ticks = [e for e in events if e["type"] == "segment_tick"]
    assert len(ticks) == 2


def test_lobby_requires_two_players():
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    lobby.join_lobby(lid, "u1", "A", chat_id="c1", mass=1000, power=100)
    with pytest.raises(RuntimeError):
        lobby.start_lobby_race(lid)


def test_lobby_max_players():
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    for i in range(8):
        lobby.join_lobby(lid, f"u{i}", f"P{i}", chat_id=f"c{i}", mass=900 + i, power=100 + i)
    with pytest.raises(RuntimeError):
        lobby.join_lobby(lid, "u8", "P8", chat_id="c8", mass=950, power=120)


def test_group_receives_only_results(monkeypatch):
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    lobby.join_lobby(lid, "u1", "A", chat_id="10", mass=1000, power=100)
    lobby.join_lobby(lid, "u2", "B", chat_id="10", mass=900, power=110)

    def fake_start_lobby_race(_, on_event=None):
        return [
            {"user_id": "u1", "name": "A", "result": {"time_s": 1.0}},
            {"user_id": "u2", "name": "B", "result": {"time_s": 2.0}},
        ]

    monkeypatch.setattr(bot_lobby, "start_lobby_race", fake_start_lobby_race)

    sent = []

    class FakeBot:
        async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
            sent.append((chat_id, text))

    class FakeContext:
        def __init__(self):
            self.args = [lid]
            self.bot = FakeBot()

    class FakeUpdate:

        effective_user = type("U", (), {"id": "u1", "full_name": "A"})()


    asyncio.run(bot_lobby.lobby_start_cmd(FakeUpdate(), FakeContext()))

    assert len(sent) == 3
    chat_ids = [s[0] for s in sent]
    # Start messages go to each user
    assert 10 not in chat_ids[:2]
    assert set(chat_ids[:2]) == {"u1", "u2"}
    # Final results only to group chat
    assert chat_ids[2] == 10

def test_join_twice_forbidden():
    lobby.reset_lobbies()
    lid1 = lobby.create_lobby("track1")
    lobby.join_lobby(lid1, "u1", "A", chat_id="c1", mass=1000, power=100)
    lid2 = lobby.create_lobby("track2")
    with pytest.raises(RuntimeError):
        lobby.join_lobby(lid2, "u1", "A", chat_id="c2", mass=1000, power=100)


def test_leave_without_id():
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    lobby.join_lobby(lid, "u1", "A", chat_id="c1", mass=1000, power=100)

    messages = []

    class FakeChat:
        async def send_message(self, text, parse_mode=None, reply_markup=None):
            messages.append(text)

    class FakeUpdate:
        effective_chat = FakeChat()
        effective_user = type("U", (), {"id": "u1", "full_name": "A"})()

    class FakeContext:
        def __init__(self, args=None):
            self.args = args or []

    asyncio.run(bot_lobby.lobby_leave_cmd(FakeUpdate(), FakeContext()))
    assert lobby.find_user_lobby("u1") is None
    assert any("Лобби покинуто" in m for m in messages)


def test_race_blocked_when_in_lobby(monkeypatch):
    lobby.reset_lobbies()
    lid = lobby.create_lobby("track1")
    lobby.join_lobby(lid, "u1", "A", chat_id="c1", mass=1000, power=100)

    messages = []

    class FakeChat:
        async def send_message(self, text, parse_mode=None, reply_markup=None):
            messages.append(text)

    class FakeUpdate:
        effective_chat = FakeChat()
        effective_user = type("U", (), {"id": "u1", "full_name": "A"})()

    called = False

    def fake_run(*a, **k):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(bot, "run_player_race", fake_run)

    asyncio.run(bot.race(FakeUpdate(), None))
    assert called is False
    assert any("лобби" in m for m in messages)
