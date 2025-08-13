import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from bot_kb import driver_kb


def test_driver_has_bonus_button():
    kb = driver_kb()
    labels = [btn.text for row in kb.inline_keyboard for btn in row]
    assert "Ввести бонускод" in labels
