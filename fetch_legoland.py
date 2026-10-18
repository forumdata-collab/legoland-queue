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
import re
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "site", "data")
HIST = os.path.join(DATA, "history.json")
MAX_HISTORY = 6000        # ~20 日（每 5 分鐘一個樣本；cron 09–17 每 5 分鐘）
TREND_SAMPLES = 24        # 前端趨勢圖用最近 24 個樣本（約 2 小時）
JST = ZoneInfo("Asia/Tokyo")
HKT = ZoneInfo("Asia/Hong_Kong")

QT_PARK = "285"
WIKI_PARK = "0c14c187-13f5-41ef-91b1-7ecb504239a7"
REQS = 0                  # 每次跑 upstream request 數（print 出嚟做記錄）
CACHE_DIR = os.path.join(HERE, "cache")
SCHED_CACHE = os.path.join(CACHE_DIR, "schedule.json")
SCHED_TTL_H = 6           # 開放時間表 cache 有效期（跨日／唔包今日+明日／過期先重抓）
SCHED_SRC = ""            # cache | fetched | stale-cache | none
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

# 設施／表演中文名（對照樂園官方日文名逐一翻譯；HK 用語）
# 角色名（Cole／Jay／Kai／Lloyd）保留英文，避免譯名同園內叫法唔一致
RIDE_ZH = {
    # 冒險世界 Adventure
    "beetle bounce": "甲蟲彈跳",
    "cargo ace": "貨運高手",
    "lost kingdom adventure": "失落王國探險",
    "pharaoh's revenge": "法老復仇",
    "s.q.u.i.d. surfer": "魷魚衝浪",
    "submarine adventure": "潛水艇探險",
    "the secret chamber of amset-ra": "阿姆塞特拉密室",
    # 積木烏托邦 Bricktopia
    "brick party": "積木派對",
    "cat cloud busters": "貓貓雲朵打散隊",
    "duplo express": "得寶小火車",
    "duplo play": "得寶遊樂區",
    "imagination celebration": "想像力嘉年華",
    "observation tower": "瞭望塔",
    "rainbow design studio": "彩虹設計工作室",
    "rebuild the word center": "重建世界中心",
    "workshop": "樂高創意工作坊",
    # 樂高工廠區 Factory Zone
    "lego factory tour": "樂高工廠導覽",
    # 騎士王國 Knight's Kingdom
    "dragon's apprentice": "小龍過山車",
    "kingdom games": "王國遊戲",
    "merlin's challenge": "梅林的挑戰",
    "merlin's flying machines": "梅林飛行器",
    "the dragon": "巨龍過山車",
    # 樂高城市 LEGO City
    "city airport": "城市機場",
    "coast guard hq": "海岸防衛隊總部",
    "driving school": "駕駛學校",
    "jr. driving school": "小童駕駛學校",
    "police building experience": "警察積木體驗",
    "rescue academy": "救援學院",
    "splash pad": "戲水區",
    "stop&go games": "停一停行一行",
    "the wharf": "碼頭區",
    "water maze": "水上迷宮",
    # 旋風忍者世界 LEGO NINJAGO World
    "cole's rock climbing wall": "攀石牆（Cole）",
    "flying ninjago": "忍者飛行",
    "jay's lightning drill": "閃電鑽（Jay）",
    "kai's sky masters": "天空飛船（Kai）",
    "lloyd's spinjitzu spinner": "旋風忍術轉盤（Lloyd）",
    "ninja games": "忍者遊戲",
    # 迷你世界 Miniland
    "miniland": "迷你世界",
    # 海盜海岸 Pirate Shores
    "anchors away!": "起錨啦！",
    "blue coat games": "藍衣海盜遊戲",
    "build a boat": "砌船仔",
    "castaway camp": "荒島營地",
    "splash battle": "水戰",
    # 酒店與外圍區
    "ocean king games": "海洋王遊戲",
    "kitchen car event area": "餐車活動區",
}

# 表演／活動（名稱來自 themeparks.wiki，原文為日文或英文）
SHOW_ZH = {
    "モンスター・パーティからの大脱出": "怪物派對大逃亡",
    "lego ninjago live": "樂高旋風忍者現場表演",
    "lego city 4d": "樂高城市 4D 電影",
    "ホプシーとあそぼう！-play time with hopsy-": "同 Hopsy 玩遊戲",
    "lego dreamzzz z-blob rescue rush": "樂高 Dreamzzz：Z-Blob 拯救大作戰",
    "lego ninjago 4d movie": "樂高旋風忍者 4D 電影",
    "lego friends 4d movie alien invasion": "樂高 Friends 4D 電影：外星人入侵",
    "またきてマーチ": "「再嚟玩」巡遊",
}


