import os
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# --- AYARLAR ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
START_MONEY = 1500
GO_BONUS = 200
JAIL_FINE = 50

# --- OYUN TAHTASI ---
# type: start, property, tax, chance, community, jail, free, goto_jail
BOARD = [
    {"name": "BAŞLANGIÇ", "type": "start"},
    {"name": "Kadıköy", "type": "property", "price": 60, "rent": 10, "color": "🟤"},
    {"name": "Kasa", "type": "community"},
    {"name": "Beşiktaş", "type": "property", "price": 60, "rent": 10, "color": "🟤"},
    {"name": "Gelir Vergisi", "type": "tax", "amount": 100},
    {"name": "Üsküdar", "type": "property", "price": 100, "rent": 15, "color": "🔵"},
    {"name": "Şans", "type": "chance"},
    {"name": "Taksim", "type": "property", "price": 100, "rent": 15, "color": "🔵"},
    {"name": "Şişli", "type": "property", "price": 120, "rent": 20, "color": "🔵"},
    {"name": "HAPİS ZİYARETİ", "type": "jail"},
    {"name": "Bakırköy", "type": "property", "price": 140, "rent": 25, "color": "🟣"},
    {"name": "Elektrik İdaresi", "type": "property", "price": 150, "rent": 30, "color": "⚡"},
    {"name": "Kadıköy-Boğaz", "type": "property", "price": 140, "rent": 25, "color": "🟣"},
    {"name": "Kasa", "type": "community"},
    {"name": "Bebek", "type": "property", "price": 160, "rent": 30, "color": "🟣"},
    {"name": "Vapur İskelesi", "type": "property", "price": 200, "rent": 40, "color": "🚢"},
    {"name": "Etiler", "type": "property", "price": 180, "rent": 35, "color": "🟠"},
    {"name": "Şans", "type": "chance"},
    {"name": "Levent", "type": "property", "price": 180, "rent": 35, "color": "🟠"},
    {"name": "Maslak", "type": "property", "price": 200, "rent": 40, "color": "🟠"},
    {"name": "ÜCRETSİZ PARK", "type": "free"},
    {"name": "Beylikdüzü", "type": "property", "price": 220, "rent": 45, "color": "🔴"},
    {"name": "Şans", "type": "chance"},
    {"name": "Büyükçekmece", "type": "property", "price": 220, "rent": 45, "color": "🔴"},
    {"name": "Silivri", "type": "property", "price": 240, "rent": 50, "color": "🔴"},
    {"name": "Metrobüs", "type": "property", "price": 200, "rent": 40, "color": "🚇"},
    {"name": "Ataköy", "type": "property", "price": 260, "rent": 55, "color": "🟡"},
    {"name": "Florya", "type": "property", "price": 260, "rent": 55, "color": "🟡"},
    {"name": "Su İdaresi", "type": "property", "price": 150, "rent": 30, "color": "💧"},
    {"name": "Yeşilköy", "type": "property", "price": 280, "rent": 60, "color": "🟡"},
    {"name": "HAPİSE GİT", "type": "goto_jail"},
    {"name": "Kartal", "type": "property", "price": 300, "rent": 65, "color": "🟢"},
    {"name": "Pendik", "type": "property", "price": 300, "rent": 65, "color": "🟢"},
    {"name": "Kasa", "type": "community"},
    {"name": "Tuzla", "type": "property", "price": 320, "rent": 70, "color": "🟢"},
    {"name": "Lüks Vergisi", "type": "tax", "amount": 150},
    {"name": "Şans", "type": "chance"},
    {"name": "Bebek Sahil", "type": "property", "price": 350, "rent": 80, "color": "🔷"},
    {"name": "Kasa", "type": "community"},
    {"name": "Boğaz Hattı", "type": "property", "price": 400, "rent": 100, "color": "🔷"},
]

# --- ŞANS / KASA KARTLARI ---
CHANCE_CARDS = [
    ("Piyango kazandın! +150$", lambda p: p.add_money(150)),
    ("Banka hatası lehine! +200$", lambda p: p.add_money(200)),
    ("Doktor ücreti öde. -50$", lambda p: p.add_money(-50)),
    ("Hapse gir! 🚓", lambda p: p.go_to_jail()),
    ("Başlangıç'a git. +200$", lambda p: p.go_to_start()),
    ("3 hane geri git.", lambda p: p.move(-3)),
]

