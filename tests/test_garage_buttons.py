import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from bot_kb import garage_kb
from economy_v1 import list_catalog


def test_garage_keyboard_lists_cars_by_class():
    class P:
        garage = ["lada_2107", "bugatti"]

    kb = garage_kb(P(), tier="starter")
    cat = list_catalog()
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    # ensure refresh and class buttons
    assert "Обновить" in labels
    assert "Starter" in labels
    # only starter-tier car should be listed
    assert cat["cars"]["lada_2107"]["name"] in labels
    assert cat["cars"]["bugatti"]["name"] not in labels
