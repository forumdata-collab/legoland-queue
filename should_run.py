#!/usr/bin/env python3
"""決定今次 cron 要唔要抓 LEGOLAND 數據。

規則（以當日 JST 開放時段為準，來自 site/data/legoland.json 嘅 park.hours*）：
  1. 現在時間喺 [開園-30 分, 閉園+30 分] 內 → 抓（cron 每 5 分鐘觸發，營業時間就係 5 分鐘一次）。
  2. 其餘時間（閉園後／開園前） → 跳過，**一個 request 都唔發**。
  3. 冇資料／讀唔到／時段日期唔係今日 → 抓（fail-open，唔會卡死唔更新）。

夜場（例如 10/30–11/1 ハロウィン・ナイト 延長）會反映喺當日 hoursClose，自動跟隨。
Exit code: 0 = 要抓；10 = 跳過（cron wrapper 見到 10 就靜靜 exit，唔出任何輸出）。
測試用：LEGOLAND_NOW="2026-10-18T19:05:00+09:00" python3 should_run.py
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "site", "data", "legoland.json")
GRACE_MIN = 30  # 開園前／閉園後緩衝


def now_jst() -> dt.datetime:
    override = os.environ.get("LEGOLAND_NOW")
    if override:
        return dt.datetime.fromisoformat(override).astimezone(JST)
    return dt.datetime.now(JST)


def main() -> int:
    now = now_jst()
    try:
        with open(DATA, encoding="utf-8") as fh:
            park = (json.load(fh) or {}).get("park") or {}
        hours_date = park.get("hoursDate") or ""
        opens, closes = park.get("hoursOpen") or "", park.get("hoursClose") or ""
    except Exception:
        return 0  # 未有資料（第一次跑）→ 抓

    if hours_date != now.date().isoformat() or not (opens and closes):
        return 0  # 時段唔係今日（跨日／舊資料）→ 抓，順便更新當日時段

    try:
        oh, om = (int(x) for x in opens.split(":"))
        ch, cm = (int(x) for x in closes.split(":"))
    except Exception:
        return 0
    start = now.replace(hour=oh, minute=om, second=0, microsecond=0) - dt.timedelta(minutes=GRACE_MIN)
    end = now.replace(hour=ch, minute=cm, second=0, microsecond=0) + dt.timedelta(minutes=GRACE_MIN)
    return 0 if start <= now <= end else 10


if __name__ == "__main__":
    sys.exit(main())
