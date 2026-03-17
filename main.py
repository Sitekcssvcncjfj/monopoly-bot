import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

import config
import db as DB
from render_board import render_board_png

BOT_TOKEN = os.getenv("BOT_TOKEN")

HELP_TEXT = (
    "<b>🎩 KGB Monopoly Bot - Oyun Rehberi</b>\n\n"
    "<b>Temel Komutlar</b>\n"
    "• /start → Paneli açar\n"
    "• /help → Yardım menüsü\n"
    "• /stats → Kendi istatistiklerin\n"
    "• /top → En iyi oyuncular\n\n"
    "<b>Oyun Sistemi</b>\n"
    "• Yeni Oyun → Yeni lobi oluşturur\n"
    "• Katıl → Oyuna dahil olursun\n"
    "• Başlat → Oyunu başlatır\n"
    "• Zar At → Sıra sende ise oynarsın\n\n"
    "<b>Mülk Sistemi</b>\n"
    "• Boş mülk gelirse satın alabilirsin\n"
    "• İstersen açık artırmaya çıkarabilirsin\n"
    "• Renk seti tamamlanınca kira artar\n"
    "• 4 evden sonra otel kurabilirsin\n\n"
    "<b>İpotek</b>\n"
    "• İpotekli mülk kira üretmez\n"
    "• Çözmek için %10 faiz ödersin\n\n"
    "<b>Takas</b>\n"
    "• Sadece sıradaki oyuncu teklif oluşturabilir\n"
    "• Mülk + para farkı ile teklif yapılabilir\n\n"
    "<b>Açık Artırma</b>\n"
    "• Pas veren oyuncu tekrar teklif veremez\n\n"
    "<b>Zaman Aşımı</b>\n"
    f"• {config.TURN_TIMEOUT_SEC} saniye içinde oynanmazsa bot otomatik oynar\n"
)

def kb_lobby():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Yeni Oyun", callback_data="ng"),
         InlineKeyboardButton("➕ Katıl", callback_data="jn")],
        [InlineKeyboardButton("▶️ Başlat", callback_data="st"),
         InlineKeyboardButton("📊 Durum", callback_data="ss")],
        [InlineKeyboardButton("🆘 Destek", url=config.SUPPORT_URL),
         InlineKeyboardButton("➕ Beni Gruba Ekle", url=config.ADD_BOT_URL)],
        [InlineKeyboardButton("📖 Help", callback_data="hp"),
         InlineKeyboardButton("🛑 Bitir", callback_data="en")],
    ])

def kb_turn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Zar At", callback_data="rl"),
         InlineKeyboardButton("📊 Durum", callback_data="ss")],
        [InlineKeyboardButton("🏠 Mülklerim", callback_data="mp"),
         InlineKeyboardButton("👥 Oyuncular", callback_data="pl")],
        [InlineKeyboardButton("🧱 İnşa", callback_data="bd"),
         InlineKeyboardButton("🏦 İpotek", callback_data="mg")],
        [InlineKeyboardButton("🤝 Takas", callback_data="tr"),
         InlineKeyboardButton("📖 Help", callback_data="hp")],
        [InlineKeyboardButton("🆘 Destek", url=config.SUPPORT_URL),
         InlineKeyboardButton("➕ Gruba Ekle", url=config.ADD_BOT_URL)],
        [InlineKeyboardButton("🛑 Bitir", callback_data="en")],
    ])

def kb_buy(pos: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Satın Al", callback_data=f"buy:{pos}")],
        [InlineKeyboardButton("📢 Açık Artırma", callback_data=f"auc:{pos}")],
        [InlineKeyboardButton("❌ Geç", callback_data=f"pas:{pos}")]
    ])

