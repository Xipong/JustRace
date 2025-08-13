from typing import Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from economy_v1 import list_catalog, list_tracks


def fmt_money(v: int) -> str:
    """Format integer value with spaces for thousands."""
    return f"{v:,}".replace(",", " ")


def _nav_menu_rows() -> List[List[InlineKeyboardButton]]:
    """Standard navigation buttons shown on every screen."""
    return [
        [
            InlineKeyboardButton("Справка", callback_data="nav:help"),
            InlineKeyboardButton("Гараж", callback_data="nav:garage"),
        ],
        [
            InlineKeyboardButton("Каталог", callback_data="nav:catalog"),
            InlineKeyboardButton("Трассы", callback_data="nav:tracks"),
        ],
        [
            InlineKeyboardButton("Водитель", callback_data="nav:driver"),
            InlineKeyboardButton("Лобби", callback_data="nav:lobby"),


def _with_nav(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    """Append navigation rows to keyboard rows and return markup."""
    return InlineKeyboardMarkup(_nav_menu_rows() + rows)


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu with quick navigation links."""
    return InlineKeyboardMarkup(_nav_menu_rows())


def garage_kb(p) -> InlineKeyboardMarkup:
    """Keyboard listing player's cars with upgrade buttons."""
    cat = list_catalog()
    rows = []
    for cid in p.garage:
        name = cat["cars"].get(cid, {}).get("name", cid)
        rows.append([InlineKeyboardButton(name, callback_data=f"upgrades:{cid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:garage")])
    return _with_nav(rows)


def catalog_kb(cat: Dict) -> InlineKeyboardMarkup:
    """Keyboard with catalog cars and buy buttons."""
    rows = []
    cars = sorted(cat["cars"].items(), key=lambda kv: kv[1]["price"])[:12]
    for cid, item in cars:
        label = f"{item['name']} — {fmt_money(item['price'])}"
        rows.append([InlineKeyboardButton(label, callback_data=f"buy:{cid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:catalog")])
    return _with_nav(rows)


def tracks_kb() -> InlineKeyboardMarkup:
    """Keyboard listing available tracks."""
    rows = []
    for tid, name in list(list_tracks().items())[:12]:
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"settrack:{tid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:tracks")])
    return _with_nav(rows)


def upgrade_parts_kb(car_id: str, parts: list) -> InlineKeyboardMarkup:
    """Keyboard with available upgrade parts for the car."""
    rows = []
    for part in parts:
        rows.append([InlineKeyboardButton(part["name"], callback_data=f"buyupg:{car_id}:{part['id']}")])
    rows.append([InlineKeyboardButton("Назад", callback_data="nav:garage")])
    return _with_nav(rows)


def driver_kb() -> InlineKeyboardMarkup:
    """Keyboard for driver profile actions."""
    rows = [[InlineKeyboardButton("Ввести бонускод", callback_data="nav:bonus")]]
    return _with_nav(rows)


def lobby_main_kb(lobby_id: str | None = None, is_host: bool = False) -> InlineKeyboardMarkup:
    """Keyboard for lobby view and actions."""
    rows: List[List[InlineKeyboardButton]] = []
    if lobby_id:
        rows.append([InlineKeyboardButton("Выйти", callback_data=f"lobby_leave:{lobby_id}")])
        rows.append([InlineKeyboardButton("Обновить", callback_data="nav:lobby")])
    else:
        rows.append([InlineKeyboardButton("Создать лобби", callback_data="lobby_create")])
        rows.append([InlineKeyboardButton("Обновить", callback_data="nav:lobby")])
    return _with_nav(rows)
