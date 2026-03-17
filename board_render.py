from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import hashlib

def _color_for_user(user_id: int):
    h = hashlib.md5(str(user_id).encode()).hexdigest()
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (80 + r // 3, 80 + g // 3, 80 + b // 3)

def render_board_png(board, players, size=900):
    """
    40 kareyi çerçeve üzerinde çizer, oyuncuları konumlarında işaretler.
    players: [{user_id,name,position,alive}, ...]
    """
    img = Image.new("RGB", (size, size), (245, 245, 245))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    margin = 30
    outer = (margin, margin, size - margin, size - margin)
    d.rectangle(outer, outline=(30, 30, 30), width=4)

    # 10 kare/kenar (köşeler dahil) => toplam 40
    tile_w = (outer[2] - outer[0]) // 10
    tile_h = tile_w

    # index -> tile rect
    rects = {}

    # Alt sıra: 0..9 (sol alt köşeden sağa)
    for i in range(10):
        x0 = outer[0] + i * tile_w
        y0 = outer[3] - tile_h
        rects[i] = (x0, y0, x0 + tile_w, y0 + tile_h)

    # Sağ sıra: 10..19 (alttan üste)
    for j in range(1, 10):
        idx = 9 + j
        x0 = outer[2] - tile_w
        y0 = outer[3] - (j + 1) * tile_h
        rects[idx] = (x0, y0, x0 + tile_w, y0 + tile_h)

    # Üst sıra: 20..29 (sağdan sola)
    for i in range(10):
        idx = 19 + i + 1  # 20..29
        x0 = outer[2] - (i + 1) * tile_w
        y0 = outer[1]
        rects[idx] = (x0, y0, x0 + tile_w, y0 + tile_h)

    # Sol sıra: 30..39 (üstten alta)
    for j in range(1, 10):
        idx = 29 + j
        x0 = outer[0]
        y0 = outer[1] + j * tile_h
        rects[idx] = (x0, y0, x0 + tile_w, y0 + tile_h)

    # çiz
    for idx in range(40):
        x0, y0, x1, y1 = rects[idx]
        d.rectangle((x0, y0, x1, y1), outline=(60, 60, 60), width=2)
        name = board[idx]["name"][:10]
        d.text((x0 + 4, y0 + 4), f"{idx}", fill=(0, 0, 0), font=font)
        d.text((x0 + 4, y0 + 16), name, fill=(0, 0, 0), font=font)

    # oyuncu işaretleri
    alive_players = [p for p in players if p.get("alive")]
    per_tile = {}
    for p in alive_players:
        per_tile.setdefault(p["position"], []).append(p)

    for pos, plist in per_tile.items():
        x0, y0, x1, y1 = rects[pos]
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        radius = 8
        for k, p in enumerate(plist[:6]):
            col = _color_for_user(p["user_id"])
            ox = (k % 3) * (radius * 2 + 2) - (radius * 2)
            oy = (k // 3) * (radius * 2 + 2) - (radius * 2)
            d.ellipse((cx + ox - radius, cy + oy - radius, cx + ox + radius, cy + oy + radius), fill=col, outline=(0, 0, 0))

    bio = BytesIO()
    bio.name = "board.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio
