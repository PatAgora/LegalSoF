#!/usr/bin/env python3
"""
Test script to verify PDF extraction and verification works end-to-end
WITHOUT any resets
"""

import requests
import json

API_BASE = "http://localhost:8001/api/v1"
MATTER_ID = 1

print("=" * 60)
print("END-TO-END ASSESSMENT TEST (NO RESETS)")
print("=" * 60)

# Step 1: Upload client info
print("\n1. Uploading client_info.json...")
with open('../test_data/client_info.json', 'rb') as f:
    files = {'file': ('client_info.json', f, 'application/json')}
    data = {'file_category': 'client_info'}
    r = requests.post(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/upload", files=files, data=data)
    print(f"   Status: {r.status_code}")

# Step 2: Upload bank statement
print("\n2. Uploading bank_statement.csv...")
with open('../test_data/example_bank_statement_comprehensive.csv', 'rb') as f:
    files = {'file': ('bank_statement.csv', f, 'text/csv')}
    data = {'file_category': 'bank_statement'}
    r = requests.post(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/upload", files=files, data=data)
    print(f"   Status: {r.status_code}")

# Step 3: Check status
print("\n3. Checking status before PDFs...")
r = requests.get(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/status")
status = r.json()
print(f"   Client info: {status['files_summary']['client_info']}")
print(f"   Bank statements: {status['files_summary']['bank_statements_count']}")
print(f"   Supporting docs: {status['files_summary']['supporting_docs_count']}")

# Step 4: Run initial assessment
print("\n4. Running initial assessment (expecting INSUFFICIENT)...")
r = requests.post(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/run")
result1 = r.json()
print(f"   Status: {r.status_code}")
assessment = result1.get('assessment', {})
decision = assessment.get('overall_decision', assessment.get('decision', 'UNKNOWN'))
print(f"   Decision: {decision}")

# Step 5: Upload PDF 1
print("\n5. Uploading inheritance_proof_probate_grant.pdf...")
with open('test_data/inheritance_proof_probate_grant.pdf', 'rb') as f:
    files = {'file': ('probate.pdf', f, 'application/pdf')}
    data = {'file_category': 'supporting_doc'}
    r = requests.post(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/upload", files=files, data=data)
    print(f"   Status: {r.status_code}")

# Step 6: Upload PDF 2
print("\n6. Uploading property_completion_statement.pdf...")
with open('test_data/property_completion_statement.pdf', 'rb') as f:
    files = {'file': ('property.pdf', f, 'application/pdf')}
    data = {'file_category': 'supporting_doc'}
    r = requests.post(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/upload", files=files, data=data)
    print(f"   Status: {r.status_code}")

# Step 7: Check status after PDFs
print("\n7. Checking status after PDFs...")
r = requests.get(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/status")
status = r.json()
print(f"   Client info: {status['files_summary']['client_info']}")
print(f"   Bank statements: {status['files_summary']['bank_statements_count']}")
print(f"   Supporting docs: {status['files_summary']['supporting_docs_count']}")

# Step 8: Run SECOND assessment (should include PDFs)
print("\n8. Running SECOND assessment (expecting VERIFIED)...")
r = requests.post(f"{API_BASE}/matters/{MATTER_ID}/sof-assessment/run")
result2 = r.json()
print(f"   Status: {r.status_code}")
assessment = result2.get('assessment', {})
decision = assessment.get('overall_decision', assessment.get('decision', 'UNKNOWN'))
print(f"   Decision: {decision}")

# Step 9: Check verification details
print("\n9. Full Assessment Response:")
print(json.dumps(result2, indent=2))

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
