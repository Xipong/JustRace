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

