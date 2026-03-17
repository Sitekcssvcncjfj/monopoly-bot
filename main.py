import os
import random
import sqlite3
from contextlib import closing

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "monopoly.db"

START_MONEY = 1500
GO_BONUS = 200
JAIL_POS = 10

BOARD = [
    {"name": "Başlangıç", "type": "start"},
    {"name": "Kadıköy", "type": "property", "price": 60, "rent": 10, "color": "🟤"},
    {"name": "Kasa", "type": "community"},
    {"name": "Beşiktaş", "type": "property", "price": 60, "rent": 10, "color": "🟤"},
    {"name": "Gelir Vergisi", "type": "tax", "amount": 100},
    {"name": "Üsküdar", "type": "property", "price": 100, "rent": 15, "color": "🔵"},
    {"name": "Şans", "type": "chance"},
    {"name": "Taksim", "type": "property", "price": 100, "rent": 15, "color": "🔵"},
    {"name": "Şişli", "type": "property", "price": 120, "rent": 20, "color": "🔵"},
    {"name": "Hapis Ziyareti", "type": "jail_visit"},
    {"name": "Bakırköy", "type": "property", "price": 140, "rent": 25, "color": "🟣"},
    {"name": "Elektrik İdaresi", "type": "property", "price": 150, "rent": 30, "color": "⚡"},
    {"name": "Bebek", "type": "property", "price": 140, "rent": 25, "color": "🟣"},
    {"name": "Kasa", "type": "community"},
    {"name": "Levent", "type": "property", "price": 160, "rent": 30, "color": "🟣"},
    {"name": "Vapur İskelesi", "type": "property", "price": 200, "rent": 40, "color": "🚢"},
    {"name": "Etiler", "type": "property", "price": 180, "rent": 35, "color": "🟠"},
    {"name": "Şans", "type": "chance"},
    {"name": "Maslak", "type": "property", "price": 180, "rent": 35, "color": "🟠"},
    {"name": "Mecidiyeköy", "type": "property", "price": 200, "rent": 40, "color": "🟠"},
    {"name": "Ücretsiz Park", "type": "free"},
    {"name": "Ataköy", "type": "property", "price": 220, "rent": 45, "color": "🔴"},
    {"name": "Şans", "type": "chance"},
    {"name": "Florya", "type": "property", "price": 220, "rent": 45, "color": "🔴"},
    {"name": "Yeşilköy", "type": "property", "price": 240, "rent": 50, "color": "🔴"},
    {"name": "Metrobüs", "type": "property", "price": 200, "rent": 40, "color": "🚇"},
    {"name": "Kartal", "type": "property", "price": 260, "rent": 55, "color": "🟡"},
    {"name": "Pendik", "type": "property", "price": 260, "rent": 55, "color": "🟡"},
    {"name": "Su İdaresi", "type": "property", "price": 150, "rent": 30, "color": "💧"},
    {"name": "Tuzla", "type": "property", "price": 280, "rent": 60, "color": "🟡"},
    {"name": "Hapise Git", "type": "goto_jail"},
    {"name": "Beylikdüzü", "type": "property", "price": 300, "rent": 65, "color": "🟢"},
    {"name": "Avcılar", "type": "property", "price": 300, "rent": 65, "color": "🟢"},
    {"name": "Kasa", "type": "community"},
    {"name": "Silivri", "type": "property", "price": 320, "rent": 70, "color": "🟢"},
    {"name": "Lüks Vergisi", "type": "tax", "amount": 150},
    {"name": "Şans", "type": "chance"},
    {"name": "Boğaz", "type": "property", "price": 350, "rent": 80, "color": "🔷"},
    {"name": "Kasa", "type": "community"},
    {"name": "Sarayburnu", "type": "property", "price": 400, "rent": 100, "color": "🔷"},
]

CHANCE_CARDS = [
    ("Piyango kazandın! +150$", 150),
    ("Banka hatası lehine! +200$", 200),
    ("Doktor ücreti öde. -50$", -50),
    ("Arabayı tamire verdin. -100$", -100),
    ("Başlangıç primi aldın. +100$", 100),
]

COMMUNITY_CARDS = [
    ("Miras kaldı! +100$", 100),
    ("Okul taksiti öde. -80$", -80),
    ("Doğum günü hediyesi aldın. +50$", 50),
    ("Elektrik faturası öde. -60$", -60),
    ("Borsa kazancı! +120$", 120),
]

