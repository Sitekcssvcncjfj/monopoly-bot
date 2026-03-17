from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import hashlib

COLOR_MAP = {
    "brown": (139, 69, 19),
    "blue": (30, 144, 255),
    "pink": (255, 105, 180),
    "orange": (255, 140, 0),
    "red": (220, 20, 60),
    "yellow": (255, 215, 0),
    "green": (34, 139, 34),
    "darkblue": (25, 25, 112),
    "railroad": (120, 120, 120),
    "utility": (80, 180, 180),
}

def _color_for_user(user_id: int):
    h = hashlib.md5(str(user_id).encode()).hexdigest()
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (60 + r // 3, 60 + g // 3, 60 + b // 3)

def render_board_png(board, players, size=1000):
    img = Image.new("RGB", (size, size), (245, 245, 245))
    d = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("arial.ttf", 14)
        title_font = ImageFont.truetype("arial.ttf", 28)
    except:
        font = ImageFont.load_default()
        title_font = ImageFont.load_default()

    margin = 30
    tile = (size - 2 * margin) // 11
    inner_start = margin + tile
    inner_end = margin + tile * 10

    rects = {}

    for i in range(11):
        idx = i
        x0 = margin + i * tile
        y0 = margin + 10 * tile
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    for i in range(1, 10):
        idx = 10 + i
        x0 = margin + 10 * tile
        y0 = margin + (10 - i) * tile
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    for i in range(11):
        idx = 20 + i
        x0 = margin + (10 - i) * tile
        y0 = margin
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    for i in range(1, 10):
        idx = 30 + i
        x0 = margin
        y0 = margin + i * tile
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    d.rectangle((margin, margin, margin + tile * 11, margin + tile * 11), outline=(20, 20, 20), width=4)

    for idx in range(40):
        x0, y0, x1, y1 = rects[idx]
        d.rectangle((x0, y0, x1, y1), fill=(255, 255, 255), outline=(60, 60, 60), width=2)

        tile_info = board[idx]
        if tile_info.get("color") in COLOR_MAP:
            stripe_color = COLOR_MAP[tile_info["color"]]
            d.rectangle((x0, y0, x1, y0 + 12), fill=stripe_color)

        d.text((x0 + 4, y0 + 16), str(idx), fill=(0, 0, 0), font=font)
        name = tile_info["name"][:11]
        d.text((x0 + 4, y0 + 32), name, fill=(0, 0, 0), font=font)

    d.rounded_rectangle((inner_start, inner_start, inner_end, inner_end), radius=25, fill=(230, 238, 255), outline=(120, 120, 120), width=3)
    d.text((inner_start + 80, inner_start + 60), "KGB MONOPOLY", fill=(20, 20, 20), font=title_font)
    d.text((inner_start + 100, inner_start + 110), "Canlı Oyun Paneli", fill=(50, 50, 50), font=font)

    per_tile = {}
    for p in players:
        if p.get("alive"):
            per_tile.setdefault(p["position"], []).append(p)

    for pos, plist in per_tile.items():
        x0, y0, x1, y1 = rects[pos]
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2 + 18
        radius = 10

        for k, p in enumerate(plist[:6]):
            col = _color_for_user(p["user_id"])
            ox = (k % 3) * 24 - 24
            oy = (k // 3) * 24 - 12
            d.ellipse(
                (cx + ox - radius, cy + oy - radius, cx + ox + radius, cy + oy + radius),
                fill=col,
                outline=(0, 0, 0),
                width=2
            )

    bio = BytesIO()
    bio.name = "board.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio
