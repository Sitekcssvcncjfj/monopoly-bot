import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest

import config
import db as DB
from render_board import render_board_png

BOT_TOKEN = os.getenv("BOT_TOKEN")

HELP_TEXT = (
    "🎩 <b>KGB Monopoly Bot - Rehber</b>\n\n"
    "━━━━━━━━━━━━━━━\n"
    "<b>Komutlar</b>\n"
    "• /start → Panel aç\n"
    "• /help → Bu mesaj\n"
    "• /stats → İstatistiklerin\n"
    "• /top → En iyi oyuncular\n\n"
    "<b>Nasıl Oynanır?</b>\n"
    "1️⃣ Yeni Oyun butonuna bas\n"
    "2️⃣ Herkes Katıl butonuna bassın\n"
    "3️⃣ Başlat butonuna bas\n"
    "4️⃣ Sıra kimdeyse Zar At bassın\n\n"
    "<b>Mülkler</b>\n"
    "• Boş mülke gelince satın al veya açık artırma\n"
    "• Aynı renkten tüm mülkleri topla → kira 2x\n"
    "• 4 ev → otel → çok yüksek kira\n\n"
    "<b>İpotek</b>\n"
    "• Paran bitince mülkü ipotek et\n"
    "• Geri almak için %10 faiz ödersin\n\n"
    "<b>Takas</b>\n"
    "• Sıra sendeyken takas teklif edebilirsin\n"
    "• Mülk + para farkı ile değiş tokuş\n\n"
    "<b>Açık Artırma</b>\n"
    "• Pas veren tekrar teklif veremez\n"
    "• Son kalan mülkü alır\n\n"
    "<b>Zaman Aşımı</b>\n"
    f"• {config.TURN_TIMEOUT_SEC}sn oynamazsan bot otomatik oynar"
)


# ==================== KLAVYELER ====================

def kb_lobby():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Yeni Oyun", callback_data="ng"),
         InlineKeyboardButton("➕ Katıl", callback_data="jn")],
        [InlineKeyboardButton("▶️ Başlat", callback_data="st"),
         InlineKeyboardButton("📊 Durum", callback_data="ss")],
        [InlineKeyboardButton("📖 Yardım", callback_data="hp"),
         InlineKeyboardButton("🛑 Bitir", callback_data="en")],
        [InlineKeyboardButton("🆘 Destek", url=config.SUPPORT_URL),
         InlineKeyboardButton("➕ Gruba Ekle", url=config.ADD_BOT_URL)],
    ])

def kb_turn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Zar At", callback_data="rl"),
         InlineKeyboardButton("📊 Durum", callback_data="ss")],
        [InlineKeyboardButton("🏠 Mülklerim", callback_data="mp"),
         InlineKeyboardButton("👥 Oyuncular", callback_data="pl")],
        [InlineKeyboardButton("🧱 İnşa Et", callback_data="bd"),
         InlineKeyboardButton("🏦 İpotek", callback_data="mg")],
        [InlineKeyboardButton("🤝 Takas Teklif Et", callback_data="tr")],
        [InlineKeyboardButton("📖 Yardım", callback_data="hp"),
         InlineKeyboardButton("🛑 Bitir", callback_data="en")],
        [InlineKeyboardButton("🆘 Destek", url=config.SUPPORT_URL),
         InlineKeyboardButton("➕ Gruba Ekle", url=config.ADD_BOT_URL)],
    ])

def kb_buy(pos):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Satın Al", callback_data=f"buy:{pos}")],
        [InlineKeyboardButton("📢 Açık Artırmaya Çıkar", callback_data=f"auc:{pos}")],
        [InlineKeyboardButton("❌ Geç", callback_data=f"pas:{pos}")],
    ])

def kb_build(chat_id, user_id):
    props = DB.get_properties(chat_id)
    rows = []
    for pos, inf in props.items():
        if inf["owner_id"] == user_id and config.BOARD[pos]["type"] == "property":
            tile = config.BOARD[pos]
            rows.append([InlineKeyboardButton(
                f"🏗️ {tile['name']} (ev:{inf['houses']} otel:{'✓' if inf['hotel'] else '✗'})",
                callback_data=f"bdp:{pos}"
            )])
    if not rows:
        rows.append([InlineKeyboardButton("📭 İnşa edilecek mülk yok", callback_data="noop")])
    rows.append([InlineKeyboardButton("⬅️ Geri", callback_data="noop")])
    return InlineKeyboardMarkup(rows)

