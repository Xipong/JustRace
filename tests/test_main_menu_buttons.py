import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from bot_kb import main_menu_kb


def test_main_menu_has_buttons():
    kb = main_menu_kb()
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "Справка" in labels
    assert "Гараж" in labels
    assert "Каталог" in labels
    assert "Трассы" in labels
    assert "Водитель" in labels
    assert "Лобби" in labels
    assert "Промокод" in labels
