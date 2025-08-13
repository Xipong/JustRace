import os, sys, pathlib, pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(autouse=True)
def _prepare(monkeypatch):
    monkeypatch.setenv("GAME_DATA_DIR", str(DATA_DIR))
    if "economy_v1" in sys.modules:
        del sys.modules["economy_v1"]
    yield


def test_buy_car_shows_stats():
    import economy_v1
    p = economy_v1.Player(user_id="1", name="T")
    msg = economy_v1.buy_car(p, "daewoo_matiz_2005")
    assert "Мощность: 38" in msg
    assert "Вес: 800" in msg


def test_car_stats_upgrade_effect():
    import economy_v1
    p = economy_v1.Player(user_id="2", name="T", garage=["lada_2107"], balance=1_000_000)
    before = economy_v1.car_stats(p, "lada_2107")
    economy_v1.buy_upgrade(p, "lada_2107", "custom")
    economy_v1.buy_upgrade(p, "lada_2107", "engine")
    after = economy_v1.car_stats(p, "lada_2107")
    assert after["power"] > before["power"]
    assert after["mass"] < before["mass"]
    assert after["tire_grip"] > before["tire_grip"]
