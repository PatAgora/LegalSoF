#!/usr/bin/env python3
"""
Debug script to check account identification in SoF storage
Run this on the server: python3 debug_accounts.py
"""
import json
from pathlib import Path

STORAGE_FILE = Path("/tmp/sof_assessment_storage.json")

print("=" * 70)
print("ACCOUNT IDENTIFICATION DEBUG")
print("=" * 70)

if not STORAGE_FILE.exists():
    print("❌ Storage file not found at /tmp/sof_assessment_storage.json")
    print("   Have you uploaded any bank statements yet?")
    exit(1)

with open(STORAGE_FILE, 'r') as f:
    storage = json.load(f)

print(f"\n📁 Found {len(storage)} matter(s) in storage\n")

for matter_id, data in storage.items():
    print(f"\n{'='*50}")
    print(f"MATTER: {matter_id}")
    print(f"{'='*50}")
    
    bank_statements = data.get('bank_statements', [])
    print(f"Total transactions: {len(bank_statements)}")
    
    if not bank_statements:
        print("   ❌ No bank statements uploaded")
        continue
    
    # Group by account
    accounts = {}
    for txn in bank_statements:
        acc_id = txn.get('account_id', 'MISSING')
        acc_type = txn.get('account_type', 'MISSING')
        bank = txn.get('bank_name', 'MISSING')
        sort_code = txn.get('sort_code', 'MISSING')
        
        key = f"{bank} {acc_type} ({acc_id})"
        if key not in accounts:
            accounts[key] = {
                'account_id': acc_id,
                'account_type': acc_type,
                'bank_name': bank,
                'sort_code': sort_code,
                'count': 0,
                'sample_txn': txn
            }
        accounts[key]['count'] += 1
    
    print(f"\n🏦 Unique accounts found: {len(accounts)}")
    
    for acc_name, info in accounts.items():
        print(f"\n   📋 {acc_name}")
        print(f"      Transactions: {info['count']}")
        print(f"      account_id: {info['account_id']}")
        print(f"      account_type: {info['account_type']}")
        print(f"      bank_name: {info['bank_name']}")
        print(f"      sort_code: {info['sort_code']}")
        
        # Show sample transaction
        sample = info['sample_txn']
        print(f"      Sample: {sample.get('date')} | £{sample.get('amount')} | {sample.get('description', '')[:40]}")
    
    # Check for missing account info
    missing_count = sum(1 for t in bank_statements if not t.get('account_id'))
    if missing_count > 0:
        print(f"\n   ⚠️ WARNING: {missing_count} transactions missing account_id!")
    
    # Show first 3 raw transactions for debugging
    print(f"\n   📝 First 3 raw transactions:")
    for i, txn in enumerate(bank_statements[:3]):
        print(f"      {i+1}. {json.dumps({k: txn.get(k) for k in ['account_id', 'account_type', 'bank_name', 'date', 'amount']}, indent=None)}")

print("\n" + "=" * 70)
print("END DEBUG")
print("=" * 70)