def kb_build_actions(pos):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Ev Kur", callback_data=f"bh:{pos}"),
         InlineKeyboardButton("🏨 Otel Kur", callback_data=f"bt:{pos}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="bd")],
    ])

def kb_mortgage(chat_id, user_id):
    props = DB.get_properties(chat_id)
    rows = []
    for pos, inf in props.items():
        if inf["owner_id"] == user_id:
            icon = "🔒" if inf["mortgaged"] else "💰"
            rows.append([InlineKeyboardButton(f"{icon} {config.BOARD[pos]['name']}", callback_data=f"mo:{pos}")])
    if not rows:
        rows.append([InlineKeyboardButton("📭 İpoteklenecek mülk yok", callback_data="noop")])
    rows.append([InlineKeyboardButton("⬅️ Geri", callback_data="noop")])
    return InlineKeyboardMarkup(rows)


# ==================== OYUN MANTIGI ====================

def get_current(chat_id):
    game = DB.get_game(chat_id)
    players = DB.get_players(chat_id)
    if not game or not players:
        return None
    idx = game["turn_idx"]
    if idx >= len(players):
        DB.update_game(chat_id, turn_idx=0)
        return players[0]
    return players[idx]

def next_turn(chat_id):
    players = DB.get_players(chat_id)
    alive = [i for i, p in enumerate(players) if p["alive"]]
    if len(alive) <= 1:
        return None
    game = DB.get_game(chat_id)
    idx = game["turn_idx"]
    for _ in range(len(players) + 1):
        idx = (idx + 1) % len(players)
        if players[idx]["alive"]:
            DB.update_game(chat_id, turn_idx=idx)
            return players[idx]
    return None

def owner_name(chat_id, oid):
    p = DB.get_player(chat_id, oid)
    return p["name"] if p else "???"

def full_set(chat_id, uid, color):
    if color not in config.COLOR_GROUPS:
        return False
    props = DB.get_properties(chat_id)
    for pos in config.COLOR_GROUPS[color]:
        if pos not in props or props[pos]["owner_id"] != uid:
            return False
    return True

def rent_calc(chat_id, pos):
    tile = config.BOARD[pos]
    props = DB.get_properties(chat_id)
    p = props.get(pos)
    base = tile.get("base_rent", 0)
    if not p or p["mortgaged"]:
        return 0
    if p["hotel"]:
        return base * 6
    if p["houses"] > 0:
        return base * (p["houses"] + 1)
    if tile["type"] == "property" and full_set(chat_id, p["owner_id"], tile["color"]):
        return base * 2
    return base

def apply_money(chat_id, uid, delta):
    pl = DB.get_player(chat_id, uid)
    if not pl:
        return None, None
    if delta > 0:
        DB.add_money_earned(uid, pl["name"], delta)
    new = pl["money"] + delta
    if new < 0:
        DB.update_player(chat_id, uid, money=new, alive=0)
        DB.delete_properties_of_player(chat_id, uid)
        return new, f"💀 {pl['name']} iflas etti!"
    DB.update_player(chat_id, uid, money=new)
    return new, None

def winner_check(chat_id):
    alive = [p for p in DB.get_players(chat_id) if p["alive"]]
    return alive[0] if len(alive) == 1 else None


# ==================== PANEL ====================

def get_keyboard(chat_id):
    game = DB.get_game(chat_id)
    if not game or not game["started"]:
        return kb_lobby()
    st = game["state"]
    if st == "buy":
        return kb_buy(game["pending_pos"])
    return kb_turn()

