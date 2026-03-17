import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

START_MONEY = 1500
GO_BONUS = 200

games = {}

BOARD = [
    {"name": "Başlangıç", "type": "start"},
    {"name": "Kadıköy", "type": "property", "price": 60, "rent": 10},
    {"name": "Şans", "type": "chance"},
    {"name": "Beşiktaş", "type": "property", "price": 80, "rent": 15},
    {"name": "Vergi", "type": "tax", "amount": 100},
    {"name": "Üsküdar", "type": "property", "price": 100, "rent": 20},
    {"name": "Boş Alan", "type": "empty"},
    {"name": "Taksim", "type": "property", "price": 120, "rent": 25},
    {"name": "Ödül", "type": "bonus", "amount": 150},
    {"name": "Şişli", "type": "property", "price": 140, "rent": 30},
    {"name": "Hapis", "type": "jail"},
    {"name": "Bakırköy", "type": "property", "price": 160, "rent": 35},
]

CHANCE_CARDS = [
    ("Piyango kazandın", 150),
    ("Cüzdanını kaybettin", -100),
    ("Maaş primi aldın", 120),
    ("Araba masrafı çıktı", -80),
]

def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎮 Yeni Oyun", callback_data="newgame"),
            InlineKeyboardButton("➕ Katıl", callback_data="join"),
        ],
        [
            InlineKeyboardButton("▶️ Başlat", callback_data="startgame"),
            InlineKeyboardButton("📊 Durum", callback_data="status"),
        ],
        [
            InlineKeyboardButton("🎲 Zar At", callback_data="roll"),
            InlineKeyboardButton("🛑 Bitir", callback_data="endgame"),
        ],
    ])

def turn_menu(can_roll=False):
    buttons = []
    if can_roll:
        buttons.append([InlineKeyboardButton("🎲 Zar At", callback_data="roll")])
    buttons.append([InlineKeyboardButton("📊 Durum", callback_data="status")])
    return InlineKeyboardMarkup(buttons)

def buy_menu(position):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Satın Al", callback_data=f"buy_{position}"),
            InlineKeyboardButton("❌ Geç", callback_data=f"pass_{position}")
        ]
    ])

class Player:
    def __init__(self, user_id, name):
        self.id = user_id
        self.name = name
        self.money = START_MONEY
        self.position = 0
        self.alive = True
        self.in_jail = False
        self.jail_turns = 0

class Game:
    def __init__(self):
        self.players = []
        self.started = False
        self.turn = 0
        self.properties = {}
        self.waiting_buy = None

    def add_player(self, user_id, name):
        for p in self.players:
            if p.id == user_id:
                return False
        self.players.append(Player(user_id, name))
        return True

    def current_player(self):
        if not self.players:
            return None
        return self.players[self.turn]

    def next_turn(self):
        alive_players = [p for p in self.players if p.alive]
        if len(alive_players) <= 1:
            return None

        while True:
            self.turn = (self.turn + 1) % len(self.players)
            if self.players[self.turn].alive:
                return self.players[self.turn]

def get_game(chat_id):
    return games.get(chat_id)

def format_status(game):
    text = "🎲 Oyun Durumu\n\n"
    for i, p in enumerate(game.players, start=1):
        state = "✅" if p.alive else "❌"
        tile = BOARD[p.position]["name"]
        text += f"{i}. {p.name} | 💰 ${p.money} | 📍 {tile} | {state}\n"

    text += "\n🏠 Mülkler:\n"
    if not game.properties:
        text += "Yok\n"
    else:
        for pos, owner_id in game.properties.items():
            owner = next((x for x in game.players if x.id == owner_id), None)
            owner_name = owner.name if owner else "Bilinmiyor"
            text += f"- {BOARD[pos]['name']} → {owner_name}\n"

    if game.started and game.current_player():
        text += f"\n➡️ Sıra: {game.current_player().name}"

    return text