def kb_build_menu(chat_id: int, user_id: int):
    props = DB.get_properties(chat_id)
    rows = []
    for pos, inf in props.items():
        if inf["owner_id"] == user_id and config.BOARD[pos]["type"] == "property":
            rows.append([InlineKeyboardButton(f"🏗️ {config.BOARD[pos]['name']}", callback_data=f"bdp:{pos}")])
    rows.append([InlineKeyboardButton("⬅️ Geri", callback_data="noop")])
    return InlineKeyboardMarkup(rows)

def kb_build_actions(pos: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Ev Kur", callback_data=f"bh:{pos}"),
         InlineKeyboardButton("🏨 Otel Kur", callback_data=f"bt:{pos}")]
    ])

def kb_mortgage_menu(chat_id: int, user_id: int):
    props = DB.get_properties(chat_id)
    rows = []
    for pos, inf in props.items():
        if inf["owner_id"] == user_id:
            state = "🔒" if inf["mortgaged"] else "💰"
            rows.append([InlineKeyboardButton(f"{state} {config.BOARD[pos]['name']}", callback_data=f"mo:{pos}")])
    rows.append([InlineKeyboardButton("⬅️ Geri", callback_data="noop")])
    return InlineKeyboardMarkup(rows)

def get_current_player(chat_id: int):
    game = DB.get_game(chat_id)
    players = DB.get_players(chat_id)
    if not game or not players:
        return None
    idx = game["turn_idx"]
    if idx >= len(players):
        DB.update_game(chat_id, turn_idx=0)
        return players[0]
    return players[idx]

def next_turn(chat_id: int):
    game = DB.get_game(chat_id)
    players = DB.get_players(chat_id)
    alive_idxs = [i for i, p in enumerate(players) if p["alive"]]
    if len(alive_idxs) <= 1:
        return None
    idx = game["turn_idx"]
    while True:
        idx = (idx + 1) % len(players)
        if players[idx]["alive"]:
            DB.update_game(chat_id, turn_idx=idx)
            return players[idx]

def owner_name(chat_id: int, owner_id: int):
    p = DB.get_player(chat_id, owner_id)
    return p["name"] if p else "Bilinmiyor"

def owns_full_set(chat_id: int, user_id: int, color: str):
    if color not in config.COLOR_GROUPS:
        return False
    props = DB.get_properties(chat_id)
    for pos in config.COLOR_GROUPS[color]:
        if pos not in props or props[pos]["owner_id"] != user_id:
            return False
    return True

def calc_rent(chat_id: int, pos: int):
    tile = config.BOARD[pos]
    props = DB.get_properties(chat_id)
    p = props.get(pos)
    base = tile.get("base_rent", 0)
    if not p:
        return base
    if p["mortgaged"]:
        return 0
    if p["hotel"]:
        return base * 6
    if p["houses"] > 0:
        return base * (p["houses"] + 1)
    if tile["type"] == "property" and owns_full_set(chat_id, p["owner_id"], tile["color"]):
        return base * 2
    return base

def apply_money(chat_id: int, user_id: int, delta: int):
    pl = DB.get_player(chat_id, user_id)
    if not pl:
        return None, None
    new_money = pl["money"] + delta
    if delta > 0:
        DB.add_money_earned(user_id, pl["name"], delta)
    if new_money < 0:
        DB.update_player(chat_id, user_id, money=new_money, alive=0)
        DB.delete_properties_of_player(chat_id, user_id)
        return new_money, f"💀 {pl['name']} iflas etti ve oyundan elendi."
    DB.update_player(chat_id, user_id, money=new_money)
    return new_money, None

def check_winner(chat_id: int):
    alive = [p for p in DB.get_players(chat_id) if p["alive"]]
    if len(alive) == 1:
        return alive[0]
    return None