COMMUNITY_CARDS = [
    ("Güzellik yarışmasını kazandın! +100$", lambda p: p.add_money(100)),
    ("Okul taksiti öde. -80$", lambda p: p.add_money(-80)),
    ("Miras kaldı! +100$", lambda p: p.add_money(100)),
    ("Hapse gir! 🚓", lambda p: p.go_to_jail()),
    ("Başlangıç'a git. +200$", lambda p: p.go_to_start()),
]

# --- OYUN SINIFLARI ---
games = {}

class Player:
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name
        self.money = START_MONEY
        self.pos = 0
        self.in_jail = False
        self.jail_turns = 0
        self.alive = True
        self.properties = []

    def add_money(self, amount):
        self.money += amount
        if self.money < 0:
            self.alive = False
            return f"💀 {self.name} iflas etti!"
        return None

    def go_to_jail(self):
        self.in_jail = True
        self.jail_turns = 0
        self.pos = 9  # Hapis indexi
        return f"🚓 {self.name} hapise gönderildi!"

    def go_to_start(self):
        self.pos = 0
        self.money += GO_BONUS
        return f"🏁 {self.name} başlangıca döndü ve +{GO_BONUS}$ aldı."

    def move(self, steps):
        old = self.pos
        self.pos = (self.pos + steps) % len(BOARD)
        passed = self.pos < old
        if passed:
            self.money += GO_BONUS
            return f"🔄 Başlangıç geçildi! +{GO_BONUS}$"
        return None

class Game:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.players = []
        self.started = False
        self.turn_idx = 0
        self.owners = {}  # pos -> player_id
        self.waiting_buy = None  # (player_id, pos)

    def add_player(self, user_id, name):
        if any(p.id == user_id for p in self.players):
            return False
        self.players.append(Player(user_id, name))
        return True

    def current_player(self):
        return self.players[self.turn_idx]

    def next_turn(self):
        alive = [i for i, p in enumerate(self.players) if p.alive]
        if len(alive) <= 1:
            return None
        while True:
            self.turn_idx = (self.turn_idx + 1) % len(self.players)
            if self.players[self.turn_idx].alive:
                return self.players[self.turn_idx]

    def get_owner_name(self, pos):
        owner_id = self.owners.get(pos)
        if not owner_id:
            return None
        owner = next((p for p in self.players if p.id == owner_id), None)
        return owner.name if owner else "Bilinmiyor"

# --- YARDIMCI FONKSİYONLAR ---
def get_game(chat_id):
    return games.get(chat_id)

def format_status(game):
    txt = "🎲 **OYUN DURUMU**\n\n"
    for p in game.players:
        status = "✅" if p.alive else "💀"
        jail = "🚓" if p.in_jail else ""
        txt += f"{status} {p.name} | 💰{p.money}$ | 📍{BOARD[p.pos]['name']} {jail}\n"
    if game.started:
        txt += f"\n➡️ Sıra: {game.current_player().name}"
    return txt

# --- HANDLERLAR ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎩 **Monopoly Bot**\n\n"
        "Komutlar:\n"
        "/newgame - Yeni oyun aç\n"
        "/join - Oyuna katıl\n"
        "/startgame - Oyunu başlat\n"
        "/status - Durumu gör\n"
        "/endgame - Oyunu bitir"
    )

async def newgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    games[chat_id] = Game(chat_id)
    await update.message.reply_text("🆕 Yeni oyun oluşturuldu! Katılmak için /join yazın.")

async def join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        return await update.message.reply_text("Önce /newgame ile oyun açın.")
    if game.started:
        return await update.message.reply_text("Oyun başladı, katılamazsın.")
    user = update.effective_user
    if game.add_player(user.id, user.first_name):
        await update.message.reply_text(f"✅ {user.first_name} oyuna katıldı.")
    else:
        await update.message.reply_text("Zaten oyundasın.")

async def startgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        return await update.message.reply_text("Önce /newgame yapın.")
    if len(game.players) < 2:
        return await update.message.reply_text("En az 2 oyuncu gerekli.")
    game.started = True
    await update.message.reply_text(
        f"🎮 Oyun başladı!\nİlk sıra: {game.current_player().name}\nZar atmak için /roll"
    )

