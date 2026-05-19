"""
Initialize Transaction Review tables in the database.
This creates the necessary schema for transaction monitoring and AML checks.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.db.base import Base
from app.models.transaction import Transaction, TransactionAlert, CountryRisk, KYCProfile, TransactionConfig
from app.models import Matter, User


def init_transaction_tables():
    """Create transaction review tables and seed reference data"""
    # Use synchronous PostgreSQL for initialization
    db_url = str(settings.DATABASE_URL).replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(db_url)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    print("✅ Transaction tables created successfully")
    
    # Seed reference data
    seed_country_risk_data(engine)
    seed_transaction_config(engine)
    
    print("✅ Transaction Review initialization complete")


def seed_country_risk_data(engine):
    """Seed country risk reference data"""
    with engine.connect() as conn:
        # Check if data already exists
        result = conn.execute(text("SELECT COUNT(*) FROM ref_country_risk"))
        count = result.scalar()
        
        if count > 0:
            print(f"ℹ️  Country risk data already exists ({count} countries)")
            return
        
        # High-risk and prohibited countries (example data - should be maintained by compliance team)
        countries = [
            # Prohibited countries (UK sanctions)
            ('IR', 'PROHIBITED', 100, True),  # Iran
            ('KP', 'PROHIBITED', 100, True),  # North Korea
            ('SY', 'PROHIBITED', 100, True),  # Syria
            ('RU', 'PROHIBITED', 100, True),  # Russia (sanctions)
            ('BY', 'PROHIBITED', 100, True),  # Belarus
            
            # High-risk countries (FATF lists, enhanced due diligence)
            ('AF', 'HIGH', 80, False),  # Afghanistan
            ('MM', 'HIGH', 80, False),  # Myanmar
            ('YE', 'HIGH', 80, False),  # Yemen
            ('SS', 'HIGH', 80, False),  # South Sudan
            ('SD', 'HIGH', 80, False),  # Sudan
            ('SO', 'HIGH', 80, False),  # Somalia
            ('LY', 'HIGH', 80, False),  # Libya
            ('HT', 'HIGH', 80, False),  # Haiti
            ('ML', 'HIGH', 80, False),  # Mali
            ('NG', 'HIGH', 80, False),  # Nigeria
            ('PK', 'HIGH', 80, False),  # Pakistan
            ('VE', 'HIGH', 80, False),  # Venezuela
            ('ZW', 'HIGH', 80, False),  # Zimbabwe
            
            # High-risk 3rd countries (money laundering risks)
            ('PA', 'HIGH_3RD', 60, False),  # Panama
            ('BZ', 'HIGH_3RD', 60, False),  # Belize
            ('VU', 'HIGH_3RD', 60, False),  # Vanuatu
            ('BS', 'HIGH_3RD', 60, False),  # Bahamas
            ('BM', 'HIGH_3RD', 60, False),  # Bermuda
            ('KY', 'HIGH_3RD', 60, False),  # Cayman Islands
            ('VG', 'HIGH_3RD', 60, False),  # British Virgin Islands
            
            # Medium-risk (emerging markets, less regulation)
            ('CN', 'MEDIUM', 40, False),  # China
            ('IN', 'MEDIUM', 40, False),  # India
            ('BR', 'MEDIUM', 40, False),  # Brazil
            ('ZA', 'MEDIUM', 40, False),  # South Africa
            ('MX', 'MEDIUM', 40, False),  # Mexico
            ('TR', 'MEDIUM', 40, False),  # Turkey
            ('EG', 'MEDIUM', 40, False),  # Egypt
            ('ID', 'MEDIUM', 40, False),  # Indonesia
            ('TH', 'MEDIUM', 40, False),  # Thailand
            ('AE', 'MEDIUM', 40, False),  # UAE
            
            # Low-risk (UK, EU, other developed countries)
            ('GB', 'LOW', 10, False),  # United Kingdom
            ('US', 'LOW', 10, False),  # United States
            ('DE', 'LOW', 10, False),  # Germany
            ('FR', 'LOW', 10, False),  # France
            ('IT', 'LOW', 10, False),  # Italy
            ('ES', 'LOW', 10, False),  # Spain
            ('NL', 'LOW', 10, False),  # Netherlands
            ('CH', 'LOW', 10, False),  # Switzerland
            ('SE', 'LOW', 10, False),  # Sweden
            ('NO', 'LOW', 10, False),  # Norway
            ('DK', 'LOW', 10, False),  # Denmark
            ('FI', 'LOW', 10, False),  # Finland
            ('IE', 'LOW', 10, False),  # Ireland
            ('BE', 'LOW', 10, False),  # Belgium
            ('AT', 'LOW', 10, False),  # Austria
            ('LU', 'LOW', 10, False),  # Luxembourg
            ('AU', 'LOW', 10, False),  # Australia
            ('NZ', 'LOW', 10, False),  # New Zealand
            ('CA', 'LOW', 10, False),  # Canada
            ('JP', 'LOW', 10, False),  # Japan
            ('SG', 'LOW', 10, False),  # Singapore
            ('HK', 'LOW', 10, False),  # Hong Kong
        ]
        
        for iso2, risk_level, score, prohibited in countries:
            conn.execute(
                text("""
                    INSERT INTO ref_country_risk (iso2, risk_level, score, prohibited)
                    VALUES (:iso2, :risk_level, :score, :prohibited)
                """),
                {"iso2": iso2, "risk_level": risk_level, "score": score, "prohibited": prohibited}
            )
        
        conn.commit()
        print(f"✅ Seeded {len(countries)} country risk records")


def seed_transaction_config(engine):
    """Seed the platform configuration catalogue.

    The transaction_config table holds every operator-tunable threshold,
    risk-appetite setting and rule toggle across the SoF, Document
    Verification, Transaction Review and Funds Lineage sections of the
    platform. Settings are namespaced by prefix:

        sof_*  → Source of Funds Analysis
        dv_*   → Document Verification
        tr_*   → Transaction Review (existing rule_*/cfg_* kept for
                  backwards compatibility with the transaction
                  monitoring service)
        fl_*   → Funds Lineage

    Idempotent — on every boot, missing rows are inserted with their
    defaults but existing rows are left untouched so an operator's
    saved values are preserved across deploys.
    """
    with engine.connect() as conn:
        # The full catalogue. Each row: (key, default_value, type,
        # description). value_type is "string" | "int" | "float" |
        # "bool" | "json". Description is shown to the operator in the
        # Configuration page so write it as user-facing copy.
        configs = [
            # ── Module master switches ────────────────────────────────
            # Each toggle controls whether the corresponding module
            # runs at all. When OFF, the module is skipped and its
            # outputs come back empty so the operator can disable a
            # whole section of the platform if it isn't applicable.
            ('sof_enabled', 'true', 'bool',
             'Turn the Source of Funds Analysis on or off. When OFF, the platform will not try to match the client\'s declared sources of funds against their bank statements and supporting documents — assessments will return as Incomplete.'),
            ('dv_enabled', 'true', 'bool',
             'Turn the Document Verification on or off. When OFF, uploaded documents are kept on file but the platform will not run any forgery / tampering checks on them. Only turn this off if you have a separate process for verifying document authenticity.'),
            ('tr_enabled', 'true', 'bool',
             'Turn the Transaction Review on or off. When OFF, the platform will not raise AML alerts from the client\'s bank transactions (e.g. cash deposits, high-risk countries, velocity). Use this only if a separate transaction-monitoring system is in place.'),
            ('fl_enabled', 'true', 'bool',
             'Turn the Funds Lineage tracer on or off. When ON, after each assessment the platform automatically walks backwards through the client\'s bank transfers to prove where their money originally came from. When OFF, this trace is not run automatically — reviewers can still run it manually from the Funds Lineage tab.'),

            # ── Source of Funds Analysis ──────────────────────────────
            ('sof_amount_tolerance_pct', '5.0', 'float',
             'How much the amount on a supporting document is allowed to differ from the amount the client declared, before the claim is flagged for manual review. Worked as a percentage. Example: 5% on a £10,000 claim allows for ±£500. Lower the percentage to be stricter, raise it to be more forgiving.'),
            ('sof_date_tolerance_days', '7', 'int',
             'The number of days of slack allowed between the date a transaction happened in the bank statement and the date the client (or their supporting document) said it happened. Anything outside this window is flagged. Default 7 days.'),
            ('sof_confidence_threshold', '0.999', 'float',
             'How confident the platform must be that a document matches the client\'s claim before it auto-passes without manual review. A number between 0.0 (no confidence) and 1.0 (certainty). Default 0.999 = effectively only auto-pass on a near-perfect match.'),
            ('sof_partial_confidence_threshold', '0.99', 'float',
             'A lower confidence bar used in borderline situations — when a document partially supports a claim but not perfectly. Match confidence at or above this value still earns a partial pass; below it the claim goes to manual review.'),
            ('sof_min_claims_required', '1', 'int',
             'The minimum number of source-of-funds claims the client must declare and successfully evidence before the matter can reach a Sufficient verdict. Most matters need 1 — raise this if you require multiple independent sources for high-risk transactions.'),

            # ── Document Verification ─────────────────────────────────
            ('dv_score_verified_min', '75', 'int',
             'Every uploaded document is given an authenticity score from 0 (almost certainly tampered) to 100 (looks genuine). Documents scoring at or above this number are automatically marked Verified. Default 75 — raise it to be stricter, lower it to accept more documents automatically.'),
            ('dv_score_suspicious_min', '45', 'int',
             'The cut-off between Suspicious and Likely Tampered. Documents scoring between this number and the Verified threshold are marked Suspicious — Needs Review. Anything below this number is marked Likely Tampered (treated as a probable forgery). Default 45.'),
            ('dv_weight_authenticity', '0.5', 'float',
             'How much weight the platform puts on the document\'s structural make-up (its PDF objects, metadata, fonts, digital signatures) when calculating the overall authenticity score. Higher = structural fingerprint matters more. The three weights should add up to roughly 1.0.'),
            ('dv_weight_forensic_flags', '0.3', 'float',
             'How much weight the platform puts on forensic warning flags raised by the pipeline — signs of image editing, OCR text not matching the visible text, font substitution, etc. Higher = these red flags hurt the score more. The three weights should add up to roughly 1.0.'),
            ('dv_weight_template_match', '0.2', 'float',
             'How much weight the platform puts on whether the document visually matches a known bank statement template (e.g. a genuine HSBC layout). Higher = bigger penalty for unrecognised layouts. The three weights should add up to roughly 1.0.'),
            ('dv_block_on_tampered', 'true', 'bool',
             'When ON, any document marked Likely Tampered will BLOCK the matter from being signed off until a reviewer manually accepts the document with a written rationale. When OFF, the warning is still recorded but the matter can proceed without an explicit override.'),
            ('dv_allow_self_accept', 'true', 'bool',
             'When ON, any analyst can mark a Suspicious document as accepted by themselves, with a written rationale. When OFF, accepting a document requires the four-eyes flow — one analyst proposes acceptance, then a different admin approves it. Use OFF for higher-risk firms that want a second pair of eyes on every sign-off.'),

            # ── Transaction Review ─────────────────────────────────────
            # Pre-existing thresholds — preserved exactly so the
            # transaction-monitoring service keeps working unchanged.
            ('cfg_high_risk_min_amount', '10000.00', 'float',
             'A transaction touching a high-risk country triggers an alert only if its value is at or above this GBP amount. Lower the number to alert on smaller cross-border movements. Default £10,000.'),
            ('cfg_outlier_vs_median', '5.0', 'float',
             'A transaction is flagged as an outlier when its amount is at least this many times the median amount across all the client\'s transactions. Example: 5 means a £25,000 credit when the typical credit is £5,000.'),
            ('cfg_outlier_min_amount', '1000.00', 'float',
             'Outlier detection ignores transactions below this GBP amount — so day-to-day spending doesn\'t generate noise. Only transactions at or above this floor are eligible to be flagged as outliers. Default £1,000.'),
            ('cfg_cash_threshold_deposit', '7500.00', 'float',
             'Cash deposits at or above this GBP amount automatically raise a "Large Cash Deposit" alert. UK regulators expect attention to cash above £10k; firms often set this lower for an early warning. Default £7,500.'),
            ('cfg_cash_threshold_withdrawal', '7500.00', 'float',
             'Cash withdrawals at or above this GBP amount automatically raise a "Large Cash Withdrawal" alert. Default £7,500.'),
            ('cfg_velocity_days', '7', 'int',
             'The size of the rolling window (in days) the velocity rule looks at when counting how many transactions a client has made. Default 7 — i.e. a week.'),
            ('cfg_velocity_count', '5', 'int',
             'A velocity alert fires when more than this many transactions happen inside the velocity window. Example: 5 transactions in 7 days. Lower the number to catch faster-moving funds.'),
            ('rule_high_risk_country', 'true', 'bool',
             'Master switch for the high-risk-country alert. When ON, transactions touching countries flagged High Risk in the platform\'s country list will raise an alert (subject to the high-risk minimum amount above).'),
            ('rule_prohibited_country', 'true', 'bool',
             'Master switch for the prohibited-country alert. When ON, any transaction touching a country on the sanctions / prohibited list raises an alert, regardless of amount.'),
            ('rule_cash_deposit', 'true', 'bool',
             'Master switch for the large-cash-deposit alert. When ON, cash credits at or above the deposit threshold raise an alert.'),
            ('rule_cash_withdrawal', 'true', 'bool',
             'Master switch for the large-cash-withdrawal alert. When ON, cash debits at or above the withdrawal threshold raise an alert.'),
            ('rule_outlier', 'true', 'bool',
             'Master switch for outlier detection. When ON, transactions that are unusually large compared to the client\'s normal activity are flagged.'),
            ('rule_velocity', 'true', 'bool',
             'Master switch for velocity (frequency) alerts. When ON, too many transactions in a short period trigger an alert.'),
            ('rule_unusual_narrative', 'true', 'bool',
             'Master switch for the unusual-narrative alert. When ON, transactions whose description matches a flagged keyword (e.g. "cash", "crypto", "bearer") will be alerted.'),
            ('unusual_narrative_keywords',
             '["cash", "bearer", "nominee", "offshore", "shell", "sanctioned", "embargo", "frozen", "cryptocurrency", "crypto", "bitcoin", "dark web", "darkweb", "ransom", "extortion"]',
             'json',
             'The list of keywords that trigger the unusual-narrative alert. Edit as a JSON array of lowercase strings. Any transaction whose description contains one of these words will raise the alert.'),

            # New transaction-review settings exposed via the Configuration page
            ('tr_round_number_alert_amount', '5000.00', 'float',
             'Round-number credits at or above this GBP amount (multiples of £1,000) are flagged for review — round figures can be a sign of staged or structured payments. Default £5,000.'),
            ('tr_structuring_window_days', '3', 'int',
             'When looking for "structuring" (multiple deposits split deliberately to stay under the cash reporting threshold), this is the window in days. Multiple deposits inside this window that sit just below the cash threshold are grouped and flagged.'),
            ('tr_structuring_band_pct', '20.0', 'float',
             'How close to the cash threshold a deposit has to be before it counts as a structuring candidate, as a percentage. Default 20% — i.e. on a £7,500 threshold, deposits between £6,000 and £7,499 are considered "just under" and looked at together.'),
            ('tr_critical_alerts_block', 'true', 'bool',
             'When ON, any Critical-severity transaction-review alert will block the matter from being marked Sufficient until the alert is resolved or accepted with a rationale. When OFF, critical alerts are recorded but do not block sign-off.'),

            # ── Funds Lineage ─────────────────────────────────────────
            ('fl_traced_pct_required', '80.0', 'float',
             'For savings / accumulation claims, the minimum percentage of the claimed amount that the platform must trace back to a verified origin (e.g. salary, investment income, sale proceeds) before the claim is automatically accepted. Anything below this percentage is flagged for manual review with the untraced amount highlighted. Default 80%.'),
            ('fl_amount_match_tolerance', '0.005', 'float',
             'When matching a debit from one bank account to the matching credit in another account, this is the allowed % difference between the two amounts. Stored as a fraction — 0.005 means 0.5%. So a £10,000 debit and a £10,050 credit (£50 difference = 0.5%) are still treated as the same transfer. Lower to be stricter, raise to allow for FX or rounding noise.'),
            ('fl_min_amount_match_gbp', '1.00', 'float',
             'A floor (in GBP) on the amount-match tolerance above, so even small transfers can be matched. The actual tolerance used is the larger of this fixed amount or the percentage tolerance. Default £1 — meaning transfers within £1 of each other will always be treated as a match.'),
            ('fl_max_lookback_days', '730', 'int',
             'How far back in time (in days) the tracer will walk when looking for the origin of the credit. Default 730 days (~2 years). Increase if your firm regularly handles clients whose funds accumulated over a longer period — e.g. inheritance held for 5+ years.'),
            ('fl_circular_reference_severity', 'high', 'string',
             'If the tracer detects money moving in a loop (Account A → Account B → Account A) it flags this as a possible attempt to obscure the origin. This setting controls how severely the loop is flagged: "low" = informational only, "medium" = noted on the report, "high" = needs reviewer attention, "critical" = blocks sign-off. Default "high".'),
            ('fl_statement_gap_warn_days', '30', 'int',
             'When the tracer hits an incoming transfer from an account whose bank statements are missing (or don\'t cover the relevant date), a "statement gap" review item is raised after this many days of missing coverage. Default 30 days — i.e. if more than a month of statements is missing from the source account, ask the client for them.'),
        ]

        existing_keys = {
            row[0] for row in conn.execute(text("SELECT key FROM transaction_config")).all()
        }

        inserted = 0
        for key, value, value_type, description in configs:
            if key in existing_keys:
                # Preserve operator-set values across deploys; only refresh
                # the description so help text can be tweaked centrally.
                conn.execute(
                    text("UPDATE transaction_config SET description = :description WHERE key = :key"),
                    {"key": key, "description": description},
                )
                continue
            conn.execute(
                text(
                    "INSERT INTO transaction_config (key, value, value_type, description) "
                    "VALUES (:key, :value, :value_type, :description)"
                ),
                {"key": key, "value": value, "value_type": value_type, "description": description},
            )
            inserted += 1

        conn.commit()
        if inserted:
            print(f"✅ Seeded {inserted} new config settings ({len(configs)} total in catalogue).")
        else:
            print(f"ℹ️  All {len(configs)} catalogue config keys already present; descriptions refreshed.")


if __name__ == "__main__":
    init_transaction_tables()