def make_caption(chat_id, title="Grup"):
    game = DB.get_game(chat_id)
    if not game:
        return "❌ Aktif oyun yok."

    players = DB.get_players(chat_id)
    cur = get_current(chat_id)
    lines = []
    lines.append(f"🎩 <b>{title}</b>")
    lines.append("━━━━━━━━━━━━━━━")

    if not game["started"]:
        lines.append("📋 <b>Durum:</b> 🟡 Lobi Açık")
        lines.append("")
        if players:
            lines.append("👥 <b>Oyuncular:</b>")
            for p in players:
                lines.append(f"  • {p['name']} — ${p['money']}")
        else:
            lines.append("Henüz kimse katılmadı.")
            lines.append("Aşağıdaki ➕ Katıl butonuna basın.")
    else:
        lines.append("📋 <b>Durum:</b> 🟢 Oyun Devam Ediyor")
        lines.append("")

        if cur:
            tile = config.BOARD[cur["position"]]
            lines.append(f"➡️ <b>Sıra: {cur['name']}</b>")
            lines.append(f"💰 Bakiye: <b>${cur['money']}</b>")
            lines.append(f"📍 Konum: <b>{tile['name']}</b>")
            lines.append("")

        st = game["state"]
        if st == "buy":
            pos = game["pending_pos"]
            t = config.BOARD[pos]
            who = DB.get_player(chat_id, game["pending_user"])
            who_name = who["name"] if who else "?"
            lines.append(f"🏠 <b>{who_name}</b> boş mülke geldi!")
            lines.append(f"📍 <b>{t['name']}</b>")
            lines.append(f"💵 Fiyat: <b>${t['price']}</b>")
            lines.append("")
            lines.append("Yukarıdaki butonlardan seçim yap:")
        elif st == "turn":
            pass
        else:
            pass

        lines.append("")
        lines.append("👥 <b>Oyuncular:</b>")
        for p in players:
            s = "✅" if p["alive"] else "💀"
            mark = " ⬅️" if cur and p["user_id"] == cur["user_id"] else ""
            tile_n = config.BOARD[p["position"]]["name"]
            lines.append(f"  {s} {p['name']} — ${p['money']} — {tile_n}{mark}")

    lines.append("")
    last = game.get("last_action", "")
    if last:
        lines.append("━━━━━━━━━━━━━━━")
        lines.append(f"📝 <i>{last}</i>")

    return "\n".join(lines)[:950]

async def panel(chat_id, ctx):
    game = DB.get_game(chat_id)
    if not game:
        return

    mid = game.get("panel_message_id")
    try:
        chat = await ctx.bot.get_chat(chat_id)
        title = chat.title or chat.full_name or "KGB Monopoly"
    except:
        title = "KGB Monopoly"

    cap = make_caption(chat_id, title)
    kb = get_keyboard(chat_id)
    players = DB.get_players(chat_id)
    png = render_board_png(config.BOARD, players)

    if mid:
        try:
            media = InputMediaPhoto(media=png, caption=cap, parse_mode="HTML")
            await ctx.bot.edit_message_media(chat_id=chat_id, message_id=mid, media=media, reply_markup=kb)
            return
        except BadRequest:
            pass
        except Exception:
            pass

    try:
        msg = await ctx.bot.send_photo(chat_id=chat_id, photo=png, caption=cap, parse_mode="HTML", reply_markup=kb)
        DB.update_game(chat_id, panel_message_id=msg.message_id)
    except Exception:
        pass

async def safe_panel(chat_id, ctx):
    try:
        await panel(chat_id, ctx)
    except Exception as e:
        print(f"Panel hatası: {e}")


# ==================== OYUN AKSIYONLARI ====================

async def act_newgame(chat_id, ctx):
    DB.create_game(chat_id)
    DB.update_game(chat_id, last_action="🎮 Yeni oyun oluşturuldu! Herkes ➕ Katıl bassın.")
    await safe_panel(chat_id, ctx)

async def act_join(chat_id, uid, name, ctx):
    game = DB.get_game(chat_id)
    if game["started"]:
        DB.update_game(chat_id, last_action=f"{name} katılamadı, oyun başladı.")
    else:
        ok = DB.add_player(chat_id, uid, name, config.START_MONEY)
        DB.update_game(chat_id, last_action=(f"✅ {name} oyuna katıldı!" if ok else f"{name} zaten oyunda."))
    await safe_panel(chat_id, ctx)

