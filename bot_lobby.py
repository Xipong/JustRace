from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from economy_v1 import load_player
from lobby import create_lobby, join_lobby, leave_lobby, start_lobby_race
from bot import esc, _uid, _uname, send_html


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
        join_lobby(context.args[0], uid, name)
        await send_html(update, f"Присоединился к лобби {esc(context.args[0])}")
    except Exception as e:
        await send_html(update, f"❌ {esc(e)}")


async def lobby_leave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _uid(update)
    if not context.args:
        await send_html(update, "Использование: <code>/lobby_leave &lt;id&gt;</code>")
        return
    leave_lobby(context.args[0], uid)
    await send_html(update, "Лобби покинуто")


async def lobby_start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await send_html(update, "Использование: <code>/lobby_start &lt;id&gt;</code>")
        return
    lid = context.args[0]
    try:
        results = start_lobby_race(lid)
    except Exception as e:
        await send_html(update, f"❌ {esc(e)}")
        return
    lines = [f"🏁 Результаты лобби {esc(lid)}:"]
    for r in results:
        if "error" in r:
            lines.append(f"{esc(r['name'])}: ❌ {esc(r['error'])}")
        else:
            res = r["result"]
            lines.append(f"{esc(r['name'])}: {res['time_s']:.2f}s, инц. {res['incidents']}")
    await send_html(update, "\n".join(lines))


def setup(app: Application) -> None:
    app.add_handler(CommandHandler("lobby_create", lobby_create_cmd))
    app.add_handler(CommandHandler("lobby_join", lobby_join_cmd))
    app.add_handler(CommandHandler("lobby_leave", lobby_leave_cmd))
    app.add_handler(CommandHandler("lobby_start", lobby_start_cmd))
