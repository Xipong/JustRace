import os, sys, importlib, pathlib
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# ensure modules use repository data directory
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
os.environ["GAME_DATA_DIR"] = str(DATA_DIR)
import economy_v1
importlib.reload(economy_v1)
from bot_kb import upgrade_parts_kb
import pytest


@pytest.fixture(autouse=True)
def _reload_modules():
    import economy_v1 as _e
    importlib.reload(_e)


def test_upgrade_menu_has_custom_button():
    p = economy_v1.Player(user_id="1", name="T", garage=["lada_2107"])
    parts = economy_v1.available_parts(p, "lada_2107")
    assert parts and parts[0]["id"] == "custom"
    kb = upgrade_parts_kb("lada_2107", parts)
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert parts[0]["name"] in labels


def test_custom_then_generic_parts():
    p = economy_v1.Player(user_id="2", name="T", garage=["lada_2107"])
    economy_v1.buy_upgrade(p, "lada_2107", "custom")
    parts = economy_v1.available_parts(p, "lada_2107")
    ids = {part["id"] for part in parts}
    assert "engine" in ids
    for part in parts:
        assert "desc" in part


def test_upgrade_price_constant_within_level():
    p = economy_v1.Player(user_id="3", name="T", garage=["lada_2107"])
    cat = economy_v1.list_catalog()
    price = cat["cars"]["lada_2107"]["price"]
    custom_cost = economy_v1.upgrade_cost(price, 0, "custom", "lada_2107")
    engine_cost = economy_v1.upgrade_cost(price, 0, "engine", "lada_2107")
    turbo_cost = economy_v1.upgrade_cost(price, 0, "turbo", "lada_2107")

    msg = economy_v1.buy_upgrade(p, "lada_2107", "custom")
    assert economy_v1.fmt_money(custom_cost) in msg

    first = economy_v1.buy_upgrade(p, "lada_2107", "engine")
    assert economy_v1.fmt_money(engine_cost) in first

    second = economy_v1.buy_upgrade(p, "lada_2107", "turbo")
    assert economy_v1.fmt_money(turbo_cost) in second


def test_upgrade_price_increases_next_level():
    p = economy_v1.Player(user_id="4", name="T", garage=["lada_2107"])
    cat = economy_v1.list_catalog()
    price = cat["cars"]["lada_2107"]["price"]
    lvl0_custom = economy_v1.upgrade_cost(price, 0, "custom", "lada_2107")
    lvl0_engine = economy_v1.upgrade_cost(price, 0, "engine", "lada_2107")

    economy_v1.buy_upgrade(p, "lada_2107", "custom")
    for part_id in economy_v1.UPGRADE_PARTS:
        economy_v1.buy_upgrade(p, "lada_2107", part_id)

    lvl1_custom = economy_v1.upgrade_cost(price, 1, "custom", "lada_2107")
    assert lvl1_custom > lvl0_custom
    msg = economy_v1.buy_upgrade(p, "lada_2107", "custom")
    assert economy_v1.fmt_money(lvl1_custom) in msg

    lvl1_engine = economy_v1.upgrade_cost(price, 1, "engine", "lada_2107")
    assert lvl1_engine > lvl0_engine
    msg_part = economy_v1.buy_upgrade(p, "lada_2107", "engine")
    assert economy_v1.fmt_money(lvl1_engine) in msg_part


def test_part_costs_vary():
    cat = economy_v1.list_catalog()
    price = cat["cars"]["lada_2107"]["price"]
    ecu_cost = economy_v1.upgrade_cost(price, 0, "ecu", "lada_2107")
    engine_cost = economy_v1.upgrade_cost(price, 0, "engine", "lada_2107")
    intake_cost = economy_v1.upgrade_cost(price, 0, "intake", "lada_2107")
    exhaust_cost = economy_v1.upgrade_cost(price, 0, "exhaust", "lada_2107")
    assert ecu_cost < engine_cost
    assert intake_cost > exhaust_cost


def test_car_specific_multiplier_overrides_default():
    cat = economy_v1.list_catalog()
    price = cat["cars"]["lada_2107"]["price"]
    default_ecu = economy_v1.upgrade_cost(price, 0, "ecu")
    lada_ecu = economy_v1.upgrade_cost(price, 0, "ecu", "lada_2107")
    lvl_mult = economy_v1.UPGRADE_LEVEL_COST_MULTS[0]
    mult = economy_v1._car_upgrade_mults("lada_2107").get("ecu", 1.0)
    expected = economy_v1.round_price(price * economy_v1.UPGRADE_BASE_COST_MULT * lvl_mult * mult)
    assert lada_ecu == expected
    assert lada_ecu < default_ecu


def test_prices_are_rounded():
    cat = economy_v1.list_catalog()
    price = cat["cars"]["lada_2107"]["price"]
    assert price % 10 == 0
    cost = economy_v1.upgrade_cost(price, 0, "engine", "lada_2107")
    assert cost % 10 == 0
    # ensure half values round upwards
    assert economy_v1.round_price(65) == 70
    assert economy_v1.round_price(64) == 60


def test_mass_tradeoffs():
    p = economy_v1.Player(user_id="5", name="T", garage=["lada_2107"])
    base = economy_v1.car_stats(p, "lada_2107")
    economy_v1.buy_upgrade(p, "lada_2107", "custom")
    custom_stats = economy_v1.car_stats(p, "lada_2107")
    economy_v1.buy_upgrade(p, "lada_2107", "turbo")
    turbo_stats = economy_v1.car_stats(p, "lada_2107")
    assert turbo_stats["mass"] > custom_stats["mass"]
    assert turbo_stats["mass"] < base["mass"]
    economy_v1.buy_upgrade(p, "lada_2107", "exhaust")
    exhaust_stats = economy_v1.car_stats(p, "lada_2107")
    assert exhaust_stats["mass"] < turbo_stats["mass"]

