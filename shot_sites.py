#!/usr/bin/env python3
"""截 hi hub 主題樂園組 + 遊戲組，同 legoland 站（desktop/mobile）。"""
import os
from playwright.sync_api import sync_playwright

OUT = "/home/ubuntu/legoland-preview"
os.makedirs(OUT, exist_ok=True)

def shot_group(pg, cat, path):
    # 每次只保留一個 style（否則多次 add_style_tag 會疊加，變成全部 section 都隱藏）
    pg.evaluate('''(css) => {
        let el = document.getElementById('__shotcss');
        if (!el) { el = document.createElement('style'); el.id = '__shotcss'; document.head.appendChild(el); }
        el.textContent = css;
    }''', f'section.group:not([data-cat="{cat}"]){{display:none!important}}')
    pg.wait_for_timeout(400)
    box = pg.locator(f'section[data-cat="{cat}"]').bounding_box()
    pg.screenshot(path=path, full_page=True,
                  clip={"x": max(0, box["x"] - 12), "y": max(0, box["y"] - 12),
                        "width": box["width"] + 24, "height": box["height"] + 24})
    print(path, "ok")

with sync_playwright() as p:
    b = p.chromium.launch(channel="chromium", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1180, "height": 1000})
    pg.goto("https://hi.we1co.me/?v=shot1"); pg.wait_for_timeout(2500)
    shot_group(pg, "park", f"{OUT}/hub-park-group.png")
    shot_group(pg, "game", f"{OUT}/hub-game-group.png")
    pg2 = b.new_page(viewport={"width": 1180, "height": 1150})
    pg2.goto("https://legoland.we1co.me/?v=shot2"); pg2.wait_for_timeout(6000)
    pg2.screenshot(path=f"{OUT}/legoland-desktop.png")   # 只截 viewport（Leaflet 全頁會有空白 tile）
    print("legoland desktop ok")
    pg3 = b.new_page(viewport={"width": 390, "height": 900}, device_scale_factor=2)
    pg3.goto("https://legoland.we1co.me/?v=shot3"); pg3.wait_for_timeout(6000)
    pg3.screenshot(path=f"{OUT}/legoland-mobile.png")
    print("legoland mobile ok")
    b.close()
