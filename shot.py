#!/usr/bin/env python3
"""截 LEGOLAND 站（desktop/mobile）+ hi hub 主題樂園組。"""
from playwright.sync_api import sync_playwright

OUT = "/home/ubuntu/legoland-preview"
import os; os.makedirs(OUT, exist_ok=True)
LIVE = "https://legoland.we1co.me/?v=shot"

with sync_playwright() as p:
    b = p.chromium.launch(channel="chromium", args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1180, "height": 1000})
    pg.goto(LIVE); pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{OUT}/legoland-desktop.png", full_page=True)
    print("desktop ok")
    pg2 = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    pg2.goto(LIVE); pg2.wait_for_timeout(2500)
    pg2.screenshot(path=f"{OUT}/legoland-mobile.png", full_page=True)
    print("mobile ok")
    pg3 = b.new_page(viewport={"width": 1180, "height": 1000})
    pg3.goto("https://hi.we1co.me/?v=shot"); pg3.wait_for_timeout(2500)
    pg3.add_style_tag(content='section.group:not([data-cat="park"]){display:none!important}')
    pg3.wait_for_timeout(400)
    box = pg3.locator('section[data-cat="park"]').bounding_box()
    pg3.screenshot(path=f"{OUT}/hub-park-group.png", full_page=True,
                   clip={"x": max(0, box["x"] - 12), "y": max(0, box["y"] - 12),
                         "width": box["width"] + 24, "height": box["height"] + 24})
    print("hub ok")
    b.close()