def get_json(url, timeout=30):
    """抓 JSON；遇 429/403/5xx 依 Retry-After 等一次再試，其餘直接拋（caller 決定）。"""
    global REQS
    for attempt in (1, 2):
        REQS += 1
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if attempt == 1 and e.code in (403, 429, 500, 502, 503, 504):
                wait = min(int(e.headers.get("Retry-After") or 0) or 5, 60)
                print(f"⏳ HTTP {e.code}（可能被限流），等 {wait}s 再試一次：{url}", file=sys.stderr)
                time.sleep(wait)
                continue
            raise


def fetch_queue_times():
    return get_json(f"https://queue-times.com/parks/{QT_PARK}/queue_times.json")


def load_schedule():
    """開放時間表：一個 call 回 31 日，所以一日抓一次就夠（省 ~107 個 request/日）。

    快取喺 cache/schedule.json（唔會部署出去）；過期、跨日、或唔包含今日+明日 → 重抓。
    抓唔到就用舊快取，完全冇就空 dict（前端會顯示「以官網為準」）。
    """
    now = dt.datetime.now(JST)
    try:
        with open(SCHED_CACHE, encoding="utf-8") as fh:
            cached = json.load(fh)
        fetched = dt.datetime.fromisoformat(cached.get("_fetchedAt", ""))
        dates = {s.get("date") for s in cached.get("schedule", [])}
        covers = now.date().isoformat() in dates and (now.date() + dt.timedelta(days=1)).isoformat() in dates
        if covers and (now - fetched) < dt.timedelta(hours=SCHED_TTL_H):
            global SCHED_SRC
            SCHED_SRC = "cache"
            return cached
    except Exception:
        pass
    sched = fetch_wiki("schedule")
    if sched:
        SCHED_SRC = "fetched"
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            sched = dict(sched, _fetchedAt=now.isoformat(timespec="seconds"))
            with open(SCHED_CACHE, "w", encoding="utf-8") as fh:
                json.dump(sched, fh, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️ schedule cache 寫唔入: {e}", file=sys.stderr)
        return sched
    try:
        with open(SCHED_CACHE, encoding="utf-8") as fh:
            cached = json.load(fh)
        SCHED_SRC = "stale-cache"
        return cached
    except Exception:
        SCHED_SRC = "none"
        return {}


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
            "nameZh": zh_name(r.get("name")),
            "isOpen": bool(r.get("is_open")),
            "wait": int(r.get("wait_time") or 0),
            "updated": r.get("last_updated", ""),
        } for r in land.get("rides", [])]
        if rides:
            out.append({"id": land.get("id"), "name": (land.get("name") or "").strip(),
                        "nameZh": LAND_ZH.get((land.get("name") or "").strip(), ""), "rides": rides})
    extra = [{
        "id": r.get("id"), "name": (r.get("name") or "").strip(), "nameZh": zh_name(r.get("name")),
        "isOpen": bool(r.get("is_open")),
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


def _norm(s):
    """正規化設施名（去掉 ® ™、【…】後綴、統一引號大小寫）以便查中文名。"""
    s = (s or "").replace("®", "").replace("™", "")
    s = re.sub(r"【[^】]*】", "", s)
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def zh_name(name):
    n = _norm(name)
    return RIDE_ZH.get(n) or SHOW_ZH.get(n) or ""


def fmt_hhmm(iso):
    if not iso:
        return ""
    try:
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%H:%M")
    except Exception:
        return ""


def load_history():
    """讀等候時間歷史（date-keyed：每日累積，唔會覆蓋）。"""
    try:
        with open(HIST, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_history(hist):
    """原子寫入（避免半寫檔案令下次 load 失敗而清空歷史）。"""
    os.makedirs(DATA, exist_ok=True)
    tmp = HIST + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(hist, fh, ensure_ascii=False)
    os.replace(tmp, HIST)


def load_geo():
    """OSM 座標 fixture + 人手對照表。冇座標嘅設施唔會硬塞位置。"""
    try:
        pois = json.load(open(os.path.join(HERE, "data", "osm-pois.json"), encoding="utf-8"))["pois"]
        m = json.load(open(os.path.join(HERE, "data", "osm-map.json"), encoding="utf-8"))
    except Exception as e:
        print(f"⚠️ 讀唔到 OSM fixture: {e}", file=sys.stderr)
        return {}, [35.0503, 136.84355]
    by_en = {}
    for p in pois:
        en = m.get("mappings", {}).get(p.get("name", ""))
        if en:
            by_en[en] = {"lat": p["lat"], "lon": p["lon"], "osmName": p["name"], "kind": p.get("kind", "")}
    return by_en, m.get("parkCenter", [35.0503, 136.84355])


def main():
    qt = fetch_queue_times()
    geo, center = load_geo()
    live = fetch_wiki("live")
    sched = load_schedule()   # 一日一次（cache），唔係每 5 分鐘抓

    lands = land_of_ride(qt)
    rides = [r for l in lands for r in l["rides"]]
    # 掛上 OSM 座標（對唔上就冇 coords，前端只會在清單顯示）
    for r in rides:
        g = geo.get(r["name"])
        if g:
            r["lat"], r["lon"] = g["lat"], g["lon"]
    located = [r for r in rides if r.get("lat")]
    open_rides = [r for r in rides if r["isOpen"]]
    waits = [r["wait"] for r in open_rides if r["wait"] > 0]

    # 表演：有 showtimes 嘅 SHOW / 娛樂項目
    shows = []
    for e in live.get("liveData", []):
        if e.get("entityType") not in ("SHOW", "ENTERTAINMENT"):
            continue
        times = sorted({fmt_hhmm(s.get("startTime")) for s in (e.get("showtimes") or []) if s.get("startTime")})
        shows.append({"name": e.get("name", ""), "nameZh": zh_name(e.get("name", "")),
                      "status": e.get("status", ""), "times": [t for t in times if t]})

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

    # ── 等候時間歷史（趨勢圖用）：每個 ride 記一個值，休息／暫停記 None ──
    now_jst = dt.datetime.now(JST)
    snapshot = {str(r["id"]): (r["wait"] if r["isOpen"] else None) for r in rides}
    hist = load_history()
    hist[now_jst.strftime("%Y-%m-%d %H:%M")] = snapshot
    keys = sorted(hist.keys())
    if len(keys) > MAX_HISTORY:
        hist = {k: hist[k] for k in keys[-MAX_HISTORY:]}
        keys = sorted(hist.keys())
    save_history(hist)
    hist_list = [{"t": k, "data": hist[k]} for k in keys[-TREND_SAMPLES:]]

    # ── 依時段（JST 小時）平均等候：累積全歷史，睇邊個鐘最塞 ──
    by_hour = {}
    for k, snap in hist.items():
        hh = k[11:13] if len(k) >= 13 else ""
        if not hh:
            continue
        vals = [v for v in snap.values() if isinstance(v, int)]
        if not vals:
            continue
        slot = by_hour.setdefault(hh, {"sum": 0, "n": 0, "max": 0, "days": 0})
        slot["sum"] += sum(vals)
        slot["n"] += len(vals)
        slot["max"] = max(slot["max"], max(vals))
        slot["days"] += 1
    hourly = [{"h": hh, "avg": round(s["sum"] / s["n"]), "max": s["max"], "samples": s["days"]}
              for hh, s in sorted(by_hour.items()) if s["n"]]

    # ── 平日 vs 週末（JP 假期唔另分；10 月無公眾假期）──
    def agg(pred):
        acc = {}
        for k, snap in hist.items():
            if not pred(k[:10]):
                continue
            hh = k[11:13]
            vals = [v for v in snap.values() if isinstance(v, int)]
            if not vals:
                continue
            s = acc.setdefault(hh, {"sum": 0, "n": 0, "max": 0, "days": 0})
            s["sum"] += sum(vals); s["n"] += len(vals)
            s["max"] = max(s["max"], max(vals)); s["days"] += 1
        return ([{"h": hh, "avg": round(s["sum"] / s["n"]), "max": s["max"], "samples": s["days"]}
                 for hh, s in sorted(acc.items()) if s["n"]],
                len({k[:10] for k in hist if pred(k[:10])}))

    def is_weekend(d):
        try:
            y, m, dd = (int(x) for x in d.split("-"))
            return dt.date(y, m, dd).weekday() >= 5
        except Exception:
            return False

    hourly_wd, days_wd = agg(lambda d: not is_weekend(d))
    hourly_we, days_we = agg(is_weekend)

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
        "geo": {"center": center, "located": len(located), "total": len(rides),
                "source": "OpenStreetMap (ODbL) via Overpass API"},
        "lands": lands,
        "shows": sorted(shows, key=lambda s: (s["times"][0] if s["times"] else "99:99")),
        "history": hist_list,
        "hourly": hourly,
        "hourlyByType": {"all": hourly, "weekday": hourly_wd, "weekend": hourly_we},
        "dayTypeDays": {"all": len({k[:10] for k in hist}), "weekday": days_wd, "weekend": days_we},
        "historyStats": {
            "samples": len(keys),
            "shown": len(hist_list),
            "since": keys[0] if keys else "",
            "last": keys[-1] if keys else "",
            "intervalMin": 5,
        },
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
          f"shows={len(shows)} hist={len(keys)} samples reqs={REQS}"
          f" sched={SCHED_SRC}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
