# 🔍 Transaction Review - Comprehensive Diagnostic Guide

**Date:** 2026-01-11  
**Status:** DEBUGGING IN PROGRESS

## 📊 System Overview

### Backend Status
- **URL:** https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
- **Port:** 8000
- **Status:** ✅ RUNNING
- **Auth:** ❌ DISABLED (all endpoints public)
- **Data:** 30 transactions + 30 alerts in database for Matter ID 1

### Frontend Status
- **URL:** https://5177-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
- **Port:** 5177 (changed from 5175)
- **Status:** ✅ RUNNING
- **API Config:** Configured to use backend sandbox URL

### Database Status
- **File:** `backend/sof_platform.db`
- **Matter:** ID 1, Reference: `REF-2024-001`
- **Transactions:** 30 records
- **Alerts:** 30 records (7 CRITICAL, 2 HIGH, 21 MEDIUM)

---

## 🎯 How It SHOULD Work

### Step 1: Navigate to Transaction Review
1. Open: https://5177-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
2. Click on "Matters" in the navigation
3. Click on matter "REF-2024-001" (Matter ID 1)
4. Click on the "🆕 Transaction Review" tab

### Step 2: Expected Behavior
The page should:
1. Show "Loading transactions..." for 1-2 seconds
2. Display debug info: Matter ID: 1, API URL
3. Load 30 transactions from API
4. Load 30 alerts from API
5. Display:
   - **Summary Cards**
     - Total Transactions: 30
     - Total Alerts: 30
     - Critical Alerts: 7
     - High Alerts: 2
   - **Filter Dropdown**
     - Filter by severity
     - Show count: "Showing 30 of 30 transactions"
   - **Transaction List**
     - 30 transaction cards with colored borders
     - Red border = CRITICAL alerts
     - Orange border = HIGH alerts
     - Yellow border = MEDIUM alerts
     - Gray border = No alerts
     - Each card shows:
       - Transaction ID (e.g., TXN001)
       - Date, Customer ID
       - Amount in GBP with direction (↑ in / ↓ out)
       - Country code
       - Narrative text
       - Inline alerts with severity badges

### Step 3: Console Logs (Expected)
Open browser console (F12) and you should see:
```
🔍 TransactionList mounted with matterId: 1
🔍 matterId type: number
🔍 matterId is valid: true
🔍 Fetching transaction data for matter: 1
🔍 API Base URL: https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
🔍 Fetching transactions from: https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transactions
🔍 Fetching alerts from: https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transaction-alerts
📊 Transaction response status: 200
📊 Alert response status: 200
✅ Transactions loaded: 30
✅ Alerts loaded: 30
📝 Sample transaction: {id: "TXN001", ...}
📝 Sample alert: {id: 1, ...}
```

---

## 🔧 Troubleshooting Steps

### Test 1: Direct API Test
1. Open: https://5177-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/test-api.html
2. Click "Test All"
3. Check results:
   - ✅ Health Check: Should pass
   - ✅ Transactions: Should show 30 items
   - ✅ Alerts: Should show 30 items (7 CRITICAL, 2 HIGH, 21 MEDIUM)
   - ✅ Dashboard: Should show stats

**If this fails:**
- CORS issue: Backend not allowing frontend domain
- API down: Backend not responding
- Network issue: Sandbox connectivity problem

### Test 2: Browser Console Check
1. Open Transaction Review tab
2. Open Console (F12)
3. Look for:
   - ❌ **CORS errors** → Backend CORS config issue
   - ❌ **404 errors** → Wrong API endpoint or matter ID
   - ❌ **Invalid matterId** → URL parameter not passed correctly
   - ❌ **Failed to fetch** → Network/connectivity issue

### Test 3: Network Tab Check
1. Open Network tab (F12 → Network)
2. Reload Transaction Review tab
3. Look for API calls:
   - `GET /api/v1/matters/1/transactions` → Should be 200 OK
   - `GET /api/v1/matters/1/transaction-alerts` → Should be 200 OK
4. Click on each request and check:
   - **Request URL:** Should be correct sandbox URL
   - **Status:** Should be 200
   - **Response:** Should contain JSON data

---

## 🐛 Common Issues & Solutions

### Issue 1: "No Transactions Yet" Message
**Symptoms:**
- Page loads but shows empty state
- Console shows 0 transactions loaded

**Possible Causes:**
1. Wrong Matter ID in URL
2. Database has no transactions for this matter
3. API returned empty array

**Solutions:**
1. Check URL: Should be `/matters/1` (not `/matters/REF-2024-001`)
2. Verify database:
   ```bash
   cd /home/user/webapp/backend
   python3 << 'EOF'
   import sqlite3
   conn = sqlite3.connect('./sof_platform.db')
   cursor = conn.cursor()
   cursor.execute("SELECT COUNT(*) FROM transactions WHERE matter_id = 1")
   print(f"Transactions for Matter 1: {cursor.fetchone()[0]}")
   cursor.execute("SELECT COUNT(*) FROM transaction_alerts WHERE matter_id = 1")
   print(f"Alerts for Matter 1: {cursor.fetchone()[0]}")
   conn.close()
   EOF
   ```
