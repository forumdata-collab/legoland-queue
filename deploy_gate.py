#!/usr/bin/env python3
"""資料／前端冇變就唔部署，省 Cloudflare Pages deployment。

用法：
  python3 deploy_gate.py check   → exit 0 = 要部署；10 = 可以跳過（內容同上次部署一樣）
  python3 deploy_gate.py commit  → 部署成功後寫入今次 digest

Digest 只計「用戶睇得到」嘅嘢：每個設施嘅名／開關／等候時間、樂園狀態同開放時段、
表演場次，加上前端檔案內容。**唔計**每次抓都會變嘅 last_updated、「資料更新」時間、
趨勢樣本（history）—— 否則永遠都「有變」，呢個 gate 就冇用。

另外 digest 會包含「10 分鐘時間格」：即係內容冇變時，最多每 10 分鐘重新部署一次，
令頁面嘅「資料更新」時間唔會停留過久（內容一變就即刻部署）。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "site", "data", "legoland.json")
STATE = os.path.join(HERE, "cache", "deploy_digest.txt")
FRONTEND = ("index.html", "embed.html")
BUCKET_MIN = 10  # 內容無變時，最多幾分鐘重新部署一次


def bucket() -> str:
    override = os.environ.get("LEGOLAND_NOW")
    now = dt.datetime.fromisoformat(override).astimezone(JST) if override else dt.datetime.now(JST)
    return now.strftime(f"%Y-%m-%dT%H:{now.minute // BUCKET_MIN * BUCKET_MIN:02d}")


def digest() -> str:
    h = hashlib.sha256()
    with open(DATA, "rb") as fh:
        d = json.load(fh)
    park = d.get("park") or {}
    visible = {
        "park": {k: park.get(k) for k in ("open", "hoursOpen", "hoursClose", "hoursDate")},
        "stats": d.get("stats"),
        "lands": [{"name": l.get("name"), "nameZh": l.get("nameZh"),
                   "rides": [[r.get("name"), r.get("nameZh"), r.get("isOpen"), r.get("wait")]
                             for r in l.get("rides", [])]} for l in d.get("lands", [])],
        "shows": [[s.get("name"), s.get("nameZh"), s.get("times")] for s in d.get("shows", [])],
    }
    h.update(json.dumps(visible, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for name in FRONTEND:
        p = os.path.join(HERE, "site", name)
        if os.path.exists(p):
            with open(p, "rb") as fh:
                h.update(fh.read())
    h.update(bucket().encode("utf-8"))
    return h.hexdigest()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        cur = digest()
    except Exception:
        return 0  # 讀唔到 → 照部署（fail-open）
    if mode == "commit":
        os.makedirs(os.path.dirname(STATE), exist_ok=True)
        with open(STATE, "w", encoding="utf-8") as fh:
            fh.write(cur)
        return 0
    try:
        with open(STATE, encoding="utf-8") as fh:
            prev = fh.read().strip()
    except Exception:
        prev = ""
    return 10 if (prev and cur == prev) else 0


if __name__ == "__main__":
    sys.exit(main())