async def send_or_edit(query, text, reply_markup=None):
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except Exception:
        await query.message.reply_text(text, reply_markup=reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎩 Monopoly Bot'a hoş geldin!\nAşağıdaki butonları kullan.",
        reply_markup=main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat.id
    user = query.from_user
    data = query.data

    if data == "newgame":
        games[chat_id] = Game()
        return await send_or_edit(
            query,
            "🎮 Yeni oyun oluşturuldu!\nKatılmak için ➕ Katıl butonuna basın.",
            main_menu()
        )

    game = get_game(chat_id)

    if data == "join":
        if not game:
            return await send_or_edit(query, "Önce yeni oyun oluşturmalısınız.", main_menu())
        if game.started:
            return await send_or_edit(query, "Oyun başladı, artık katılamazsın.", main_menu())

        added = game.add_player(user.id, user.first_name)
        if added:
            return await send_or_edit(
                query,
                f"✅ {user.first_name} oyuna katıldı.\nOyuncu sayısı: {len(game.players)}",
                main_menu()
            )
        else:
            return await send_or_edit(query, "Zaten oyundasın.", main_menu())

    if data == "startgame":
        if not game:
            return await send_or_edit(query, "Önce yeni oyun oluştur.", main_menu())
        if game.started:
            return await send_or_edit(query, "Oyun zaten başladı.", main_menu())
        if len(game.players) < 2:
            return await send_or_edit(query, "En az 2 oyuncu gerekli.", main_menu())

        game.started = True
        current = game.current_player()
        return await send_or_edit(
            query,
            f"🚀 Oyun başladı!\nİlk sıra: {current.name}",
            turn_menu(can_roll=True)
        )

    if data == "status":
        if not game:
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        can_roll = game.started and game.current_player() and game.current_player().id == user.id
        return await send_or_edit(query, format_status(game), turn_menu(can_roll=can_roll))

    if data == "endgame":
        if chat_id in games:
            del games[chat_id]
        return await send_or_edit(query, "🛑 Oyun sonlandırıldı.", main_menu())

    if data == "roll":
        if not game:
            return await send_or_edit(query, "Aktif oyun yok.", main_menu())
        if not game.started:
            return await send_or_edit(query, "Oyun başlamadı.", main_menu())

        player = game.current_player()

        if player.id != user.id:
            return await send_or_edit(
                query,
                f"⏳ Sıra sende değil.\nSıradaki oyuncu: {player.name}",
                turn_menu(can_roll=False)
            )

        if player.in_jail:
            player.jail_turns += 1
            if player.jail_turns >= 2:
                player.in_jail = False
                player.jail_turns = 0
            else:
                next_player = game.next_turn()
                return await send_or_edit(
                    query,
                    f"🚔 {player.name} hapiste olduğu için turu geçti.\n➡️ Sıradaki: {next_player.name}",
                    turn_menu(can_roll=False)
                )

        dice = random.randint(1, 6)
        old_pos = player.position
        player.position = (player.position + dice) % len(BOARD)

        text = f"🎲 {player.name} {dice} attı.\n"
        if player.position < old_pos:
            player.money += GO_BONUS
            text += f"🏁 Başlangıç geçti, +${GO_BONUS}\n"

        tile = BOARD[player.position]
        text += f"📍 {tile['name']} karesine geldi.\n"

        if tile["type"] == "property":
            owner_id = game.properties.get(player.position)

            if owner_id is None:
                if player.money >= tile["price"]:
                    game.waiting_buy = (player.id, player.position)
                    return await send_or_edit(
                        query,
                        text + f"🏠 Bu mülk boş.\nFiyat: ${tile['price']}\nSatın almak ister misin?",
                        buy_menu(player.position)
                    )
                else:
                    text += "💸 Satın almak için yeterli paran yok.\n"

            elif owner_id != player.id:
                owner = next((x for x in game.players if x.id == owner_id), None)
                rent = tile["rent"]
                player.money -= rent
                if owner and owner.alive:
                    owner.money += rent
                    text += f"💰 {owner.name} oyuncusuna ${rent} kira ödendi.\n"

            else:
                text += "🏡 Kendi mülküne geldin.\n"

        elif tile["type"] == "tax":
            player.money -= tile["amount"]
            text += f"🧾 Vergi ödedin: -${tile['amount']}\n"

        elif tile["type"] == "bonus":
            player.money += tile["amount"]
            text += f"🎁 Bonus aldın: +${tile['amount']}\n"

        elif tile["type"] == "chance":
            card_text, amount = random.choice(CHANCE_CARDS)
            player.money += amount
            if amount >= 0:
                text += f"🎴 Şans: {card_text} +${amount}\n"
            else:
                text += f"🎴 Şans: {card_text} -${abs(amount)}\n"

        elif tile["type"] == "jail":
            player.in_jail = True
            player.jail_turns = 0
            text += "🚔 Hapse girdin! Bir tur bekleyeceksin.\n"

        else:
            text += "😌 Bu karede özel bir şey olmadı.\n"

        if player.money < 0:
            player.alive = False
            text += f"💀 {player.name} iflas etti ve elendi.\n"

        alive_players = [p for p in game.players if p.alive]
        if len(alive_players) == 1:
            winner = alive_players[0]
            del games[chat_id]
            return await send_or_edit(query, text + f"\n🏆 Kazanan: {winner.name}", main_menu())

        next_player = game.next_turn()
        text += f"\n➡️ Sıradaki oyuncu: {next_player.name}"
        return await send_or_edit(query, text, turn_menu(can_roll=False))

    if data.startswith("buy_"):
        if not game or not game.waiting_buy:
            return await send_or_edit(query, "Satın alma işlemi bulunamadı.", main_menu())

        pos = int(data.split("_")[1])
        player = game.current_player()

        if game.waiting_buy != (user.id, pos):
            return await send_or_edit(query, "Bu satın alma sırası sende değil.", main_menu())

        tile = BOARD[pos]
        if player.money >= tile["price"]:
            player.money -= tile["price"]
            game.properties[pos] = player.id
            game.waiting_buy = None

            next_player = game.next_turn()
            return await send_or_edit(
                query,
                f"✅ {player.name}, {tile['name']} mülkünü satın aldı.\n➡️ Sıradaki oyuncu: {next_player.name}",
                turn_menu(can_roll=False)
            )
        else:
            game.waiting_buy = None
            next_player = game.next_turn()
            return await send_or_edit(
                query,
                "💸 Yeterli para yok, mülk alınamadı.\n"
                f"➡️ Sıradaki oyuncu: {next_player.name}",
                turn_menu(can_roll=False)
            )

    if data.startswith("pass_"):
        if not game or not game.waiting_buy:
            return await send_or_edit(query, "Geçilecek aktif satın alma yok.", main_menu())

        pos = int(data.split("_")[1])
        if game.waiting_buy != (user.id, pos):
            return await send_or_edit(query, "Bu işlem sana ait değil.", main_menu())

        game.waiting_buy = None
        next_player = game.next_turn()
        return await send_or_edit(
            query,
            f"❌ {BOARD[pos]['name']} satın alınmadı.\n➡️ Sıradaki oyuncu: {next_player.name}",
            turn_menu(can_roll=False)
        )

async def start_command_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable eksik.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command_alias))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
