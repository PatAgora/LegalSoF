# Demo Test Data: HSBC Current Account Earlier Statements

This file (`hsbc_current_earlier_statements.csv`) is designed for demonstrating how the system handles **Statement Gaps** and resolves them when additional bank statements are provided.

## Demo Scenario

### Before (Statement Gap Shown)
1. Upload only the Santander Savings statement
2. Run the SoF Assessment
3. The Funds Lineage will show **Statement Gaps** with orange highlighting:
   - "Need HSBC Current ****5678 statements from before 2023-06-15"
   - Standing orders from HSBC cannot be traced further

### After (Gap Resolved)
1. Upload this file (`hsbc_current_earlier_statements.csv`) as additional documentation
2. Re-run the SoF Assessment or refresh the Funds Lineage
3. The system will now:
   - Match the standing orders from HSBC to Santander
   - Trace the funds back to **SALARY - ACME CORP LTD** entries
   - Show **External Origin (Verified)** for salary payments
   - Remove the Statement Gap warnings
   - Update confidence scores

## File Contents

This CSV contains HSBC Current ****5678 transactions from **September 2021 to June 2022**, including:

| Type | Description | Amount |
|------|-------------|--------|
| Monthly Salary | SALARY - ACME CORP LTD | £4,500 |
| Christmas Bonus | CHRISTMAS BONUS - ACME CORP | £2,000 |
| Standing Orders | TO SANTANDER ****3456 | -£3,000/month |
| Mortgage | MORTGAGE PAYMENT | -£1,200/month |
| Bills | Various utilities | Variable |

## Expected Outcome After Upload

1. **Funds Lineage Tree** will show:
   - Green dots (✓ Verified) for salary entries
   - Blue dots (↔ Matched) for standing orders between accounts
   - No more orange "Statement Gap" items

2. **Assessment Summary** will show:
   - Higher traced percentage (approaching 100%)
   - Verified external income source: "Employment Income"
   - Questions for Clients section updated (no longer asking for earlier statements)

## Demo Script

1. "Here we can see the system has identified a gap in our statement coverage..."
2. "The standing orders into the savings account come from HSBC, but we don't have those statements yet..."
3. "Let me upload the earlier HSBC statements..."
4. [Upload file]
5. "Now the system can trace the funds back to their source - regular salary payments from ACME Corp"
6. "Notice how the Statement Gaps are now resolved and shown as Verified External Origins"
