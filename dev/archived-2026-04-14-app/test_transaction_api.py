#!/usr/bin/env python3
"""
Transaction Review API Test Script
Tests the complete Transaction Review integration
"""
import os
import sys
import requests
import json
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
MATTER_ID = 1  # Test matter ID

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    print("ERROR: Set ADMIN_PASSWORD environment variable before running tests.")
    sys.exit(1)

# Authentication token (will be set after login)
AUTH_TOKEN = None

def login():
    """Authenticate and get token"""
    global AUTH_TOKEN
    print("\n🔐 Authenticating...")

    url = f"{BASE_URL}/auth/login"
    data = {
        "email": "admin@example.com",
        "password": ADMIN_PASSWORD
    }
    
    try:
        response = requests.post(url, json=data)
        
        if response.status_code == 200:
            result = response.json()
            AUTH_TOKEN = result.get('access_token')
            print(f"✅ Authentication successful")
            return True
        else:
            print(f"❌ Authentication failed: {response.status_code}")
            print(f"   Error: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Login request failed: {e}")
        return False

def get_headers():
    """Get authorization headers"""
    if AUTH_TOKEN:
        return {"Authorization": f"Bearer {AUTH_TOKEN}"}
    return {}

def test_upload_transactions():
    """Test uploading transactions CSV"""
    print("\n🧪 Testing Transaction Upload...")
    
    csv_file = Path("test_transactions.csv")
    if not csv_file.exists():
        print(f"❌ Test CSV file not found: {csv_file}")
        return False
    
    url = f"{BASE_URL}/matters/{MATTER_ID}/transactions/upload"
    
    with open(csv_file, 'rb') as f:
        files = {'file': ('test_transactions.csv', f, 'text/csv')}
        data = {'customer_id': 'CUST001'}
        
        try:
            response = requests.post(url, files=files, data=data, headers=get_headers())
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Upload successful!")
                print(f"   Transactions created: {result.get('transactions_created', 0)}")
                print(f"   Alerts generated: {result.get('alerts_generated', 0)}")
                return True
            else:
                print(f"❌ Upload failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return False

def test_get_transactions():
    """Test retrieving transactions"""
    print("\n🧪 Testing Get Transactions...")
    
    url = f"{BASE_URL}/matters/{MATTER_ID}/transactions"
    
    try:
        response = requests.get(url, params={'customer_id': 'CUST001'}, headers=get_headers())
        
        if response.status_code == 200:
            transactions = response.json()
            print(f"✅ Retrieved {len(transactions)} transactions")
            if transactions:
                print(f"   First transaction: {transactions[0].get('id')} - £{transactions[0].get('amount')}")
            return True
        else:
            print(f"❌ Failed to get transactions: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_get_alerts():
    """Test retrieving transaction alerts"""
    print("\n🧪 Testing Get Transaction Alerts...")
    
    url = f"{BASE_URL}/matters/{MATTER_ID}/transaction-alerts"
    
    try:
        response = requests.get(url, params={'customer_id': 'CUST001'}, headers=get_headers())
        
        if response.status_code == 200:
            alerts = response.json()
            print(f"✅ Retrieved {len(alerts)} alerts")
            
            # Count by severity
            severity_counts = {}
            for alert in alerts:
                severity = alert.get('severity', 'UNKNOWN')
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            for severity, count in sorted(severity_counts.items()):
                print(f"   {severity}: {count}")
            
            # Show first few alerts
            if alerts:
                print(f"\n   Sample Alerts:")
                for alert in alerts[:3]:
                    print(f"   - {alert.get('severity')}: {', '.join(alert.get('reasons', []))}")
            
            return True
        else:
            print(f"❌ Failed to get alerts: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_dashboard():
    """Test transaction dashboard endpoint"""
    print("\n🧪 Testing Transaction Dashboard...")
    
    url = f"{BASE_URL}/matters/{MATTER_ID}/transaction-dashboard"
    
    try:
        response = requests.get(url, params={'customer_id': 'CUST001'}, headers=get_headers())
        
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Dashboard data retrieved")
            print(f"   Total Transactions: {stats.get('total_transactions', 0)}")
            print(f"   Total Alerts: {stats.get('total_alerts', 0)}")
            print(f"   Critical Alerts: {stats.get('critical_alerts', 0)}")
            print(f"   High Alerts: {stats.get('high_alerts', 0)}")
            print(f"   Total In: £{stats.get('total_in', 0):,.2f}")
            print(f"   Total Out: £{stats.get('total_out', 0):,.2f}")
            print(f"   High Risk Value: £{stats.get('high_risk_value', 0):,.2f}")
            print(f"   Alert Rate: {stats.get('alert_rate', 0):.1f}%")
            return True
        else:
            print(f"❌ Failed to get dashboard: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_get_config():
    """Test getting transaction config"""
    print("\n🧪 Testing Get Transaction Config...")
    
    url = f"{BASE_URL}/transaction-config"
    
    try:
        response = requests.get(url, headers=get_headers())
        
        if response.status_code == 200:
            config = response.json()
            print(f"✅ Config retrieved: {len(config)} settings")
            
            # Show key settings
            key_settings = ['high_risk_min_amount', 'cash_deposit_threshold', 'cash_withdrawal_threshold']
            for key in key_settings:
                if key in config:
                    print(f"   {key}: {config[key]}")
            
            return True
        else:
            print(f"❌ Failed to get config: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("TRANSACTION REVIEW API TEST SUITE")
    print("=" * 60)
    
    # Authenticate first
    if not login():
        print("\n❌ Authentication failed. Cannot run tests.")
        return
    
    tests = [
        ("Upload Transactions", test_upload_transactions),
        ("Get Transactions", test_get_transactions),
        ("Get Alerts", test_get_alerts),
        ("Dashboard Stats", test_dashboard),
        ("Get Config", test_get_config),
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\n{'✅' if passed == total else '⚠️'} {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Transaction Review integration is working correctly.")
    else:
        print("\n⚠️ Some tests failed. Please check the error messages above.")

if __name__ == "__main__":
    main()
