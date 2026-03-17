import os
import random
import sqlite3
from contextlib import closing
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
            INSERT INTO games (chat_id, started, turn, waiting_buy_user, waiting_buy_pos)
            VALUES (?, 0, 0, NULL, NULL)
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
                "mortgaged": r[4]
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
    alive_indexes = [i for i, p in enumerate(players) if p["alive"]]
    if len(alive_indexes) <= 1:
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

def owns_full_set(chat_id, user_id, color):
    if color not in COLOR_GROUPS:
        return False
    props = get_properties(chat_id)
    group = COLOR_GROUPS[color]
    for pos in group:
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
    houses = prop["houses"]
    hotel = prop["hotel"]

    if hotel:
        return base * 6
    if houses > 0:
        return base * (houses + 1)

    if tile["type"] == "property" and owns_full_set(chat_id, prop["owner_id"], tile["color"]):
        return base * 2

    return base

def can_build_house(chat_id, user_id, position):
    tile = BOARD[position]
    if tile["type"] != "property":
        return False, "Bu mülke ev dikilmez."
    if not owns_full_set(chat_id, user_id, tile["color"]):
        return False, "Önce renk setini tamamlamalısın."
    props = get_properties(chat_id)
    prop = props.get(position)
    if not prop or prop["owner_id"] != user_id:
        return False, "Bu mülk sana ait değil."
    if prop["mortgaged"]:
        return False, "İpotekli mülke ev kurulamaz."
    if prop["hotel"]:
        return False, "Bu mülkte zaten otel var."
    if prop["houses"] >= 4:
        return False, "Maksimum 4 ev yapılabilir. Sonraki adım otel."
    return True, None

def can_build_hotel(chat_id, user_id, position):
    tile = BOARD[position]
    if tile["type"] != "property":
        return False, "Bu mülke otel dikilmez."
    props = get_properties(chat_id)
    prop = props.get(position)
    if not prop or prop["owner_id"] != user_id:
        return False, "Bu mülk sana ait değil."
    if prop["mortgaged"]:
        return False, "İpotekli mülke otel kurulamaz."
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
            InlineKeyboardButton("🧱 Geliştir", callback_data="build_menu"),
        ],
        [
            InlineKeyboardButton("➕ Beni Gruba Ekle", url=ADD_BOT_URL),
            InlineKeyboardButton("🆘 Destek", url=SUPPORT_URL),
        ],
        [
            InlineKeyboardButton("🛑 Oyunu Bitir", callback_data="endgame"),
        ]
    ])

def buy_menu(position):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Satın Al", callback_data=f"buy_{position}"),
            InlineKeyboardButton("❌ Geç", callback_data=f"pass_{position}")
        ]
    ])

def build_menu_for_player(chat_id, user_id):
    props = get_properties(chat_id)
    buttons = []
    for pos, info in props.items():
        if info["owner_id"] == user_id and BOARD[pos]["type"] == "property":
            title = BOARD[pos]["name"]
            buttons.append([InlineKeyboardButton(f"🧱 {title}", callback_data=f"propbuild_{pos}")])
    if not buttons:
        buttons.append([InlineKeyboardButton("❌ Kapat", callback_data="close_build")])
    else:
        buttons.append([InlineKeyboardButton("❌ Kapat", callback_data="close_build")])
    return InlineKeyboardMarkup(buttons)

def build_actions_menu(position):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Ev Kur", callback_data=f"buildhouse_{position}")],
        [InlineKeyboardButton("🏨 Otel Kur", callback_data=f"buildhotel_{position}")],
        [InlineKeyboardButton("⬅️ Geri", callback_data="build_menu")]
    ])

def send_text_with_panel(text):
    return text, main_menu()

def format_status(chat_id):
    game = get_game(chat_id)
    players = get_players(chat_id)
    props = get_properties(chat_id)

    text = "🎲 Oyun Durumu\n\n"
    for i, p in enumerate(players, start=1):
        state = "✅" if p["alive"] else "💀"
        jail = " 🚔" if p["in_jail"] else ""
        tile_name = BOARD[p["position"]]["name"]
        turn_mark = ""
        if game and game["started"] and game["turn"] == i - 1:
            turn_mark = " ⬅️"
        text += f"{i}. {p['name']} | 💰 ${p['money']} | 📍 {tile_name}{jail} | {state}{turn_mark}\n"

    text += "\n🏠 Mülkler:\n"
    if not props:
        text += "Yok\n"
    else:
        for pos, info in props.items():
            extra = ""
            if info["hotel"]:
                extra = " | 🏨 Otel"
            elif info["houses"] > 0:
                extra = f" | 🏠 {info['houses']} ev"
            text += f"- {BOARD[pos]['name']} → {owner_name(chat_id, info['owner_id'])}{extra}\n"

    return text

