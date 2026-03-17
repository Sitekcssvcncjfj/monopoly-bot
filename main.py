import os
import random
import time
from io import BytesIO

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

import config
import db as DB
from render_board import render_board_png

BOT_TOKEN = os.getenv("BOT_TOKEN")


# ----------------- Yardım Metni -----------------

HELP_TEXT = (
    "<b>🎩 KGB Monopoly Bot - Oyun Rehberi</b>\n\n"
    "<b>Temel:</b>\n"
    "• Yeni Oyun: sıfırlar, lobby açar.\n"
    "• Katıl: oyuna gir.\n"
    "• Başlat: 2+ kişiyle oyunu başlatır.\n"
    "• Zar At: sadece sırası gelen oyuncu oynar.\n\n"
    "<b>Satın Alma:</b>\n"
    "• Boş mülke gelince Satın Al / Açık Artırma / Geç.\n\n"
    "<b>Açık Artırma:</b>\n"
    "• Sırayla teklif verilir.\n"
    "• Pas geçen açık artırmadan çıkar.\n\n"
    "<b>Ev/Otel:</b>\n"
    "• Renk setini tamamlamadan ev kurulamaz.\n"
    "• 4 ev → otel.\n\n"
    "<b>İpotek:</b>\n"
    "• Bina/otel yoksa ipotek yapılır.\n    "
    "• İpotekli mülk kira üretmez.\n"
    "• Devredilirse yeni sahip %10 faiz öder.\n\n"
    "<b>Takas:</b>\n"
    "• Sadece sıradaki oyuncu, zar atmadan önce takas önerebilir.\n"
    "• Teklif kabul/ret.\n\n"
    "<b>Zaman Aşımı:</b>\n"
    f"• Sıradaki oyuncu {config.TURN_TIMEOUT_SEC}s içinde oynamazsa bot otomatik zar atar.\n"
)


# ----------------- UI -----------------

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
        [InlineKeyboardButton("❌ Geç", callback_data=f"pas:{pos}")],
        [InlineKeyboardButton("📊 Durum", callback_data="ss"),
         InlineKeyboardButton("📖 Help", callback_data="hp")]
    ])

def kb_auction(can_act: bool, pos: int):
    if can_act:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("💸 +10", callback_data="ab:10"),
             InlineKeyboardButton("💸 +50", callback_data="ab:50"),
             InlineKeyboardButton("💸 +100", callback_data="ab:100")],
            [InlineKeyboardButton("⛔ Pas", callback_data="ap")],
            [InlineKeyboardButton("📊 Durum", callback_data="ss"),
             InlineKeyboardButton("📖 Help", callback_data="hp")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ Açık artırma sürüyor...", callback_data="noop")],
        [InlineKeyboardButton("📊 Durum", callback_data="ss"),
         InlineKeyboardButton("📖 Help", callback_data="hp")]
    ])

def kb_trade_pick(chat_id: int, proposer_id: int):
    players = [p for p in DB.get_players(chat_id) if p["alive"] and p["user_id"] != proposer_id]
    rows = []
    for p in players[:10]:
        rows.append([InlineKeyboardButton(f"🤝 {p['name']}", callback_data=f"trt:{p['user_id']}")])
    rows.append([InlineKeyboardButton("⬅️ İptal", callback_data="tr_cancel")])
    return InlineKeyboardMarkup(rows)

def kb_trade_choose_props(chat_id: int, proposer_id: int, target_id: int, step: str, selected_offer=None, selected_req=None, cash_delta=0):
    props = DB.get_properties(chat_id)
    my_props = [pos for pos, inf in props.items() if inf["owner_id"] == proposer_id]
    tg_props = [pos for pos, inf in props.items() if inf["owner_id"] == target_id]

    rows = []
    if step == "offer":
        rows.append([InlineKeyboardButton("📌 Vereceğin mülkü seç", callback_data="noop")])
        for pos in my_props[:12]:
            rows.append([InlineKeyboardButton(f"➡️ {config.BOARD[pos]['name']}", callback_data=f"tro:{pos}")])
    else:
        rows.append([InlineKeyboardButton("📌 İstediğin mülkü seç", callback_data="noop")])
        for pos in tg_props[:12]:
            rows.append([InlineKeyboardButton(f"⬅️ {config.BOARD[pos]['name']}", callback_data=f"trr:{pos}")])

    # para farkı ayarı (teklif ekranında)
    if selected_offer is not None and selected_req is not None:
        rows.append([
            InlineKeyboardButton("💰 -50", callback_data="trc:-50"),
            InlineKeyboardButton("💰 +50", callback_data="trc:+50"),
        ])
        rows.append([
            InlineKeyboardButton("💰 -10", callback_data="trc:-10"),
            InlineKeyboardButton("💰 +10", callback_data="trc:+10"),
        ])
        rows.append([InlineKeyboardButton(f"✅ Teklifi Gönder (Δ={cash_delta}$)", callback_data="tr_send")])

    rows.append([InlineKeyboardButton("⬅️ İptal", callback_data="tr_cancel")])
    return InlineKeyboardMarkup(rows)

def kb_trade_pending(can_answer: bool):
    if can_answer:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Kabul", callback_data="tr_yes"),
             InlineKeyboardButton("❌ Reddet", callback_data="tr_no")],
            [InlineKeyboardButton("📊 Durum", callback_data="ss"),
             InlineKeyboardButton("📖 Help", callback_data="hp")]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏳ Takas yanıt bekliyor...", callback_data="noop")],
        [InlineKeyboardButton("📊 Durum", callback_data="ss"),
         InlineKeyboardButton("📖 Help", callback_data="hp")]
    ])

def kb_build_menu(chat_id: int, user_id: int):
    props = DB.get_properties(chat_id)
    my_buildables = []
    for pos, inf in props.items():
        if inf["owner_id"] == user_id and config.BOARD[pos]["type"] == "property":
            my_buildables.append(pos)
    rows = [[InlineKeyboardButton("🧱 İnşa edilecek mülk seç", callback_data="noop")]]
    for pos in my_buildables[:12]:
        rows.append([InlineKeyboardButton(f"🏗️ {config.BOARD[pos]['name']}", callback_data=f"bdp:{pos}")])
    rows.append([InlineKeyboardButton("⬅️ Geri", callback_data="back_turn")])
    return InlineKeyboardMarkup(rows)

