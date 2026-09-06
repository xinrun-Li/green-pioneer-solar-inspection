#!/usr/bin/env bash
# healthcheck.sh - 检查绿能先锋各服务健康状态
# 检查 Django 健康端点及主要 API 端点的可用性，输出健康状态摘要
set -uo pipefail

BASE_URL="${HEALTH_BASE_URL:-http://localhost:8000}"
API="$BASE_URL/api/v1"
PASS=0
FAIL=0
FAILED_ITEMS=()

check() {
  local name="$1"
  local url="$2"
  local expect="${3:-200}"
  local code
  code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null)
  if [[ "$code" == "$expect" ]]; then
    echo "  [OK] $name ($code)"
    PASS=$((PASS + 1))
  else
    echo "  [FAIL] $name (expected $expect, got ${code:-timeout})"
    FAIL=$((FAIL + 1))
    FAILED_ITEMS+=("$name")
  fi
}

echo "=========================================="
echo "Green Pioneer Health Check ($(date '+%Y-%m-%d %H:%M:%S'))"
echo "=========================================="
echo ""
echo "[1/3] Backend Services"
check "health"          "$API/health" 200
check "login"           "$API/auth/login" 405
check "me"              "$API/auth/me" 200
check "stations"        "$API/stations/current/map" 403
check "upload-batches"  "$API/upload-batches/" 403
check "recognition"     "$API/recognition-jobs/" 403
check "events"          "$API/events/" 403
check "inspections"     "$API/inspections/" 403
check "assistant"       "$API/assistant/conversations/" 403
check "reports"         "$API/reports/" 403
echo ""

echo "[2/3] Admin"
check "Django Admin"    "$BASE_URL/admin/login/" 200
echo ""

echo "[3/3] Frontend"
FRONTEND_URL="${HEALTH_FRONTEND_URL:-http://localhost:5173}"
FRONTEND_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$FRONTEND_URL" 2>/dev/null)
if [[ "$FRONTEND_CODE" == "000" ]]; then
  echo "  [FAIL] frontend (cannot connect to $FRONTEND_URL)"
  FAIL=$((FAIL + 1))
  FAILED_ITEMS+=("frontend")
else
  echo "  [OK] frontend ($FRONTEND_CODE)"
  PASS=$((PASS + 1))
fi

echo ""
echo "=========================================="
if [[ $FAIL -eq 0 ]]; then
  echo "ALL PASSED: $PASS checks passed"
  exit 0
else
  echo "SOME FAILED: $PASS passed, $FAIL failed"
  printf '  Failed: %s\n' "${FAILED_ITEMS[@]}"
  echo "  Hint: Run ./scripts/start.sh first."
  exit 1
fi