def format_players(chat_id):
    players = get_players(chat_id)
    if not players:
        return "Oyuncu yok."
    text = "👥 Oyuncular\n\n"
    for i, p in enumerate(players, start=1):
        state = "✅" if p["alive"] else "💀"
        text += f"{i}. {p['name']} | 💰 ${p['money']} | {state}\n"
    return text

def format_my_props(chat_id, user_id):
    props = get_properties(chat_id)
    my_props = [pos for pos, info in props.items() if info["owner_id"] == user_id]
    if not my_props:
        return "🏠 Henüz mülkün yok."

    text = "🏠 Mülklerin\n\n"
    total = 0
    for pos in my_props:
        tile = BOARD[pos]
        info = props[pos]
        rent = calculate_rent(chat_id, pos)
        worth = tile.get("price", 0)
        total += worth
        extra = ""
        if info["hotel"]:
            extra = " | 🏨 Otel"
        elif info["houses"] > 0:
            extra = f" | 🏠 {info['houses']} ev"
        text += f"- {tile['name']} | Değer: ${worth} | Kira: ${rent}{extra}\n"

    text += f"\n💎 Toplam mülk değeri: ${total}"
    return text

async def send_or_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Beni Gruba Ekle", url=ADD_BOT_URL)],
        [InlineKeyboardButton("🆘 Destek", url=SUPPORT_URL)]
    ])
    await update.message.reply_text(
        "🎩 Monopoly Bot'a hoş geldin!\n\nAşağıdan beni grubuna ekleyebilir veya destek kanalına gidebilirsin.\n\n"
        "Gruba ekledikten sonra oyun menüsü için /start yaz.",
        reply_markup=keyboard
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user
    data = query.data

    if data == "newgame":
        create_game(chat_id)
        return await send_or_edit(query, "🎮 Yeni oyun oluşturuldu!\nKatılmak için ➕ Katıl butonuna basın.", main_menu())

    if data == "join":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Önce yeni oyun oluşturulmalı.", main_menu())
        game = get_game(chat_id)
        if game["started"]:
            return await send_or_edit(query, "Oyun başladı, artık katılamazsın.", main_menu())
        ok = add_player(chat_id, user.id, user.first_name)
        if ok:
            return await send_or_edit(query, f"✅ {user.first_name} oyuna katıldı.", main_menu())
        return await send_or_edit(query, "Zaten oyundasın.", main_menu())

    if data == "startgame":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Önce yeni oyun oluştur.", main_menu())
        players = get_players(chat_id)
        if len(players) < 2:
            return await send_or_edit(query, "En az 2 oyuncu gerekli.", main_menu())
        update_game(chat_id, started=1, turn=0)
        current = get_current_player(chat_id)
        return await send_or_edit(query, f"🚀 Oyun başladı!\nİlk sıra: {current['name']}", main_menu())

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

    if data == "build_menu":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        return await send_or_edit(query, "Geliştirmek istediğin mülkü seç:", build_menu_for_player(chat_id, user.id))

    if data == "close_build":
        return await send_or_edit(query, "Menü kapatıldı.", main_menu())

    if data.startswith("propbuild_"):
        pos = int(data.split("_")[1])
        props = get_properties(chat_id)
        if pos not in props or props[pos]["owner_id"] != user.id:
            return await send_or_edit(query, "Bu mülk sana ait değil.", main_menu())

        tile = BOARD[pos]
        info = props[pos]
        rent = calculate_rent(chat_id, pos)
        text = (
            f"🏠 {tile['name']}\n"
            f"Renk: {tile.get('color', '-')}\n"
            f"Güncel kira: ${rent}\n"
            f"Ev sayısı: {info['houses']}\n"
            f"Otel: {'Var' if info['hotel'] else 'Yok'}\n"
            f"Ev kurma bedeli: ${tile['price'] // 2}\n"
            f"Otel kurma bedeli: ${tile['price']}\n"
        )
        return await send_or_edit(query, text, build_actions_menu(pos))

    if data.startswith("buildhouse_"):
        pos = int(data.split("_")[1])
        can_build, reason = can_build_house(chat_id, user.id, pos)
        if not can_build:
            return await send_or_edit(query, f"❌ {reason}", main_menu())

        tile = BOARD[pos]
        cost = tile["price"] // 2
        players = get_players(chat_id)
        player = next((p for p in players if p["user_id"] == user.id), None)
        if not player or player["money"] < cost:
            return await send_or_edit(query, "💸 Yeterli paran yok.", main_menu())

        props = get_properties(chat_id)
        houses = props[pos]["houses"] + 1
        update_property(chat_id, pos, houses=houses)
        update_player(chat_id, user.id, money=player["money"] - cost)

        return await send_or_edit(query, f"🏠 {BOARD[pos]['name']} mülküne 1 ev kuruldu.\nToplam ev: {houses}", main_menu())

    if data.startswith("buildhotel_"):
        pos = int(data.split("_")[1])
        can_build, reason = can_build_hotel(chat_id, user.id, pos)
        if not can_build:
            return await send_or_edit(query, f"❌ {reason}", main_menu())

        tile = BOARD[pos]
        cost = tile["price"]
        players = get_players(chat_id)
        player = next((p for p in players if p["user_id"] == user.id), None)
        if not player or player["money"] < cost:
            return await send_or_edit(query, "💸 Yeterli paran yok.", main_menu())

        update_property(chat_id, pos, houses=0, hotel=1)
        update_player(chat_id, user.id, money=player["money"] - cost)

        return await send_or_edit(query, f"🏨 {BOARD[pos]['name']} mülküne otel kuruldu.", main_menu())

    if data == "endgame":
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        delete_game(chat_id)
        return await send_or_edit(query, "🛑 Oyun bitirildi.", main_menu())

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
            return await send_or_edit(query, f"⏳ Sıra sende değil.\nSıradaki oyuncu: {current['name']}", main_menu())

        if current["in_jail"]:
            jail_turns = current["jail_turns"] + 1
            if jail_turns >= 2:
                update_player(chat_id, user.id, in_jail=0, jail_turns=0)
                jail_text = "🔓 Hapisten çıktın.\n"
            else:
                update_player(chat_id, user.id, jail_turns=jail_turns)
                nxt = next_turn(chat_id)
                return await send_or_edit(query, f"🚔 Hapistesin, bu turu kaçırdın.\n➡️ Sıradaki: {nxt['name']}", main_menu())
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
            return await send_or_edit(query,
                f"🎲 {current['name']} {d1}+{d2} attı.\n😵 3 kez çift zar geldi!\n🚓 Hapse gönderildin.\n➡️ Sıradaki: {nxt['name']}",
                main_menu()
            )

        old_pos = current["position"]
        new_pos = (old_pos + total) % len(BOARD)
        money = current["money"]

        text = f"{jail_text}🎲 {current['name']} zar attı: {d1} + {d2} = {total}\n"

        if new_pos < old_pos:
            money += GO_BONUS
            text += f"🏁 Başlangıçtan geçtin, +${GO_BONUS}\n"

        tile = BOARD[new_pos]
        text += f"📍 {tile['name']} karesine geldin.\n"

        update_player(chat_id, user.id, position=new_pos, money=money, doubles_count=doubles_count)
        props = get_properties(chat_id)

        if tile["type"] in ["property", "railroad", "utility"]:
            info = props.get(new_pos)
            if info is None:
                if money >= tile["price"]:
                    update_game(chat_id, waiting_buy_user=user.id, waiting_buy_pos=new_pos)
                    return await send_or_edit(
                        query,
                        text + f"🏠 Bu mülk boş.\nFiyat: ${tile['price']}\nSatın almak ister misin?",
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

                text += f"💰 {owner['name']} oyuncusuna ${rent} kira ödendi.\n"
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
            text += "🅿️ Ücretsiz park. Rahatla.\n"

        elif tile["type"] == "jail":
            text += "👮 Sadece hapis ziyareti.\n"

        alive_players = [p for p in get_players(chat_id) if p["alive"]]
        if len(alive_players) == 1:
            winner = alive_players[0]
            delete_game(chat_id)
            return await send_or_edit(query, text + f"\n🏆 Kazanan: {winner['name']}", main_menu())

        if is_double and any(p["user_id"] == user.id and p["alive"] for p in get_players(chat_id)):
            text += "\n✨ Çift zar geldi, tekrar oynayabilirsin!"
            return await send_or_edit(query, text, main_menu())

        nxt = next_turn(chat_id)
        text += f"\n➡️ Sıradaki oyuncu: {nxt['name']}"
        return await send_or_edit(query, text, main_menu())

    if data.startswith("buy_"):
        if not game_exists(chat_id):
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())

        game = get_game(chat_id)
        pos = int(data.split("_")[1])

        if game["waiting_buy_user"] != user.id or game["waiting_buy_pos"] != pos:
            return await send_or_edit(query, "Bu satın alma hakkı sende değil.", main_menu())

        players = get_players(chat_id)
        player = next((p for p in players if p["user_id"] == user.id), None)
        tile = BOARD[pos]

        if not player or player["money"] < tile["price"]:
            update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)
            nxt = next_turn(chat_id)
            return await send_or_edit(query, f"💸 Yetersiz para.\n➡️ Sıradaki: {nxt['name']}", main_menu())

        update_player(chat_id, user.id, money=player["money"] - tile["price"])
        set_property_owner(chat_id, pos, user.id)
        update_game(chat_id, waiting_buy_user=None, waiting_buy_pos=None)

        nxt = next_turn(chat_id)
        return await send_or_edit(query,
            f"✅ {player['name']} {tile['name']} mülkünü satın aldı.\n➡️ Sıradaki oyuncu: {nxt['name']}",
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
        return await send_or_edit(query,
            f"❌ {BOARD[pos]['name']} satın alınmadı.\n➡️ Sıradaki oyuncu: {nxt['name']}",
            main_menu()
        )

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN eksik.")
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Monopoly Bot V3 çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