def build_caption(chat_id: int, chat_title: str = "Grup"):
    game = DB.get_game(chat_id)
    players = DB.get_players(chat_id)

    if not game:
        return "🎩 <b>KGB Monopoly</b>\nPanel bulunamadı."

    text = f"🎩 <b>{chat_title} | KGB Monopoly</b>\n"
    text += "━━━━━━━━━━━━━━━\n"

    if not players:
        text += "Henüz oyuncu yok.\n➕ <b>Katıl</b> butonuyla oyuna dahil olabilirsin."
        return text[:950]

    cur = get_current_player(chat_id)

    text += f"🎮 Durum: <b>{'Oyun Başladı' if game['started'] else 'Lobi Açık'}</b>\n"

    if game["started"] and cur:
        tile = config.BOARD[cur["position"]]["name"]
        text += f"➡️ Sıra: <b>{cur['name']}</b>\n"
        text += f"💰 Bakiye: <b>${cur['money']}</b>\n"
        text += f"📍 Konum: <b>{tile}</b>\n"

    text += "\n👥 <b>Oyuncular</b>\n"
    for p in players[:8]:
        status = "✅" if p["alive"] else "💀"
        text += f"• {status} <b>{p['name']}</b> — ${p['money']}\n"

    if game["last_action"]:
        text += "\n━━━━━━━━━━━━━━━\n"
        text += f"📝 <i>{game['last_action']}</i>"

    return text[:950]

async def ensure_panel_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game:
        return None
    if game["panel_message_id"]:
        return game["panel_message_id"]

    players = DB.get_players(chat_id)
    png = render_board_png(config.BOARD, players)
    msg = await context.bot.send_photo(
        chat_id=chat_id,
        photo=png,
        caption="🎮 Panel hazırlanıyor...",
        parse_mode="HTML"
    )
    DB.update_game(chat_id, panel_message_id=msg.message_id)
    return msg.message_id

