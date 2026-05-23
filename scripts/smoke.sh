#!/usr/bin/env bash
# Smoke-test the local stack end-to-end.
# Run after `make up`.

set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
TODAY=$(date -u +%Y-%m-%d)
TOMORROW=$(python3 -c "from datetime import date, timedelta; print((date.today()+timedelta(days=1)).isoformat())")

echo "──▶ /health"
curl -fsS "$BASE/health"; echo

echo
echo "──▶ /rag/search — carta d'identità"
curl -fsS -X POST "$BASE/rag/search" \
     -H "Content-Type: application/json" \
     -d '{"query":"come rinnovare la carta di identità","top_k":2}' | head -c 800
echo

echo
echo "──▶ /appointments/slots/available — anagrafe, domani"
curl -fsS "$BASE/appointments/slots/available?office=anagrafe&date=$TOMORROW" | head -c 800
echo

echo
echo "──▶ Simulating a Vapi 'tool-calls' webhook (prenota_appuntamento)"
curl -fsS -X POST "$BASE/vapi/webhook" \
     -H "Content-Type: application/json" \
     -d "{
       \"message\": {
         \"type\": \"tool-calls\",
         \"toolCallList\": [{
           \"id\": \"smoke-1\",
           \"function\": {
             \"name\": \"prenota_appuntamento\",
             \"arguments\": {
               \"citizen_name\": \"Mario Rossi\",
               \"office\": \"anagrafe\",
               \"scheduled_at\": \"${TOMORROW}T10:00:00+02:00\",
               \"reason\": \"rinnovo carta identità\"
             }
           }
         }]
       }
     }"
echo

echo
echo "──▶ /appointments (list)"
curl -fsS "$BASE/appointments" | head -c 800
echo

echo
echo "✓ Smoke test complete."