async def act_start(chat_id, ctx):
    players = DB.get_players(chat_id)
    if len(players) < 2:
        DB.update_game(chat_id, last_action="⚠️ En az 2 oyuncu gerekli!")
        await safe_panel(chat_id, ctx)
        return
    for p in players:
        DB.add_games_played(p["user_id"], p["name"], 1)
    DB.update_game(chat_id, started=1, turn_idx=0, state="turn",
                   last_action=f"🚀 Oyun başladı! İlk sıra: {players[0]['name']}")
    await safe_panel(chat_id, ctx)

async def act_roll(chat_id, uid, ctx):
    game = DB.get_game(chat_id)
    if not game["started"]:
        return

    cur = get_current(chat_id)
    if not cur:
        return
    if cur["user_id"] != uid:
        DB.update_game(chat_id, last_action=f"⏳ Sıra sende değil! Sıradaki: {cur['name']}")
        await safe_panel(chat_id, ctx)
        return

    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    total = d1 + d2
    is_double = d1 == d2

    # çift zar sayacı
    dc = cur["doubles_count"] + 1 if is_double else 0
    if dc >= 3:
        DB.update_player(chat_id, uid, position=config.JAIL_POS, in_jail=1, jail_turns=0, doubles_count=0)
        nxt = next_turn(chat_id)
        DB.update_game(chat_id, state="turn",
                       last_action=f"🎲 {cur['name']} {d1}+{d2} attı → 3.kez çift zar! 🚓 Hapise gitti! Sıra: {nxt['name'] if nxt else '?'}")
        await safe_panel(chat_id, ctx)
        return

    old = cur["position"]
    new = (old + total) % len(config.BOARD)
    money = cur["money"]

    go_pass = new < old
    if go_pass:
        money += config.GO_BONUS

    DB.update_player(chat_id, uid, position=new, money=money, doubles_count=dc)

    tile = config.BOARD[new]
    msg = f"🎲 {cur['name']} zar attı: {d1}+{d2}=<b>{total}</b>"
    if go_pass:
        msg += f" 🏁 +${config.GO_BONUS}"
    msg += f" → 📍 <b>{tile['name']}</b>"

    # kare etkisi
    if tile["type"] in ("property", "railroad", "utility"):
        props = DB.get_properties(chat_id)
        info = props.get(new)
        if info is None:
            DB.update_game(chat_id, state="buy", pending_user=uid, pending_pos=new, last_action=msg)
            await safe_panel(chat_id, ctx)
            return
        elif info["owner_id"] != uid:
            rent = rent_calc(chat_id, new)
            if rent > 0:
                _, bmsg = apply_money(chat_id, uid, -rent)
                apply_money(chat_id, info["owner_id"], rent)
                msg += f" 💰 {owner_name(chat_id, info['owner_id'])}'a <b>${rent}</b> kira ödendi."
                if bmsg:
                    msg += f" {bmsg}"
            else:
                msg += " 🔒 İpotekli mülk, kira yok."
        else:
            msg += " 🏡 Kendi mülkün."

    elif tile["type"] == "tax":
        _, bmsg = apply_money(chat_id, uid, -tile["amount"])
        msg += f" 🧾 <b>-${tile['amount']}</b> vergi."
        if bmsg:
            msg += f" {bmsg}"

    elif tile["type"] == "chance":
        text, delta = random.choice(config.CHANCE_CARDS)
        _, bmsg = apply_money(chat_id, uid, delta)
        s = "+" if delta >= 0 else ""
        msg += f" 🎴 Şans: {text} <b>({s}${delta})</b>"
        if bmsg:
            msg += f" {bmsg}"

    elif tile["type"] == "community":
        text, delta = random.choice(config.COMMUNITY_CARDS)
        _, bmsg = apply_money(chat_id, uid, delta)
        s = "+" if delta >= 0 else ""
        msg += f" 📦 Kasa: {text} <b>({s}${delta})</b>"
        if bmsg:
            msg += f" {bmsg}"

    elif tile["type"] == "goto_jail":
        DB.update_player(chat_id, uid, position=config.JAIL_POS, in_jail=1, jail_turns=0, doubles_count=0)
        msg += " 🚓 Hapise gönderildin!"

    elif tile["type"] == "free":
        msg += " 🅿️ Ücretsiz Park. Dinlen."

    elif tile["type"] == "jail":
        msg += " 👮 Hapis ziyareti. Rahat."

    # kazanan kontrol
    w = winner_check(chat_id)
    if w:
        DB.add_games_won(w["user_id"], w["name"], 1)
        DB.delete_game(chat_id)
        await ctx.bot.send_message(chat_id,
            "🏆 <b>OYUN BİTTİ!</b> 🏆\n\n"
            f"👑 Kazanan: <b>{w['name']}</b>\n"
            f"💰 Son Bakiye: <b>${w['money']}</b>\n"
            "━━━━━━━━━━━━━━━\n"
            "Yeni oyun için aşağıdaki menüyü kullanın.",
            parse_mode="HTML", reply_markup=kb_lobby())
        return

    # çift zar ise tekrar oynayabilir
    if is_double and DB.get_player(chat_id, uid)["alive"]:
        msg += "\n✨ <b>Çift zar! Tekrar oynayabilirsin!</b>"
        DB.update_game(chat_id, state="turn", last_action=msg)
        await safe_panel(chat_id, ctx)
        return

    nxt = next_turn(chat_id)
    msg += f"\n➡️ Sıra: <b>{nxt['name'] if nxt else '?'}</b>"
    DB.update_game(chat_id, state="turn", last_action=msg)
    await safe_panel(chat_id, ctx)

