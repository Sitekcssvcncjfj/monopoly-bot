START_MONEY = 1500
GO_BONUS = 200

TURN_TIMEOUT_SEC = 90
AUCTION_TIMEOUT_SEC = 60
TRADE_TIMEOUT_SEC = 90

SUPPORT_URL = "https://t.me/KGBotomasyon"
ADD_BOT_URL = "https://t.me/KGBMonopolyBOT?startgroup=true"

# 40 karelik basit Monopoly benzeri tahta
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
    {"name": "Hapis (Ziyaret)", "type": "jail"},
    {"name": "Bakırköy", "type": "property", "price": 180, "base_rent": 40, "color": "pink"},
    {"name": "Elektrik", "type": "utility", "price": 150, "base_rent": 35, "color": "utility"},
    {"name": "Bebek", "type": "property", "price": 180, "base_rent": 40, "color": "pink"},
    {"name": "Kasa", "type": "community"},
    {"name": "Levent", "type": "property", "price": 200, "base_rent": 45, "color": "pink"},
    {"name": "Vapur", "type": "railroad", "price": 200, "base_rent": 50, "color": "railroad"},
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
    {"name": "Su", "type": "utility", "price": 150, "base_rent": 35, "color": "utility"},
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

JAIL_POS = 9

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
