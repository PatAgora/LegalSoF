#!/bin/bash
# Quick test runner for individual scenarios

SCENARIO_DIR="$1"

if [ -z "$SCENARIO_DIR" ]; then
    echo "Usage: ./test_scenario.sh <scenario_directory>"
    echo ""
    echo "Available scenarios:"
    echo "  scenario_1_perfect_match"
    echo "  scenario_2_missing_solicitor"
    echo "  scenario_3_amount_mismatch"
    echo "  scenario_4_date_discrepancy"
    echo "  scenario_5_wrong_documents"
    exit 1
fi

if [ ! -d "$SCENARIO_DIR" ]; then
    echo "Error: Directory $SCENARIO_DIR does not exist"
    exit 1
fi

echo "Testing scenario: $SCENARIO_DIR"
echo "================================"
echo ""

# Step 1: Reset
echo "Step 1: Resetting assessment..."
curl -s -X DELETE http://localhost:8001/api/v1/matters/1/sof-assessment/reset
echo ""
sleep 1

# Step 2: Upload client info
echo ""
echo "Step 2: Uploading client info..."
curl -s -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@$SCENARIO_DIR/client_info.json" \
  -F "file_category=client_info"
echo ""
sleep 1

# Step 3: Upload bank statement (use matching by default, unless specified)
BANK_STATEMENT="bank_statement_matching.pdf"
if [ "$2" == "non-matching" ]; then
    BANK_STATEMENT="bank_statement_non_matching.pdf"
fi

echo ""
echo "Step 3: Uploading bank statement ($BANK_STATEMENT)..."
curl -s -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
  -F "file=@$SCENARIO_DIR/$BANK_STATEMENT" \
  -F "file_category=bank_statement"
echo ""
sleep 1

# Step 4: Upload all supporting documents
echo ""
echo "Step 4: Uploading supporting documents..."
for doc in "$SCENARIO_DIR"/*.pdf; do
    filename=$(basename "$doc")
    if [[ ! "$filename" =~ ^bank_statement ]]; then
        echo "  Uploading: $filename"
        curl -s -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/upload \
          -F "file=@$doc" \
          -F "file_category=supporting_doc"
        echo ""
        sleep 0.5
    fi
done

# Step 5: Run assessment
echo ""
echo "Step 5: Running assessment..."
curl -s -X POST http://localhost:8001/api/v1/matters/1/sof-assessment/run
echo ""
sleep 2

# Step 6: Get results
echo ""
echo "Step 6: Retrieving results..."
curl -s http://localhost:8001/api/v1/matters/1/sof-assessment/results | python3 -m json.tool

echo ""
echo "================================"
echo "Test complete!"
echo ""
echo "View detailed results in the frontend:"
echo "https://5174-iuy1pmhbm169wep8nogbw-b32ec7bb.sandbox.novita.ai"