async def act_buy(chat_id, uid, pos, ctx):
    game = DB.get_game(chat_id)
    if game["pending_user"] != uid or game["pending_pos"] != pos:
        return
    pl = DB.get_player(chat_id, uid)
    tile = config.BOARD[pos]
    if pl["money"] >= tile["price"]:
        DB.update_player(chat_id, uid, money=pl["money"] - tile["price"])
        DB.set_property_owner(chat_id, pos, uid)
        nxt = next_turn(chat_id)
        DB.update_game(chat_id, state="turn", pending_user=None, pending_pos=None,
                       last_action=f"✅ {pl['name']} <b>{tile['name']}</b> satın aldı! (-${tile['price']})\n➡️ Sıra: <b>{nxt['name']}</b>")
    else:
        nxt = next_turn(chat_id)
        DB.update_game(chat_id, state="turn", pending_user=None, pending_pos=None,
                       last_action=f"💸 {pl['name']} {tile['name']} alamadı, parası yetmedi.\n➡️ Sıra: <b>{nxt['name']}</b>")
    await safe_panel(chat_id, ctx)

async def act_pass(chat_id, uid, pos, ctx):
    game = DB.get_game(chat_id)
    if game["pending_user"] != uid or game["pending_pos"] != pos:
        return
    nxt = next_turn(chat_id)
    DB.update_game(chat_id, state="turn", pending_user=None, pending_pos=None,
                   last_action=f"❌ {config.BOARD[pos]['name']} satın alınmadı.\n➡️ Sıra: <b>{nxt['name']}</b>")
    await safe_panel(chat_id, ctx)

async def act_endgame(chat_id, ctx):
    DB.delete_game(chat_id)
    await ctx.bot.send_message(chat_id, "🛑 Oyun sonlandırıldı.", reply_markup=kb_lobby())


# ==================== HANDLERLAR ====================

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cid = update.effective_chat.id
    if not DB.game_exists(cid):
        DB.create_game(cid)
    await safe_panel(cid, ctx)

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML", disable_web_page_preview=True)

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    s = DB.get_stat(u.id)
    if not s:
        return await update.message.reply_text(
            "📊 Henüz istatistiğin yok.\nBir oyun tamamladığında burada görünecek.")
    await update.message.reply_text(
        f"📊 <b>{s['name']} | İstatistikler</b>\n\n"
        f"🎮 Oynanan: <b>{s['games_played']}</b>\n"
        f"🏆 Kazanılan: <b>{s['games_won']}</b>\n"
        f"💰 Toplam Kazanç: <b>${s['money_earned']}</b>",
        parse_mode="HTML")

