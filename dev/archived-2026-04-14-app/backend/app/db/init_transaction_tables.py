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
    """Seed default transaction monitoring configuration"""
    with engine.connect() as conn:
        # Check if config already exists
        result = conn.execute(text("SELECT COUNT(*) FROM transaction_config"))
        count = result.scalar()
        
        if count > 0:
            print(f"ℹ️  Transaction config already exists ({count} settings)")
            return
        
        # Default configuration (based on original app)
        configs = [
            # Thresholds
            ('cfg_high_risk_min_amount', '10000.00', 'float', 'Minimum amount (GBP) to trigger high-risk country alert'),
            ('cfg_outlier_vs_median', '5.0', 'float', 'Multiplier for outlier detection (x times median)'),
            ('cfg_outlier_min_amount', '1000.00', 'float', 'Minimum amount (GBP) for outlier detection'),
            ('cfg_cash_threshold_deposit', '7500.00', 'float', 'Cash deposit threshold (GBP)'),
            ('cfg_cash_threshold_withdrawal', '7500.00', 'float', 'Cash withdrawal threshold (GBP)'),
            ('cfg_velocity_days', '7', 'int', 'Days to check for velocity alerts'),
            ('cfg_velocity_count', '5', 'int', 'Number of transactions for velocity alert'),
            
            # Rule toggles
            ('rule_high_risk_country', 'true', 'bool', 'Alert on high-risk country transactions'),
            ('rule_prohibited_country', 'true', 'bool', 'Alert on prohibited country transactions'),
            ('rule_cash_deposit', 'true', 'bool', 'Alert on large cash deposits'),
            ('rule_cash_withdrawal', 'true', 'bool', 'Alert on large cash withdrawals'),
            ('rule_outlier', 'true', 'bool', 'Alert on outlier transactions'),
            ('rule_velocity', 'true', 'bool', 'Alert on transaction velocity'),
            ('rule_unusual_narrative', 'true', 'bool', 'Alert on unusual narrative patterns'),
            
            # Narrative keywords (JSON list)
            ('unusual_narrative_keywords', '["cash", "bearer", "nominee", "offshore", "shell", "sanctioned", "embargo", "frozen", "cryptocurrency", "crypto", "bitcoin", "dark web", "darkweb", "ransom", "extortion"]', 'json', 'Keywords that trigger unusual narrative alerts'),
        ]
        
        for key, value, value_type, description in configs:
            conn.execute(
                text("""
                    INSERT INTO transaction_config (key, value, value_type, description)
                    VALUES (:key, :value, :value_type, :description)
                """),
                {"key": key, "value": value, "value_type": value_type, "description": description}
            )
        
        conn.commit()
        print(f"✅ Seeded {len(configs)} transaction config settings")


if __name__ == "__main__":
    init_transaction_tables()
