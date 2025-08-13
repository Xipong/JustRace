from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes
from typing import Dict, List, Callable
import asyncio
import time
from collections import defaultdict

from economy_v1 import load_player
from game_api import load_car_by_id
from lobby import (
    create_lobby,
    join_lobby,
    leave_lobby,
    start_lobby_race,
    LOBBIES,
    find_user_lobby,
)
from bot_kb import lobby_main_kb
from bot import _uid, _uname, send_html, esc


async def broadcast_lobby_state(lobby_id: str, bot) -> None:
    if not bot:
        return
    lobby_info = LOBBIES.get(lobby_id)
    if not lobby_info:
        return
    lines = [f"<b>Лобби {esc(lobby_id)}</b>"]
    players = lobby_info.get("players", [])
    for p in players:
        car = p.get("car", "?")
        lines.append(f"- {esc(p['name'])} — {esc(car)}")
    msg = "\n".join(lines)
    for p in players:
        is_host = players[0]["user_id"] == p["user_id"] if players else False
        await bot.send_message(
            int(p["chat_id"]),
            msg,
            parse_mode=ParseMode.HTML,
            reply_markup=lobby_main_kb(lobby_id, is_host),
        )

async def lobby_create_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    name = _uname(update)
    p = load_player(uid, name)
    track_id = context.args[0] if context.args else p.current_track
    if not track_id:
        await send_html(update, "Укажи трассу: <code>/lobby_create &lt;track_id&gt;</code>")
        return
    lid = create_lobby(track_id)
    await send_html(
        update,
        f"Лобби <code>{esc(lid)}</code> создано для трассы {esc(track_id)}. Подключайся: /lobby_join {esc(lid)}",
    )


async def lobby_join_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    name = _uname(update)
    if not context.args:
        await send_html(update, "Использование: <code>/lobby_join &lt;id&gt;</code>")
        return
    try:
        p = load_player(uid, name)
        if not p.current_car:
            await send_html(update, "Сначала выбери машину: /garage")
            return
        car = load_car_by_id(p.current_car)
        chat_id = str(update.effective_chat.id)
        join_lobby(
            context.args[0],
            uid,
            name,
            chat_id=chat_id,
            mass=car.mass,
            power=car.power,
            car=car.name,
        )
        lid = context.args[0]
        await send_html(update, f"Присоединился к лобби {esc(lid)}")
        await broadcast_lobby_state(lid, getattr(context, "bot", None))
    except Exception as e:
        await send_html(update, f"❌ {esc(e)}")


async def lobby_leave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    lid = context.args[0] if context.args else find_user_lobby(uid)
    if not lid:
        await send_html(update, "Ты не в лобби")
        return
    leave_lobby(lid, uid)
    await send_html(update, "Лобби покинуто")
    await broadcast_lobby_state(lid, getattr(context, "bot", None))


async def lobby_start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await send_html(update, "Использование: <code>/lobby_start &lt;id&gt;</code>")
        return
    lid = context.args[0]
    lobby_info = LOBBIES.get(lid, {})
    player_stats = lobby_info.get("players", [])
    if uid not in [p["user_id"] for p in player_stats]:
        await send_html(update, "Сначала присоединись к лобби")
        return

    groups: Dict[str, List[Dict]] = {}
    for p in player_stats:
        groups.setdefault(p.get("chat_id", p["user_id"]), []).append(p)

    def _to_chat_id(x):
        try:
            return int(x)
        except (TypeError, ValueError):
            return x

    def tag(p: Dict) -> str:
        return f'<a href="tg://user?id={p["user_id"]}">{esc(p["name"])}</a>'

    tags_all = " ".join(tag(p) for p in player_stats)
    for p in player_stats:
        await context.bot.send_message(
            _to_chat_id(p["user_id"]),
            f"🏁 Гонка началась: {tags_all}",
            parse_mode=ParseMode.HTML,
        )

    loop = asyncio.get_running_loop()
    prev: Dict[str, float] = defaultdict(float)

    def on_evt(evt: Dict) -> None:
        uid = evt.get("user_id")
        etype = evt.get("type")
        msg = None
        if etype == "segment_change":
            msg = (
                f"➡️ {esc(evt['name'])}: Новый участок {esc(evt['segment'])} "
                f"🚀{evt['speed']:.1f} км/ч ⏱{evt['time_s']:.1f} сек"
            )
        elif etype == "penalty":
            msg = (
                f"🚫 {esc(evt['name'])} penalty {esc(evt.get('severity','minor'))}"
                f"+{evt['delta_s']:.2f}s on {esc(evt['segment'])}"
            )
        elif etype == "lap_complete":
            msg = (
                f"🏁 {esc(evt['name'])} завершил круг {evt['lap']} "
                f"за {evt['time_s']:.2f}s"
            )
        elif etype == "race_complete":
            msg = f"🏁 {esc(evt['name'])} финишировал за {evt['time_s']:.2f}s"
        if msg and uid:
            asyncio.run_coroutine_threadsafe(
                context.bot.send_message(_to_chat_id(uid), msg, parse_mode=ParseMode.HTML),
                loop,
            )
        if uid is not None and "time_s" in evt:
            delay = max(0.0, evt["time_s"] - prev[uid])
            prev[uid] = evt["time_s"]
            time.sleep(min(delay, 5.0))

    try:
        results = await loop.run_in_executor(None, lambda: start_lobby_race(lid, on_event=on_evt))
    except Exception as e:
        await send_html(update, f"❌ {esc(e)}")
        return

    finished = [r for r in results if "result" in r]
    finished.sort(key=lambda r: r["result"]["time_s"])
    winner_time = finished[0]["result"]["time_s"] if finished else 0.0

    lines = [f"🏁 Результаты лобби {esc(lid)}:"]
    for pos, r in enumerate(finished, 1):
        info = next((p for p in player_stats if p["user_id"] == r["user_id"]), {})
        delta = r["result"]["time_s"] - winner_time
        diff = "лидер" if delta <= 0.0001 else f"+{delta:.2f}s"
        lines.append(
            f"{pos}. {esc(r['name'])}: {r['result']['time_s']:.2f}s ({diff}) ⚖️{info.get('mass',0):.0f}кг 🐎{info.get('power',0):.0f}"
        )

    for r in results:
        if "error" in r:
            lines.append(f"{esc(r['name'])}: ❌ {esc(r['error'])}")

    message = "\n".join(lines)
    for chat_id in groups.keys():
        await context.bot.send_message(_to_chat_id(chat_id), message, parse_mode=ParseMode.HTML)


def setup(app: Application) -> None:
    app.add_handler(CommandHandler("lobby_create", lobby_create_cmd))
    app.add_handler(CommandHandler("lobby_join", lobby_join_cmd))
    app.add_handler(CommandHandler("lobby_leave", lobby_leave_cmd))
    app.add_handler(CommandHandler("lobby_start", lobby_start_cmd))
