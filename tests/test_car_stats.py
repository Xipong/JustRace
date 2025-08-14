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
    cid = "daewoo_matiz_2005"
    p = economy_v1.Player(user_id="2", name="T", garage=[cid], balance=1_000_000)
    before = economy_v1.car_stats(p, cid)
    economy_v1.buy_upgrade(p, cid, "custom")
    economy_v1.buy_upgrade(p, cid, "engine")
    after = economy_v1.car_stats(p, cid)
    assert after["power"] > before["power"]
    assert after["mass"] == pytest.approx(before["mass"])
    assert after["tire_grip"] == pytest.approx(before["tire_grip"])
    assert after["engine_volume"] > before["engine_volume"]


def test_upgrade_individual_effects():
    import economy_v1
    cid = "daewoo_matiz_2005"
    p = economy_v1.Player(user_id="3", name="T", garage=[cid], balance=1_000_000)
    economy_v1.buy_upgrade(p, cid, "custom")
    before = economy_v1.car_stats(p, cid)
    economy_v1.buy_upgrade(p, cid, "weight")
    after_weight = economy_v1.car_stats(p, cid)
    assert after_weight["mass"] < before["mass"]
    assert after_weight["power"] == pytest.approx(before["power"])
    economy_v1.buy_upgrade(p, cid, "tires")
    after_tires = economy_v1.car_stats(p, cid)
    assert after_tires["tire_grip"] > after_weight["tire_grip"]


def test_high_level_parts_more_effective():
    import economy_v1
    cid = "daewoo_matiz_2005"
    p = economy_v1.Player(user_id="4", name="T", garage=[cid], balance=1_000_000)

    economy_v1.buy_upgrade(p, cid, "custom")
    before_lvl0 = economy_v1.car_stats(p, cid)
    economy_v1.buy_upgrade(p, cid, "engine")
    after_lvl0 = economy_v1.car_stats(p, cid)
    ratio_lvl0 = after_lvl0["power"] / before_lvl0["power"]

    for part in economy_v1.UPGRADE_PARTS:
        if part != "engine":
            economy_v1.buy_upgrade(p, cid, part)
    economy_v1.buy_upgrade(p, cid, "custom")
    before_lvl1 = economy_v1.car_stats(p, cid)
    economy_v1.buy_upgrade(p, cid, "engine")
    after_lvl1 = economy_v1.car_stats(p, cid)
    ratio_lvl1 = after_lvl1["power"] / before_lvl1["power"]

    assert ratio_lvl1 > ratio_lvl0