async def update_panel(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game:
        return

    mid = await ensure_panel_message(chat_id, context)
    chat = await context.bot.get_chat(chat_id)
    chat_title = getattr(chat, "title", None) or getattr(chat, "full_name", None) or "KGB Monopoly"

    caption = build_caption(chat_id, chat_title)
    keyboard = kb_turn() if game["started"] else kb_lobby()

    players = DB.get_players(chat_id)
    png = render_board_png(config.BOARD, players)

    try:
        media = InputMediaPhoto(media=png, caption=caption, parse_mode="HTML")
        await context.bot.edit_message_media(
            chat_id=chat_id,
            message_id=mid,
            media=media,
            reply_markup=keyboard
        )
    except Exception:
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=mid,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception:
            pass

async def start_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    players = DB.get_players(chat_id)
    if len(players) < 2:
        DB.update_game(chat_id, last_action="Oyunu başlatmak için en az 2 oyuncu gerekli.")
        return

    for p in players:
        DB.add_games_played(p["user_id"], p["name"], 1)

    DB.update_game(chat_id, started=1, turn_idx=0, state="turn", last_action="Oyun başladı! Bol şans.")

async def do_roll(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game or not game["started"]:
        return

    cur = get_current_player(chat_id)
    if not cur or cur["user_id"] != user_id:
        return

    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    total = d1 + d2

    old_pos = cur["position"]
    new_pos = (old_pos + total) % len(config.BOARD)
    money = cur["money"]

    if new_pos < old_pos:
        money += config.GO_BONUS

    DB.update_player(chat_id, user_id, position=new_pos, money=money)

    tile = config.BOARD[new_pos]
    msg = f"{cur['name']} zar attı: {d1}+{d2}={total}. {tile['name']} karesine geldi."

    if tile["type"] in ("property", "railroad", "utility"):
        props = DB.get_properties(chat_id)
        info = props.get(new_pos)

        if info is None:
            DB.update_game(chat_id, state="buy", pending_user=user_id, pending_pos=new_pos, last_action=msg)
            return

        if info["owner_id"] != user_id:
            rent = calc_rent(chat_id, new_pos)
            _, bmsg = apply_money(chat_id, user_id, -rent)
            apply_money(chat_id, info["owner_id"], rent)
            msg += f" ${rent} kira ödedi."
            if bmsg:
                msg += f" {bmsg}"

    elif tile["type"] == "tax":
        _, bmsg = apply_money(chat_id, user_id, -tile["amount"])
        msg += f" ${tile['amount']} vergi ödedi."
        if bmsg:
            msg += f" {bmsg}"

    elif tile["type"] == "chance":
        text, delta = random.choice(config.CHANCE_CARDS)
        _, bmsg = apply_money(chat_id, user_id, delta)
        msg += f" Şans: {text}."
        if bmsg:
            msg += f" {bmsg}"

    elif tile["type"] == "community":
        text, delta = random.choice(config.COMMUNITY_CARDS)
        _, bmsg = apply_money(chat_id, user_id, delta)
        msg += f" Kasa: {text}."
        if bmsg:
            msg += f" {bmsg}"

    DB.update_game(chat_id, last_action=msg, state="turn")

    winner = check_winner(chat_id)
    if winner:
        DB.add_games_won(winner["user_id"], winner["name"], 1)
        win_text = (
            "🏆 <b>OYUN SONA ERDİ</b> 🏆\n\n"
            f"👑 Kazanan: <b>{winner['name']}</b>\n"
            f"💰 Son Bakiye: <b>${winner['money']}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "Yeni bir oyun başlatmak için aşağıdaki menüyü kullanabilirsiniz."
        )
        DB.delete_game(chat_id)
        await context.bot.send_message(chat_id, win_text, parse_mode="HTML", reply_markup=kb_lobby())
        return

    nxt = next_turn(chat_id)
    if nxt:
        DB.update_game(chat_id, last_action=msg + f" Sıradaki oyuncu: {nxt['name']}")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not DB.game_exists(chat_id):
        DB.create_game(chat_id)
    await ensure_panel_message(chat_id, context)
    await update_panel(chat_id, context)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stat = DB.get_stat(user.id)

    if not stat:
        return await update.message.reply_text(
            "📊 Henüz kayıtlı istatistiğin yok.\nBir oyuna katılıp tamamladığında istatistiklerin görünür."
        )

    text = (
        f"📊 <b>{stat['name']} | İstatistikler</b>\n\n"
        f"🎮 Oynanan Oyun: <b>{stat['games_played']}</b>\n"
        f"🏆 Kazanılan Oyun: <b>{stat['games_won']}</b>\n"
        f"💰 Toplam Kazanç: <b>${stat['money_earned']}</b>\n"
    )

    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = DB.top_stats(10)

    if not top:
        return await update.message.reply_text("🏆 Henüz leaderboard oluşmadı.")

    text = "🏆 <b>En İyi Oyuncular</b>\n\n"
    for i, s in enumerate(top, start=1):
        text += (
            f"{i}. <b>{s['name']}</b>\n"
            f"   ├ Kazanma: {s['games_won']}\n"
            f"   ├ Oyun: {s['games_played']}\n"
            f"   └ Kazanç: ${s['money_earned']}\n\n"
        )

    await update.message.reply_text(text, parse_mode="HTML")

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    user_id = q.from_user.id

    if not DB.game_exists(chat_id):
        DB.create_game(chat_id)

    game = DB.get_game(chat_id)
    data = q.data

    if data == "hp":
        await q.message.reply_text(HELP_TEXT, parse_mode="HTML")
        return

    if data == "en":
        DB.delete_game(chat_id)
        await q.message.reply_text("🛑 Oyun kapatıldı. /start ile tekrar açabilirsiniz.")
        return

    if data == "ng":
        DB.create_game(chat_id)
        DB.update_game(chat_id, last_action="Yeni oyun oluşturuldu.")
        await ensure_panel_message(chat_id, context)
        await update_panel(chat_id, context)
        return

    if data == "jn":
        if game["started"]:
            DB.update_game(chat_id, last_action="Oyun başladı; artık katılamazsın.")
        else:
            ok = DB.add_player(chat_id, user_id, q.from_user.first_name, config.START_MONEY)
            DB.update_game(chat_id, last_action=("Oyuna katıldın." if ok else "Zaten oyundasın."))
        await update_panel(chat_id, context)
        return

    if data == "st":
        await start_game(chat_id, context)
        await update_panel(chat_id, context)
        return

    if data == "ss":
        await q.message.reply_text(format_status(chat_id), parse_mode="HTML")
        return

    if data == "pl":
        await q.message.reply_text(format_players(chat_id), parse_mode="HTML")
        return

    if data == "mp":
        await q.message.reply_text(format_my_props(chat_id, user_id), parse_mode="HTML")
        return

    if data == "rl":
        cur = get_current_player(chat_id)
        if not cur or cur["user_id"] != user_id:
            DB.update_game(chat_id, last_action="Sıra sende değil.")
            await update_panel(chat_id, context)
            return
        await do_roll(chat_id, user_id, context)
        await update_panel(chat_id, context)
        return

    if data.startswith("buy:"):
        pos = int(data.split(":")[1])
        game = DB.get_game(chat_id)
        if game["pending_user"] == user_id and game["pending_pos"] == pos:
            player = DB.get_player(chat_id, user_id)
            tile = config.BOARD[pos]
            if player["money"] >= tile["price"]:
                DB.update_player(chat_id, user_id, money=player["money"] - tile["price"])
                DB.set_property_owner(chat_id, pos, user_id)
                nxt = next_turn(chat_id)
                DB.update_game(chat_id, state="turn", pending_user=None, pending_pos=None,
                               last_action=f"{player['name']} {tile['name']} mülkünü satın aldı. Sıradaki: {nxt['name']}")
        await update_panel(chat_id, context)
        return

    if data.startswith("pas:"):
        pos = int(data.split(":")[1])
        game = DB.get_game(chat_id)
        if game["pending_user"] == user_id and game["pending_pos"] == pos:
            nxt = next_turn(chat_id)
            DB.update_game(chat_id, state="turn", pending_user=None, pending_pos=None,
                           last_action=f"{config.BOARD[pos]['name']} satın alınmadı. Sıradaki: {nxt['name']}")
        await update_panel(chat_id, context)
        return

def format_players(chat_id: int):
    ps = DB.get_players(chat_id)
    t = "<b>👥 Oyuncular</b>\n\n"
    for p in ps:
        st = "✅" if p["alive"] else "💀"
        t += f"• <b>{p['name']}</b> | ${p['money']} | {st}\n"
    return t

def format_my_props(chat_id: int, user_id: int):
    props = DB.get_properties(chat_id)
    my = [pos for pos, inf in props.items() if inf["owner_id"] == user_id]
    if not my:
        return "🏠 Mülkün yok."
    t = "<b>🏠 Mülklerin</b>\n\n"
    for pos in my:
        inf = props[pos]
        extra = ""
        if inf["mortgaged"]:
            extra += " 🔒"
        if inf["hotel"]:
            extra += " 🏨"
        elif inf["houses"]:
            extra += f" 🏠x{inf['houses']}"
        t += f"• {config.BOARD[pos]['name']} | kira ${calc_rent(chat_id, pos)}{extra}\n"
    return t

def format_status(chat_id: int):
    game = DB.get_game(chat_id)
    ps = DB.get_players(chat_id)
    cur = get_current_player(chat_id)
    t = "<b>📊 Oyun Durumu</b>\n\n"
    if cur and game and game["started"]:
        t += f"➡️ Sıra: <b>{cur['name']}</b>\n\n"
    for p in ps:
        tile = config.BOARD[p["position"]]["name"]
        st = "✅" if p["alive"] else "💀"
        t += f"• {p['name']} | ${p['money']} | {tile} | {st}\n"
    return t

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable eksik.")

    DB.init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CallbackQueryHandler(on_button))

    print("KGB Monopoly Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
