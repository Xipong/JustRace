import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from bot_kb import garage_kb
from economy_v1 import list_catalog


def test_garage_keyboard_lists_cars():
    class P:
        garage = ["lada_2107", "bugatti"]
    kb = garage_kb(P())
    cat = list_catalog()
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    # ensure refresh button
    assert "Обновить" in labels
    for cid in P.garage:
        name = cat["cars"][cid]["name"]
        assert name in labels
