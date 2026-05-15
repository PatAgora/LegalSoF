#!/bin/bash

echo "🔍 TRANSACTION REVIEW - COMPREHENSIVE DIAGNOSTICS"
echo "=================================================="
echo ""

echo "=== 1. Backend Health ==="
curl -s https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/health | jq . 2>/dev/null || echo "❌ Backend not responding"
echo ""

echo "=== 2. Database Verification ==="
cd backend && python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./sof_platform.db')
cursor = conn.cursor()

# Check matter exists
cursor.execute("SELECT id, reference_number, client_name FROM matters WHERE id = 1")
matter = cursor.fetchone()
if matter:
    print(f"✅ Matter found: ID={matter[0]}, Ref={matter[1]}, Client={matter[2]}")
else:
    print("❌ Matter 1 not found!")

# Check transactions
cursor.execute("SELECT COUNT(*) FROM transactions WHERE matter_id = 1")
txn_count = cursor.fetchone()[0]
print(f"✅ Transactions for Matter 1: {txn_count}")

# Check alerts
cursor.execute("SELECT COUNT(*) FROM transaction_alerts WHERE matter_id = 1")
alert_count = cursor.fetchone()[0]
print(f"✅ Alerts for Matter 1: {alert_count}")

# Alert breakdown
cursor.execute("SELECT severity, COUNT(*) FROM transaction_alerts WHERE matter_id = 1 GROUP BY severity")
print("\nAlert breakdown:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
EOF
cd ..
echo ""

echo "=== 3. API Response Verification ==="
echo -n "Transactions from API: "
TXN_COUNT=$(curl -s https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transactions | jq 'length' 2>/dev/null)
if [ "$TXN_COUNT" = "30" ]; then
    echo "✅ $TXN_COUNT (correct)"
else
    echo "❌ $TXN_COUNT (expected 30)"
fi

echo -n "Alerts from API: "
ALERT_COUNT=$(curl -s https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transaction-alerts | jq 'length' 2>/dev/null)
if [ "$ALERT_COUNT" = "30" ]; then
    echo "✅ $ALERT_COUNT (correct)"
else
    echo "❌ $ALERT_COUNT (expected 30)"
fi

echo -n "Dashboard API: "
DASH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transaction-dashboard)
if [ "$DASH_STATUS" = "200" ]; then
    echo "✅ $DASH_STATUS OK"
else
    echo "❌ $DASH_STATUS (expected 200)"
fi
echo ""

echo "=== 4. Frontend Configuration ==="
if [ -f "frontend/.env" ]; then
    echo "✅ .env file exists"
    cat frontend/.env
else
    echo "❌ .env file missing!"
fi
echo ""

echo "=== 5. Frontend Status ==="
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5177 2>/dev/null)
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "✅ Frontend running on port 5177"
else
    echo "⚠️  Frontend status: $FRONTEND_STATUS"
fi
echo ""

echo "=== 6. Sample Data Check ==="
echo "First 3 transactions:"
curl -s https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transactions | jq -r '.[0:3] | .[] | "\(.id) - \(.txn_date) - \(.customer_id) - £\(.amount) \(.currency) - \(.country_iso2)"' 2>/dev/null
echo ""

echo "=================================================="
echo "🎯 DIAGNOSIS COMPLETE"
echo ""
echo "Expected Results:"
echo "  ✅ Backend: healthy"
echo "  ✅ Database: 1 matter, 30 transactions, 30 alerts"
echo "  ✅ API: All endpoints return 200 with correct data"
echo "  ✅ Frontend: .env configured, server running"
echo ""
echo "Next Steps:"
echo "  1. Open: https://5177-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai"
echo "  2. Navigate to: Matters → REF-2024-001 → Transaction Review"
echo "  3. Open browser console (F12) and check for errors"
echo "  4. If you see 'No Transactions Yet', share console logs"
echo ""
