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
    img = Image.new("RGB", (size, size), (245, 245, 245))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    margin = 30
    board_size = size - 2 * margin
    tile = board_size // 11  # kenar hesap için daha düzgün
    inner_start = margin + tile
    inner_end = margin + tile * 10

    rects = {}

    # 0-10 alt sıra (sağdan sola yerine soldan sağ mantık)
    # alt sol köşe 0
    for i in range(11):
        idx = i
        x0 = margin + i * tile
        y0 = margin + 10 * tile
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    # 11-20 sağ sütun aşağıdan yukarı
    for i in range(1, 10):
        idx = 10 + i
        x0 = margin + 10 * tile
        y0 = margin + (10 - i) * tile
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    # 21-30 üst sıra sağdan sola
    for i in range(11):
        idx = 20 + i
        x0 = margin + (10 - i) * tile
        y0 = margin
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    # 31-39 sol sütun yukarıdan aşağı
    for i in range(1, 10):
        idx = 30 + i
        x0 = margin
        y0 = margin + i * tile
        rects[idx] = (x0, y0, x0 + tile, y0 + tile)

    # dış çerçeve
    d.rectangle((margin, margin, margin + tile * 11, margin + tile * 11), outline=(30, 30, 30), width=4)

    # kareleri çiz
    for idx in range(40):
        x0, y0, x1, y1 = rects[idx]
        d.rectangle((x0, y0, x1, y1), outline=(60, 60, 60), width=2)
        name = board[idx]["name"][:10]
        d.text((x0 + 4, y0 + 4), str(idx), fill=(0, 0, 0), font=font)
        d.text((x0 + 4, y0 + 18), name, fill=(0, 0, 0), font=font)

    # orta alan
    d.rectangle((inner_start, inner_start, inner_end, inner_end), fill=(230, 240, 255), outline=(120, 120, 120))
    d.text((inner_start + 40, inner_start + 40), "KGB MONOPOLY", fill=(0, 0, 0), font=font)

    # oyuncular
    per_tile = {}
    for p in players:
        if p.get("alive"):
            per_tile.setdefault(p["position"], []).append(p)

    for pos, plist in per_tile.items():
        x0, y0, x1, y1 = rects[pos]
        cx = (x0 + x1) // 2
        cy = (y0 + y1) // 2
        radius = 8

        for k, p in enumerate(plist[:6]):
            col = _color_for_user(p["user_id"])
            ox = (k % 3) * 18 - 18
            oy = (k // 3) * 18 - 9
            d.ellipse(
                (cx + ox - radius, cy + oy - radius, cx + ox + radius, cy + oy + radius),
                fill=col,
                outline=(0, 0, 0)
            )

    bio = BytesIO()
    bio.name = "board.png"
    img.save(bio, "PNG")
    bio.seek(0)
    return bio