3. Test API directly: `curl https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transactions`

### Issue 2: CORS Error
**Symptoms:**
- Console shows: `Access to fetch... has been blocked by CORS policy`
- Network tab shows failed requests

**Solution:**
Backend CORS is configured to allow all origins (`*`). If you see this:
1. Backend might have crashed - check backend logs
2. Backend might be on different URL than expected
3. Restart backend:
   ```bash
   cd /home/user/webapp/backend
   pkill -f uvicorn
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
   ```

### Issue 3: Matter Not Found (404)
**Symptoms:**
- API returns 404
- Console shows "Transaction fetch failed: 404"

**Solution:**
The matter reference in UI (`REF-2024-001`) must map to Matter ID 1 in database:
```bash
cd /home/user/webapp/backend
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./sof_platform.db')
cursor = conn.cursor()
cursor.execute("UPDATE matters SET reference_number = 'REF-2024-001' WHERE id = 1")
conn.commit()
print(f"Updated matter 1 to REF-2024-001")
conn.close()
EOF
```

### Issue 4: Environment Variable Issue
**Symptoms:**
- API calls go to `http://localhost:8000` instead of sandbox URL
- CORS errors in console

**Solution:**
1. Check `.env` file:
   ```bash
   cat /home/user/webapp/frontend/.env
   ```
   Should contain:
   ```
   VITE_API_BASE_URL=https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai
   ```
2. If wrong, update it and restart frontend
3. Hard refresh browser (Ctrl+Shift+R / Cmd+Shift+R)

---

## 📋 Verification Checklist

Run these checks in order:

- [ ] **Backend Health:** `curl https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/health`
  - Should return: `{"status":"healthy","environment":"development"}`

- [ ] **Database Data:** Check transactions exist for Matter 1
  ```bash
  cd /home/user/webapp/backend && python3 -c "import sqlite3; conn=sqlite3.connect('./sof_platform.db'); print(f'Transactions: {conn.execute(\"SELECT COUNT(*) FROM transactions WHERE matter_id=1\").fetchone()[0]}'); print(f'Alerts: {conn.execute(\"SELECT COUNT(*) FROM transaction_alerts WHERE matter_id=1\").fetchone()[0]}')"
  ```
  - Should show: Transactions: 30, Alerts: 30

- [ ] **API Transactions:** `curl https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transactions | jq 'length'`
  - Should return: `30`

- [ ] **API Alerts:** `curl https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transaction-alerts | jq 'length'`
  - Should return: `30`

- [ ] **Frontend Env:** `cat /home/user/webapp/frontend/.env`
  - Should contain: `VITE_API_BASE_URL=https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai`

- [ ] **Frontend Running:** `curl http://localhost:5177 | head -1`
  - Should return: `<!doctype html>`

- [ ] **Test Page:** Open https://5177-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/test-api.html
  - All tests should pass (green)

- [ ] **Browser Console:** Open Transaction Review tab → Check console
  - Should see debug logs starting with 🔍 and ending with ✅

- [ ] **Network Tab:** Check API calls return 200 OK with JSON data

---

## 🎬 Quick Test Script

Run this to test everything at once:

```bash
#!/bin/bash
cd /home/user/webapp

echo "=== Backend Health ==="
curl -s https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/health | jq .

echo -e "\n=== Database Counts ==="
cd backend && python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('./sof_platform.db')
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM transactions WHERE matter_id = 1")
print(f"Transactions: {cursor.fetchone()[0]}")
cursor.execute("SELECT COUNT(*) FROM transaction_alerts WHERE matter_id = 1")
print(f"Alerts: {cursor.fetchone()[0]}")
conn.close()
EOF

echo -e "\n=== API Response Counts ==="
echo -n "Transactions from API: "
curl -s https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transactions | jq 'length'
echo -n "Alerts from API: "
curl -s https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/api/v1/matters/1/transaction-alerts | jq 'length'

echo -e "\n=== Frontend Environment ==="
cd ../frontend && cat .env

echo -e "\n=== All checks complete ==="
```

---

## 📞 What to Report

If the Transaction Review tab still doesn't work, please provide:

1. **Screenshot** of the Transaction Review tab
2. **Browser Console** logs (copy all text)
3. **Network Tab** screenshot showing API calls
4. **Output** of the Quick Test Script above
5. **Error messages** from the debug info panel (if visible)

---

## 🔄 Last Resort: Full Restart

If nothing works, restart everything:

```bash
cd /home/user/webapp

# Kill all processes
pkill -f uvicorn
pkill -f vite

# Restart backend
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &

# Wait for backend to start
sleep 5

# Restart frontend
cd ../frontend
npm run dev -- --host 0.0.0.0 --port 5177 --clearScreen false > /tmp/frontend.log 2>&1 &

# Wait for frontend to start
sleep 5

# Test health
curl https://8000-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/health

echo "All services restarted. Open: https://5177-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai"
```

---

**Last Updated:** 2026-01-11 12:00 UTC  
**Status:** Awaiting user browser console logs to diagnose issue
