import requests
import json

BASE_URL = "http://localhost:8000"

print("🧪 Testing Frontend Data Flow\n")

# Step 1: Login
print("1. Testing Login...")
login_resp = requests.post(f'{BASE_URL}/api/v1/auth/login', json={
    'email': 'admin@example.com',
    'password': 'admin123'
})
if login_resp.status_code == 200:
    token = login_resp.json()['access_token']
    print(f"   ✅ Login successful - Token: {token[:20]}...")
else:
    print(f"   ❌ Login failed: {login_resp.status_code}")
    exit(1)

headers = {'Authorization': f'Bearer {token}'}

# Step 2: Test Alerts Endpoint
print("\n2. Testing Transaction Alerts...")
alerts_resp = requests.get(f'{BASE_URL}/api/v1/matters/1/transaction-alerts', headers=headers)
if alerts_resp.status_code == 200:
    alerts = alerts_resp.json()
    print(f"   ✅ Alerts retrieved: {len(alerts)} total")
    
    # Count by severity
    severity_counts = {}
    for alert in alerts:
        sev = alert.get('severity', 'UNKNOWN')
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    print(f"   📊 Breakdown:")
    for sev, count in sorted(severity_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"      {sev}: {count}")
    
    # Show sample alert
    if alerts:
        sample = alerts[0]
        print(f"\n   📝 Sample Alert:")
        print(f"      ID: {sample.get('id')}")
        print(f"      Transaction: {sample.get('txn_id')}")
        print(f"      Severity: {sample.get('severity')}")
        print(f"      Amount: £{sample.get('amount', 0):,.2f}")
        print(f"      Country: {sample.get('country_iso2')}")
        print(f"      Reasons: {sample.get('reasons', [])[:2]}")
else:
    print(f"   ❌ Failed: {alerts_resp.status_code} - {alerts_resp.text}")

# Step 3: Test Dashboard Endpoint
print("\n3. Testing Dashboard...")
dashboard_resp = requests.get(f'{BASE_URL}/api/v1/matters/1/transaction-dashboard', headers=headers)
if dashboard_resp.status_code == 200:
    data = dashboard_resp.json()
    stats = data.get('stats', {})
    print(f"   ✅ Dashboard retrieved")
    print(f"   📊 Stats:")
    print(f"      Total Transactions: {stats.get('total_transactions', 0)}")
    print(f"      Total Alerts: {stats.get('total_alerts', 0)}")
    print(f"      Critical Alerts: {stats.get('critical_alerts', 0)}")
    print(f"      High Alerts: {stats.get('high_alerts', 0)}")
    print(f"      Money In: £{stats.get('total_in', 0):,.2f}")
    print(f"      Money Out: £{stats.get('total_out', 0):,.2f}")
    print(f"      Alert Rate: {stats.get('alert_rate', 0):.1f}%")
else:
    print(f"   ❌ Failed: {dashboard_resp.status_code} - {dashboard_resp.text}")

# Step 4: Test without auth (simulate frontend without login)
print("\n4. Testing Without Authentication (Frontend Scenario)...")
no_auth_resp = requests.get(f'{BASE_URL}/api/v1/matters/1/transaction-alerts')
print(f"   Status: {no_auth_resp.status_code}")
if no_auth_resp.status_code == 403:
    print(f"   ⚠️  Auth required - This is why frontend shows no data!")
    print(f"   💡 Solution: User must login to get token in localStorage")
elif no_auth_resp.status_code == 200:
    print(f"   ⚠️  Auth NOT required - Endpoints are open!")

print("\n" + "="*60)
print("🎯 DIAGNOSIS:")
print("="*60)
if no_auth_resp.status_code == 403:
    print("Frontend components need valid JWT token from localStorage.")
    print("User MUST login at frontend first to see Transaction Review data.")
    print("\nTo fix:")
    print("1. Open frontend URL")
    print("2. Login with admin@example.com / admin123")
    print("3. Token will be stored in localStorage")
    print("4. Then navigate to Transaction Review tab")
else:
    print("Backend endpoints are accessible without auth.")
    print("Frontend should be showing data. Check browser console.")

print("\n✅ Test complete!")
