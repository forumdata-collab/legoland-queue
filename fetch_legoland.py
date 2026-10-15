#!/usr/bin/env python3
"""LEGOLAND Japan（名古屋）即時狀態 → data/legoland.json

資料來源（兩個都免費、免 key）：
  1. queue-times.com  /parks/285/queue_times.json     — 9 個分區 + 45 項設施嘅開／閉 + 等候時間
  2. api.themeparks.wiki /v1/entity/<park>/live       — 表演（含開演時間）+ 樂園狀態
                        /v1/entity/<park>/schedule    — 當日開放時間
官方網站／App 冇公開 API，亦冇座標（所以本站係清單式，唔做地圖）。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "site", "data")
JST = ZoneInfo("Asia/Tokyo")
HKT = ZoneInfo("Asia/Hong_Kong")

QT_PARK = "285"
WIKI_PARK = "0c14c187-13f5-41ef-91b1-7ecb504239a7"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# 分區中文名（queue-times 只提供英文）
LAND_ZH = {
    "Adventure": "冒險世界",
    "Bricktopia": "積木烏托邦",
    "Factory Zone": "樂高工廠區",
    "Knight’s Kingdom": "騎士王國",
    "Knight's Kingdom": "騎士王國",
    "LEGO City": "樂高城市",
    "LEGO NINJAGO World": "旋風忍者世界",
    "Miniland": "迷你世界",
    "Pirate Shores": "海盜海岸",
    "LEGOLAND Japan Hotel & Outer Area": "酒店與外圍區",
    "": "其他",
}


def get_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def fetch_queue_times():
    return get_json(f"https://queue-times.com/parks/{QT_PARK}/queue_times.json")


def fetch_wiki(path):
    try:
        return get_json(f"https://api.themeparks.wiki/v1/entity/{WIKI_PARK}/{path}")
    except Exception as e:
        print(f"⚠️ themeparks.wiki /{path} 失敗: {e}", file=sys.stderr)
        return {}


def land_of_ride(qt):
    """queue-times 頂層 rides 冇分區 → 歸入『其他』。"""
    out = []
    for land in qt.get("lands", []):
        rides = [{
            "id": r.get("id"),
            "name": (r.get("name") or "").strip(),
            "isOpen": bool(r.get("is_open")),
            "wait": int(r.get("wait_time") or 0),
            "updated": r.get("last_updated", ""),
        } for r in land.get("rides", [])]
        if rides:
            out.append({"id": land.get("id"), "name": (land.get("name") or "").strip(),
                        "nameZh": LAND_ZH.get((land.get("name") or "").strip(), ""), "rides": rides})
    extra = [{
        "id": r.get("id"), "name": (r.get("name") or "").strip(), "isOpen": bool(r.get("is_open")),
        "wait": int(r.get("wait_time") or 0), "updated": r.get("last_updated", ""),
    } for r in qt.get("rides", [])]
    if extra:
        for l in out:
            if l["name"] == "":
                l["rides"] += extra
                break
        else:
            out.append({"id": 0, "name": "", "nameZh": LAND_ZH[""], "rides": extra})
    return out


def fmt_hhmm(iso):
    if not iso:
        return ""
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%H:%M")
    except Exception:
        return ""


def main():
    qt = fetch_queue_times()
    live = fetch_wiki("live")
    sched = fetch_wiki("schedule")

    lands = land_of_ride(qt)
    rides = [r for l in lands for r in l["rides"]]
    open_rides = [r for r in rides if r["isOpen"]]
    waits = [r["wait"] for r in open_rides if r["wait"] > 0]

    # 表演：有 showtimes 嘅 SHOW / 娛樂項目
    shows = []
    for e in live.get("liveData", []):
        if e.get("entityType") not in ("SHOW", "ENTERTAINMENT"):
            continue
        times = sorted({fmt_hhmm(s.get("startTime")) for s in (e.get("showtimes") or []) if s.get("startTime")})
        shows.append({"name": e.get("name", ""), "status": e.get("status", ""), "times": [t for t in times if t]})

    # 今日開放時間
    today = dt.datetime.now(JST).date().isoformat()
    hours = next((s for s in sched.get("schedule", []) if s.get("date") == today), None)
    if not hours:
        hours = next((s for s in sched.get("schedule", []) if s.get("date")), None)

    park_live = next((e for e in live.get("liveData", []) if e.get("entityType") == "PARK"), {})
    # 開放與否以「今日開放時間 + 現在 JST」為準（設施 is_open 在閉園前後會滯後，唔可靠）
    park_open = False
    if hours and hours.get("date") == today:
        try:
            o = dt.datetime.fromisoformat((hours.get("openingTime") or "").replace("Z", "+00:00")).astimezone(JST)
            c = dt.datetime.fromisoformat((hours.get("closingTime") or "").replace("Z", "+00:00")).astimezone(JST)
            park_open = o <= dt.datetime.now(JST) <= c
        except Exception:
            park_open = bool(open_rides)
    else:
        park_open = bool(open_rides)
    latest = max([r["updated"] for r in rides if r["updated"]] or [""])

    payload = {
        "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "updatedJst": dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M"),
        "updatedHkt": dt.datetime.now(HKT).strftime("%Y-%m-%d %H:%M"),
        "rideUpdated": latest,
        "park": {
            "name": "LEGOLAND Japan",
            "nameZh": "日本樂高樂園（名古屋）",
            "open": park_open,
            "status": park_live.get("status", ""),
            "hoursOpen": fmt_hhmm((hours or {}).get("openingTime", "")),
            "hoursClose": fmt_hhmm((hours or {}).get("closingTime", "")),
            "hoursDate": (hours or {}).get("date", ""),
        },
        "stats": {
            "total": len(rides),
            # 閉園後 queue-times 嘅 is_open 會滯後，所以「開放中」只計真正有等候時間嘅
            "open": len([r for r in open_rides if r["wait"] > 0]) if not park_open else len(open_rides),
            "openFlagged": len(open_rides),
            "avgWait": round(sum(waits) / len(waits)) if waits else 0,
            "maxWait": max(waits) if waits else 0,
        },
        "lands": lands,
        "shows": sorted(shows, key=lambda s: (s["times"][0] if s["times"] else "99:99")),
        "sources": [
            {"name": "queue-times.com", "url": f"https://queue-times.com/parks/{QT_PARK}"},
            {"name": "themeparks.wiki", "url": "https://api.themeparks.wiki/"},
        ],
    }

    os.makedirs(DATA, exist_ok=True)
    tmp = os.path.join(DATA, "legoland.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(DATA, "legoland.json"))
    print(f"OPEN={payload['stats']['open']}/{payload['stats']['total']} "
          f"AVG={payload['stats']['avgWait']} MAX={payload['stats']['maxWait']} "
          f"park={'open' if park_open else 'closed'} hours={payload['park']['hoursOpen']}-{payload['park']['hoursClose']} "
          f"shows={len(shows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
