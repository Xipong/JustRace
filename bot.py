import os, asyncio, html, logging
from dataclasses import asdict
from typing import Dict, List
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from .economy_v1 import load_player, list_catalog, buy_car, set_current_car, list_tracks, set_current_track
from .game_api import run_player_race

DATA_DIR = Path(os.getenv("GAME_DATA_DIR", "./data"))
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("racing-bot")

def esc(s: object) -> str:
    return html.escape(str(s))

def fmt_money(v: int) -> str:
    return f"{v:,}".replace(",", " ")

def _uid(update: Update) -> str:
    return str(update.effective_user.id)

def _uname(update: Update) -> str:
    u = update.effective_user
    return (u.full_name or u.username or str(u.id))

def catalog_kb(cat: Dict) -> InlineKeyboardMarkup:
    rows = []
    cars = sorted(cat["cars"].items(), key=lambda kv: kv[1]["price"])[:12]
    for cid, item in cars:
        label = f"{item['name']} — {fmt_money(item['price'])}"
        rows.append([InlineKeyboardButton(label, callback_data=f"buy:{cid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:catalog")])
    return InlineKeyboardMarkup(rows)

def tracks_kb() -> InlineKeyboardMarkup:
    rows = []
    for tid, name in list(list_tracks().items())[:12]:
        rows.append([InlineKeyboardButton(f"{name}", callback_data=f"settrack:{tid}")])
    rows.append([InlineKeyboardButton("Обновить", callback_data="nav:tracks")])
    return InlineKeyboardMarkup(rows)

async def send_html(update: Update, text: str):
    # В HTML-режиме переносы строк — это \n, не <br/>.
    await update.effective_chat.send_message(text, parse_mode=ParseMode.HTML)

# ---- Handlers ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    load_player(uid, name)
    msg = (
        "Привет! Доступные команды:\n"
        "<code>/catalog</code> — каталог машин\n"
        "<code>/buy &lt;id&gt;</code> — купить\n"
        "<code>/garage</code> — мой гараж\n"
        "<code>/setcar &lt;id&gt;</code> — выбрать машину\n"
        "<code>/driver</code> — навыки пилота\n"
        "<code>/track</code> — выбрать трассу\n"
        "<code>/settrack &lt;id&gt;</code> — задать трассу\n"
        "<code>/race</code> — начать гонку"
    )
    await send_html(update, msg)
async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat = list_catalog()
    if not cat["cars"]:
        await send_html(update, "Каталог пуст. Залей JSON-файлы машин в <code>data/cars</code>.")
        return
    lines = ["<b>Каталог:</b>"]
    for cid, item in sorted(cat["cars"].items(), key=lambda kv: kv[1]['price']):
        lines.append(f"<code>{esc(cid)}</code> — {esc(item['name'])}: {fmt_money(item['price'])}")
    await update.effective_chat.send_message(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=catalog_kb(cat)
    )

async def buy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    p = load_player(uid, name)
    if not context.args:
        await send_html(update, "Использование: <code>/buy &lt;car_id&gt;</code> (см. /catalog)")
        return
    car_id = context.args[0]
    msg = buy_car(p, car_id)
    await send_html(update, esc(msg))

async def garage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    p = load_player(uid, name)
    if not p.garage:
        await update.effective_chat.send_message(
            "Гараж пуст. Открой каталог и купи машину.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Каталог", callback_data="nav:catalog")]])
        )
        return
    lines = [f"<b>Баланс:</b> {fmt_money(p.balance)}", "<b>Гараж:</b>"] + [f"- <code>{esc(cid)}</code>" for cid in p.garage]
    await send_html(update, "\n".join(lines))

async def setcar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    p = load_player(uid, name)
    if not context.args:
        await send_html(update, "Использование: <code>/setcar &lt;car_id&gt;</code>")
        return
    await send_html(update, esc(set_current_car(p, context.args[0])))

async def driver(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    p = load_player(uid, name)
    if not p.driver_json:
        await send_html(update, "Профиль пилота появится после первой гонки (<code>/race</code>).")
        return
    from .models_v2 import DriverProfile
    d = DriverProfile.from_json(p.driver_json)
    skills = asdict(d)
    lines = ["<b>Навыки пилота:</b>"]
    for k in ["braking","consistency","stress","throttle","cornering","starts"]:
        if k in skills:
            lines.append(f"{esc(k.capitalize())}: {skills[k]:.1f}")
    await send_html(update, "\n".join(lines))

async def track_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message("<b>Выбор трассы:</b>", parse_mode=ParseMode.HTML, reply_markup=tracks_kb())

async def settrack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    p = load_player(uid, name)
    if not context.args:
        await send_html(update, "Использование: <code>/settrack &lt;track_id&gt;</code> (см. /track)")
        return
    await send_html(update, esc(set_current_track(p, context.args[0])))

async def race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    events: List[Dict] = []

    def on_evt(evt: Dict):
        events.append(evt)

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, lambda: run_player_race(uid, name, laps=1, on_event=on_evt))
    except Exception as e:
        logger.exception("Race error")
        await send_html(update, f"❌ {esc(e)}")
        return

    for evt in events:
        t = evt.get("type")
        if t == "penalty":
            sev = esc(evt.get("severity", "minor"))
            await send_html(update, f"⚠️ Пенальти ({sev}): +{evt['delta_s']:.2f}s на {esc(evt['segment'])} (нагрузка {evt['load']:.2f})")
        elif t == "segment_change":
            await send_html(update, f"➡️ {esc(evt['segment'])}")
        elif t == "lap_complete":
            await send_html(update, f"🏁 Круг {evt['lap']} — {evt['time_s']:.2f}s")
        elif t == "race_complete":
            await send_html(update, f"🏁 Гонка — {evt['time_s']:.2f}s, инцидентов: {evt.get('incidents',0)}")
        elif t == "skill_up":
            await send_html(update, f"📈 {esc(evt['skill'])} +{evt['delta']:.2f} → {evt['new']:.1f}")

    await send_html(update, f"<b>Итог:</b> время {result['time_s']:.2f}s, инцидентов {result['incidents']}, награда {fmt_money(result['reward'])}")

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data:
        return
    data = query.data
    uid = _uid(update); name = _uname(update)
    if data == "nav:catalog":
        await query.answer()
        await catalog(update, context)
    elif data.startswith("buy:"):
        await query.answer()
        p = load_player(uid, name)
        await send_html(update, esc(buy_car(p, data.split(":",1)[1])))
    elif data == "nav:tracks":
        await query.answer()
        await track_cmd(update, context)
    elif data.startswith("settrack:"):
        await query.answer()
        p = load_player(uid, name)
        await send_html(update, esc(set_current_track(p, data.split(":",1)[1])))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await update.effective_chat.send_message("⚠️ Внутренняя ошибка. Попробуй ещё раз позже.")
    except Exception:
        pass

def build_app() -> Application:
    token = BOT_TOKEN or os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN. Создай .env или экспортируй переменную окружения.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", catalog))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("garage", garage))
    app.add_handler(CommandHandler("setcar", setcar_cmd))
    app.add_handler(CommandHandler("driver", driver))
    app.add_handler(CommandHandler("track", track_cmd))
    app.add_handler(CommandHandler("settrack", settrack_cmd))
    app.add_handler(CommandHandler("race", race))
    app.add_handler(CallbackQueryHandler(on_callback))
    from . import bot_lobby
    bot_lobby.setup(app)
    app.add_error_handler(error_handler)
    return app

def main():
    app = build_app()
    print("Bot is ready. Use: python run.py (or python -m scripts.run_bot)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
