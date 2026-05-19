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
             'Master switch for the Source of Funds Analysis module. When disabled, the SoF engine returns an empty result and no claim verification is performed.'),
            ('dv_enabled', 'true', 'bool',
             'Master switch for the Document Verification module. When disabled, uploaded documents are stored but not forensically checked. Use only if you have an alternative verification process.'),
            ('tr_enabled', 'true', 'bool',
             'Master switch for the Transaction Review module. When disabled, the transaction monitoring engine produces no alerts and matters do not get an AML alert breakdown.'),
            ('fl_enabled', 'true', 'bool',
             'Master switch for the Funds Lineage module. When disabled, the lineage tracer is not run automatically after a SoF assessment.'),

            # ── Source of Funds Analysis ──────────────────────────────
            ('sof_amount_tolerance_pct', '5.0', 'float',
             'Allowed % difference between the amount declared on a SoF claim and the amount evidenced on a document or bank transaction. Above this threshold the claim is flagged for manual review.'),
            ('sof_date_tolerance_days', '7', 'int',
             'Number of days of slack permitted between a claim date and the matched bank transaction or supporting document date.'),
            ('sof_confidence_threshold', '0.999', 'float',
             'Minimum document-match confidence (0.0–1.0) for a SoF claim to auto-pass without manual review.'),
            ('sof_partial_confidence_threshold', '0.99', 'float',
             'Lower confidence threshold (0.0–1.0) used for partial / borderline auto-acceptance paths in the SoF engine.'),
            ('sof_min_claims_required', '1', 'int',
             'Minimum number of SoF claims that must be evidenced for the matter to reach a "sufficient" outcome.'),

            # ── Document Verification ─────────────────────────────────
            ('dv_score_verified_min', '75', 'int',
             'Minimum authenticity score (0–100) at which a document is automatically classified as Verified.'),
            ('dv_score_suspicious_min', '45', 'int',
             'Authenticity score at and above which a document is classified as Suspicious rather than Likely Tampered.'),
            ('dv_weight_authenticity', '0.5', 'float',
             'Weight applied to the structural authenticity sub-score when computing the overall document score (0.0–1.0).'),
            ('dv_weight_forensic_flags', '0.3', 'float',
             'Weight applied to the forensic-flag deduction when computing the overall document score (0.0–1.0).'),
            ('dv_weight_template_match', '0.2', 'float',
             'Weight applied to the bank-template fingerprint match when computing the overall document score (0.0–1.0).'),
            ('dv_block_on_tampered', 'true', 'bool',
             'When enabled, documents with the Likely Tampered verdict block downstream processing until a reviewer accepts the document with a rationale.'),
            ('dv_allow_self_accept', 'true', 'bool',
             'When enabled, any analyst can accept a Suspicious document inline with a rationale. When disabled, only admins via the four-eyes flow can sign off.'),

            # ── Transaction Review ─────────────────────────────────────
            # Pre-existing thresholds — preserved exactly so the
            # transaction-monitoring service keeps working unchanged.
            ('cfg_high_risk_min_amount', '10000.00', 'float',
             'Minimum transaction amount (GBP) that triggers a high-risk-country alert.'),
            ('cfg_outlier_vs_median', '5.0', 'float',
             'A transaction is flagged as an outlier when its amount exceeds this multiple of the median.'),
            ('cfg_outlier_min_amount', '1000.00', 'float',
             'Minimum transaction amount (GBP) considered when running outlier detection.'),
            ('cfg_cash_threshold_deposit', '7500.00', 'float',
             'Cash deposit value (GBP) at and above which a Large Cash Deposit alert is raised.'),
            ('cfg_cash_threshold_withdrawal', '7500.00', 'float',
             'Cash withdrawal value (GBP) at and above which a Large Cash Withdrawal alert is raised.'),
            ('cfg_velocity_days', '7', 'int',
             'Window (in days) used by the velocity rule when counting recent transactions.'),
            ('cfg_velocity_count', '5', 'int',
             'Number of transactions inside the velocity window that triggers a velocity alert.'),
            ('rule_high_risk_country', 'true', 'bool', 'Raise an alert when a transaction touches a high-risk country.'),
            ('rule_prohibited_country', 'true', 'bool', 'Raise an alert when a transaction touches a prohibited country.'),
            ('rule_cash_deposit', 'true', 'bool', 'Raise an alert on large cash deposits.'),
            ('rule_cash_withdrawal', 'true', 'bool', 'Raise an alert on large cash withdrawals.'),
            ('rule_outlier', 'true', 'bool', 'Raise an alert on outlier transactions.'),
            ('rule_velocity', 'true', 'bool', 'Raise an alert on rapid transaction velocity.'),
            ('rule_unusual_narrative', 'true', 'bool', 'Raise an alert when a transaction narrative matches a flagged keyword.'),
            ('unusual_narrative_keywords',
             '["cash", "bearer", "nominee", "offshore", "shell", "sanctioned", "embargo", "frozen", "cryptocurrency", "crypto", "bitcoin", "dark web", "darkweb", "ransom", "extortion"]',
             'json', 'Keywords that trigger the unusual-narrative alert. Stored as a JSON list of strings.'),

            # New transaction-review settings exposed via the Configuration page
            ('tr_round_number_alert_amount', '5000.00', 'float',
             'A credit at or above this amount with a round number (multiple of 1000) is flagged for review.'),
            ('tr_structuring_window_days', '3', 'int',
             'Window (in days) used when looking for structuring/smurfing patterns (multiple deposits just below the reporting threshold).'),
            ('tr_structuring_band_pct', '20.0', 'float',
             'Transactions falling within this percentage band BELOW the cash threshold are considered candidates for structuring.'),
            ('tr_critical_alerts_block', 'true', 'bool',
             'When enabled, any Critical transaction-review alert blocks the matter from being marked as "sufficient" until resolved.'),

            # ── Funds Lineage ─────────────────────────────────────────
            ('fl_traced_pct_required', '80.0', 'float',
             'Minimum % of the claimed amount that must be traced to a verified origin for a savings/accumulation claim to auto-pass.'),
            ('fl_amount_match_tolerance', '0.005', 'float',
             'Allowed fractional tolerance (0.005 = 0.5%) when matching debits to credits across accounts during lineage tracing.'),
            ('fl_min_amount_match_gbp', '1.00', 'float',
             'Floor (GBP) on the lineage amount-match tolerance. Pairs within max(this, total*amount_match_tolerance) are treated as equivalent.'),
            ('fl_max_lookback_days', '730', 'int',
             'Maximum number of days the lineage tracer will walk backwards from the target credit when searching for funding sources.'),
            ('fl_circular_reference_severity', 'high', 'string',
             'Severity (low | medium | high | critical) raised when the lineage tracer detects an A→B→A loop between accounts.'),
            ('fl_statement_gap_warn_days', '30', 'int',
             'When statements for an upstream account are missing for more than this many days, a "statement gap" review item is raised.'),
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
