import os
import random
import sqlite3
from contextlib import closing
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = "monopoly.db"

START_MONEY = 1500
GO_BONUS = 200
JAIL_POS = 9

SUPPORT_URL = "https://t.me/KGBotomasyon"
ADD_BOT_URL = "https://t.me/KGBMonopolyBOT?startgroup=true"

BOARD = [
    {"name": "Başlangıç", "type": "start"},
    {"name": "Kadıköy", "type": "property", "price": 100, "base_rent": 20, "color": "brown"},
    {"name": "Kasa", "type": "community"},
    {"name": "Beşiktaş", "type": "property", "price": 100, "base_rent": 20, "color": "brown"},
    {"name": "Vergi", "type": "tax", "amount": 100},
    {"name": "Üsküdar", "type": "property", "price": 140, "base_rent": 30, "color": "blue"},
    {"name": "Şans", "type": "chance"},
    {"name": "Taksim", "type": "property", "price": 140, "base_rent": 30, "color": "blue"},
    {"name": "Şişli", "type": "property", "price": 160, "base_rent": 35, "color": "blue"},
    {"name": "Hapis", "type": "jail"},
    {"name": "Bakırköy", "type": "property", "price": 180, "base_rent": 40, "color": "pink"},
    {"name": "Elektrik İdaresi", "type": "utility", "price": 150, "base_rent": 35, "color": "utility"},
    {"name": "Bebek", "type": "property", "price": 180, "base_rent": 40, "color": "pink"},
    {"name": "Kasa", "type": "community"},
    {"name": "Levent", "type": "property", "price": 200, "base_rent": 45, "color": "pink"},
    {"name": "Vapur İskelesi", "type": "railroad", "price": 200, "base_rent": 50, "color": "railroad"},
    {"name": "Etiler", "type": "property", "price": 220, "base_rent": 50, "color": "orange"},
    {"name": "Şans", "type": "chance"},
    {"name": "Maslak", "type": "property", "price": 220, "base_rent": 50, "color": "orange"},
    {"name": "Mecidiyeköy", "type": "property", "price": 240, "base_rent": 55, "color": "orange"},
    {"name": "Ücretsiz Park", "type": "free"},
    {"name": "Ataköy", "type": "property", "price": 260, "base_rent": 60, "color": "red"},
    {"name": "Şans", "type": "chance"},
    {"name": "Florya", "type": "property", "price": 260, "base_rent": 60, "color": "red"},
    {"name": "Yeşilköy", "type": "property", "price": 280, "base_rent": 65, "color": "red"},
    {"name": "Metrobüs", "type": "railroad", "price": 200, "base_rent": 50, "color": "railroad"},
    {"name": "Kartal", "type": "property", "price": 300, "base_rent": 70, "color": "yellow"},
    {"name": "Pendik", "type": "property", "price": 300, "base_rent": 70, "color": "yellow"},
    {"name": "Su İdaresi", "type": "utility", "price": 150, "base_rent": 35, "color": "utility"},
    {"name": "Tuzla", "type": "property", "price": 320, "base_rent": 75, "color": "yellow"},
    {"name": "Hapise Git", "type": "goto_jail"},
    {"name": "Beylikdüzü", "type": "property", "price": 340, "base_rent": 80, "color": "green"},
    {"name": "Avcılar", "type": "property", "price": 340, "base_rent": 80, "color": "green"},
    {"name": "Kasa", "type": "community"},
    {"name": "Silivri", "type": "property", "price": 360, "base_rent": 85, "color": "green"},
    {"name": "Lüks Vergisi", "type": "tax", "amount": 150},
    {"name": "Şans", "type": "chance"},
    {"name": "Boğaz", "type": "property", "price": 380, "base_rent": 90, "color": "darkblue"},
    {"name": "Kasa", "type": "community"},
    {"name": "Sarayburnu", "type": "property", "price": 400, "base_rent": 100, "color": "darkblue"},
]

COLOR_GROUPS = {
    "brown": [1, 3],
    "blue": [5, 7, 8],
    "pink": [10, 12, 14],
    "orange": [16, 18, 19],
    "red": [21, 23, 24],
    "yellow": [26, 27, 29],
    "green": [31, 32, 34],
    "darkblue": [37, 39],
}

CHANCE_CARDS = [
    ("Piyango kazandın", 150),
    ("Araban bozuldu", -100),
    ("Maaş primi aldın", 120),
    ("Cüzdanını düşürdün", -80),
]

