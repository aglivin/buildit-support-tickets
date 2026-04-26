#!/usr/bin/env bash
# run_and_test.sh — start the stack and smoke-test the API
set -euo pipefail

# ── 1. Verify .env exists and has an API key ──────────────────────────────────
if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example and add your OPENAI_API_KEY."
  echo "  cp .env.example .env"
  exit 1
fi

if ! grep -qE "^OPENAI_API_KEY=sk-" .env; then
  echo "ERROR: OPENAI_API_KEY not set in .env (must start with sk-)"
  exit 1
fi

# ── 2. Start the stack ────────────────────────────────────────────────────────
echo ">>> Starting docker compose (building if needed)..."
docker compose up -d --build

# ── 3. Wait for the API to be healthy ─────────────────────────────────────────
echo ">>> Waiting for API to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/healthz > /dev/null 2>&1; then
    echo "    API is up."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: API did not start in 30s. Check logs: docker compose logs api"
    exit 1
  fi
  sleep 1
done

# ── 4. Smoke tests ────────────────────────────────────────────────────────────
echo ""
echo ">>> Smoke test 1: health check"
curl -sf http://localhost:8000/healthz | python3 -m json.tool

echo ""
echo ">>> Smoke test 2: create ticket (expect 201)"
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"Charged twice for October","body":"I see two charges of 49 on my card from Oct 3. Please refund one.","customer_email":"anna@example.com"}')
HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS:")
echo "HTTP $HTTP_STATUS"
echo "$BODY" | python3 -m json.tool

echo ""
echo ">>> Smoke test 3: duplicate within window (expect 200)"
RESPONSE2=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"Charged twice for October","body":"I see two charges of 49 on my card from Oct 3. Please refund one.","customer_email":"anna@example.com"}')
HTTP_STATUS2=$(echo "$RESPONSE2" | grep "HTTP_STATUS:" | cut -d: -f2)
BODY2=$(echo "$RESPONSE2" | grep -v "HTTP_STATUS:")
echo "HTTP $HTTP_STATUS2"
echo "$BODY2" | python3 -m json.tool

echo ""
echo ">>> Smoke test 4: list tickets"
curl -sf "http://localhost:8000/tickets?limit=5" | python3 -m json.tool

echo ""
echo ">>> Smoke test 5: invalid email (expect 422)"
curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST http://localhost:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Test body","customer_email":"not-an-email"}'

echo ""
echo "=== All smoke tests done ==="
echo ""
echo ">>> Running unit tests (no DB needed)..."
uv run --no-sync pytest -v

echo ""
echo "=== Done. To stop: docker compose down ==="
