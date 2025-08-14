from typing import Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from economy_v1 import list_catalog, list_tracks

TIERS = ["starter", "club", "sport", "gt", "hyper"]


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
        ],
    ]


def _with_nav(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    """Append navigation rows to keyboard rows and return markup."""
    return InlineKeyboardMarkup(_nav_menu_rows() + rows)


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu with quick navigation links."""
    return InlineKeyboardMarkup(_nav_menu_rows())


def garage_kb(p, tier: str | None = None, page: int = 1) -> InlineKeyboardMarkup:
    """Keyboard listing player's cars with upgrade buttons, grouped by class."""
    cat = list_catalog()
    tiers = TIERS
    tier = tier or tiers[0]

    rows: List[List[InlineKeyboardButton]] = []
    # class selection buttons
    rows.append([
        InlineKeyboardButton(t.capitalize(), callback_data=f"gar_tier:{t}")
        for t in tiers
    ])

    cars = [cid for cid in p.garage if cat["cars"].get(cid, {}).get("tier") == tier]
    per_page = 10
    start = (page - 1) * per_page
    for cid in cars[start:start + per_page]:
        name = cat["cars"].get(cid, {}).get("name", cid)
        rows.append([InlineKeyboardButton(name, callback_data=f"upgrades:{cid}")])

    total_pages = max(1, (len(cars) + per_page - 1) // per_page)
    if total_pages > 1:
        rows.append([
            InlineKeyboardButton(str(i + 1), callback_data=f"gar_page:{tier}:{i + 1}")
            for i in range(total_pages)
        ])

    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:garage")])
    return _with_nav(rows)


def catalog_kb(cat: Dict, tier: str | None = None, page: int = 1) -> InlineKeyboardMarkup:
    """Keyboard with catalog cars and buy buttons, grouped by class with pagination."""
    tiers = TIERS
    tier = tier or tiers[0]

    rows: List[List[InlineKeyboardButton]] = []
    # class selection buttons
    rows.append([
        InlineKeyboardButton(t.capitalize(), callback_data=f"cat_tier:{t}")
        for t in tiers
    ])

    cars = [
        (cid, item)
        for cid, item in cat["cars"].items()
        if item.get("tier") == tier
    ]
    cars.sort(key=lambda kv: kv[1]["price"])

    per_page = 10
    start = (page - 1) * per_page
    for cid, item in cars[start:start + per_page]:
        label = f"{item['name']} — {fmt_money(item['price'])}"
        rows.append([InlineKeyboardButton(label, callback_data=f"buy:{cid}")])

    total_pages = max(1, (len(cars) + per_page - 1) // per_page)
    if total_pages > 1:
        rows.append([
            InlineKeyboardButton(str(i + 1), callback_data=f"cat_page:{tier}:{i + 1}")
            for i in range(total_pages)
        ])

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