COMMUNITY_CARDS = [
    ("Miras kaldı", 100),
    ("Fatura ödedin", -70),
    ("Doğum günü hediyesi aldın", 80),
    ("Borsa kazancı", 130),
]

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
                waiting_buy_pos INTEGER,
                auction_pos INTEGER,
                auction_turn_user INTEGER,
                auction_highest_bid INTEGER DEFAULT 0,
                auction_highest_user INTEGER
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
                houses INTEGER DEFAULT 0,
                hotel INTEGER DEFAULT 0,
                mortgaged INTEGER DEFAULT 0,
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
        c.execute("""
            INSERT INTO games (
                chat_id, started, turn, waiting_buy_user, waiting_buy_pos,
                auction_pos, auction_turn_user, auction_highest_bid, auction_highest_user
            ) VALUES (?, 0, 0, NULL, NULL, NULL, NULL, 0, NULL)
        """, (chat_id,))
        conn.commit()

def game_exists(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM games WHERE chat_id = ?", (chat_id,))
        return c.fetchone() is not None

def get_game(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT chat_id, started, turn, waiting_buy_user, waiting_buy_pos,
                   auction_pos, auction_turn_user, auction_highest_bid, auction_highest_user
            FROM games WHERE chat_id = ?
        """, (chat_id,))
        row = c.fetchone()
        if not row:
            return None
        return {
            "chat_id": row[0],
            "started": bool(row[1]),
            "turn": row[2],
            "waiting_buy_user": row[3],
            "waiting_buy_pos": row[4],
            "auction_pos": row[5],
            "auction_turn_user": row[6],
            "auction_highest_bid": row[7],
            "auction_highest_user": row[8],
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
            FROM players WHERE chat_id = ?
            ORDER BY rowid
        """, (chat_id,))
        rows = c.fetchall()
        return [{
            "user_id": r[0],
            "name": r[1],
            "money": r[2],
            "position": r[3],
            "alive": bool(r[4]),
            "in_jail": bool(r[5]),
            "jail_turns": r[6],
            "doubles_count": r[7],
        } for r in rows]

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

def get_properties(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("SELECT position, owner_id, houses, hotel, mortgaged FROM properties WHERE chat_id = ?", (chat_id,))
        rows = c.fetchall()
        return {
            r[0]: {
                "owner_id": r[1],
                "houses": r[2],
                "hotel": r[3],
                "mortgaged": r[4],
            } for r in rows
        }

def set_property_owner(chat_id, position, owner_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO properties (chat_id, position, owner_id, houses, hotel, mortgaged)
            VALUES (?, ?, ?, 0, 0, 0)
            ON CONFLICT(chat_id, position) DO UPDATE SET owner_id=excluded.owner_id
        """, (chat_id, position, owner_id))
        conn.commit()

def update_property(chat_id, position, **kwargs):
    if not kwargs:
        return
    keys = []
    values = []
    for k, v in kwargs.items():
        keys.append(f"{k} = ?")
        values.append(v)
    values.extend([chat_id, position])
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE properties SET {', '.join(keys)} WHERE chat_id = ? AND position = ?", values)
        conn.commit()

def delete_properties_of_player(chat_id, owner_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM properties WHERE chat_id = ? AND owner_id = ?", (chat_id, owner_id))
        conn.commit()

def delete_game(chat_id):
    with closing(db()) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM games WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM players WHERE chat_id = ?", (chat_id,))
        c.execute("DELETE FROM properties WHERE chat_id = ?", (chat_id,))
        conn.commit()

def get_current_player(chat_id):
    game = get_game(chat_id)
    players = get_players(chat_id)
    if not game or not players:
        return None
    turn = game["turn"]
    if turn >= len(players):
        update_game(chat_id, turn=0)
        return players[0]
    return players[turn]

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
    player = next((p for p in get_players(chat_id) if p["user_id"] == owner_id), None)
    return player["name"] if player else "Bilinmiyor"

def owns_full_set(chat_id, user_id, color):
    if color not in COLOR_GROUPS:
        return False
    props = get_properties(chat_id)
    for pos in COLOR_GROUPS[color]:
        if pos not in props or props[pos]["owner_id"] != user_id:
            return False
    return True

def calculate_rent(chat_id, position):
    tile = BOARD[position]
    props = get_properties(chat_id)
    if position not in props:
        return tile.get("base_rent", 0)

    prop = props[position]
    if prop["mortgaged"]:
        return 0

    base = tile.get("base_rent", 0)
    if prop["hotel"]:
        return base * 6
    if prop["houses"] > 0:
        return base * (prop["houses"] + 1)

    if tile["type"] == "property" and owns_full_set(chat_id, prop["owner_id"], tile["color"]):
        return base * 2

    return base

def can_build_house(chat_id, user_id, position):
    tile = BOARD[position]
    props = get_properties(chat_id)
    prop = props.get(position)
    if tile["type"] != "property":
        return False, "Bu mülke ev kurulmaz."
    if not prop or prop["owner_id"] != user_id:
        return False, "Bu mülk sana ait değil."
    if prop["mortgaged"]:
        return False, "İpotekli mülke ev kurulmaz."
    if not owns_full_set(chat_id, user_id, tile["color"]):
        return False, "Önce renk setini tamamlamalısın."
    if prop["hotel"]:
        return False, "Zaten otel var."
    if prop["houses"] >= 4:
        return False, "Önce otel kurman gerekir."
    return True, None

def can_build_hotel(chat_id, user_id, position):
    tile = BOARD[position]
    props = get_properties(chat_id)
    prop = props.get(position)
    if tile["type"] != "property":
        return False, "Bu mülke otel kurulmaz."
    if not prop or prop["owner_id"] != user_id:
        return False, "Bu mülk sana ait değil."
    if prop["mortgaged"]:
        return False, "İpotekli mülke otel kurulmaz."
    if prop["hotel"]:
        return False, "Zaten otel var."
    if prop["houses"] < 4:
        return False, "Önce 4 ev kurmalısın."
    return True, None

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

def main_menu(is_private=False):
    if is_private:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Beni Gruba Ekle", url=ADD_BOT_URL)],
            [InlineKeyboardButton("🆘 Destek", url=SUPPORT_URL)],
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
                InlineKeyboardButton("🛑 Bitir", callback_data="endgame"),
            ]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Yeni Oyun", callback_data="newgame"),
         InlineKeyboardButton("➕ Katıl", callback_data="join")],
        [InlineKeyboardButton("▶️ Başlat", callback_data="startgame"),
         InlineKeyboardButton("🎲 Zar At", callback_data="roll")],
        [InlineKeyboardButton("📊 Durum", callback_data="status"),
         InlineKeyboardButton("👥 Oyuncular", callback_data="players")],
        [InlineKeyboardButton("🏠 Mülklerim", callback_data="myprops"),
         InlineKeyboardButton("🧱 Geliştir", callback_data="build_menu")],
        [InlineKeyboardButton("🏦 İpotek", callback_data="mortgage_menu"),
         InlineKeyboardButton("🤝 Takas", callback_data="trade_menu")],
        [InlineKeyboardButton("🆘 Destek", url=SUPPORT_URL),
         InlineKeyboardButton("➕ Beni Gruba Ekle", url=ADD_BOT_URL)],
        [InlineKeyboardButton("🛑 Bitir", callback_data="endgame")],
    ])

def buy_menu(position):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Satın Al", callback_data=f"buy_{position}")],
        [InlineKeyboardButton("📢 Açık Artırma", callback_data=f"auction_{position}")],
        [InlineKeyboardButton("❌ Geç", callback_data=f"pass_{position}")]
    ])

def build_menu_for_player(chat_id, user_id):
    props = get_properties(chat_id)
    buttons = []
    for pos, info in props.items():
        if info["owner_id"] == user_id and BOARD[pos]["type"] == "property":
            buttons.append([InlineKeyboardButton(f"🧱 {BOARD[pos]['name']}", callback_data=f"propbuild_{pos}")])
    buttons.append([InlineKeyboardButton("⬅️ Ana Menü", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

def build_actions_menu(position):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Ev Kur", callback_data=f"buildhouse_{position}")],
        [InlineKeyboardButton("🏨 Otel Kur", callback_data=f"buildhotel_{position}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="build_menu")]
    ])

def mortgage_menu_for_player(chat_id, user_id):
    props = get_properties(chat_id)
    buttons = []
    for pos, info in props.items():
        if info["owner_id"] == user_id:
            state = "🔒" if info["mortgaged"] else "💰"
            buttons.append([InlineKeyboardButton(f"{state} {BOARD[pos]['name']}", callback_data=f"mortgage_{pos}")])
    buttons.append([InlineKeyboardButton("⬅️ Ana Menü", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

def trade_players_menu(chat_id, user_id):
    buttons = []
    for p in get_players(chat_id):
        if p["user_id"] != user_id and p["alive"]:
            buttons.append([InlineKeyboardButton(f"🤝 {p['name']}", callback_data=f"tradepick_{p['user_id']}")])
    buttons.append([InlineKeyboardButton("⬅️ Ana Menü", callback_data="back_main")])
    return InlineKeyboardMarkup(buttons)

def auction_menu(position):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💸 +10", callback_data=f"bid10_{position}"),
         InlineKeyboardButton("💸 +50", callback_data=f"bid50_{position}")],
        [InlineKeyboardButton("✅ Bitir", callback_data=f"finishauction_{position}")],
        [InlineKeyboardButton("❌ Vazgeç", callback_data="back_main")]
    ])

def format_status(chat_id):
    game = get_game(chat_id)
    players = get_players(chat_id)
    props = get_properties(chat_id)

    text = "🎲 <b>Oyun Durumu</b>\n\n"
    for i, p in enumerate(players, start=1):
        state = "✅" if p["alive"] else "💀"
        jail = " 🚔" if p["in_jail"] else ""
        tile_name = BOARD[p["position"]]["name"]
        turn_mark = " ⬅️" if game and game["started"] and game["turn"] == i - 1 else ""
        text += f"{i}. <b>{p['name']}</b> | 💰 ${p['money']} | 📍 {tile_name}{jail} | {state}{turn_mark}\n"

    text += "\n🏠 <b>Mülkler</b>\n"
    if not props:
        text += "Yok"
    else:
        for pos, info in props.items():
            extra = ""
            if info["mortgaged"]:
                extra += " | 🔒 İpotek"
            if info["hotel"]:
                extra += " | 🏨 Otel"
            elif info["houses"] > 0:
                extra += f" | 🏠 {info['houses']} ev"
            text += f"- {BOARD[pos]['name']} → {owner_name(chat_id, info['owner_id'])}{extra}\n"
    return text

def format_players(chat_id):
    players = get_players(chat_id)
    if not players:
        return "Oyuncu yok."
    text = "👥 <b>Oyuncular</b>\n\n"
    for i, p in enumerate(players, start=1):
        state = "✅" if p["alive"] else "💀"
        text += f"{i}. <b>{p['name']}</b> | 💰 ${p['money']} | {state}\n"
    return text

def format_my_props(chat_id, user_id):
    props = get_properties(chat_id)
    my_props = [pos for pos, info in props.items() if info["owner_id"] == user_id]
    if not my_props:
        return "🏠 Henüz mülkün yok."

    text = "🏠 <b>Mülklerin</b>\n\n"
    total = 0
    for pos in my_props:
        tile = BOARD[pos]
        info = props[pos]
        total += tile.get("price", 0)
        extra = ""
        if info["mortgaged"]:
            extra += " | 🔒 İpotekli"
        if info["hotel"]:
            extra += " | 🏨 Otel"
        elif info["houses"] > 0:
            extra += f" | 🏠 {info['houses']} ev"
        text += f"- {tile['name']} | Değer: ${tile.get('price', 0)} | Kira: ${calculate_rent(chat_id, pos)}{extra}\n"
    text += f"\n💎 Toplam portföy: ${total}"
    return text

async def send_or_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_private = update.effective_chat.type == ChatType.PRIVATE
    if is_private:
        text = (
            "🎩 <b>KGB Monopoly Bot</b>\n\n"
            "Telegram grubunda arkadaşlarınla Monopoly tarzı oyun oynamak için hazır.\n\n"
            "Aşağıdan beni grubuna ekleyebilir, destek kanalına gidebilir veya oyun menüsünü kullanabilirsin."
        )
    else:
        text = (
            "🎮 <b>Oyun Menüsü</b>\n\n"
            "Aşağıdaki butonlarla oyunu oluşturabilir, katılabilir ve oynayabilirsiniz."
        )
    await update.message.reply_text(text, reply_markup=main_menu(is_private=is_private), parse_mode="HTML")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    is_private = query.message.chat.type == ChatType.PRIVATE
    user = query.from_user
    data = query.data
    menu = main_menu(is_private=is_private)

    if data == "back_main":
        return await send_or_edit(query, "🎮 <b>Ana Menü</b>", menu)

    if data == "newgame":
        create_game(chat_id)
        return await send_or_edit(query, "🎮 Yeni oyun oluşturuldu.\nKatılmak için <b>➕ Katıl</b> butonuna basın.", menu)

    if data == "join":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Önce yeni oyun oluşturulmalı.", menu)
        game = get_game(chat_id)
        if game["started"]:
            return await send_or_edit(query, "Oyun başladı, artık katılamazsın.", menu)
        ok = add_player(chat_id, user.id, user.first_name)
        return await send_or_edit(query, f"✅ {user.first_name} oyuna katıldı." if ok else "Zaten oyundasın.", menu)

    if data == "startgame":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Önce yeni oyun oluştur.", menu)
        players = get_players(chat_id)
        if len(players) < 2:
            return await send_or_edit(query, "En az 2 oyuncu gerekli.", menu)
        update_game(chat_id, started=1, turn=0)
        cur = get_current_player(chat_id)
        return await send_or_edit(query, f"🚀 Oyun başladı!\nİlk sıra: <b>{cur['name']}</b>", menu)

    if data == "status":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        return await send_or_edit(query, format_status(chat_id), menu)

    if data == "players":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        return await send_or_edit(query, format_players(chat_id), menu)

    if data == "myprops":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        return await send_or_edit(query, format_my_props(chat_id, user.id), menu)

    if data == "build_menu":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        return await send_or_edit(query, "🧱 Geliştirmek istediğin mülkü seç:", build_menu_for_player(chat_id, user.id))

    if data.startswith("propbuild_"):
        pos = int(data.split("_")[1])
        props = get_properties(chat_id)
        if pos not in props or props[pos]["owner_id"] != user.id:
            return await send_or_edit(query, "Bu mülk sana ait değil.", menu)
        tile = BOARD[pos]
        info = props[pos]
        text = (
            f"🏠 <b>{tile['name']}</b>\n"
            f"Renk: {tile.get('color', '-')}\n"
            f"Kira: ${calculate_rent(chat_id, pos)}\n"
            f"Ev: {info['houses']}\n"
            f"Otel: {'Var' if info['hotel'] else 'Yok'}\n"
            f"İpotek: {'Var' if info['mortgaged'] else 'Yok'}\n"
            f"Ev kurma bedeli: ${tile['price'] // 2}\n"
            f"Otel kurma bedeli: ${tile['price']}"
        )
        return await send_or_edit(query, text, build_actions_menu(pos))

    if data.startswith("buildhouse_"):
        pos = int(data.split("_")[1])
        can_build, reason = can_build_house(chat_id, user.id, pos)
        if not can_build:
            return await send_or_edit(query, f"❌ {reason}", menu)
        tile = BOARD[pos]
        player = next((p for p in get_players(chat_id) if p["user_id"] == user.id), None)
        cost = tile["price"] // 2
        if player["money"] < cost:
            return await send_or_edit(query, "💸 Yeterli paran yok.", menu)
        props = get_properties(chat_id)
        update_property(chat_id, pos, houses=props[pos]["houses"] + 1)
        update_player(chat_id, user.id, money=player["money"] - cost)
        return await send_or_edit(query, f"🏠 {tile['name']} mülküne 1 ev kuruldu.", menu)

    if data.startswith("buildhotel_"):
        pos = int(data.split("_")[1])
        can_build, reason = can_build_hotel(chat_id, user.id, pos)
        if not can_build:
            return await send_or_edit(query, f"❌ {reason}", menu)
        tile = BOARD[pos]
        player = next((p for p in get_players(chat_id) if p["user_id"] == user.id), None)
        cost = tile["price"]
        if player["money"] < cost:
            return await send_or_edit(query, "💸 Yeterli paran yok.", menu)
        update_property(chat_id, pos, houses=0, hotel=1)
        update_player(chat_id, user.id, money=player["money"] - cost)
        return await send_or_edit(query, f"🏨 {tile['name']} mülküne otel kuruldu.", menu)

    if data == "mortgage_menu":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        return await send_or_edit(query, "🏦 İpotek menüsü\nBir mülk seç:", mortgage_menu_for_player(chat_id, user.id))

    if data.startswith("mortgage_"):
        pos = int(data.split("_")[1])
        props = get_properties(chat_id)
        prop = props.get(pos)
        if not prop or prop["owner_id"] != user.id:
            return await send_or_edit(query, "Bu mülk sana ait değil.", menu)
        tile = BOARD[pos]
        player = next((p for p in get_players(chat_id) if p["user_id"] == user.id), None)
        mortgage_value = tile["price"] // 2

        if prop["mortgaged"]:
            redeem_cost = int(mortgage_value * 1.1)
            if player["money"] < redeem_cost:
                return await send_or_edit(query, f"💸 İpotekten çıkarmak için ${redeem_cost} gerekir.", menu)
            update_property(chat_id, pos, mortgaged=0)
            update_player(chat_id, user.id, money=player["money"] - redeem_cost)
            return await send_or_edit(query, f"🔓 {tile['name']} ipotekten çıkarıldı. -${redeem_cost}", menu)
        else:
            if prop["houses"] > 0 or prop["hotel"] > 0:
                return await send_or_edit(query, "Önce ev/otel kaldırılmalı.", menu)
            update_property(chat_id, pos, mortgaged=1)
            update_player(chat_id, user.id, money=player["money"] + mortgage_value)
            return await send_or_edit(query, f"🏦 {tile['name']} ipotek edildi. +${mortgage_value}", menu)

    if data == "trade_menu":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        return await send_or_edit(query, "🤝 Takas yapmak istediğin oyuncuyu seç:", trade_players_menu(chat_id, user.id))

    if data.startswith("tradepick_"):
        target_id = int(data.split("_")[1])
        my_props = [pos for pos, info in get_properties(chat_id).items() if info["owner_id"] == user.id]
        target_props = [pos for pos, info in get_properties(chat_id).items() if info["owner_id"] == target_id]

        if not my_props and not target_props:
            return await send_or_edit(query, "Takas için yeterli mülk yok.", menu)

        # Basit takas: ilk mülkleri karşılıklı değiştir
        if my_props and target_props:
            my_pos = my_props[0]
            target_pos = target_props[0]
            update_property(chat_id, my_pos, owner_id=target_id)
            update_property(chat_id, target_pos, owner_id=user.id)
            return await send_or_edit(
                query,
                f"🤝 Takas gerçekleşti!\n"
                f"Sen verdin: {BOARD[my_pos]['name']}\n"
                f"Sen aldın: {BOARD[target_pos]['name']}",
                menu
            )
        return await send_or_edit(query, "Takas için iki tarafta da en az 1 mülk olmalı.", menu)

    if data == "endgame":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        delete_game(chat_id)
        return await send_or_edit(query, "🛑 Oyun bitirildi.", menu)

    if data == "roll":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", menu)
        game = get_game(chat_id)
        if not game["started"]:
            return await send_or_edit(query, "Oyun başlamadı.", menu)

        current = get_current_player(chat_id)
        if not current:
            return await send_or_edit(query, "Oyuncu bulunamadı.", menu)
        if current["user_id"] != user.id:
            return await send_or_edit(query, f"⏳ Sıra sende değil.\nSıradaki oyuncu: <b>{current['name']}</b>", menu)

        if current["in_jail"]:
            jail_turns = current["jail_turns"] + 1
            if jail_turns >= 2:
                update_player(chat_id, user.id, in_jail=0, jail_turns=0)
                jail_text = "🔓 Hapisten çıktın.\n"
            else:
                update_player(chat_id, user.id, jail_turns=jail_turns)
                nxt = next_turn(chat_id)
                return await send_or_edit(query, f"🚔 Hapistesin, bu turu kaçırdın.\n➡️ Sıradaki: <b>{nxt['name']}</b>", menu)
        else:
            jail_text = ""

        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        total = d1 + d2
        is_double = d1 == d2
        doubles_count = current["doubles_count"] + 1 if is_double else 0

        if doubles_count >= 3:
            update_player(chat_id, user.id, position=JAIL_POS, in_jail=1, jail_turns=0, doubles_count=0)
            nxt = next_turn(chat_id)
            return await send_or_edit(
                query,
                f"🎲 {current['name']} {d1}+{d2} attı.\n😵 3 kez çift zar!\n🚓 Hapse gönderildin.\n➡️ Sıradaki: <b>{nxt['name']}</b>",
                menu
            )

        old_pos = current["position"]
        new_pos = (old_pos + total) % len(BOARD)
        money = current["money"]
        text = f"{jail_text}🎲 <b>{current['name']}</b> zar attı: {d1} + {d2} = <b>{total}</b>\n"

        if new_pos < old_pos:
            money += GO_BONUS
            text += f"🏁 Başlangıçtan geçtin, +${GO_BONUS}\n"

        tile = BOARD[new_pos]
        text += f"📍 <b>{tile['name']}</b> karesine geldin.\n"
        update_player(chat_id, user.id, position=new_pos, money=money, doubles_count=doubles_count)

        props = get_properties(chat_id)

        if tile["type"] in ["property", "railroad", "utility"]:
            info = props.get(new_pos)
            if info is None:
                if money >= tile["price"]:
                    update_game(chat_id, waiting_buy_user=user.id, waiting_buy_pos=new_pos)
                    return await send_or_edit(
                        query,
                        text + f"🏠 Bu alan boş.\nFiyat: <b>${tile['price']}</b>\nNe yapmak istersin?",
                        buy_menu(new_pos)
                    )
                else:
                    text += "💸 Satın alacak kadar paran yok.\n"
            elif info["owner_id"] != user.id:
                rent = calculate_rent(chat_id, new_pos)
                owner = next((p for p in get_players(chat_id) if p["user_id"] == info["owner_id"]), None)
                _, bankrupt_msg = apply_money(chat_id, user.id, -rent)
                if owner and owner["alive"]:
                    apply_money(chat_id, owner["user_id"], rent)
                text += f"💰 {owner['name']} oyuncusuna <b>${rent}</b> kira ödendi.\n"
                if bankrupt_msg:
                    text += bankrupt_msg + "\n"
            else:
                text += "🏡 Kendi mülküne geldin.\n"

        elif tile["type"] == "tax":
            _, bankrupt_msg = apply_money(chat_id, user.id, -tile["amount"])
            text += f"🧾 Vergi ödedin: -${tile['amount']}\n"
            if bankrupt_msg:
                text += bankrupt_msg + "\n"

        elif tile["type"] == "chance":
            card_text, delta = random.choice(CHANCE_CARDS)
            _, bankrupt_msg = apply_money(chat_id, user.id, delta)
            text += f"🎴 Şans: {card_text} ({'+' if delta >= 0 else '-'}${abs(delta)})\n"
            if bankrupt_msg:
                text += bankrupt_msg + "\n"

        elif tile["type"] == "community":
            card_text, delta = random.choice(COMMUNITY_CARDS)
            _, bankrupt_msg = apply_money(chat_id, user.id, delta)
            text += f"📦 Kasa: {card_text} ({'+' if delta >= 0 else '-'}${abs(delta)})\n"
            if bankrupt_msg:
                text += bankrupt_msg + "\n"

        elif tile["type"] == "goto_jail":
            update_player(chat_id, user.id, position=JAIL_POS, in_jail=1, jail_turns=0, doubles_count=0)
            text += "🚓 Hapise gönderildin!\n"

        elif tile["type"] == "free":
            text += "🅿️ Ücretsiz park. Dinlen.\n"

        elif tile["type"] == "jail":
            text += "👮 Sadece hapis ziyareti.\n"

        alive_players = [p for p in get_players(chat_id) if p["alive"]]
        if len(alive_players) == 1:
            winner = alive_players[0]
            delete_game(chat_id)
            return await send_or_edit(query, text + f"\n🏆 Kazanan: <b>{winner['name']}</b>", menu)

        if is_double and any(p["user_id"] == user.id and p["alive"] for p in get_players(chat_id)):
            text += "\n✨ Çift zar geldi, tekrar oynayabilirsin!"
            return await send_or_edit(query, text, menu)

        nxt = next_turn(chat_id)
        text += f"\n➡️ Sıradaki oyuncu: <b>{nxt['name']}</b>"
        return await send_or_edit(query, text, menu)

    if data.startswith("buy_"):
        pos = int(data.split("_")[1])
        game = get_game(chat_id)
        if not game or game["waiting_buy_user"] != user.id or game["waiting_buy_pos"] != pos:
            return await send_or_edit(query, "Bu satın alma hakkı sende değil.", menu)

        player = next((p for p in get_players(chat_id) if p["user_id"] == user.id), None)
        tile = BOARD[pos]

        if not player or player["money"] < tile["price"]:
            update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)
            nxt = next_turn(chat_id)
            return await send_or_edit(query, f"💸 Yetersiz para.\n➡️ Sıradaki: <b>{nxt['name']}</b>", menu)

        update_player(chat_id, user.id, money=player["money"] - tile["price"])
        set_property_owner(chat_id, pos, user.id)
        update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)

        nxt = next_turn(chat_id)
        return await send_or_edit(
            query,
            f"✅ <b>{player['name']}</b> {tile['name']} mülkünü satın aldı.\n➡️ Sıradaki: <b>{nxt['name']}</b>",
            menu
        )

    if data.startswith("auction_"):
        pos = int(data.split("_")[1])
        game = get_game(chat_id)
        if not game or game["waiting_buy_user"] != user.id or game["waiting_buy_pos"] != pos:
            return await send_or_edit(query, "Açık artırma başlatılamadı.", menu)
        update_game(
            chat_id,
            waiting_buy_user=None,
            waiting_buy_pos=None,
            auction_pos=pos,
            auction_turn_user=user.id,
            auction_highest_bid=0,
            auction_highest_user=None
        )
        return await send_or_edit(
            query,
            f"📢 <b>{BOARD[pos]['name']}</b> için açık artırma başladı!\nEn yüksek teklif: $0",
            auction_menu(pos)
        )

    if data.startswith("bid10_") or data.startswith("bid50_"):
        parts = data.split("_")
        amount = 10 if parts[0] == "bid10" else 50
        pos = int(parts[1])

        game = get_game(chat_id)
        if not game or game["auction_pos"] != pos:
            return await send_or_edit(query, "Aktif açık artırma yok.", menu)

        player = next((p for p in get_players(chat_id) if p["user_id"] == user.id and p["alive"]), None)
        if not player:
            return await send_or_edit(query, "Oyuncu bulunamadı.", menu)

        new_bid = game["auction_highest_bid"] + amount
        if player["money"] < new_bid:
            return await send_or_edit(query, "💸 Bu teklifi verecek kadar paran yok.", auction_menu(pos))

        update_game(chat_id, auction_highest_bid=new_bid, auction_highest_user=user.id)
        return await send_or_edit(
            query,
            f"📢 <b>{BOARD[pos]['name']}</b> açık artırması\n\nEn yüksek teklif: <b>${new_bid}</b>\nLider: <b>{player['name']}</b>",
            auction_menu(pos)
        )

    if data.startswith("finishauction_"):
        pos = int(data.split("_")[1])
        game = get_game(chat_id)
        if not game or game["auction_pos"] != pos:
            return await send_or_edit(query, "Aktif açık artırma yok.", menu)

        winner_id = game["auction_highest_user"]
        bid = game["auction_highest_bid"]

        if not winner_id:
            update_game(chat_id, auction_pos=None, auction_turn_user=None, auction_highest_bid=0, auction_highest_user=None)
            nxt = next_turn(chat_id)
            return await send_or_edit(query, f"❌ Teklif gelmedi.\n➡️ Sıradaki: <b>{nxt['name']}</b>", menu)

        player = next((p for p in get_players(chat_id) if p["user_id"] == winner_id), None)
        if not player or player["money"] < bid:
            update_game(chat_id, auction_pos=None, auction_turn_user=None, auction_highest_bid=0, auction_highest_user=None)
            nxt = next_turn(chat_id)
            return await send_or_edit(query, f"💸 Kazananın parası yetmedi.\n➡️ Sıradaki: <b>{nxt['name']}</b>", menu)

        update_player(chat_id, winner_id, money=player["money"] - bid)
        set_property_owner(chat_id, pos, winner_id)
        update_game(chat_id, auction_pos=None, auction_turn_user=None, auction_highest_bid=0, auction_highest_user=None)

        nxt = next_turn(chat_id)
        return await send_or_edit(
            query,
            f"🏁 Açık artırmayı <b>{player['name']}</b> kazandı!\nMülk: {BOARD[pos]['name']}\nÖdenen: <b>${bid}</b>\n➡️ Sıradaki: <b>{nxt['name']}</b>",
            menu
        )

    if data.startswith("pass_"):
        pos = int(data.split("_")[1])
        game = get_game(chat_id)
        if not game or game["waiting_buy_user"] != user.id or game["waiting_buy_pos"] != pos:
            return await send_or_edit(query, "Bu işlem sana ait değil.", menu)
        update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)
        nxt = next_turn(chat_id)
        return await send_or_edit(query, f"❌ {BOARD[pos]['name']} satın alınmadı.\n➡️ Sıradaki: <b>{nxt['name']}</b>", menu)

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN eksik.")
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("Monopoly Bot V4 çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
