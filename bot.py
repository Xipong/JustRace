import os, asyncio, html, logging, time
from dataclasses import asdict
from typing import Dict

from dotenv import load_dotenv

load_dotenv()

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.request import HTTPXRequest

from bot_kb import (
    fmt_money,
    main_menu_kb,
    garage_kb,
    catalog_kb,
    tracks_kb,
)
from economy_v1 import (
    load_player,
    list_catalog,
    buy_car,
    set_current_car,
    list_tracks,
    set_current_track,
)
from game_api import run_player_race, get_upgrade_status

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("racing-bot")


def esc(s: object) -> str:
    return html.escape(str(s))

def _uid(update: Update) -> str:
    return str(update.effective_user.id)

def _uname(update: Update) -> str:
    u = update.effective_user
    return (u.full_name or u.username or str(u.id))

def help_text() -> str:
    return (
        "Привет! Доступные команды:\n"
        "<code>/catalog</code> — каталог машин\n"
        "<code>/buy &lt;id&gt;</code> — купить\n"
        "<code>/garage</code> — мой гараж\n"
        "<code>/setcar &lt;id&gt;</code> — выбрать машину\n"
        "<code>/driver</code> — навыки пилота\n"
        "<code>/track</code> — выбрать трассу\n"
        "<code>/settrack &lt;id&gt;</code> — задать трассу\n"
        "<code>/race</code> — начать гонку\n"
        "<code>/upgrades</code> — апгрейды машины\n"
        "<code>/lobby_create</code> — создать лобби"
    )

async def send_html(update: Update, text: str):
    # В HTML-режиме переносы строк — это \n, не <br/>.
    await update.effective_chat.send_message(text, parse_mode=ParseMode.HTML)

# ---- Handlers ----

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    load_player(uid, name)
    await update.effective_chat.send_message(
        help_text(), parse_mode=ParseMode.HTML, reply_markup=main_menu_kb()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(
        help_text(), parse_mode=ParseMode.HTML, reply_markup=main_menu_kb()
    )
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
    cat = list_catalog()
    lines = [f"<b>Баланс:</b> {fmt_money(p.balance)}", "<b>Гараж:</b>"]
    for cid in p.garage:
        name = cat["cars"].get(cid, {}).get("name", cid)
        lines.append(f"- <code>{esc(cid)}</code> — {esc(name)}")
    await update.effective_chat.send_message(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=garage_kb(p)
    )

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
    from models_v2 import DriverProfile
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

async def upgrades_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    p = load_player(uid, name)
    car_id = context.args[0] if context.args else p.current_car
    if not car_id:
        await send_html(update, "Укажи машину: <code>/upgrades &lt;car_id&gt;</code>")
        return
    msg = get_upgrade_status(uid, name, car_id)
    await send_html(update, esc(msg))

async def race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update); name = _uname(update)
    loop = asyncio.get_running_loop()

    def on_evt(evt: Dict):
        etype = evt.get("type")
        msg = None
        if etype == "penalty":
            sev = esc(evt.get("severity", "minor"))
            msg = (
                f"🚫 <b>Пенальти ({sev})</b>\n"
                f"⏱ <i>+{evt['delta_s']:.2f}s</i> на {esc(evt['segment'])}\n"
                f"📉 Нагрузка: {evt['load']:.2f}"
            )
        elif etype == "segment_tick":
            msg = (
                f"🏎️ <b>Круг {evt['lap']}/{evt['laps']}</b>\n"
                f"📍 <b>{esc(evt['segment'])}</b> <i>(ID {evt['segment_id']})</i>\n"
                f"⚡️ <code>{evt['speed']:.1f} км/ч</code>\n"
                f"⏰ <code>{evt['time_s']:.1f} сек</code>\n"
                f"📊 <code>{evt['distance']:.0f}/{evt['segment_length']:.0f} м</code>"
            )
            asyncio.run_coroutine_threadsafe(send_html(update, msg), loop)
            time.sleep(20.0)
            return
        elif etype == "segment_change":
            msg = (
                f"🔁 <b>Новый участок: {esc(evt['segment'])}</b>\n"
                f"⚡️ <code>{evt['speed']:.1f} км/ч</code>\n"
                f"⏰ <code>{evt['time_s']:.1f} сек</code>"
            )
        elif etype == "lap_complete":
            msg = f"🏁 <b>Круг {evt['lap']} завершён</b> — <code>{evt['time_s']:.2f}s</code>"
        elif etype == "race_complete":
            msg = (
                f"🏁 <b>Гонка завершена!</b>\n"
                f"⏱ <code>{evt['time_s']:.2f}s</code>\n"
                f"⚠️ Инцидентов: <code>{evt.get('incidents',0)}</code>"
            )
        elif etype == "skill_up":
            msg = f"📈 <b>{esc(evt['skill'])}</b> +{evt['delta']:.2f} → {evt['new']:.1f}"
        if msg:
            asyncio.run_coroutine_threadsafe(send_html(update, msg), loop)

    try:
        result = await loop.run_in_executor(None, lambda: run_player_race(uid, name, laps=1, on_event=on_evt))
    except Exception as e:
        logger.exception("Race error")
        await send_html(update, f"❌ {esc(e)}")
        return

    await send_html(
        update,
        f"🏆 <b>Итог:</b> ⏱ {result['time_s']:.2f}s | ⚠️ {result['incidents']} | 💰 {fmt_money(result['reward'])}"
    )

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
    elif data == "nav:garage":
        await query.answer()
        await garage(update, context)
    elif data == "nav:help":
        await query.answer()
        await help_cmd(update, context)
    elif data.startswith("upgrades:"):
        await query.answer()
        car_id = data.split(":",1)[1]
        msg = get_upgrade_status(uid, name, car_id)
        await send_html(update, esc(msg))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled error", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_chat:
            await update.effective_chat.send_message("⚠️ Внутренняя ошибка. Попробуй ещё раз позже.")
    except Exception:
        pass

def build_app() -> Application:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("Не задан BOT_TOKEN. Создай .env или экспортируй переменную окружения.")

    # Disable certificate verification and ignore proxy settings from the
    # environment. Some environments (e.g. CI) inject a proxy with a custom
    # certificate which can break TLS handshakes when verifying.
    request = HTTPXRequest(httpx_kwargs={"verify": False, "trust_env": False})
    app = Application.builder().token(token).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("catalog", catalog))
    app.add_handler(CommandHandler("buy", buy_cmd))
    app.add_handler(CommandHandler("garage", garage))
    app.add_handler(CommandHandler("setcar", setcar_cmd))
    app.add_handler(CommandHandler("driver", driver))
    app.add_handler(CommandHandler("track", track_cmd))
    app.add_handler(CommandHandler("settrack", settrack_cmd))
    app.add_handler(CommandHandler("upgrades", upgrades_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("race", race))
    app.add_handler(CallbackQueryHandler(on_callback))
    import bot_lobby
    bot_lobby.setup(app)
    app.add_error_handler(error_handler)
    return app

def main():
    app = build_app()
    print("Bot is ready. Use: python run.py (or python -m scripts.run_bot)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