# ---------------- DB ----------------

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS games (
                chat_id INTEGER PRIMARY KEY,
                started INTEGER DEFAULT 0,
                turn INTEGER DEFAULT 0,
                waiting_buy_user INTEGER,
                waiting_buy_pos INTEGER
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS players (
                chat_id INTEGER,
                user_id INTEGER,
                name TEXT,
                money INTEGER,
                position INTEGER,
                alive INTEGER,
                in_jail INTEGER,
                jail_turns INTEGER,
                doubles_count INTEGER,
                PRIMARY KEY (chat_id, user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS properties (
                chat_id INTEGER,
                position INTEGER,
                owner_id INTEGER,
                PRIMARY KEY (chat_id, position)
            )
        """)
        conn.commit()

def create_game(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM games WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM players WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM properties WHERE chat_id = ?", (chat_id,))
        c.execute(
            "INSERT INTO games (chat_id, started, turn, waiting_buy_user, waiting_buy_pos) VALUES (?, 0, 0, NULL, NULL)",
            (chat_id,)
        )
        conn.commit()

def game_exists(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM games WHERE chat_id = ?", (chat_id,))
        return c.fetchone() is not None

def get_game(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT chat_id, started, turn, waiting_buy_user, waiting_buy_pos FROM games WHERE chat_id = ?", (chat_id,))
        row = c.fetchone()
        if not row:
            return None
        return {
            "chat_id": row[0],
            "started": bool(row[1]),
            "turn": row[2],
            "waiting_buy_user": row[3],
            "waiting_buy_pos": row[4],
        }

def update_game(chat_id, **kwargs):
    if not kwargs:
        return
    keys = []
    values = []
    for k, v in kwargs.items():
        keys.append(f"{k} = ?")
        values.append(v)
    values.append(chat_id)
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE games SET {', '.join(keys)} WHERE chat_id = ?", values)
        conn.commit()

def add_player(chat_id, user_id, name):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM players WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
        if c.fetchone():
            return False
        c.execute("""
            INSERT INTO players (chat_id, user_id, name, money, position, alive, in_jail, jail_turns, doubles_count)
            VALUES (?, ?, ?, ?, 0, 1, 0, 0, 0)
        """, (chat_id, user_id, name, START_MONEY))
        conn.commit()
        return True

def get_players(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT user_id, name, money, position, alive, in_jail, jail_turns, doubles_count
            FROM players
            WHERE chat_id = ?
            ORDER BY rowid
        """, (chat_id,))
        rows = c.fetchall()
        return [
            {
                "user_id": r[0],
                "name": r[1],
                "money": r[2],
                "position": r[3],
                "alive": bool(r[4]),
                "in_jail": bool(r[5]),
                "jail_turns": r[6],
                "doubles_count": r[7],
            }
            for r in rows
        ]

def update_player(chat_id, user_id, **kwargs):
    if not kwargs:
        return
    keys = []
    values = []
    for k, v in kwargs.items():
        keys.append(f"{k} = ?")
        values.append(v)
    values.extend([chat_id, user_id])
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE players SET {', '.join(keys)} WHERE chat_id = ? AND user_id = ?", values)
        conn.commit()

def set_property_owner(chat_id, position, owner_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO properties (chat_id, position, owner_id)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id, position) DO UPDATE SET owner_id=excluded.owner_id
        """, (chat_id, position, owner_id))
        conn.commit()

def delete_properties_of_player(chat_id, owner_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM properties WHERE chat_id = ? AND owner_id = ?", (chat_id, owner_id))
        conn.commit()

def get_properties(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT position, owner_id FROM properties WHERE chat_id = ?", (chat_id,))
        rows = c.fetchall()
        return {r[0]: r[1] for r in rows}

def delete_game(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM games WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM players WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM properties WHERE chat_id = ?", (chat_id,))
        conn.commit()

# ---------------- UI ----------------

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Yeni Oyun", callback_data="newgame"),
            InlineKeyboardButton("➕ Katıl", callback_data="join"),
        ],
        [
            InlineKeyboardButton("▶️ Başlat", callback_data="startgame"),
            InlineKeyboardButton("🎲 Zar At", callback_data="roll"),
        ],
        [
            InlineKeyboardButton("📊 Durum", callback_data="status"),
            InlineKeyboardButton("👥 Oyuncular", callback_data="players"),
        ],
        [
            InlineKeyboardButton("🏠 Mülklerim", callback_data="myprops"),
            InlineKeyboardButton("🛑 Bitir", callback_data="endgame"),
        ],
    ])

def buy_menu(position):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Satın Al", callback_data=f"buy_{position}"),
            InlineKeyboardButton("❌ Geç", callback_data=f"pass_{position}"),
        ]
    ])

async def send_or_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup)

async def is_admin(chat, user_id, bot):
    member = await bot.get_chat_member(chat.id, user_id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

def get_current_player(chat_id):
    game = get_game(chat_id)
    if not game:
        return None
    players = get_players(chat_id)
    if not players:
        return None
    if game["turn"] >= len(players):
        update_game(chat_id, turn=0)
        return players[0]
    return players[game["turn"]]

def next_turn(chat_id):
    game = get_game(chat_id)
    players = get_players(chat_id)
    alive_indices = [i for i, p in enumerate(players) if p["alive"]]
    if len(alive_indices) <= 1:
        return None
    turn = game["turn"]
    while True:
        turn = (turn + 1) % len(players)
        if players[turn]["alive"]:
            update_game(chat_id, turn=turn)
            return players[turn]

def owner_name(chat_id, owner_id):
    players = get_players(chat_id)
    p = next((x for x in players if x["user_id"] == owner_id), None)
    return p["name"] if p else "Bilinmiyor"

def format_status(chat_id):
    game = get_game(chat_id)
    players = get_players(chat_id)
    props = get_properties(chat_id)

    text = "🎲 Oyun Durumu\n\n"
    for i, p in enumerate(players, start=1):
        state = "✅" if p["alive"] else "💀"
        jail = " 🚓" if p["in_jail"] else ""
        tile = BOARD[p["position"]]["name"]
        turn_mark = " ⬅️" if game and game["started"] and i - 1 == game["turn"] else ""
        text += f"{i}. {p['name']} | 💰 ${p['money']} | 📍 {tile}{jail} | {state}{turn_mark}\n"

    text += "\n🏠 Satın Alınan Mülkler:\n"
    if not props:
        text += "Yok\n"
    else:
        for pos, own_id in props.items():
            text += f"- {BOARD[pos]['name']} → {owner_name(chat_id, own_id)}\n"

    return text

def format_players(chat_id):
    players = get_players(chat_id)
    if not players:
        return "Oyuncu yok."
    text = "👥 Oyuncular\n\n"
    for i, p in enumerate(players, start=1):
        state = "✅" if p["alive"] else "💀"
        text += f"{i}. {p['name']} | ${p['money']} | {state}\n"
    return text

def format_my_props(chat_id, user_id):
    props = get_properties(chat_id)
    my_positions = [pos for pos, owner in props.items() if owner == user_id]
    if not my_positions:
        return "🏠 Henüz mülkün yok."
    text = "🏠 Mülklerin\n\n"
    total = 0
    for pos in my_positions:
        tile = BOARD[pos]
        total += tile.get("price", 0)
        text += f"- {tile['name']} | Fiyat: ${tile.get('price', 0)} | Kira: ${tile.get('rent', 0)}\n"
    text += f"\n💎 Toplam portföy değeri: ${total}"
    return text

def apply_money(chat_id, user_id, delta):
    players = get_players(chat_id)
    player = next((p for p in players if p["user_id"] == user_id), None)
    if not player:
        return None, None
    new_money = player["money"] + delta
    alive = 1
    msg = None
    if new_money < 0:
        alive = 0
        msg = f"💀 {player['name']} iflas etti!"
        delete_properties_of_player(chat_id, user_id)
    update_player(chat_id, user_id, money=new_money, alive=alive)
    return new_money, msg

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎩 Monopoly Bot V2\n\nButonları kullanarak oynayabilirsiniz.",
        reply_markup=main_menu()
    )

# ---------------- BUTTONS ----------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat = query.message.chat
    chat_id = chat.id
    user = query.from_user
    data = query.data

    if data == "newgame":
        if not await is_admin(chat, user.id, context.bot):
            return await send_or_edit(query, "Bu işlemi sadece admin yapabilir.", main_menu())
        create_game(chat_id)
        return await send_or_edit(query, "🎮 Yeni oyun oluşturuldu!\nKatılmak için ➕ Katıl", main_menu())

    if data == "join":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Önce yeni oyun oluşturulmalı.", main_menu())
        game = get_game(chat_id)
        if game["started"]:
            return await send_or_edit(query, "Oyun başladı, artık katılamazsın.", main_menu())
        ok = add_player(chat_id, user.id, user.first_name)
        if ok:
            players = get_players(chat_id)
            return await send_or_edit(query, f"✅ {user.first_name} katıldı.\nOyuncu sayısı: {len(players)}", main_menu())
        return await send_or_edit(query, "Zaten oyundasın.", main_menu())

    if data == "startgame":
        if not await is_admin(chat, user.id, context.bot):
            return await send_or_edit(query, "Oyunu sadece admin başlatabilir.", main_menu())
        if not game_exists(chat_id):
            return await send_or_edit(query, "Önce yeni oyun oluştur.", main_menu())
        players = get_players(chat_id)
        if len(players) < 2:
            return await send_or_edit(query, "En az 2 oyuncu gerekli.", main_menu())
        update_game(chat_id, started=1, turn=0)
        cur = get_current_player(chat_id)
        return await send_or_edit(query, f"🚀 Oyun başladı!\nİlk sıra: {cur['name']}", main_menu())

    if data == "status":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        return await send_or_edit(query, format_status(chat_id), main_menu())

    if data == "players":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        return await send_or_edit(query, format_players(chat_id), main_menu())

    if data == "myprops":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        return await send_or_edit(query, format_my_props(chat_id, user.id), main_menu())

    if data == "endgame":
        if not await is_admin(chat, user.id, context.bot):
            return await send_or_edit(query, "Oyunu sadece admin bitirebilir.", main_menu())
        delete_game(chat_id)
        return await send_or_edit(query, "🛑 Oyun sonlandırıldı.", main_menu())

    if data == "roll":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())

        game = get_game(chat_id)
        if not game["started"]:
            return await send_or_edit(query, "Oyun başlamadı.", main_menu())

        current = get_current_player(chat_id)
        if not current:
            return await send_or_edit(query, "Oyuncu bulunamadı.", main_menu())

        if current["user_id"] != user.id:
            return await send_or_edit(query, f"⏳ Sıra sende değil.\nSıradaki: {current['name']}", main_menu())

        if current["in_jail"]:
            jail_turns = current["jail_turns"] + 1
            if jail_turns >= 2:
                update_player(chat_id, user.id, in_jail=0, jail_turns=0)
                jail_text = "🔓 Hapisten çıktın.\n"
            else:
                update_player(chat_id, user.id, jail_turns=jail_turns)
                nxt = next_turn(chat_id)
                return await send_or_edit(
                    query,
                    f"🚓 Hapistesin. Bu tur oynayamadın.\n➡️ Sıradaki: {nxt['name']}",
                    main_menu()
                )
        else:
            jail_text = ""

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        total = d1 + d2
        is_double = d1 == d2

        doubles_count = current["doubles_count"] + 1 if is_double else 0

        if doubles_count >= 3:
            update_player(
                chat_id,
                user.id,
                position=JAIL_POS,
                in_jail=1,
                jail_turns=0,
                doubles_count=0
            )
            nxt = next_turn(chat_id)
            return await send_or_edit(
                query,
                f"🎲 {current['name']} {d1}+{d2} attı.\n"
                f"😵 3 kez çift zar geldi!\n🚓 Hapse gönderildin.\n"
                f"➡️ Sıradaki: {nxt['name']}",
                main_menu()
            )

        old_pos = current["position"]
        new_pos = (old_pos + total) % len(BOARD)
        money = current["money"]

        text = f"{jail_text}🎲 {current['name']} zar attı: {d1} + {d2} = {total}\n"

        if new_pos < old_pos:
            money += GO_BONUS
            text += f"🏁 Başlangıç geçildi, +${GO_BONUS}\n"

        tile = BOARD[new_pos]
        text += f"📍 {tile['name']} karesine geldi.\n"

        update_player(chat_id, user.id, position=new_pos, money=money, doubles_count=doubles_count)

        props = get_properties(chat_id)

        if tile["type"] == "property":
            owner_id = props.get(new_pos)
            if owner_id is None:
                if money >= tile["price"]:
                    update_game(chat_id, waiting_buy_user=user.id, waiting_buy_pos=new_pos)
                    return await send_or_edit(
                        query,
                        text + f"🏠 Bu mülk boş.\nFiyat: ${tile['price']}\nAlmak ister misin?",
                        buy_menu(new_pos)
                    )
                else:
                    text += "💸 Yeterli para yok, satın alamazsın.\n"

            elif owner_id != user.id:
                rent = tile["rent"]
                owner = next((p for p in get_players(chat_id) if p["user_id"] == owner_id), None)

                player_money, bankrupt_msg = apply_money(chat_id, user.id, -rent)
                if owner and owner["alive"]:
                    apply_money(chat_id, owner_id, rent)

                text += f"💰 {owner['name']} oyuncusuna ${rent} kira ödendi.\n"
                if bankrupt_msg:
                    text += bankrupt_msg + "\n"

            else:
                text += "🏡 Kendi mülkün.\n"

        elif tile["type"] == "tax":
            _, bankrupt_msg = apply_money(chat_id, user.id, -tile["amount"])
            text += f"🧾 Vergi ödedin: -${tile['amount']}\n"
            if bankrupt_msg:
                text += bankrupt_msg + "\n"

        elif tile["type"] == "chance":
            card_text, delta = random.choice(CHANCE_CARDS)
            _, bankrupt_msg = apply_money(chat_id, user.id, delta)
            sign = "+" if delta >= 0 else "-"
            text += f"🎴 Şans: {card_text} ({sign}${abs(delta)})\n"
            if bankrupt_msg:
                text += bankrupt_msg + "\n"

        elif tile["type"] == "community":
            card_text, delta = random.choice(COMMUNITY_CARDS)
            _, bankrupt_msg = apply_money(chat_id, user.id, delta)
            sign = "+" if delta >= 0 else "-"
            text += f"📦 Kasa: {card_text} ({sign}${abs(delta)})\n"
            if bankrupt_msg:
                text += bankrupt_msg + "\n"

        elif tile["type"] == "goto_jail":
            update_player(chat_id, user.id, position=JAIL_POS, in_jail=1, jail_turns=0, doubles_count=0)
            text += "🚓 Hapise gönderildin!\n"

        elif tile["type"] == "free":
            text += "🅿️ Ücretsiz park. Dinlen.\n"

        elif tile["type"] == "jail_visit":
            text += "👮 Sadece ziyaret.\n"

        alive_players = [p for p in get_players(chat_id) if p["alive"]]
        if len(alive_players) == 1:
            winner = alive_players[0]
            delete_game(chat_id)
            return await send_or_edit(query, text + f"\n🏆 Kazanan: {winner['name']}", main_menu())

        if is_double and any(p["user_id"] == user.id and p["alive"] for p in get_players(chat_id)):
            text += "\n✨ Çift zar geldi, tekrar oynayabilirsin!"
            return await send_or_edit(query, text, main_menu())

        nxt = next_turn(chat_id)
        text += f"\n➡️ Sıradaki: {nxt['name']}"
        return await send_or_edit(query, text, main_menu())

    if data.startswith("buy_"):
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        game = get_game(chat_id)
        pos = int(data.split("_")[1])

        if game["waiting_buy_user"] != user.id or game["waiting_buy_pos"] != pos:
            return await send_or_edit(query, "Bu satın alma sırası sende değil.", main_menu())

        player = next((p for p in get_players(chat_id) if p["user_id"] == user.id), None)
        tile = BOARD[pos]

        if not player:
            return await send_or_edit(query, "Oyuncu bulunamadı.", main_menu())

        if player["money"] < tile["price"]:
            update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)
            nxt = next_turn(chat_id)
            return await send_or_edit(query, f"💸 Yetersiz bakiye.\n➡️ Sıradaki: {nxt['name']}", main_menu())

        update_player(chat_id, user.id, money=player["money"] - tile["price"])
        set_property_owner(chat_id, pos, user.id)
        update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)

        nxt = next_turn(chat_id)
        return await send_or_edit(
            query,
            f"✅ {player['name']} {tile['name']} mülkünü satın aldı.\n➡️ Sıradaki: {nxt['name']}",
            main_menu()
        )

    if data.startswith("pass_"):
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        game = get_game(chat_id)
        pos = int(data.split("_")[1])

        if game["waiting_buy_user"] != user.id or game["waiting_buy_pos"] != pos:
            return await send_or_edit(query, "Bu işlem sana ait değil.", main_menu())

        update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)
        nxt = next_turn(chat_id)
        return await send_or_edit(
            query,
            f"❌ {BOARD[pos]['name']} satın alınmadı.\n➡️ Sıradaki: {nxt['name']}",
            main_menu()
        )

# ---------------- MAIN ----------------

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN eksik.")
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Monopoly Bot V2 çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