def kb_build_actions(pos: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Ev Kur", callback_data=f"bh:{pos}"),
         InlineKeyboardButton("🏨 Otel Kur", callback_data=f"bt:{pos}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="bd")]
    ])

def kb_mortgage_menu(chat_id: int, user_id: int):
    props = DB.get_properties(chat_id)
    rows = [[InlineKeyboardButton("🏦 İpotek yapılacak/çözülecek mülk", callback_data="noop")]]
    for pos, inf in props.items():
        if inf["owner_id"] == user_id:
            state = "🔒" if inf["mortgaged"] else "💰"
            rows.append([InlineKeyboardButton(f"{state} {config.BOARD[pos]['name']}", callback_data=f"mo:{pos}")])
    rows.append([InlineKeyboardButton("⬅️ Geri", callback_data="back_turn")])
    return InlineKeyboardMarkup(rows)


# ----------------- Oyun Mantığı -----------------

def owner_name(chat_id: int, owner_id: int):
    p = DB.get_player(chat_id, owner_id)
    return p["name"] if p else "Bilinmiyor"

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

def mortgage_value(pos: int):
    return config.BOARD[pos].get("price", 0) // 2

def mortgage_interest(pos: int):
    mv = mortgage_value(pos)
    return max(1, int(mv * 0.10))

def apply_money(chat_id: int, user_id: int, delta: int):
    pl = DB.get_player(chat_id, user_id)
    if not pl:
        return None, None
    new_money = pl["money"] + delta
    if new_money < 0:
        DB.update_player(chat_id, user_id, money=new_money, alive=0)
        DB.delete_properties_of_player(chat_id, user_id)
        return new_money, f"💀 {pl['name']} iflas etti!"
    DB.update_player(chat_id, user_id, money=new_money)
    return new_money, None

def check_winner(chat_id: int):
    alive = [p for p in DB.get_players(chat_id) if p["alive"]]
    if len(alive) == 1:
        return alive[0]
    return None


# ----------------- Panel (tek mesaj) -----------------

