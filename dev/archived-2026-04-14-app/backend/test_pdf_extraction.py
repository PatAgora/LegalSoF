#!/usr/bin/env python3
"""
Test PDF document extraction and verification
"""
import sys
import json

# Test PDF extraction
print("=" * 60)
print("Testing PDF Document Extraction")
print("=" * 60)

from app.services.pdf_extractor import pdf_extractor

# Test probate PDF
print("\n### Testing Probate Grant PDF ###\n")
with open('test_data/inheritance_proof_probate_grant.pdf', 'rb') as f:
    content = f.read()

result = pdf_extractor.extract_document_data(content, 'Probate grant')
print(f"Document Type: {result['document_type']}")
print(f"Confidence: {result['confidence']}")
print(f"Extracted Data:")
for key, value in result['extracted_data'].items():
    print(f"  {key}: {value}")

# Test property PDF
print("\n### Testing Property Completion Statement PDF ###\n")
with open('test_data/property_completion_statement.pdf', 'rb') as f:
    content = f.read()

result = pdf_extractor.extract_document_data(content, 'completion statement')
print(f"Document Type: {result['document_type']}")
print(f"Confidence: {result['confidence']}")
print(f"Extracted Data:")
for key, value in result['extracted_data'].items():
    print(f"  {key}: {value}")

# Test document verification
print("\n" + "=" * 60)
print("Testing Document Verification")
print("=" * 60)

from app.services.document_verifier import document_verifier

# Sample claims
claims = [
    {
        "claim_id": 1,
        "source_type": "Inheritance from Estate",
        "expected_amount": 250000.0,
        "confidence": 0.9
    },
    {
        "claim_id": 2,
        "source_type": "Property Sale Proceeds",
        "expected_amount": 300000.0,
        "confidence": 0.9
    }
]

# Sample bank statements
bank_statements = [
    {
        "date": "2023-05-15",
        "amount": 250000.0,
        "direction": "credit",
        "description": "Estate Distribution - Smith & Partners Solicitors",
        "counterparty": "Smith & Partners Solicitors"
    },
    {
        "date": "2023-07-01",
        "amount": 300000.82,
        "direction": "credit",
        "description": "Property Sale Proceeds - 45 Oak Street London",
        "counterparty": "Taylor & Brown Solicitors"
    }
]

# Sample supporting docs (with extracted data)
supporting_docs = []

# Add probate document
with open('test_data/inheritance_proof_probate_grant.pdf', 'rb') as f:
    content = f.read()
probate_result = pdf_extractor.extract_document_data(content, 'Probate grant')
supporting_docs.append({
    "document_type": "Probate grant",
    "extracted_data": probate_result['extracted_data'],
    "extraction_confidence": probate_result['confidence']
})

# Add property document
with open('test_data/property_completion_statement.pdf', 'rb') as f:
    content = f.read()
property_result = pdf_extractor.extract_document_data(content, 'completion statement')
supporting_docs.append({
    "document_type": "completion statement",
    "extracted_data": property_result['extracted_data'],
    "extraction_confidence": property_result['confidence']
})

print(f"\nClaims: {len(claims)}")
print(f"Bank Statements: {len(bank_statements)}")
print(f"Supporting Documents: {len(supporting_docs)}")

verification_result = document_verifier.verify_documents_against_claims(
    claims=claims,
    supporting_docs=supporting_docs,
    bank_statements=bank_statements
)

print(f"\n### Verification Results ###\n")
print(f"Overall Verification Rate: {verification_result['overall_verification_rate']*100:.0f}%")
print(f"\nVerifications:")
for ver in verification_result['verifications']:
    print(f"\n  Claim {ver['claim_id']}: {ver['claim_source']}")
    print(f"    Amount: £{ver['claim_amount']:,.2f}")
    print(f"    Verified: {'✅ YES' if ver['verified'] else '❌ NO'}")
    print(f"    Confidence: {ver['confidence']*100:.0f}%")
    if ver.get('issues'):
        print(f"    Issues: {', '.join(ver['issues'])}")
    if ver.get('verification_details'):
        details = ver['verification_details']
        if details.get('checks_passed'):
            print(f"    Checks Passed:")
            for check in details['checks_passed'][:3]:
                print(f"      - {check}")

print(f"\nMissing Documents: {verification_result['missing_documents']}")

print("\n" + "=" * 60)
print("Test Complete")
print("=" * 60)
