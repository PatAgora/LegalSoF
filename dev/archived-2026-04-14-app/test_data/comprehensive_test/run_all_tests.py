#!/usr/bin/env python3
"""
Comprehensive Test Runner for SoF Assessment System
Runs all test scenarios and reports results
"""

import requests
import json
import os
import time
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8001"
MATTER_ID = 1
OUTPUT_DIR = "/home/user/webapp/test_data/comprehensive_test"

# ANSI color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")


def print_section(text):
    """Print formatted section"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}--- {text} ---{Colors.END}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")


def reset_assessment():
    """Reset the assessment"""
    try:
        response = requests.delete(f"{BASE_URL}/api/v1/matters/{MATTER_ID}/sof-assessment/reset")
        if response.status_code == 200:
            print_success("Assessment reset successfully")
            return True
        else:
            print_error(f"Failed to reset assessment: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"Error resetting assessment: {str(e)}")
        return False


def upload_file(file_path, file_category):
    """Upload a file to the assessment"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            data = {'file_category': file_category}
            
            response = requests.post(
                f"{BASE_URL}/api/v1/matters/{MATTER_ID}/sof-assessment/upload",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                print_success(f"Uploaded: {os.path.basename(file_path)}")
                return True
            else:
                print_error(f"Failed to upload {os.path.basename(file_path)}: {response.status_code}")
                print_error(f"Response: {response.text}")
                return False
    except Exception as e:
        print_error(f"Error uploading {file_path}: {str(e)}")
        return False


def run_assessment():
    """Run the assessment"""
    try:
        response = requests.post(f"{BASE_URL}/api/v1/matters/{MATTER_ID}/sof-assessment/run")
        if response.status_code == 200:
            print_success("Assessment completed successfully")
            return True
        else:
            print_error(f"Assessment failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error running assessment: {str(e)}")
        return False


def get_results():
    """Get assessment results"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/matters/{MATTER_ID}/sof-assessment/results")
        if response.status_code == 200:
            return response.json()
        else:
            print_error(f"Failed to get results: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"Error getting results: {str(e)}")
        return None


def print_claim_result(claim, index):
    """Print formatted claim result"""
    source_type = claim.get('claim_source', 'Unknown')
    amount = claim.get('expected_amount', 0)
    verified = claim.get('verified', False)
    doc_verified = claim.get('document_verified', False)
    confidence = claim.get('document_verification', {}).get('confidence', 0)
    
    # Determine status
    if verified and doc_verified and confidence >= 99.9:
        status = f"{Colors.GREEN}✅ FULLY VERIFIED (100%){Colors.END}"
    elif doc_verified and confidence < 99.9:
        status = f"{Colors.YELLOW}⚠️ REQUIRES REVIEW ({confidence:.1f}%){Colors.END}"
    elif verified and not doc_verified:
        status = f"{Colors.YELLOW}⚠️ Bank Only - Docs Required{Colors.END}"
    else:
        status = f"{Colors.RED}❌ NOT VERIFIED{Colors.END}"
    
    print(f"\n  {Colors.BOLD}Claim {index + 1}: {source_type} - £{amount:,.2f}{Colors.END}")
    print(f"  Status: {status}")
    
    # Show differences if any
    differences = claim.get('document_verification', {}).get('verification_details', {}).get('differences', [])
    if differences:
        print(f"  {Colors.YELLOW}Differences Found:{Colors.END}")
        for diff in differences:
            field = diff.get('field', 'Unknown')
            issue = diff.get('issue', 'Unknown issue')
            severity = diff.get('severity', 'unknown')
            print(f"    • {field}: {issue} (Severity: {severity})")
    
    # Show checks passed
    checks = claim.get('document_verification', {}).get('verification_details', {}).get('checks_passed', [])
    if checks:
        print(f"  {Colors.GREEN}Checks Passed: {len(checks)}{Colors.END}")
        for check in checks[:3]:  # Show first 3
            print(f"    ✓ {check}")
        if len(checks) > 3:
            print(f"    ... and {len(checks) - 3} more")


def test_scenario(scenario_name, scenario_dir, use_matching_bank_statement=True):
    """Test a single scenario"""
    print_section(f"Testing: {scenario_name}")
    
    scenario_path = os.path.join(OUTPUT_DIR, scenario_dir)
    
    # 1. Reset
    print_info("Step 1: Resetting assessment...")
    if not reset_assessment():
        return False
    
    time.sleep(0.5)
    
    # 2. Upload client info
    print_info("Step 2: Uploading client info...")
    client_info_path = os.path.join(scenario_path, "client_info.json")
    if not upload_file(client_info_path, "client_info"):
        return False
    
    time.sleep(0.5)
    
    # 3. Upload bank statement
    print_info("Step 3: Uploading bank statement...")
    bank_statement = "bank_statement_matching.pdf" if use_matching_bank_statement else "bank_statement_non_matching.pdf"
    bank_statement_path = os.path.join(scenario_path, bank_statement)
    if not upload_file(bank_statement_path, "bank_statement"):
        return False
    
    time.sleep(0.5)
    
    # 4. Upload supporting documents
    print_info("Step 4: Uploading supporting documents...")
    for file in os.listdir(scenario_path):
        if file.endswith('.pdf') and not file.startswith('bank_statement'):
            file_path = os.path.join(scenario_path, file)
            if not upload_file(file_path, "supporting_doc"):
                return False
            time.sleep(0.3)
    
    # 5. Run assessment
    print_info("Step 5: Running assessment...")
    if not run_assessment():
        return False
    
    time.sleep(1)
    
    # 6. Get and display results
    print_info("Step 6: Retrieving results...")
    results = get_results()
    
    if results:
        print_success("Results retrieved successfully")
        
        # Display results
        evidence_matches = results.get('evidence_matches', [])
        print(f"\n  {Colors.BOLD}Total Claims: {len(evidence_matches)}{Colors.END}")
        
        for idx, claim in enumerate(evidence_matches):
            print_claim_result(claim, idx)
        
        return True
    else:
        print_error("Failed to retrieve results")
        return False


def main():
    """Main test runner"""
    print_header("SoF ASSESSMENT COMPREHENSIVE TEST SUITE")
    
    # Check backend is running
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print_success("Backend is running and healthy")
        else:
            print_error("Backend health check failed")
            return
    except Exception as e:
        print_error(f"Cannot connect to backend at {BASE_URL}")
        print_error(f"Please ensure the backend is running: cd /home/user/webapp && uvicorn backend.app.main:app --host 0.0.0.0 --port 8001")
        return
    
    # Test scenarios
    scenarios = [
        {
            "name": "Scenario 1: Perfect Match ✅",
            "dir": "scenario_1_perfect_match",
            "use_matching": True,
            "expected": "All claims FULLY VERIFIED (100%)"
        },
        {
            "name": "Scenario 2: Missing Solicitor ⚠️",
            "dir": "scenario_2_missing_solicitor",
            "use_matching": True,
            "expected": "Business Sale REQUIRES REVIEW (~83%), Loan VERIFIED (100%)"
        },
        {
            "name": "Scenario 3: Amount Mismatch ❌",
            "dir": "scenario_3_amount_mismatch",
            "use_matching": False,
            "expected": "Both claims REQUIRE REVIEW (amount differences)"
        },
        {
            "name": "Scenario 4: Date Discrepancy ⚠️",
            "dir": "scenario_4_date_discrepancy",
            "use_matching": False,
            "expected": "Both claims REQUIRE REVIEW (date differences)"
        },
        {
            "name": "Scenario 5: Wrong Document Type ❌",
            "dir": "scenario_5_wrong_documents",
            "use_matching": True,
            "expected": "Gift VERIFIED (100%), Savings REQUIRES REVIEW (wrong doc type)"
        }
    ]
    
    results_summary = []
    
    for scenario in scenarios:
        print("\n")
        success = test_scenario(
            scenario["name"],
            scenario["dir"],
            scenario["use_matching"]
        )
        
        results_summary.append({
            "name": scenario["name"],
            "expected": scenario["expected"],
            "success": success
        })
        
        time.sleep(2)  # Pause between scenarios
    
    # Print summary
    print_header("TEST RESULTS SUMMARY")
    
    for result in results_summary:
        status = f"{Colors.GREEN}PASSED{Colors.END}" if result["success"] else f"{Colors.RED}FAILED{Colors.END}"
        print(f"\n{Colors.BOLD}{result['name']}{Colors.END}")
        print(f"  Expected: {result['expected']}")
        print(f"  Status: {status}")
    
    # Print next steps
    print_header("NEXT STEPS")
    print(f"""
{Colors.BOLD}1. Review Results in Frontend:{Colors.END}
   Open: {Colors.CYAN}https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai{Colors.END}
   
{Colors.BOLD}2. Test Manual Acceptance Workflow:{Colors.END}
   For claims requiring review, test the "Accept Differences" button
   
{Colors.BOLD}3. Verify PDF Extraction:{Colors.END}
   Check that all transaction data comes from PDF bank statements
   
{Colors.BOLD}4. Test Individual Scenarios:{Colors.END}
   cd /home/user/webapp/test_data/comprehensive_test/[scenario_dir]
   Follow steps in README.md
    """)


if __name__ == "__main__":
    main()