async def ensure_panel_message(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game:
        return None
    if game["panel_message_id"]:
        return game["panel_message_id"]

    # yeni panel oluştur
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

def panel_keyboard(chat_id: int, viewer_id: int | None = None):
    game = DB.get_game(chat_id)
    if not game:
        return kb_lobby()
    if not game["started"]:
        return kb_lobby()

    st = game["state"]
    if st == "buy":
        return kb_buy(game["pending_pos"])
    if st == "auction":
        auc = DB.get_auction(chat_id)
        cur_uid = auc["bidders"][auc["current_idx"]] if auc else None
        can_act = (viewer_id is not None and viewer_id == cur_uid)
        return kb_auction(can_act=can_act, pos=auc["pos"] if auc else 0)
    if st == "trade_pending":
        tr = DB.get_trade(chat_id)
        can_answer = (viewer_id is not None and tr and viewer_id == tr["target_id"])
        return kb_trade_pending(can_answer)
    # normal turn
    return kb_turn()

def build_caption(chat_id: int):
    game = DB.get_game(chat_id)
    players = DB.get_players(chat_id)
    if not game:
        return "🎩 <b>KGB Monopoly</b>\nPanel yok. /start ile aç."

    if not players:
        return (
            "🎩 <b>KGB Monopoly</b>\n\n"
            "Oyuncu yok. ➕ Katıl ile oyuna girin."
        )

    cur = get_current_player(chat_id)
    state = game["state"]
    last = game["last_action"] or ""

    text = "🎩 <b>KGB Monopoly</b>\n"
    text += f"🟢 Durum: <b>{'Başladı' if game['started'] else 'Lobby'}</b>\n"

    if game["started"] and cur:
        tile = config.BOARD[cur["position"]]["name"]
        text += f"➡️ Sıra: <b>{cur['name']}</b> | 💰 ${cur['money']} | 📍 {tile}\n"

    if state == "buy":
        pos = game["pending_pos"]
        t = config.BOARD[pos]
        text += f"\n🏠 <b>{t['name']}</b> boş. Fiyat: <b>${t['price']}</b>\n"
        text += "Satın al / açık artırma / geç."
    elif state == "auction":
        auc = DB.get_auction(chat_id)
        if auc:
            cur_uid = auc["bidders"][auc["current_idx"]]
            curp = DB.get_player(chat_id, cur_uid)
            text += (
                f"\n📢 <b>Açık Artırma</b> | Mülk: <b>{config.BOARD[auc['pos']]['name']}</b>\n"
                f"🏷️ En yüksek: <b>${auc['highest_bid']}</b> ({owner_name(chat_id, auc['highest_user']) if auc['highest_user'] else 'yok'})\n"
                f"👉 Sıra: <b>{curp['name'] if curp else cur_uid}</b>\n"
            )
    elif state == "trade_pending":
        tr = DB.get_trade(chat_id)
        if tr:
            proposer = DB.get_player(chat_id, tr["proposer_id"])
            target = DB.get_player(chat_id, tr["target_id"])
            text += "\n🤝 <b>Takas Teklifi</b>\n"
            text += f"• {proposer['name'] if proposer else tr['proposer_id']} ↔ {target['name'] if target else tr['target_id']}\n"
            text += f"• Verilen: <b>{config.BOARD[tr['offer_pos']]['name']}</b>\n"
            text += f"• İstenen: <b>{config.BOARD[tr['request_pos']]['name']}</b>\n"
            if tr["cash_delta"] != 0:
                if tr["cash_delta"] > 0:
                    text += f"• Para farkı: Proposer → Target <b>${tr['cash_delta']}</b>\n"
                else:
                    text += f"• Para farkı: Target → Proposer <b>${abs(tr['cash_delta'])}</b>\n"
            text += "\nHedef oyuncu kabul/ret verebilir."
    else:
        pass

    if last:
        text += f"\n\n📝 <i>{last}</i>"

    # caption limitini çok aşmayalım
    return text[:950]

async def update_panel(chat_id: int, context: ContextTypes.DEFAULT_TYPE, viewer_id: int | None = None, force_new_image: bool = True):
    game = DB.get_game(chat_id)
    if not game:
        return

    mid = await ensure_panel_message(chat_id, context)
    caption = build_caption(chat_id)
    keyboard = panel_keyboard(chat_id, viewer_id=viewer_id)

    # her aksiyonda board görselini güncelle (tek mesaj canlı panel + gerçek tahta)
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
        # media edit olmazsa caption edit dene
        try:
            await context.bot.edit_message_caption(
                chat_id=chat_id,
                message_id=mid,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception:
            # panel silindiyse yeniden oluştur
            DB.update_game(chat_id, panel_message_id=None)
            await ensure_panel_message(chat_id, context)


# ----------------- Timeout Jobs -----------------

def schedule_turn_timeout(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    job_name = f"turn_timeout:{chat_id}"
    # eski job'u kaldır
    for j in context.job_queue.get_jobs_by_name(job_name):
        j.schedule_removal()

    context.job_queue.run_once(turn_timeout_job, when=config.TURN_TIMEOUT_SEC, data={"chat_id": chat_id}, name=job_name)

async def turn_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    game = DB.get_game(chat_id)
    if not game or not game["started"]:
        return
    if game["state"] != "turn":
        return
    cur = get_current_player(chat_id)
    if not cur or not cur["alive"]:
        return

    DB.update_game(chat_id, last_action=f"⏰ Zaman aşımı! {cur['name']} için bot otomatik zar attı.")
    await do_roll(chat_id, cur["user_id"], context, auto=True)

def schedule_auction_timeout(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    job_name = f"auction_timeout:{chat_id}"
    for j in context.job_queue.get_jobs_by_name(job_name):
        j.schedule_removal()
    context.job_queue.run_once(auction_timeout_job, when=config.AUCTION_TIMEOUT_SEC, data={"chat_id": chat_id}, name=job_name)

async def auction_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    game = DB.get_game(chat_id)
    if not game or game["state"] != "auction":
        return
    auc = DB.get_auction(chat_id)
    if not auc:
        return
    cur_uid = auc["bidders"][auc["current_idx"]]
    cur = DB.get_player(chat_id, cur_uid)
    DB.update_game(chat_id, last_action=f"⏰ Açık artırma zaman aşımı: {cur['name'] if cur else cur_uid} otomatik PAS.")
    await auction_pass(chat_id, cur_uid, context)

def schedule_trade_timeout(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    job_name = f"trade_timeout:{chat_id}"
    for j in context.job_queue.get_jobs_by_name(job_name):
        j.schedule_removal()
    context.job_queue.run_once(trade_timeout_job, when=config.TRADE_TIMEOUT_SEC, data={"chat_id": chat_id}, name=job_name)

async def trade_timeout_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data["chat_id"]
    game = DB.get_game(chat_id)
    if not game or game["state"] != "trade_pending":
        return
    DB.update_game(chat_id, last_action="⏰ Takas yanıtı gelmedi, otomatik reddedildi.")
    DB.clear_trade(chat_id)
    DB.update_game(chat_id, state="turn")
    schedule_turn_timeout(chat_id, context)
    await update_panel(chat_id, context)


# ----------------- Oyun Aksiyonları -----------------

async def start_game(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    players = DB.get_players(chat_id)
    if len(players) < 2:
        DB.update_game(chat_id, last_action="En az 2 oyuncu gerekli.")
        return
    DB.update_game(chat_id, started=1, turn_idx=0, state="turn", last_action="Oyun başladı!")
    schedule_turn_timeout(chat_id, context)

async def do_roll(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE, auto: bool = False):
    game = DB.get_game(chat_id)
    if not game or not game["started"]:
        return

    if game["state"] != "turn":
        return

    cur = get_current_player(chat_id)
    if not cur or cur["user_id"] != user_id:
        return

    # hapis basit: 2 tur bekle
    if cur["in_jail"]:
        jt = cur["jail_turns"] + 1
        if jt >= 2:
            DB.update_player(chat_id, user_id, in_jail=0, jail_turns=0)
            jail_msg = "🔓 Hapisten çıktın."
        else:
            DB.update_player(chat_id, user_id, jail_turns=jt)
            nxt = next_turn(chat_id)
            DB.update_game(chat_id, last_action=f"🚔 {cur['name']} hapiste, tur atladı. Sıra: {nxt['name']}")
            schedule_turn_timeout(chat_id, context)
            await update_panel(chat_id, context)
            return
    else:
        jail_msg = ""

    d1 = random.randint(1, 6)
    d2 = random.randint(1, 6)
    total = d1 + d2
    is_double = (d1 == d2)
    doubles_count = cur["doubles_count"] + 1 if is_double else 0

    if doubles_count >= 3:
        DB.update_player(chat_id, user_id, position=config.JAIL_POS, in_jail=1, jail_turns=0, doubles_count=0)
        nxt = next_turn(chat_id)
        DB.update_game(chat_id, last_action=f"🎲 {cur['name']} {d1}+{d2} attı. 3 çift zar → 🚓 Hapis! Sıra: {nxt['name']}", state="turn")
        schedule_turn_timeout(chat_id, context)
        await update_panel(chat_id, context)
        return

    old_pos = cur["position"]
    new_pos = (old_pos + total) % len(config.BOARD)

    money = cur["money"]
    passed_go = new_pos < old_pos
    if passed_go:
        money += config.GO_BONUS

    DB.update_player(chat_id, user_id, position=new_pos, money=money, doubles_count=doubles_count)

    tile = config.BOARD[new_pos]
    msg = f"{'🤖 ' if auto else ''}{jail_msg} 🎲 {cur['name']} zar: {d1}+{d2}={total}. "
    if passed_go:
        msg += f"🏁 +${config.GO_BONUS}. "
    msg += f"📍 {tile['name']}."

    # kare etkisi
    if tile["type"] in ("property", "railroad", "utility"):
        props = DB.get_properties(chat_id)
        info = props.get(new_pos)
        if info is None:
            # satın alma fazı
            DB.update_game(chat_id, state="buy", pending_user=user_id, pending_pos=new_pos, last_action=msg)
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        if info["owner_id"] == user_id:
            DB.update_game(chat_id, last_action=msg + " 🏡 Kendi mülkün.")
        else:
            rent = calc_rent(chat_id, new_pos)
            if rent <= 0:
                DB.update_game(chat_id, last_action=msg + " 🔒 İpotekli mülk, kira yok.")
            else:
                _, bmsg = apply_money(chat_id, user_id, -rent)
                if info["owner_id"]:
                    apply_money(chat_id, info["owner_id"], rent)
                DB.update_game(chat_id, last_action=msg + f" 💰 {owner_name(chat_id, info['owner_id'])}’a ${rent} kira ödendi." + (f" {bmsg}" if bmsg else ""))
    elif tile["type"] == "tax":
        _, bmsg = apply_money(chat_id, user_id, -tile["amount"])
        DB.update_game(chat_id, last_action=msg + f" 🧾 -${tile['amount']} vergi." + (f" {bmsg}" if bmsg else ""))
    elif tile["type"] == "chance":
        text, delta = random.choice(config.CHANCE_CARDS)
        _, bmsg = apply_money(chat_id, user_id, delta)
        sign = "+" if delta >= 0 else "-"
        DB.update_game(chat_id, last_action=msg + f" 🎴 Şans: {text} ({sign}${abs(delta)})." + (f" {bmsg}" if bmsg else ""))
    elif tile["type"] == "community":
        text, delta = random.choice(config.COMMUNITY_CARDS)
        _, bmsg = apply_money(chat_id, user_id, delta)
        sign = "+" if delta >= 0 else "-"
        DB.update_game(chat_id, last_action=msg + f" 📦 Kasa: {text} ({sign}${abs(delta)})." + (f" {bmsg}" if bmsg else ""))
    elif tile["type"] == "goto_jail":
        DB.update_player(chat_id, user_id, position=config.JAIL_POS, in_jail=1, jail_turns=0, doubles_count=0)
        DB.update_game(chat_id, last_action=msg + " 🚓 Hapise gönderildin!")
    else:
        DB.update_game(chat_id, last_action=msg)

    # kazanan?
    winner = check_winner(chat_id)
    if winner:
        DB.update_game(chat_id, last_action=f"🏆 Oyun bitti! Kazanan: {winner['name']}")
        DB.delete_game(chat_id)
        await context.bot.send_message(chat_id, f"🏆 Oyun bitti! Kazanan: {winner['name']}")
        return

    if is_double and DB.get_player(chat_id, user_id)["alive"]:
        DB.update_game(chat_id, state="turn", last_action=DB.get_game(chat_id)["last_action"] + " ✨ Çift zar! Tekrar oynayabilirsin.")
        schedule_turn_timeout(chat_id, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    nxt = next_turn(chat_id)
    DB.update_game(chat_id, state="turn", last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
    schedule_turn_timeout(chat_id, context)
    await update_panel(chat_id, context)


async def buy_property(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game or game["state"] != "buy" or game["pending_user"] != user_id:
        return
    pos = game["pending_pos"]
    tile = config.BOARD[pos]
    player = DB.get_player(chat_id, user_id)
    if player["money"] < tile["price"]:
        DB.update_game(chat_id, last_action="💸 Yetersiz para, satın alma iptal.", state="turn", pending_user=None, pending_pos=None)
        nxt = next_turn(chat_id)
        DB.update_game(chat_id, last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
        schedule_turn_timeout(chat_id, context)
        await update_panel(chat_id, context)
        return
    DB.update_player(chat_id, user_id, money=player["money"] - tile["price"])
    DB.set_property_owner(chat_id, pos, user_id)
    DB.update_game(chat_id, last_action=f"✅ {player['name']} {tile['name']} satın aldı.", state="turn", pending_user=None, pending_pos=None)

    nxt = next_turn(chat_id)
    DB.update_game(chat_id, last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
    schedule_turn_timeout(chat_id, context)
    await update_panel(chat_id, context)

async def pass_buy(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game or game["state"] != "buy" or game["pending_user"] != user_id:
        return
    pos = game["pending_pos"]
    DB.update_game(chat_id, state="turn", pending_user=None, pending_pos=None, last_action=f"❌ {config.BOARD[pos]['name']} alınmadı.")
    nxt = next_turn(chat_id)
    DB.update_game(chat_id, last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
    schedule_turn_timeout(chat_id, context)
    await update_panel(chat_id, context)

async def start_auction_from_buy(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game or game["state"] != "buy" or game["pending_user"] != user_id:
        return
    pos = game["pending_pos"]
    bidders = [p["user_id"] for p in DB.get_players(chat_id) if p["alive"]]
    DB.start_auction(chat_id, pos, bidders)
    DB.update_game(chat_id, state="auction", pending_user=None, pending_pos=None, last_action=f"📢 {config.BOARD[pos]['name']} açık artırma başladı!")
    schedule_auction_timeout(chat_id, context)
    await update_panel(chat_id, context)

def auction_active_bidders(auc):
    return [uid for uid in auc["bidders"] if uid not in set(auc["passed"])]

def auction_current_user(auc):
    active = auction_active_bidders(auc)
    # current_idx bidders listesinde geziniyor; pas geçmişse ilerle
    idx = auc["current_idx"]
    bidders = auc["bidders"]
    for _ in range(len(bidders) + 1):
        uid = bidders[idx]
        if uid in active:
            return uid, idx
        idx = (idx + 1) % len(bidders)
    return None, idx

async def auction_bid(chat_id: int, user_id: int, inc: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game or game["state"] != "auction":
        return
    auc = DB.get_auction(chat_id)
    if not auc:
        DB.update_game(chat_id, state="turn", last_action="Açık artırma bulunamadı.")
        schedule_turn_timeout(chat_id, context)
        await update_panel(chat_id, context)
        return

    cur_uid, fixed_idx = auction_current_user(auc)
    if cur_uid != user_id:
        return

    pl = DB.get_player(chat_id, user_id)
    new_bid = auc["highest_bid"] + inc
    if pl["money"] < new_bid:
        DB.update_game(chat_id, last_action=f"💸 {pl['name']} bu teklifi veremiyor (gerekli: ${new_bid}).")
        schedule_auction_timeout(chat_id, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    auc["highest_bid"] = new_bid
    auc["highest_user"] = user_id
    # sıradaki aktif kişiye geç
    auc["current_idx"] = (fixed_idx + 1) % len(auc["bidders"])
    DB.update_auction(chat_id, current_idx=auc["current_idx"], highest_bid=new_bid, highest_user=user_id, passed=auc["passed"])
    DB.update_game(chat_id, last_action=f"💸 {pl['name']} teklif verdi: ${new_bid}")
    schedule_auction_timeout(chat_id, context)

    # bitiş kontrol
    await auction_check_end(chat_id, context)
    await update_panel(chat_id, context, viewer_id=user_id)

async def auction_pass(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    if not game or game["state"] != "auction":
        return
    auc = DB.get_auction(chat_id)
    if not auc:
        return

    cur_uid, fixed_idx = auction_current_user(auc)
    if cur_uid != user_id:
        return

    if user_id not in auc["passed"]:
        auc["passed"].append(user_id)

    auc["current_idx"] = (fixed_idx + 1) % len(auc["bidders"])
    DB.update_auction(chat_id, passed=auc["passed"], current_idx=auc["current_idx"])
    pl = DB.get_player(chat_id, user_id)
    DB.update_game(chat_id, last_action=f"⛔ {pl['name']} PAS geçti.")
    schedule_auction_timeout(chat_id, context)

    await auction_check_end(chat_id, context)
    await update_panel(chat_id, context, viewer_id=user_id)

async def auction_check_end(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    auc = DB.get_auction(chat_id)
    if not auc:
        return
    active = auction_active_bidders(auc)

    # herkes pas geçtiyse (aktif boşsa)
    if len(active) == 0:
        DB.clear_auction(chat_id)
        DB.update_game(chat_id, state="turn", last_action="❌ Açık artırmada teklif kalmadı, mülk satılmadı.")
        nxt = next_turn(chat_id)
        DB.update_game(chat_id, last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
        schedule_turn_timeout(chat_id, context)
        return

    # aktif tek kişi kaldıysa bitir
    if len(active) == 1:
        winner_id = active[0]
        bid = auc["highest_bid"]
        pos = auc["pos"]
        tile = config.BOARD[pos]

        if bid <= 0:
            # kimse teklif vermedi
            DB.clear_auction(chat_id)
            DB.update_game(chat_id, state="turn", last_action="❌ Açık artırmada teklif gelmedi, mülk satılmadı.")
            nxt = next_turn(chat_id)
            DB.update_game(chat_id, last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
            schedule_turn_timeout(chat_id, context)
            return

        pl = DB.get_player(chat_id, winner_id)
        if not pl or pl["money"] < bid:
            DB.clear_auction(chat_id)
            DB.update_game(chat_id, state="turn", last_action="💸 Kazananın parası yetmedi, satış iptal.")
            nxt = next_turn(chat_id)
            DB.update_game(chat_id, last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
            schedule_turn_timeout(chat_id, context)
            return

        # ipotekli devri kuralı: (burada mülk boştu, mortgaged yok) ama generic kalsın
        props = DB.get_properties(chat_id)
        info = props.get(pos)
        # satın al
        DB.update_player(chat_id, winner_id, money=pl["money"] - bid)
        DB.set_property_owner(chat_id, pos, winner_id)

        DB.clear_auction(chat_id)
        DB.update_game(chat_id, state="turn", last_action=f"🏁 Açık artırmayı {pl['name']} kazandı! {tile['name']} → ${bid}")

        nxt = next_turn(chat_id)
        DB.update_game(chat_id, last_action=DB.get_game(chat_id)["last_action"] + f" ➡️ Sıra: {nxt['name']}")
        schedule_turn_timeout(chat_id, context)
        return


# ----------------- Build / Mortgage -----------------

def can_build_house(chat_id: int, user_id: int, pos: int):
    tile = config.BOARD[pos]
    props = DB.get_properties(chat_id)
    inf = props.get(pos)
    if tile["type"] != "property":
        return False, "Bu mülke ev kurulmaz."
    if not inf or inf["owner_id"] != user_id:
        return False, "Bu mülk sana ait değil."
    if inf["mortgaged"]:
        return False, "İpotekli mülke ev kurulmaz."
    if inf["hotel"]:
        return False, "Zaten otel var."
    if not owns_full_set(chat_id, user_id, tile["color"]):
        return False, "Renk setini tamamlamalısın."
    if inf["houses"] >= 4:
        return False, "Maks 4 ev. Sonraki otel."
    return True, None

def can_build_hotel(chat_id: int, user_id: int, pos: int):
    tile = config.BOARD[pos]
    props = DB.get_properties(chat_id)
    inf = props.get(pos)
    if tile["type"] != "property":
        return False, "Bu mülke otel kurulmaz."
    if not inf or inf["owner_id"] != user_id:
        return False, "Bu mülk sana ait değil."
    if inf["mortgaged"]:
        return False, "İpotekli mülke otel kurulmaz."
    if inf["hotel"]:
        return False, "Zaten otel var."
    if inf["houses"] < 4:
        return False, "Önce 4 ev kur."
    return True, None

async def toggle_mortgage(chat_id: int, user_id: int, pos: int, context: ContextTypes.DEFAULT_TYPE):
    props = DB.get_properties(chat_id)
    inf = props.get(pos)
    if not inf or inf["owner_id"] != user_id:
        DB.update_game(chat_id, last_action="Bu mülk sana ait değil.")
        return
    if inf["houses"] > 0 or inf["hotel"]:
        DB.update_game(chat_id, last_action="Önce ev/otel kaldırılmalı.")
        return

    pl = DB.get_player(chat_id, user_id)
    mv = mortgage_value(pos)
    if inf["mortgaged"]:
        # çöz: %10 faizli geri öde
        cost = int(mv * 1.1)
        if pl["money"] < cost:
            DB.update_game(chat_id, last_action=f"💸 İpotekten çıkarmak için ${cost} lazım.")
            return
        DB.update_property(chat_id, pos, mortgaged=0)
        DB.update_player(chat_id, user_id, money=pl["money"] - cost)
        DB.update_game(chat_id, last_action=f"🔓 {config.BOARD[pos]['name']} ipotek çözüldü. -${cost}")
    else:
        DB.update_property(chat_id, pos, mortgaged=1)
        DB.update_player(chat_id, user_id, money=pl["money"] + mv)
        DB.update_game(chat_id, last_action=f"🏦 {config.BOARD[pos]['name']} ipotek edildi. +${mv}")


# ----------------- Trade (gelişmiş) -----------------

# trade_setup bilgisi games.last_action içine değil; basitçe memory değil, trade tablosu + state ile yönetiyoruz.
# adımlar için geçici seçimleri environment yerine "games.pending_*" kullanacağız: pending_pos = offer, pending_user = target vb.
# pratikte: state=trade_setup, pending_user=target_id, pending_pos=offer_pos, last_action='TRADE:need_request:cash=...'

def parse_trade_setup(last_action: str):
    # format: "TRADE|step=offer|offer=1|req=2|cash=10|proposer=...|target=..."
    if not last_action.startswith("TRADE|"):
        return None
    parts = last_action.split("|")[1:]
    d = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            d[k] = v
    # normalize
    for k in ("offer", "req", "cash", "proposer", "target"):
        if k in d and d[k] != "None":
            try:
                d[k] = int(d[k])
            except:
                pass
        elif k in d:
            d[k] = None
    return d

def make_trade_setup(step: str, proposer: int, target: int, offer=None, req=None, cash=0):
    return f"TRADE|step={step}|proposer={proposer}|target={target}|offer={offer}|req={req}|cash={cash}"

async def trade_send(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    game = DB.get_game(chat_id)
    data = parse_trade_setup(game["last_action"] or "")
    if not data:
        DB.update_game(chat_id, last_action="Takas verisi bulunamadı.", state="turn")
        return

    proposer = data["proposer"]
    target = data["target"]
    offer = data["offer"]
    req = data["req"]
    cash = data["cash"] or 0

    # doğrula sahiplik
    props = DB.get_properties(chat_id)
    if offer not in props or props[offer]["owner_id"] != proposer:
        DB.update_game(chat_id, last_action="Takas iptal: teklif edilen mülk artık sende değil.", state="turn")
        return
    if req not in props or props[req]["owner_id"] != target:
        DB.update_game(chat_id, last_action="Takas iptal: istenen mülk artık karşı tarafta değil.", state="turn")
        return

    # binalı mülkleri takasa kapat (sorunsuzluk için)
    if props[offer]["houses"] or props[offer]["hotel"] or props[req]["houses"] or props[req]["hotel"]:
        DB.update_game(chat_id, last_action="Takas için iki mülkte de ev/otel olmamalı.", state="turn")
        return

    DB.create_trade(chat_id, proposer, target, offer, req, cash)
    DB.update_game(chat_id, state="trade_pending", last_action=f"🤝 Takas teklifi gönderildi: {owner_name(chat_id, proposer)} → {owner_name(chat_id, target)}")
    schedule_trade_timeout(chat_id, context)

async def trade_apply(chat_id: int, accept: bool, context: ContextTypes.DEFAULT_TYPE):
    tr = DB.get_trade(chat_id)
    if not tr:
        DB.update_game(chat_id, state="turn", last_action="Takas bulunamadı.")
        schedule_turn_timeout(chat_id, context)
        return

    proposer = tr["proposer_id"]
    target = tr["target_id"]
    offer = tr["offer_pos"]
    req = tr["request_pos"]
    cash = tr["cash_delta"]

    if not accept:
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="❌ Takas reddedildi.")
        schedule_turn_timeout(chat_id, context)
        return

    props = DB.get_properties(chat_id)
    p1 = DB.get_player(chat_id, proposer)
    p2 = DB.get_player(chat_id, target)
    if not p1 or not p2:
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="Takas iptal: oyuncu bulunamadı.")
        schedule_turn_timeout(chat_id, context)
        return

    # sahiplik tekrar kontrol
    if offer not in props or props[offer]["owner_id"] != proposer:
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="Takas iptal: teklif edilen mülk artık sende değil.")
        schedule_turn_timeout(chat_id, context)
        return
    if req not in props or props[req]["owner_id"] != target:
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="Takas iptal: istenen mülk artık karşı tarafta değil.")
        schedule_turn_timeout(chat_id, context)
        return

    # para farkı uygula
    # cash >0: proposer -> target
    if cash > 0 and p1["money"] < cash:
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="Takas iptal: proposer parası yetmedi.")
        schedule_turn_timeout(chat_id, context)
        return
    if cash < 0 and p2["money"] < abs(cash):
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="Takas iptal: target parası yetmedi.")
        schedule_turn_timeout(chat_id, context)
        return

    # ipotekli devri kuralı: yeni sahip %10 faiz öder (ödeyemezse iptal)
    # offer mülkü target'a geçecek
    # req mülkü proposer'a geçecek
    extra_cost_target = 0
    extra_cost_proposer = 0
    if props[offer]["mortgaged"]:
        extra_cost_target += mortgage_interest(offer)
    if props[req]["mortgaged"]:
        extra_cost_proposer += mortgage_interest(req)

    if p2["money"] < extra_cost_target:
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="Takas iptal: target ipotek faizi ödeyemedi.")
        schedule_turn_timeout(chat_id, context)
        return
    if p1["money"] < extra_cost_proposer:
        DB.clear_trade(chat_id)
        DB.update_game(chat_id, state="turn", last_action="Takas iptal: proposer ipotek faizi ödeyemedi.")
        schedule_turn_timeout(chat_id, context)
        return

    # transfer
    DB.update_property(chat_id, offer, owner_id=target)
    DB.update_property(chat_id, req, owner_id=proposer)

    # cash
    if cash > 0:
        DB.update_player(chat_id, proposer, money=p1["money"] - cash)
        DB.update_player(chat_id, target, money=p2["money"] + cash)
        p1 = DB.get_player(chat_id, proposer)
        p2 = DB.get_player(chat_id, target)
    elif cash < 0:
        DB.update_player(chat_id, target, money=p2["money"] - abs(cash))
        DB.update_player(chat_id, proposer, money=p1["money"] + abs(cash))
        p1 = DB.get_player(chat_id, proposer)
        p2 = DB.get_player(chat_id, target)

    # mortgage interest
    if extra_cost_target:
        DB.update_player(chat_id, target, money=p2["money"] - extra_cost_target)
        p2 = DB.get_player(chat_id, target)
    if extra_cost_proposer:
        DB.update_player(chat_id, proposer, money=p1["money"] - extra_cost_proposer)
        p1 = DB.get_player(chat_id, proposer)

    DB.clear_trade(chat_id)
    DB.update_game(chat_id, state="turn", last_action=(
        f"✅ Takas tamamlandı!\n"
        f"• {p1['name']} aldı: {config.BOARD[req]['name']}\n"
        f"• {p2['name']} aldı: {config.BOARD[offer]['name']}\n"
        + (f"• Para farkı: {cash}$\n" if cash else "")
        + (f"• İpotek faizi ödendi: proposer ${extra_cost_proposer}, target ${extra_cost_target}" if (extra_cost_proposer or extra_cost_target) else "")
    ))
    schedule_turn_timeout(chat_id, context)


# ----------------- Menüler / Listeler -----------------

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
    props = DB.get_properties(chat_id)
    cur = get_current_player(chat_id)
    t = "<b>📊 Durum</b>\n\n"
    if cur and game and game["started"]:
        t += f"➡️ Sıra: <b>{cur['name']}</b>\n\n"
    t += "<b>Oyuncular</b>\n"
    for p in ps:
        tile = config.BOARD[p["position"]]["name"]
        st = "✅" if p["alive"] else "💀"
        t += f"• {p['name']} | ${p['money']} | {tile} | {st}\n"
    t += "\n<b>Mülk sayısı:</b> " + str(len(props))
    return t


# ----------------- Handlers -----------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not DB.game_exists(chat_id):
        DB.create_game(chat_id)

    await ensure_panel_message(chat_id, context)
    await update_panel(chat_id, context)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode="HTML", disable_web_page_preview=True)

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    user_id = q.from_user.id

    if not DB.game_exists(chat_id):
        DB.create_game(chat_id)

    game = DB.get_game(chat_id)

    data = q.data

    # noop
    if data == "noop":
        return

    # help
    if data == "hp":
        await q.message.reply_text(HELP_TEXT, parse_mode="HTML", disable_web_page_preview=True)
        return

    # end
    if data == "en":
        DB.delete_game(chat_id)
        await q.message.reply_text("🛑 Oyun kapatıldı. /start ile tekrar açabilirsiniz.")
        return

    # new game
    if data == "ng":
        DB.create_game(chat_id)
        DB.update_game(chat_id, last_action="Yeni oyun oluşturuldu.")
        await ensure_panel_message(chat_id, context)
        await update_panel(chat_id, context)
        return

    # join
    if data == "jn":
        if game["started"]:
            DB.update_game(chat_id, last_action="Oyun başladı; artık katılamazsın.")
        else:
            ok = DB.add_player(chat_id, user_id, q.from_user.first_name, config.START_MONEY)
            DB.update_game(chat_id, last_action=("✅ Oyuna katıldın." if ok else "Zaten oyundasın."))
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    # start
    if data == "st":
        await start_game(chat_id, context)
        await update_panel(chat_id, context)
        return

    # status
    if data == "ss":
        await q.message.reply_text(format_status(chat_id), parse_mode="HTML")
        return

    # players
    if data == "pl":
        await q.message.reply_text(format_players(chat_id), parse_mode="HTML")
        return

    # my props
    if data == "mp":
        await q.message.reply_text(format_my_props(chat_id, user_id), parse_mode="HTML")
        return

    # roll
    if data == "rl":
        g = DB.get_game(chat_id)
        if not g["started"]:
            DB.update_game(chat_id, last_action="Oyun başlamadı.")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        if g["state"] != "turn":
            DB.update_game(chat_id, last_action="Şu an başka bir işlem var (satın alma/açık artırma/takas).")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        cur = get_current_player(chat_id)
        if not cur or cur["user_id"] != user_id:
            DB.update_game(chat_id, last_action=f"Sıra sende değil. Sıradaki: {cur['name'] if cur else '?'}")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        await do_roll(chat_id, user_id, context, auto=False)
        return

    # buy / pass / auction from buy state
    if data.startswith("buy:"):
        pos = int(data.split(":")[1])
        g = DB.get_game(chat_id)
        if g["state"] == "buy" and g["pending_user"] == user_id and g["pending_pos"] == pos:
            await buy_property(chat_id, user_id, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    if data.startswith("pas:"):
        pos = int(data.split(":")[1])
        g = DB.get_game(chat_id)
        if g["state"] == "buy" and g["pending_user"] == user_id and g["pending_pos"] == pos:
            await pass_buy(chat_id, user_id, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    if data.startswith("auc:"):
        pos = int(data.split(":")[1])
        g = DB.get_game(chat_id)
        if g["state"] == "buy" and g["pending_user"] == user_id and g["pending_pos"] == pos:
            await start_auction_from_buy(chat_id, user_id, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    # auction bid/pass
    if data.startswith("ab:"):
        inc = int(data.split(":")[1])
        await auction_bid(chat_id, user_id, inc, context)
        return

    if data == "ap":
        await auction_pass(chat_id, user_id, context)
        return

    # build / mortgage / trade only current player & state turn
    if data == "bd":
        g = DB.get_game(chat_id)
        cur = get_current_player(chat_id)
        if not g["started"] or g["state"] != "turn" or not cur or cur["user_id"] != user_id:
            DB.update_game(chat_id, last_action="İnşa sadece sıradaki oyuncunun turunda yapılır.")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        # menü aç: panelde last_action'a yazıp paneli güncellemek yerine ayrı menü gönderelim
        await q.message.reply_text("🧱 İnşa menüsü:", reply_markup=kb_build_menu(chat_id, user_id))
        return

    if data.startswith("bdp:"):
        pos = int(data.split(":")[1])
        await q.message.reply_text(
            f"🏗️ {config.BOARD[pos]['name']} için işlem seç:",
            reply_markup=kb_build_actions(pos)
        )
        return

    if data.startswith("bh:"):
        pos = int(data.split(":")[1])
        ok, reason = can_build_house(chat_id, user_id, pos)
        if not ok:
            DB.update_game(chat_id, last_action=f"❌ {reason}")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        tile = config.BOARD[pos]
        cost = tile["price"] // 2
        pl = DB.get_player(chat_id, user_id)
        if pl["money"] < cost:
            DB.update_game(chat_id, last_action="💸 Yeterli para yok.")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        props = DB.get_properties(chat_id)
        DB.update_property(chat_id, pos, houses=props[pos]["houses"] + 1)
        DB.update_player(chat_id, user_id, money=pl["money"] - cost)
        DB.update_game(chat_id, last_action=f"🏠 {tile['name']} mülküne 1 ev kuruldu. (-${cost})")
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    if data.startswith("bt:"):
        pos = int(data.split(":")[1])
        ok, reason = can_build_hotel(chat_id, user_id, pos)
        if not ok:
            DB.update_game(chat_id, last_action=f"❌ {reason}")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        tile = config.BOARD[pos]
        cost = tile["price"]
        pl = DB.get_player(chat_id, user_id)
        if pl["money"] < cost:
            DB.update_game(chat_id, last_action="💸 Yeterli para yok.")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        DB.update_property(chat_id, pos, houses=0, hotel=1)
        DB.update_player(chat_id, user_id, money=pl["money"] - cost)
        DB.update_game(chat_id, last_action=f"🏨 {tile['name']} mülküne otel kuruldu. (-${cost})")
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    if data == "mg":
        g = DB.get_game(chat_id)
        cur = get_current_player(chat_id)
        if not g["started"] or g["state"] != "turn" or not cur or cur["user_id"] != user_id:
            DB.update_game(chat_id, last_action="İpotek sadece sıradaki oyuncunun turunda yapılır.")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        await q.message.reply_text("🏦 İpotek menüsü:", reply_markup=kb_mortgage_menu(chat_id, user_id))
        return

    if data.startswith("mo:"):
        pos = int(data.split(":")[1])
        await toggle_mortgage(chat_id, user_id, pos, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    # trade flow (sadece current player, state turn, zar atmadan önce)
    if data == "tr":
        g = DB.get_game(chat_id)
        cur = get_current_player(chat_id)
        if not g["started"] or g["state"] != "turn" or not cur or cur["user_id"] != user_id:
            DB.update_game(chat_id, last_action="Takas sadece sıradaki oyuncunun turunda (zar atmadan önce) yapılır.")
            await update_panel(chat_id, context, viewer_id=user_id)
            return
        # trade setup başlat: panelde last_action'a setup göm
        DB.update_game(chat_id, last_action=make_trade_setup("pick", proposer=user_id, target=None, offer=None, req=None, cash=0))
        await q.message.reply_text("🤝 Takas yapmak istediğin oyuncuyu seç:", reply_markup=kb_trade_pick(chat_id, user_id))
        return

    if data.startswith("trt:"):
        target_id = int(data.split(":")[1])
        game = DB.get_game(chat_id)
        dct = parse_trade_setup(game["last_action"] or "")
        if not dct or dct.get("proposer") != user_id:
            return
        DB.update_game(chat_id, last_action=make_trade_setup("offer", proposer=user_id, target=target_id, offer=None, req=None, cash=0))
        await q.message.reply_text("Takas: vereceğin mülkü seç:", reply_markup=kb_trade_choose_props(chat_id, user_id, target_id, "offer"))
        return

    if data.startswith("tro:"):
        offer_pos = int(data.split(":")[1])
        game = DB.get_game(chat_id)
        dct = parse_trade_setup(game["last_action"] or "")
        if not dct or dct.get("proposer") != user_id:
            return
        target_id = dct["target"]
        DB.update_game(chat_id, last_action=make_trade_setup("req", proposer=user_id, target=target_id, offer=offer_pos, req=None, cash=dct.get("cash", 0) or 0))
        await q.message.reply_text("Takas: istediğin mülkü seç:", reply_markup=kb_trade_choose_props(chat_id, user_id, target_id, "req"))
        return

    if data.startswith("trr:"):
        req_pos = int(data.split(":")[1])
        game = DB.get_game(chat_id)
        dct = parse_trade_setup(game["last_action"] or "")
        if not dct or dct.get("proposer") != user_id:
            return
        target_id = dct["target"]
        offer_pos = dct["offer"]
        cash = dct.get("cash", 0) or 0
        DB.update_game(chat_id, last_action=make_trade_setup("confirm", proposer=user_id, target=target_id, offer=offer_pos, req=req_pos, cash=cash))
        await q.message.reply_text(
            "Takas: para farkı ayarla (opsiyonel) ve gönder:",
            reply_markup=kb_trade_choose_props(chat_id, user_id, target_id, "req", selected_offer=offer_pos, selected_req=req_pos, cash_delta=cash)
        )
        return

    if data.startswith("trc:"):
        delta = int(data.split(":")[1])
        game = DB.get_game(chat_id)
        dct = parse_trade_setup(game["last_action"] or "")
        if not dct or dct.get("proposer") != user_id:
            return
        cash = (dct.get("cash", 0) or 0) + delta
        DB.update_game(chat_id, last_action=make_trade_setup("confirm", proposer=dct["proposer"], target=dct["target"], offer=dct["offer"], req=dct["req"], cash=cash))
        await q.message.reply_text(
            f"Para farkı güncellendi: Δ={cash}$",
            reply_markup=kb_trade_choose_props(chat_id, user_id, dct["target"], "req", selected_offer=dct["offer"], selected_req=dct["req"], cash_delta=cash)
        )
        return

    if data == "tr_send":
        game = DB.get_game(chat_id)
        dct = parse_trade_setup(game["last_action"] or "")
        if not dct or dct.get("proposer") != user_id:
            return
        await trade_send(chat_id, context)
        await update_panel(chat_id, context)
        return

    if data == "tr_cancel":
        DB.update_game(chat_id, last_action="Takas iptal.", state="turn")
        schedule_turn_timeout(chat_id, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    if data == "tr_yes":
        game = DB.get_game(chat_id)
        tr = DB.get_trade(chat_id)
        if not tr or game["state"] != "trade_pending" or tr["target_id"] != user_id:
            return
        await trade_apply(chat_id, True, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    if data == "tr_no":
        game = DB.get_game(chat_id)
        tr = DB.get_trade(chat_id)
        if not tr or game["state"] != "trade_pending" or tr["target_id"] != user_id:
            return
        await trade_apply(chat_id, False, context)
        await update_panel(chat_id, context, viewer_id=user_id)
        return

    if data == "back_turn":
        # sadece bilgi
        return

    # fallback
    DB.update_game(chat_id, last_action="Bilinmeyen buton.")
    await update_panel(chat_id, context, viewer_id=user_id)


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable eksik.")

    DB.init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(on_button))

    print("KGB Monopoly FINAL (V5) running...")
    app.run_polling()

if __name__ == "__main__":
    main()
