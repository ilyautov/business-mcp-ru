#!/usr/bin/env python3
"""Обложка зонтика: assets/social-preview.png, 1280x640.

Стиль общий с пятью серверами и с marketplaces-mcp-ru: тёмный фон, моноширинный
заголовок с акцентом, чипы с цифрами. Цифры берутся из каталогов соседних
репозиториев тем же способом, что страницы сайта, поэтому обложка не может
разойтись с кодом.

Запуск: python3 scripts/make_social_preview.py
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pages import PAGES, catalog_path  # noqa: E402

import yaml  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

W, H, MARGIN = 1280, 640, 80
BG_TOP, BG_BOT = (13, 17, 23), (17, 22, 33)
TITLE, SUB = (230, 237, 243), (148, 158, 169)
ORANGE, OCHRE, GREEN = (217, 119, 87), (181, 73, 31), (84, 184, 124)
CHIP_BORDER, CHIP_TEXT, RED = (52, 60, 70), (201, 209, 217), (229, 99, 91)


def fonts():
    import matplotlib
    ttf = glob.glob(os.path.join(os.path.dirname(matplotlib.__file__),
                                 "mpl-data/fonts/ttf"))[0]
    return (os.path.join(ttf, "DejaVuSansMono-Bold.ttf"),
            os.path.join(ttf, "DejaVuSansMono.ttf"))


def total_methods() -> int:
    n = 0
    for page in PAGES:
        raw = yaml.safe_load(catalog_path(page["svc"]).read_text(encoding="utf-8"))
        n += len(raw["endpoints"])
    return n


def main() -> None:
    bold, reg = fonts()
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for y in range(H):
        k = y / H
        c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * k) for i in range(3))
        for x in range(W):
            px[x, y] = c
    d = ImageDraw.Draw(img)
    f_title, f_sub = ImageFont.truetype(bold, 72), ImageFont.truetype(reg, 30)
    f_chip, f_diff = ImageFont.truetype(reg, 26), ImageFont.truetype(bold, 28)
    f_foot = ImageFont.truetype(reg, 25)

    def w(text, f):
        return d.textbbox((0, 0), text, font=f)[2]

    def chip(x, y, label, accent=None):
        pad, h = 20, 52
        box = w(label, f_chip) + pad * 2
        d.rounded_rectangle([x, y, x + box, y + h], radius=14,
                            outline=accent or CHIP_BORDER, width=2)
        d.text((x + pad, y + 12), label, font=f_chip, fill=accent or CHIP_TEXT)
        return x + box

    x, ty = MARGIN, 128
    d.text((x, ty), "business-mcp", font=f_title, fill=TITLE)
    x += w("business-mcp", f_title)
    d.text((x, ty), "-ru", font=f_title, fill=ORANGE)
    x += w("-ru", f_title) + 18
    d.rounded_rectangle([x, ty + 10, x + 54, ty + 64], radius=10, fill=OCHRE)

    d.text((MARGIN, 254), "Российские деловые сервисы в ИИ-ассистенте",
           font=f_sub, fill=SUB)

    cx = MARGIN
    cx = chip(cx, 330, f"{total_methods()} методов", accent=GREEN) + 16
    cx = chip(cx, 330, "5 серверов") + 16
    cx = chip(cx, 330, "общее ядро") + 16
    chip(cx, 330, "MIT")

    d.text((MARGIN, 452), "hh.ru · VK · Диадок · СБИС · Честный знак",
           font=f_diff, fill=GREEN)
    d.text((MARGIN, 496), "каждый ставится отдельно, ядро у всех одно",
           font=f_diff, fill=SUB)

    foot = "Claude Code · Cursor · Codex · Claude Desktop"
    d.text((W - MARGIN - w(foot, f_foot), 566), foot, font=f_foot, fill=SUB)

    out = Path(__file__).resolve().parents[1] / "assets" / "social-preview.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    print("записано:", out, img.size)


if __name__ == "__main__":
    main()
