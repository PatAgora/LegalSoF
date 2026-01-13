#!/usr/bin/env python3
"""
Multi-Matter Test Loader for SoF Assessment System
Loads all test scenarios into SEPARATE matters so you can view them all in the UI
"""

import requests
import json
import os
import time
from pathlib import Path

# Configuration
BASE_URL = "http://localhost:8001"
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


def reset_assessment(matter_id):
    """Reset the assessment for a specific matter"""
    try:
        response = requests.delete(f"{BASE_URL}/api/v1/matters/{matter_id}/sof-assessment/reset")
        if response.status_code == 200:
            print_success(f"Assessment reset for Matter {matter_id}")
            return True
        else:
            print_warning(f"Reset returned {response.status_code} (may not exist yet)")
            return True  # Continue anyway
    except Exception as e:
        print_warning(f"Reset error (continuing anyway): {str(e)}")
        return True


def upload_file(matter_id, file_path, file_category):
    """Upload a file to the assessment"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            data = {'file_category': file_category}
            
            response = requests.post(
                f"{BASE_URL}/api/v1/matters/{matter_id}/sof-assessment/upload",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                print_success(f"  Uploaded: {os.path.basename(file_path)}")
                return True
            else:
                print_error(f"  Failed to upload {os.path.basename(file_path)}: {response.status_code}")
                print_error(f"  Response: {response.text}")
                return False
    except Exception as e:
        print_error(f"  Error uploading {file_path}: {str(e)}")
        return False


def run_assessment(matter_id):
    """Run the assessment"""
    try:
        response = requests.post(f"{BASE_URL}/api/v1/matters/{matter_id}/sof-assessment/run")
        if response.status_code == 200:
            print_success(f"Assessment completed for Matter {matter_id}")
            return True
        else:
            print_error(f"Assessment failed: {response.status_code}")
            print_error(f"Response: {response.text}")
            return False
    except Exception as e:
        print_error(f"Error running assessment: {str(e)}")
        return False


def get_results(matter_id):
    """Get assessment results"""
    try:
        response = requests.get(f"{BASE_URL}/api/v1/matters/{matter_id}/sof-assessment/results")
        if response.status_code == 200:
            return response.json()
        else:
            print_error(f"Failed to get results: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"Error getting results: {str(e)}")
        return None


def print_claim_summary(claim, index):
    """Print brief claim summary"""
    source_type = claim.get('claim_source', 'Unknown')
    amount = claim.get('expected_amount', 0)
    verified = claim.get('verified', False)
    doc_verified = claim.get('document_verified', False)
    confidence = claim.get('document_verification', {}).get('confidence', 0)
    
    # Determine status symbol
    if verified and doc_verified and confidence >= 99.9:
        status = f"{Colors.GREEN}✅{Colors.END}"
    elif doc_verified and confidence < 99.9:
        status = f"{Colors.YELLOW}⚠️{Colors.END}"
    elif verified and not doc_verified:
        status = f"{Colors.YELLOW}⚠️{Colors.END}"
    else:
        status = f"{Colors.RED}❌{Colors.END}"
    
    return f"{status} {source_type}: £{amount:,.0f} ({confidence:.0f}%)"


def load_scenario(scenario_name, scenario_dir, matter_id, use_matching_bank=True):
    """Load a single scenario into a specific matter"""
    
    print_section(f"Loading: {scenario_name} → Matter {matter_id}")
    
    scenario_path = os.path.join(OUTPUT_DIR, scenario_dir)
    
    # 1. Reset
    print_info("Resetting assessment...")
    if not reset_assessment(matter_id):
        return False
    
    time.sleep(0.3)
    
    # 2. Upload client info
    print_info("Uploading client info...")
    client_info_path = os.path.join(scenario_path, "client_info.json")
    if not upload_file(matter_id, client_info_path, "client_info"):
        return False
    
    time.sleep(0.3)
    
    # 3. Upload bank statement
    print_info("Uploading bank statement...")
    bank_statement = "bank_statement_matching.pdf" if use_matching_bank else "bank_statement_non_matching.pdf"
    bank_statement_path = os.path.join(scenario_path, bank_statement)
    if not upload_file(matter_id, bank_statement_path, "bank_statement"):
        return False
    
    time.sleep(0.3)
    
    # 4. Upload supporting documents
    print_info("Uploading supporting documents...")
    doc_count = 0
    for file in sorted(os.listdir(scenario_path)):
        if file.endswith('.pdf') and not file.startswith('bank_statement'):
            file_path = os.path.join(scenario_path, file)
            if upload_file(matter_id, file_path, "supporting_doc"):
                doc_count += 1
            time.sleep(0.2)
    
    print_success(f"Uploaded {doc_count} supporting documents")
    
    # 5. Run assessment
    print_info("Running assessment...")
    if not run_assessment(matter_id):
        return False
    
    time.sleep(0.5)
    
    # 6. Get and display brief results
    print_info("Retrieving results...")
    results = get_results(matter_id)
    
    if results:
        evidence_matches = results.get('evidence_matches', [])
        print(f"\n  {Colors.BOLD}Results Summary:{Colors.END}")
        for idx, claim in enumerate(evidence_matches):
            print(f"    {print_claim_summary(claim, idx)}")
        
        print(f"\n  {Colors.BOLD}View in UI:{Colors.END}")
        print(f"    {Colors.CYAN}https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/{matter_id}/sof-assessment{Colors.END}")
        
        return True
    else:
        print_error("Failed to retrieve results")
        return False


def main():
    """Main test loader - loads all scenarios into separate matters"""
    
    print_header("SOF ASSESSMENT - LOAD ALL TEST SCENARIOS")
    
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
        print_error(f"Please ensure the backend is running:")
        print_error(f"  cd /home/user/webapp")
        print_error(f"  uvicorn backend.app.main:app --host 0.0.0.0 --port 8001")
        return
    
    # Define scenarios with their matter IDs
    scenarios = [
        {
            "name": "Scenario 1: Perfect Match ✅",
            "dir": "scenario_1_perfect_match",
            "matter_id": 1,
            "use_matching": True,
            "description": "Both claims should be FULLY VERIFIED (100%)"
        },
        {
            "name": "Scenario 2: Missing Solicitor ⚠️",
            "dir": "scenario_2_missing_solicitor",
            "matter_id": 2,
            "use_matching": True,
            "description": "Business Sale REQUIRES REVIEW (~83%), Loan VERIFIED"
        },
        {
            "name": "Scenario 3: Amount Mismatch ❌",
            "dir": "scenario_3_amount_mismatch",
            "matter_id": 3,
            "use_matching": False,
            "description": "Both claims REQUIRE REVIEW (amount differences)"
        },
        {
            "name": "Scenario 4: Date Discrepancy ⚠️",
            "dir": "scenario_4_date_discrepancy",
            "matter_id": 4,
            "use_matching": False,
            "description": "Both claims REQUIRE REVIEW (date differences)"
        },
        {
            "name": "Scenario 5: Wrong Document Type ❌",
            "dir": "scenario_5_wrong_documents",
            "matter_id": 5,
            "use_matching": True,
            "description": "Gift VERIFIED, Savings REQUIRES REVIEW (wrong doc)"
        }
    ]
    
    loaded_scenarios = []
    
    # Load each scenario into its own matter
    for scenario in scenarios:
        print("\n")
        success = load_scenario(
            scenario["name"],
            scenario["dir"],
            scenario["matter_id"],
            scenario["use_matching"]
        )
        
        loaded_scenarios.append({
            "name": scenario["name"],
            "matter_id": scenario["matter_id"],
            "description": scenario["description"],
            "success": success
        })
        
        time.sleep(1)  # Pause between scenarios
    
    # Print final summary
    print_header("ALL SCENARIOS LOADED - VIEW IN FRONTEND")
    
    print(f"\n{Colors.BOLD}All test scenarios have been loaded into separate matters:{Colors.END}\n")
    
    for scenario in loaded_scenarios:
        status = f"{Colors.GREEN}✓ LOADED{Colors.END}" if scenario["success"] else f"{Colors.RED}✗ FAILED{Colors.END}"
        print(f"\n{Colors.BOLD}Matter {scenario['matter_id']}: {scenario['name']}{Colors.END}")
        print(f"  Expected: {scenario['description']}")
        print(f"  Status: {status}")
        print(f"  URL: {Colors.CYAN}https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai/matters/{scenario['matter_id']}/sof-assessment{Colors.END}")
    
    print(f"\n\n{Colors.BOLD}{Colors.GREEN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}ALL SCENARIOS READY TO VIEW IN FRONTEND{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*80}{Colors.END}\n")
    
    print(f"{Colors.BOLD}Navigate to each matter in the UI to see the results:{Colors.END}")
    print(f"  • Matter 1: Perfect Match (100%)")
    print(f"  • Matter 2: Missing Solicitor (~83%)")
    print(f"  • Matter 3: Amount Mismatch")
    print(f"  • Matter 4: Date Discrepancy")
    print(f"  • Matter 5: Wrong Document Type")
    print()
    print(f"{Colors.BOLD}Frontend URL:{Colors.END} {Colors.CYAN}https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai{Colors.END}\n")


if __name__ == "__main__":
    main()
