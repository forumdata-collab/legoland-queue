#!/bin/bash
# LEGOLAND Japan（名古屋）即時狀況 — 抓取 + 部署 wrapper（cron no_agent 用）
# 成功 = 完全靜默（0 輸出）；失敗才出訊息
set -uo pipefail
cd /home/ubuntu/legoland-map || exit 1

exec 9>/tmp/legoland-sync.lock
flock -n 9 || exit 0

# 營業時間（含前後 30 分鐘緩衝）每 5 分鐘抓；閉園後／開園前每 60 分鐘一次。
# should_run.py: 0 = 抓, 10 = 跳過（其他非零 = 出錯，就照抓，fail-open）
python3 should_run.py; gate=$?
if [ "$gate" -eq 10 ]; then exit 0; fi

out=$(python3 fetch_legoland.py 2>&1); rc=$?
printf '[%s] rc=%s %s\n' "$(date '+%F %T')" "$rc" "$out" >> /home/ubuntu/legoland-map/deploy.log
if [ "$rc" -ne 0 ]; then
  echo "❌ LEGOLAND Japan 抓取失敗（rc=$rc）"
  printf '%s\n' "$out" | tail -4
  exit 1
fi

set -a; . /home/ubuntu/.hermes/.env; set +a
export CLOUDFLARE_API_TOKEN="${CLOUDFLARE_API_TOKEN:-$CF_WORKERS_TOKEN}"
export CLOUDFLARE_ACCOUNT_ID="${CLOUDFLARE_ACCOUNT_ID:-$CF_ACCOUNT_ID}"

# 用戶睇得到嘅內容同上次一樣（例如閉園時段、無變化嘅等候時間）→ 唔部署，省 Pages deployment
python3 deploy_gate.py check; dg=$?
if [ "$dg" -eq 10 ]; then
  printf '[%s] skip-deploy（內容無變）\n' "$(date '+%F %T')" >> /home/ubuntu/legoland-map/deploy.log
  exit 0
fi

if ! env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
     npx wrangler pages deploy site --project-name=legoland-queue --branch=main --commit-dirty=true \
     >> /home/ubuntu/legoland-map/deploy.log 2>&1; then
  echo "❌ LEGOLAND Japan 部署失敗"
  tail -5 /home/ubuntu/legoland-map/deploy.log
  exit 1
fi
python3 deploy_gate.py commit   # 部署成功先記住 digest（失敗唔記，下次會再試）
exit 0
