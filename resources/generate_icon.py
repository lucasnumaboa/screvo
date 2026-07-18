"""Gera o ícone .ico do Screvo (tela rosa + traços de texto + ponto REC)."""
import os
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
sizes = [16, 32, 48, 64, 128, 256]
BASE = 256

# Degradê rosa (topo -> base)
TOP = (255, 182, 193)     # #FFB6C1
MID = (255, 145, 164)     # #FF91A4
BOT = (255, 105, 180)     # #FF69B4


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        if t < 0.5:
            col = _lerp(TOP, MID, t / 0.5)
        else:
            col = _lerp(MID, BOT, (t - 0.5) / 0.5)
        for x in range(size):
            px[x, y] = col + (255,)
    return img


def _render(size):
    grad = _gradient(size)

    # Máscara arredondada
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    radius = int(size * 0.22)
    md.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    draw = ImageDraw.Draw(img)

    # Tela branca
    sx0, sy0 = size * 0.22, size * 0.28
    sx1, sy1 = size * 0.78, size * 0.68
    draw.rounded_rectangle([sx0, sy0, sx1, sy1],
                           radius=max(1, int(size * 0.05)),
                           fill=(255, 255, 255, 255))

    # Linhas de texto (rosa)
    lw = max(1, int(size * 0.03))
    pink = (255, 105, 180, 255)
    for i, yf in enumerate((0.40, 0.48, 0.56)):
        y = size * yf
        x2 = size * (0.68 if i < 2 else 0.58)
        draw.line([size * 0.29, y, x2, y], fill=pink, width=lw)

    # Ponto REC (vermelho)
    r = size * 0.045
    cx, cy = size * 0.70, size * 0.36
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 23, 68, 255))

    return img


base = _render(BASE)
base.save(OUT, format="ICO", sizes=[(s, s) for s in sizes])
print(f"Icone criado: {OUT}")
