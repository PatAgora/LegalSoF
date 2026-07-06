"""
Initialize Transaction Review tables in the database.
This creates the necessary schema for transaction monitoring and AML checks.
"""
import json
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
        # Helper for a per-risk-tier ("tiered") setting value. A tiered
        # setting stores JSON {low, medium, high}; the value the engine
        # uses is picked from the matter's risk rating at run time.
        def _t(low, medium, high):
            return json.dumps({"low": low, "medium": medium, "high": high})

        # The full catalogue. Each row: (key, default_value, type,
        # description). value_type is "string" | "int" | "float" |
        # "bool" | "json", or the per-risk-tier forms "tiered_float" |
        # "tiered_int" | "tiered_bool" whose value is JSON {low,medium,
        # high}. Description is shown to the operator in the
        # Configuration page so write it as user-facing copy.
        configs = [
            # ── Module master switches (firm-wide, not tiered) ────────
            # NOTE: there is deliberately no sof_enabled switch — Source
            # of Funds Analysis is the core of the platform and is
            # always on; the dv/tr/fl modules below are optional.
            ('dv_enabled', 'true', 'bool',
             'Turn the Document Verification on or off. When OFF, uploaded documents are kept on file but the platform will not run any forgery / tampering checks on them. Only turn this off if you have a separate process for verifying document authenticity.'),
            ('tr_enabled', 'true', 'bool',
             'Turn the Transaction Review on or off. When OFF, the platform will not raise AML alerts from the client\'s bank transactions (e.g. cash deposits, high-risk countries, velocity). Use this only if a separate transaction-monitoring system is in place.'),
            ('fl_enabled', 'true', 'bool',
             'Turn the Funds Lineage tracer on or off. When ON, after each assessment the platform automatically walks backwards through the client\'s bank transfers to prove where their money originally came from. When OFF, this trace is not run automatically — reviewers can still run it manually from the Funds Lineage tab.'),

            # ── Source of Funds Analysis ──────────────────────────────
            ('sof_ai_extraction', 'true', 'bool',
             'When enabled, free-text Source of Funds explanations are read by an AI model to identify the claimed sources and amounts — this understands paraphrasing and unusual wording, so claims are far less likely to be missed. When disabled (or when no AI provider API key is configured on the server) the platform falls back to a built-in keyword parser. Note: enabling this sends the client explanation text to the configured AI provider for processing.'),
            ('sof_amount_tolerance_pct', _t(10.0, 5.0, 2.5), 'tiered_float',
             'How much the amount on a supporting document is allowed to differ from the amount the client declared, before the claim is flagged for manual review (percentage). Set tighter for higher-risk clients — e.g. 2.5% high / 5% medium / 10% low.'),
            ('sof_date_tolerance_days', _t(14, 7, 3), 'tiered_int',
             'The number of days of slack allowed between the date a transaction happened in the bank statement and the date the client (or their supporting document) said it happened. Anything outside this window is flagged.'),
            ('sof_confidence_threshold', _t(0.99, 0.999, 0.999), 'tiered_float',
             'How confident the platform must be that a document matches the client\'s claim before it auto-passes without manual review (0.0–1.0). Higher = stricter; high-risk clients should sit near 1.0.'),
            ('sof_partial_confidence_threshold', _t(0.95, 0.99, 0.999), 'tiered_float',
             'A lower confidence bar used in borderline situations — when a document partially supports a claim but not perfectly. Match confidence at or above this value still earns a partial pass; below it the claim goes to manual review.'),
            ('sof_min_claims_required', _t(1, 1, 1), 'tiered_int',
             'The minimum number of source-of-funds claims the client must declare and successfully evidence before the matter can reach a Sufficient verdict. Raise it for higher-risk clients if you require multiple independent sources.'),
            ('sof_large_credit_threshold', _t(15000.0, 10000.0, 5000.0), 'tiered_float',
             'Incoming credits at or above this GBP amount that cannot be matched to a declared source-of-funds claim are flagged as large unexplained credits, and do not count towards the "funding traced" percentage. Lower it for higher-risk clients.'),
            ('sof_third_party_min_amount', _t(2500.0, 1000.0, 500.0), 'tiered_float',
             'Incoming credits at or above this GBP amount from a payer who is neither the client nor a declared source (e.g. an undeclared relative or company) raise a Third-Party Funds flag. The SRA thematic review expects undeclared third-party funding to be identified and evidenced.'),
            ('sof_require_cmra', 'true', 'bool',
             'When ON (recommended), the Source of Funds assessment cannot be run on a matter until a completed client risk assessment AND matter risk assessment exist (Regulation 28(12)-(13)). Turn OFF only during a transition period while historical matters are being back-filled with risk assessments.'),

            # ── Client & Matter Risk Assessments ──────────────────────
            ('cmra_weight_client', _t(0.30, 0.30, 0.30), 'tiered_float',
             'Weight given to the CLIENT risk factor set when computing the overall client/matter risk rating. All five weights should sum to 1.0.'),
            ('cmra_weight_service_matter', _t(0.25, 0.25, 0.25), 'tiered_float',
             'Weight given to the SERVICE/MATTER risk factor set (matter type, retainer shape) in the overall risk rating.'),
            ('cmra_weight_geography', _t(0.20, 0.20, 0.20), 'tiered_float',
             'Weight given to the GEOGRAPHY risk factor set (client location, funds origin, property location) in the overall risk rating.'),
            ('cmra_weight_delivery_channel', _t(0.15, 0.15, 0.15), 'tiered_float',
             'Weight given to the DELIVERY CHANNEL risk factor set (face-to-face vs remote, intermediated) in the overall risk rating.'),
            ('cmra_weight_sector_product', _t(0.10, 0.10, 0.10), 'tiered_float',
             'Weight given to the SECTOR/PRODUCT risk factor set in the overall risk rating.'),
            ('cmra_medium_threshold', _t(1.60, 1.60, 1.60), 'tiered_float',
             'Weighted risk score (1.0-3.0) at or above which the overall rating becomes MEDIUM. Any single factor scored 3 forces at least medium regardless.'),
            ('cmra_high_threshold', _t(2.40, 2.40, 2.40), 'tiered_float',
             'Weighted risk score (1.0-3.0) at or above which the overall rating becomes HIGH, triggering enhanced due diligence.'),

            # ── Document Verification ─────────────────────────────────
            ('dv_score_verified_min', _t(65, 75, 85), 'tiered_int',
             'Every uploaded document is given an authenticity score from 0 (almost certainly tampered) to 100 (looks genuine). Documents scoring at or above this number are automatically marked Verified. Higher = stricter for higher-risk clients.'),
            ('dv_score_suspicious_min', _t(40, 45, 55), 'tiered_int',
             'The cut-off between Suspicious and Likely Tampered. Documents scoring between this number and the Verified threshold are marked Suspicious — Needs Review. Anything below this number is marked Likely Tampered.'),
            ('dv_weight_authenticity', '0.5', 'float',
             'How much weight the platform puts on the document\'s structural make-up (its PDF objects, metadata, fonts, digital signatures) when calculating the overall authenticity score. The three weights should add up to roughly 1.0.'),
            ('dv_weight_forensic_flags', '0.3', 'float',
             'How much weight the platform puts on forensic warning flags raised by the pipeline — signs of image editing, OCR text not matching the visible text, font substitution, etc. The three weights should add up to roughly 1.0.'),
            ('dv_weight_template_match', '0.2', 'float',
             'How much weight the platform puts on whether the document visually matches a known bank statement template (e.g. a genuine HSBC layout). The three weights should add up to roughly 1.0.'),
            ('dv_block_on_tampered', _t('true', 'true', 'true'), 'tiered_bool',
             'When ON, any document marked Likely Tampered will BLOCK the matter from being signed off until a reviewer manually accepts the document with a written rationale. When OFF, the warning is still recorded but the matter can proceed.'),
            ('dv_allow_self_accept', 'true', 'bool',
             'When ON, any analyst can mark a Suspicious document as accepted by themselves, with a written rationale. When OFF, accepting a document requires the four-eyes flow — one analyst proposes acceptance, then a different admin approves it.'),

            # ── Transaction Review ─────────────────────────────────────
            ('cfg_high_risk_min_amount', _t(15000.0, 10000.0, 5000.0), 'tiered_float',
             'A transaction touching a high-risk country triggers an alert only if its value is at or above this GBP amount. Lower it for higher-risk clients to catch smaller cross-border movements.'),
            ('cfg_outlier_vs_median', _t(7.0, 5.0, 3.0), 'tiered_float',
             'A transaction is flagged as an outlier when its amount is at least this many times the median amount across all the client\'s transactions. Lower = more sensitive.'),
            ('cfg_outlier_min_amount', _t(2000.0, 1000.0, 500.0), 'tiered_float',
             'Outlier detection ignores transactions below this GBP amount — so day-to-day spending doesn\'t generate noise. Only transactions at or above this floor are eligible to be flagged as outliers.'),
            ('cfg_cash_threshold_deposit', _t(10000.0, 7500.0, 3000.0), 'tiered_float',
             'Cash deposits at or above this GBP amount automatically raise a "Large Cash Deposit" alert. Set lower for higher-risk clients for an earlier warning.'),
            ('cfg_cash_threshold_withdrawal', _t(10000.0, 7500.0, 3000.0), 'tiered_float',
             'Cash withdrawals at or above this GBP amount automatically raise a "Large Cash Withdrawal" alert. Set lower for higher-risk clients.'),
            ('cfg_velocity_days', _t(7, 7, 7), 'tiered_int',
             'The size of the rolling window (in days) the velocity rule looks at when counting how many transactions a client has made.'),
            ('cfg_velocity_count', _t(8, 5, 3), 'tiered_int',
             'A velocity alert fires when more than this many transactions happen inside the velocity window. Lower = catches faster-moving funds; tighten for higher-risk clients.'),
            ('rule_high_risk_country', _t('true', 'true', 'true'), 'tiered_bool',
             'The high-risk-country alert. When ON, transactions touching countries flagged High Risk raise an alert (subject to the high-risk minimum amount).'),
            ('rule_prohibited_country', _t('true', 'true', 'true'), 'tiered_bool',
             'The prohibited-country alert. When ON, any transaction touching a country on the sanctions / prohibited list raises an alert, regardless of amount.'),
            ('rule_cash_deposit', _t('true', 'true', 'true'), 'tiered_bool',
             'The large-cash-deposit alert. When ON, cash credits at or above the deposit threshold raise an alert.'),
            ('rule_cash_withdrawal', _t('true', 'true', 'true'), 'tiered_bool',
             'The large-cash-withdrawal alert. When ON, cash debits at or above the withdrawal threshold raise an alert.'),
            ('rule_outlier', _t('true', 'true', 'true'), 'tiered_bool',
             'Outlier detection. When ON, transactions that are unusually large compared to the client\'s normal activity are flagged.'),
            ('rule_velocity', _t('true', 'true', 'true'), 'tiered_bool',
             'Velocity (frequency) alerts. When ON, too many transactions in a short period trigger an alert.'),
            ('rule_unusual_narrative', _t('true', 'true', 'true'), 'tiered_bool',
             'The unusual-narrative alert. When ON, transactions whose description matches a flagged keyword (e.g. "cash", "crypto", "bearer") raise an alert.'),
            ('unusual_narrative_keywords',
             '["cash", "bearer", "nominee", "offshore", "shell", "sanctioned", "embargo", "frozen", "cryptocurrency", "crypto", "bitcoin", "dark web", "darkweb", "ransom", "extortion"]',
             'json',
             'The list of keywords that trigger the unusual-narrative alert. Edit as a JSON array of lowercase strings. Any transaction whose description contains one of these words will raise the alert.'),
            ('tr_round_number_alert_amount', _t(10000.0, 5000.0, 2500.0), 'tiered_float',
             'Round-number credits at or above this GBP amount (multiples of £1,000) are flagged for review — round figures can be a sign of staged or structured payments.'),
            ('tr_structuring_window_days', _t(3, 3, 5), 'tiered_int',
             'When looking for "structuring" (multiple deposits split deliberately to stay under the cash reporting threshold), this is the window in days.'),
            ('tr_structuring_band_pct', _t(15.0, 20.0, 25.0), 'tiered_float',
             'How close to the cash threshold a deposit has to be before it counts as a structuring candidate, as a percentage.'),
            ('tr_critical_alerts_block', _t('true', 'true', 'true'), 'tiered_bool',
             'When ON, any Critical-severity transaction-review alert will block the matter from being marked Sufficient until the alert is resolved or accepted with a rationale.'),

            # ── Funds Lineage ─────────────────────────────────────────
            ('fl_traced_pct_required', _t(70.0, 80.0, 90.0), 'tiered_float',
             'For savings / accumulation claims, the minimum percentage of the claimed amount that must be traced back to a verified origin before the claim is automatically accepted. Higher = stricter for higher-risk clients.'),
            ('fl_amount_match_tolerance', _t(0.01, 0.005, 0.0025), 'tiered_float',
             'When matching a debit from one bank account to the matching credit in another, this is the allowed fractional difference (0.005 = 0.5%). Tighten for higher-risk clients.'),
            ('fl_min_amount_match_gbp', _t(1.0, 1.0, 1.0), 'tiered_float',
             'A floor (in GBP) on the amount-match tolerance, so even small transfers can be matched. The actual tolerance is the larger of this fixed amount or the percentage tolerance.'),
            ('fl_max_lookback_days', _t(730, 730, 1095), 'tiered_int',
             'How far back in time (in days) the tracer will walk when looking for the origin of the credit. Increase for higher-risk clients whose funds accumulated over longer periods.'),
            ('fl_circular_reference_severity', 'high', 'string',
             'If the tracer detects money moving in a loop (Account A → Account B → Account A) it flags this as a possible attempt to obscure the origin. Severity: "low" = informational, "medium" = noted, "high" = needs review, "critical" = blocks sign-off.'),
            ('fl_statement_gap_warn_days', _t(45, 30, 14), 'tiered_int',
             'When the tracer hits an incoming transfer from an account whose bank statements are missing, a "statement gap" review item is raised after this many days of missing coverage. Tighten for higher-risk clients.'),
        ]

        # Keys removed from the catalogue in a later release. Delete
        # them so they don't linger as orphan rows on the Configuration
        # page. sof_enabled was retired — Source of Funds Analysis is
        # the core module and is always on.
        retired_keys = ['sof_enabled']
        for rk in retired_keys:
            conn.execute(
                text("DELETE FROM transaction_config WHERE key = :key"),
                {"key": rk},
            )

        # Map of existing rows: key -> (value, value_type).
        existing = {
            row[0]: (row[1], row[2])
            for row in conn.execute(
                text("SELECT key, value, value_type FROM transaction_config")
            ).all()
        }

        inserted = 0
        migrated = 0
        for key, value, value_type, description in configs:
            if key in existing:
                old_value, old_type = existing[key]
                # Migration: a key that is now tiered but is stored as a
                # plain scalar (from an earlier release) gets converted —
                # the operator's single value is applied to ALL three
                # tiers so nothing changes behaviourally until they
                # deliberately differentiate the tiers.
                if value_type.startswith('tiered_') and not (old_type or '').startswith('tiered_'):
                    base = value_type[len('tiered_'):]
                    if base == 'bool':
                        v = str(old_value).strip().lower() in ('true', '1', 'yes')
                    elif base == 'int':
                        try:
                            v = int(float(old_value))
                        except (TypeError, ValueError):
                            v = 0
                    else:
                        try:
                            v = float(old_value)
                        except (TypeError, ValueError):
                            v = 0.0
                    tiered_value = json.dumps({"low": v, "medium": v, "high": v})
                    conn.execute(
                        text(
                            "UPDATE transaction_config SET value = :value, "
                            "value_type = :value_type, description = :description "
                            "WHERE key = :key"
                        ),
                        {"key": key, "value": tiered_value,
                         "value_type": value_type, "description": description},
                    )
                    migrated += 1
                else:
                    # Preserve operator-set values across deploys; only
                    # refresh the description so help text can be tweaked
                    # centrally.
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
        print(
            f"✅ Config catalogue: {len(configs)} settings "
            f"({inserted} inserted, {migrated} migrated to per-risk-tier)."
        )


if __name__ == "__main__":
    init_transaction_tables()