async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    top = DB.top_stats(10)
    if not top:
        return await update.message.reply_text("🏆 Henüz leaderboard yok.")
    text = "🏆 <b>En İyi Oyuncular</b>\n\n"
    for i, s in enumerate(top, start=1):
        text += f"{i}. <b>{s['name']}</b> — 🏆{s['games_won']} — 💰${s['money_earned']}\n"
    await update.message.reply_text(text, parse_mode="HTML")

async def on_btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = q.message.chat_id
    uid = q.from_user.id
    data = q.data

    if not DB.game_exists(cid):
        DB.create_game(cid)

    if data == "noop":
        return

    if data == "hp":
        await q.message.reply_text(HELP_TEXT, parse_mode="HTML", disable_web_page_preview=True)
        return

    if data == "ng":
        await act_newgame(cid, ctx)
        return

    if data == "jn":
        await act_join(cid, uid, q.from_user.first_name, ctx)
        return

    if data == "st":
        await act_start(cid, ctx)
        return

    if data == "rl":
        await act_roll(cid, uid, ctx)
        return

    if data.startswith("buy:"):
        pos = int(data.split(":")[1])
        await act_buy(cid, uid, pos, ctx)
        return

    if data.startswith("pas:"):
        pos = int(data.split(":")[1])
        await act_pass(cid, uid, pos, ctx)
        return

    if data.startswith("auc:"):
        pos = int(data.split(":")[1])
        game = DB.get_game(cid)
        if game["pending_user"] == uid and game["pending_pos"] == pos:
            bidders = [p["user_id"] for p in DB.get_players(cid) if p["alive"]]
            DB.start_auction(cid, pos, bidders)
            DB.update_game(cid, state="turn", pending_user=None, pending_pos=None,
                           last_action=f"📢 {config.BOARD[pos]['name']} açık artırmaya çıktı! En yüksek teklif: $0")
        await safe_panel(cid, ctx)
        return

    if data == "ss":
        ps = DB.get_players(cid)
        cur = get_current(cid)
        game = DB.get_game(cid)
        t = "📊 <b>Durum</b>\n\n"
        if cur and game and game["started"]:
            t += f"➡️ Sıra: <b>{cur['name']}</b>\n\n"
        for p in ps:
            tile = config.BOARD[p["position"]]["name"]
            st = "✅" if p["alive"] else "💀"
            t += f"• {p['name']} — ${p['money']} — {tile} {st}\n"
        await q.message.reply_text(t, parse_mode="HTML")
        return

    if data == "pl":
        ps = DB.get_players(cid)
        t = "👥 <b>Oyuncular</b>\n\n"
        for p in ps:
            st = "✅" if p["alive"] else "💀"
            t += f"• {st} <b>{p['name']}</b> — ${p['money']}\n"
        await q.message.reply_text(t, parse_mode="HTML")
        return

    if data == "mp":
        props = DB.get_properties(cid)
        my = [pos for pos, inf in props.items() if inf["owner_id"] == uid]
        if not my:
            t = "🏠 Mülkün yok."
        else:
            t = "🏠 <b>Mülklerin</b>\n\n"
            for pos in my:
                inf = props[pos]
                extra = ""
                if inf["mortgaged"]:
                    extra += " 🔒"
                if inf["hotel"]:
                    extra += " 🏨"
                elif inf["houses"] > 0:
                    extra += f" 🏠x{inf['houses']}"
                t += f"• {config.BOARD[pos]['name']} — kira ${rent_calc(cid, pos)}{extra}\n"
        await q.message.reply_text(t, parse_mode="HTML")
        return

    if data == "bd":
        await q.message.reply_text("🧱 İnşa menüsü:", reply_markup=kb_build(cid, uid))
        return

    if data.startswith("bdp:"):
        pos = int(data.split(":")[1])
        await q.message.reply_text(f"🏗️ {config.BOARD[pos]['name']} — ne yapmak istersin?",
                                   reply_markup=kb_build_actions(pos))
        return

    if data.startswith("bh:"):
        pos = int(data.split(":")[1])
        tile = config.BOARD[pos]
        props = DB.get_properties(cid)
        inf = props.get(pos)
        if not inf or inf["owner_id"] != uid:
            DB.update_game(cid, last_action="❌ Bu mülk sana ait değil.")
        elif inf["mortgaged"]:
            DB.update_game(cid, last_action="❌ İpotekli mülke ev kurulamaz.")
        elif not full_set(cid, uid, tile["color"]):
            DB.update_game(cid, last_action="❌ Önce renk setini tamamla.")
        elif inf["hotel"]:
            DB.update_game(cid, last_action="❌ Zaten otel var.")
        elif inf["houses"] >= 4:
            DB.update_game(cid, last_action="❌ 4 ev var. Otel kur.")
        else:
            cost = tile["price"] // 2
            pl = DB.get_player(cid, uid)
            if pl["money"] < cost:
                DB.update_game(cid, last_action="💸 Yeterli para yok.")
            else:
                DB.update_property(cid, pos, houses=inf["houses"] + 1)
                DB.update_player(cid, uid, money=pl["money"] - cost)
                DB.update_game(cid, last_action=f"🏠 {tile['name']} mülküne ev kuruldu! ({inf['houses']+1}/4) -${cost}")
        await safe_panel(cid, ctx)
        return

    if data.startswith("bt:"):
        pos = int(data.split(":")[1])
        tile = config.BOARD[pos]
        props = DB.get_properties(cid)
        inf = props.get(pos)
        if not inf or inf["owner_id"] != uid:
            DB.update_game(cid, last_action="❌ Bu mülk sana ait değil.")
        elif inf["mortgaged"]:
            DB.update_game(cid, last_action="❌ İpotekli mülke otel kurulamaz.")
        elif inf["hotel"]:
            DB.update_game(cid, last_action="❌ Zaten otel var.")
        elif inf["houses"] < 4:
            DB.update_game(cid, last_action="❌ Önce 4 ev kur.")
        else:
            cost = tile["price"]
            pl = DB.get_player(cid, uid)
            if pl["money"] < cost:
                DB.update_game(cid, last_action="💸 Yeterli para yok.")
            else:
                DB.update_property(cid, pos, houses=0, hotel=1)
                DB.update_player(cid, uid, money=pl["money"] - cost)
                DB.update_game(cid, last_action=f"🏨 {tile['name']} mülküne otel kuruldu! -${cost}")
        await safe_panel(cid, ctx)
        return

    if data == "mg":
        await q.message.reply_text("🏦 İpotek menüsü:", reply_markup=kb_mortgage(cid, uid))
        return

    if data.startswith("mo:"):
        pos = int(data.split(":")[1])
        props = DB.get_properties(cid)
        inf = props.get(pos)
        if not inf or inf["owner_id"] != uid:
            DB.update_game(cid, last_action="❌ Bu mülk sana ait değil.")
        elif inf["houses"] > 0 or inf["hotel"]:
            DB.update_game(cid, last_action="❌ Önce ev/otelleri satmalısın.")
        else:
            tile = config.BOARD[pos]
            mv = tile["price"] // 2
            pl = DB.get_player(cid, uid)
            if inf["mortgaged"]:
                cost = int(mv * 1.1)
                if pl["money"] < cost:
                    DB.update_game(cid, last_action=f"💸 İpotek kaldırmak için ${cost} gerekli.")
                else:
                    DB.update_property(cid, pos, mortgaged=0)
                    DB.update_player(cid, uid, money=pl["money"] - cost)
                    DB.update_game(cid, last_action=f"🔓 {tile['name']} ipotek kaldırıldı. -${cost}")
            else:
                DB.update_property(cid, pos, mortgaged=1)
                DB.update_player(cid, uid, money=pl["money"] + mv)
                DB.update_game(cid, last_action=f"🏦 {tile['name']} ipotek edildi. +${mv}")
        await safe_panel(cid, ctx)
        return

    if data == "tr":
        await q.message.reply_text("🤝 Takas henüz bu sürümde aktif değil.")
        return

    if data == "en":
        await act_endgame(cid, ctx)
        return


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN eksik!")
    DB.init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CallbackQueryHandler(on_btn))
    print("KGB Monopoly Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
