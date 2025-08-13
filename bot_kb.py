from typing import Dict
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from economy_v1 import list_catalog, list_tracks


def fmt_money(v: int) -> str:
    """Format integer value with spaces for thousands."""
    return f"{v:,}".replace(",", " ")


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu with quick navigation links."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Справка", callback_data="nav:help"),
            InlineKeyboardButton("Гараж", callback_data="nav:garage"),
        ],
        [
            InlineKeyboardButton("Каталог", callback_data="nav:catalog"),
            InlineKeyboardButton("Трассы", callback_data="nav:tracks"),
        ],
    ])


def garage_kb(p) -> InlineKeyboardMarkup:
    """Keyboard listing player's cars with upgrade buttons."""
    cat = list_catalog()
    rows = []
    for cid in p.garage:
        name = cat["cars"].get(cid, {}).get("name", cid)
        rows.append([InlineKeyboardButton(name, callback_data=f"upgrades:{cid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:garage")])
    return InlineKeyboardMarkup(rows)


def catalog_kb(cat: Dict) -> InlineKeyboardMarkup:
    """Keyboard with catalog cars and buy buttons."""
    rows = []
    cars = sorted(cat["cars"].items(), key=lambda kv: kv[1]["price"])[:12]
    for cid, item in cars:
        label = f"{item['name']} — {fmt_money(item['price'])}"
        rows.append([InlineKeyboardButton(label, callback_data=f"buy:{cid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:catalog")])
    return InlineKeyboardMarkup(rows)


def tracks_kb() -> InlineKeyboardMarkup:
    """Keyboard listing available tracks."""
    rows = []
    for tid, name in list(list_tracks().items())[:12]:
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"settrack:{tid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:tracks")])
    return InlineKeyboardMarkup(rows)