async def roll(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game or not game.started:
        return await update.message.reply_text("Aktif oyun yok.")
    user = update.effective_user
    player = game.current_player()
    if player.id != user.id:
        return await update.message.reply_text(f"Sıra sende değil! Sıradaki: {player.name}")

    if player.in_jail:
        player.jail_turns += 1
        if player.jail_turns >= 3:
            player.in_jail = False
            player.jail_turns = 0
            msg = "🔓 3 tur doldu, hapisten çıktın!"
        else:
            msg = f"🚓 Hapistesin. {3 - player.jail_turns} tur kaldı."
            game.next_turn()
            return await update.message.reply_text(msg + f"\n➡️ Sıra: {game.current_player().name}")

    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    msg = f"🎲 {player.name} zar attı: {d1} + {d2} = {total}\n"

    passed_msg = player.move(total)
    if passed_msg:
        msg += passed_msg + "\n"

    tile = BOARD[player.pos]
    msg += f"📍 {tile['name']} karesine geldi.\n"

    # Tile işleme
    if tile["type"] == "property":
        owner_id = game.owners.get(player.pos)
        if owner_id is None:
            if player.money >= tile["price"]:
                game.waiting_buy = (player.id, player.pos)
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"🏠 Satın Al ({tile['price']}$)", callback_data=f"buy_{player.pos}"),
                    InlineKeyboardButton("❌ Geç", callback_data=f"pass_{player.pos}")
                ]])
                await update.message.reply_text(msg + "Bu mülk boş. Satın almak ister misin?", reply_markup=kb)
                return
            else:
                msg += "💸 Yetersiz bakiye, satın alamazsın.\n"
        elif owner_id != player.id:
            owner = next((p for p in game.players if p.id == owner_id), None)
            rent = tile["rent"]
            loss = player.add_money(-rent)
            if owner and owner.alive:
                owner.add_money(rent)
            msg += f"💰 {owner.name} oyuncusuna {rent}$ kira ödendi.\n"
            if loss:
                msg += loss + "\n"
        else:
            msg += "🏡 Kendi mülküne geldin.\n"

    elif tile["type"] == "tax":
        loss = player.add_money(-tile["amount"])
        msg += f"🧾 Vergi ödedin: -{tile['amount']}$\n"
        if loss:
            msg += loss + "\n"

    elif tile["type"] == "chance":
        card = random.choice(CHANCE_CARDS)
        msg += f"🎴 Şans: {card[0]}\n"
        result = card[1](player)
        if result:
            msg += result + "\n"

    elif tile["type"] == "community":
        card = random.choice(COMMUNITY_CARDS)
        msg += f"📦 Kasa: {card[0]}\n"
        result = card[1](player)
        if result:
            msg += result + "\n"

    elif tile["type"] == "goto_jail":
        msg += player.go_to_jail() + "\n"

    elif tile["type"] == "jail":
        msg += "👮 Hapis ziyareti. Güvenli alan.\n"

    elif tile["type"] == "free":
        msg += "🅿️ Ücretsiz park. Dinlen.\n"

    # Kazanan kontrolü
    alive = [p for p in game.players if p.alive]
    if len(alive) == 1:
        msg += f"\n🏆 **OYUN BİTTİ!** Kazanan: {alive[0].name}"
        games.pop(chat_id, None)
        return await update.message.reply_text(msg)

    next_p = game.next_turn()
    if next_p:
        msg += f"\n➡️ Sıradaki: {next_p.name}"
    await update.message.reply_text(msg)

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    game = get_game(chat_id)
    if not game:
        return
    data = query.data
    user_id = query.from_user.id

    if data.startswith("buy_"):
        pos = int(data.split("_")[1])
        if game.waiting_buy != (user_id, pos):
            return await query.edit_message_text("Bu işlem başkasına ait.")
        player = next((p for p in game.players if p.id == user_id), None)
        tile = BOARD[pos]
        if player.money >= tile["price"]:
            player.money -= tile["price"]
            game.owners[pos] = user_id
            player.properties.append(pos)
            game.waiting_buy = None
            await query.edit_message_text(f"✅ {player.name}, {tile['name']} mülkünü satın aldı.")
            next_p = game.next_turn()
            if next_p:
                await query.message.reply_text(f"➡️ Sıradaki: {next_p.name}")
        else:
            await query.edit_message_text("💸 Yetersiz bakiye.")

    elif data.startswith("pass_"):
        pos = int(data.split("_")[1])
        if game.waiting_buy != (user_id, pos):
            return
        game.waiting_buy = None
        await query.edit_message_text("❌ Satın alma pas geçildi.")
        next_p = game.next_turn()
        if next_p:
            await query.message.reply_text(f"➡️ Sıradaki: {next_p.name}")

async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = get_game(chat_id)
    if not game:
        return await update.message.reply_text("Aktif oyun yok.")
    await update.message.reply_text(format_status(game), parse_mode="Markdown")

async def endgame(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        del games[chat_id]
        await update.message.reply_text("🛑 Oyun sonlandırıldı.")
    else:
        await update.message.reply_text("Aktif oyun yok.")

# --- MAIN ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newgame", newgame))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("startgame", startgame))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("endgame", endgame))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Monopoly Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
