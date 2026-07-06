"""
Transaction monitoring service - AML alert generation engine.
Implements 9 built-in rules for detecting suspicious transactions
(country risk, cash, outlier, velocity, narrative keywords,
structuring, round-number credits).
"""
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaction import Transaction, TransactionAlert, CountryRisk, TransactionConfig
import json
import logging
import re
import statistics

logger = logging.getLogger(__name__)

# Severity ladder used when escalating merged alerts.
_SEVERITY_ORDER = ['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

# Narrative patterns indicating a cash credit even when the parser did
# not populate the `channel` field (parsers generally never set it).
_CASH_CREDIT_NARRATIVE = re.compile(
    r'\bcash\b.*\b(deposit|paid in|lodgement)\b|counter credit',
    re.IGNORECASE,
)


class TransactionMonitoringService:
    """Service for running AML checks on transactions"""
    
    def __init__(self, db: Session):
        self.db = db
        # Raw config rows: {key: (value, value_type)}. Resolved into a
        # concrete `self.config` per-matter (tiered settings depend on
        # the matter's risk rating) at the start of run_checks_for_matter.
        self._raw_config = self._load_raw_config()
        self.config = self._resolve_config('medium')
        self.country_risks = self._load_country_risks()

    def _load_raw_config(self) -> Dict[str, tuple]:
        """Load raw configuration rows from the database."""
        return {
            item.key: (item.value, item.value_type)
            for item in self.db.query(TransactionConfig).all()
        }

    def _resolve_config(self, tier: str) -> Dict[str, any]:
        """Resolve every config row to the concrete value for `tier`
        ('low' | 'medium' | 'high'). Tiered settings pick their
        per-risk-tier value; scalar settings are coerced as before."""
        from app.services.config_resolver import resolve_value
        out: Dict[str, any] = {}
        for key, (value, value_type) in self._raw_config.items():
            try:
                out[key] = resolve_value(value, value_type, tier, key=key)
            except Exception as exc:
                # Leave the key unset so callers' .get(key, default)
                # falls back to the documented built-in default rather
                # than an unusable raw value.
                logger.warning(
                    "Config key %r could not be resolved (%s: %s); "
                    "the built-in default will apply",
                    key, type(exc).__name__, exc,
                )
        return out
    
    def _load_country_risks(self) -> Dict[str, dict]:
        """Load country risk data from database"""
        countries = self.db.query(CountryRisk).all()
        return {
            country.iso2: {
                'risk_level': country.risk_level,
                'score': country.score,
                'prohibited': country.prohibited
            }
            for country in countries
        }
    
    def run_checks_for_matter(self, matter_id: int) -> List[TransactionAlert]:
        """Run all AML checks for a matter's transactions"""
        # Resolve the per-risk-tier configuration for THIS matter — a
        # high-risk client gets the High-tier thresholds and rule
        # toggles, etc.
        from app.models import Matter
        from app.services.config_resolver import map_risk_tier
        matter = self.db.query(Matter).filter(Matter.id == matter_id).first()
        rating = (matter.risk_rating.value if matter and matter.risk_rating else 'medium')
        self.config = self._resolve_config(map_risk_tier(rating))

        # Module master switch — operator can disable the whole
        # Transaction Review section from the Configuration page.
        if not self.config.get('tr_enabled', True):
            return []

        # Get all transactions for this matter
        transactions = self.db.query(Transaction).filter(
            Transaction.matter_id == matter_id
        ).order_by(Transaction.txn_date).all()

        if not transactions:
            return []
        
        alerts = []
        
        for txn in transactions:
            # Run each rule
            txn_alerts = []
            
            if self.config.get('rule_prohibited_country', True):
                alert = self._check_prohibited_country(txn, matter_id)
                if alert:
                    txn_alerts.append(alert)
            
            if self.config.get('rule_high_risk_country', True):
                alert = self._check_high_risk_country(txn, matter_id)
                if alert:
                    txn_alerts.append(alert)
            
            if self.config.get('rule_cash_deposit', True):
                alert = self._check_cash_deposit(txn, matter_id)
                if alert:
                    txn_alerts.append(alert)
            
            if self.config.get('rule_cash_withdrawal', True):
                alert = self._check_cash_withdrawal(txn, matter_id)
                if alert:
                    txn_alerts.append(alert)
            
            if self.config.get('rule_outlier', True):
                alert = self._check_outlier(txn, matter_id, transactions)
                if alert:
                    txn_alerts.append(alert)
            
            if self.config.get('rule_velocity', True):
                alert = self._check_velocity(txn, matter_id, transactions)
                if alert:
                    txn_alerts.append(alert)
            
            if self.config.get('rule_unusual_narrative', True):
                alert = self._check_unusual_narrative(txn, matter_id)
                if alert:
                    txn_alerts.append(alert)

            # Structuring detection (tr_structuring_window_days /
            # tr_structuring_band_pct) — deposits deliberately split to
            # stay under the cash reporting threshold.
            alert = self._check_structuring(txn, matter_id, transactions)
            if alert:
                txn_alerts.append(alert)

            # Round-number credit detection (tr_round_number_alert_amount).
            alert = self._check_round_number(txn, matter_id)
            if alert:
                txn_alerts.append(alert)

            # Merge alerts for same transaction
            if txn_alerts:
                merged_alert = self._merge_transaction_alerts(txn_alerts)
                alerts.append(merged_alert)
        
        # Save alerts to database
        for alert in alerts:
            self.db.add(alert)
        
        self.db.commit()
        
        return alerts
    
    def _check_prohibited_country(self, txn: Transaction, matter_id: int) -> TransactionAlert:
        """Rule 1: Check for prohibited countries"""
        if not txn.country_iso2:
            return None
        
        country = self.country_risks.get(txn.country_iso2)
        if not country:
            return None
        
        if country['prohibited']:
            return TransactionAlert(
                matter_id=matter_id,
                txn_id=txn.id,
                customer_id=txn.customer_id,
                score=100,
                severity='CRITICAL',
                reasons=['Prohibited country under UK/EU sanctions'],
                rule_tags=['PROHIBITED_COUNTRY']
            )
        
        return None
    
    def _check_high_risk_country(self, txn: Transaction, matter_id: int) -> TransactionAlert:
        """Rule 2: Check for high-risk countries above threshold"""
        if not txn.country_iso2:
            return None
        
        country = self.country_risks.get(txn.country_iso2)
        if not country:
            return None
        
        min_amount = self.config.get('cfg_high_risk_min_amount', 10000.0)
        
        if country['risk_level'] in ('HIGH', 'HIGH_3RD') and txn.base_amount >= min_amount:
            severity = 'HIGH' if country['risk_level'] == 'HIGH' else 'MEDIUM'
            score = country['score']
            
            return TransactionAlert(
                matter_id=matter_id,
                txn_id=txn.id,
                customer_id=txn.customer_id,
                score=score,
                severity=severity,
                reasons=[f"{country['risk_level'].replace('_', ' ').title()} country - Enhanced due diligence required (Amount: £{txn.base_amount:,.2f})"],
                rule_tags=['HIGH_RISK_COUNTRY']
            )
        
        return None
    
    def _is_cash_credit(self, txn: Transaction) -> bool:
        """Cash indicator for a credit: the `channel` field when the
        parser sets it, otherwise a narrative match (parsers generally
        never populate `channel`, so channel-only detection fails open)."""
        if txn.channel and 'cash' in txn.channel.lower():
            return True
        if txn.direction == 'in' and txn.narrative and _CASH_CREDIT_NARRATIVE.search(txn.narrative):
            return True
        return False

    def _check_cash_deposit(self, txn: Transaction, matter_id: int) -> TransactionAlert:
        """Rule 3: Check for large cash deposits"""
        threshold = self.config.get('cfg_cash_threshold_deposit', 7500.0)

        if txn.direction == 'in' and self._is_cash_credit(txn):
            if txn.base_amount >= threshold:
                excess = txn.base_amount - threshold
                
                return TransactionAlert(
                    matter_id=matter_id,
                    txn_id=txn.id,
                    customer_id=txn.customer_id,
                    score=75,
                    severity='HIGH',
                    reasons=[f"Large cash deposit exceeds threshold (£{threshold:,.2f}) by £{excess:,.2f}"],
                    rule_tags=['LARGE_CASH_DEPOSIT']
                )
        
        return None
    
    def _check_cash_withdrawal(self, txn: Transaction, matter_id: int) -> TransactionAlert:
        """Rule 4: Check for large cash withdrawals"""
        threshold = self.config.get('cfg_cash_threshold_withdrawal', 7500.0)
        
        if txn.direction == 'out' and txn.channel and 'cash' in txn.channel.lower():
            if txn.base_amount >= threshold:
                excess = txn.base_amount - threshold
                
                return TransactionAlert(
                    matter_id=matter_id,
                    txn_id=txn.id,
                    customer_id=txn.customer_id,
                    score=75,
                    severity='HIGH',
                    reasons=[f"Large cash withdrawal exceeds threshold (£{threshold:,.2f}) by £{excess:,.2f}"],
                    rule_tags=['LARGE_CASH_WITHDRAWAL']
                )
        
        return None
    
    def _check_outlier(self, txn: Transaction, matter_id: int, all_txns: List[Transaction]) -> TransactionAlert:
        """Rule 5: Check for outlier transactions (significantly above normal)"""
        min_amount = self.config.get('cfg_outlier_min_amount', 1000.0)
        multiplier = self.config.get('cfg_outlier_vs_median', 5.0)
        
        if txn.base_amount < min_amount:
            return None
        
        # Calculate median transaction amount for this customer/direction
        same_direction = [t.base_amount for t in all_txns if t.direction == txn.direction and t.id != txn.id]
        
        if len(same_direction) < 3:
            return None
        
        median = statistics.median(same_direction)

        if median == 0:
            return None
        
        if txn.base_amount >= median * multiplier:
            return TransactionAlert(
                matter_id=matter_id,
                txn_id=txn.id,
                customer_id=txn.customer_id,
                score=60,
                severity='MEDIUM',
                reasons=[f"Transaction amount (£{txn.base_amount:,.2f}) is {txn.base_amount/median:.1f}× median (£{median:,.2f}) for {txn.direction} transactions"],
                rule_tags=['OUTLIER']
            )
        
        return None
    
    def _check_velocity(self, txn: Transaction, matter_id: int, all_txns: List[Transaction]) -> TransactionAlert:
        """Rule 6: Check for rapid transaction patterns (velocity)"""
        velocity_days = self.config.get('cfg_velocity_days', 7)
        velocity_count = self.config.get('cfg_velocity_count', 5)
        
        # Count transactions in a strict N-day window ending at this
        # transaction. The lower bound is EXCLUSIVE — an inclusive
        # bound on both ends would span N+1 days.
        window_start = txn.txn_date - timedelta(days=velocity_days)
        window_end = txn.txn_date

        txns_in_window = [
            t for t in all_txns
            if window_start < t.txn_date <= window_end and t.direction == txn.direction
        ]
        
        if len(txns_in_window) >= velocity_count:
            total_amount = sum(t.base_amount for t in txns_in_window)
            
            return TransactionAlert(
                matter_id=matter_id,
                txn_id=txn.id,
                customer_id=txn.customer_id,
                score=50,
                severity='MEDIUM',
                reasons=[f"High transaction velocity: {len(txns_in_window)} {txn.direction} transactions totaling £{total_amount:,.2f} in {velocity_days} days"],
                rule_tags=['VELOCITY']
            )
        
        return None
    
    def _check_unusual_narrative(self, txn: Transaction, matter_id: int) -> TransactionAlert:
        """Rule 7: Check for suspicious keywords in transaction narrative"""
        if not txn.narrative:
            return None
        
        keywords = self.config.get('unusual_narrative_keywords', [])
        narrative_lower = txn.narrative.lower()
        
        found_keywords = [kw for kw in keywords if kw.lower() in narrative_lower]
        
        if found_keywords:
            return TransactionAlert(
                matter_id=matter_id,
                txn_id=txn.id,
                customer_id=txn.customer_id,
                score=45,
                severity='MEDIUM',
                reasons=[f"Narrative contains suspicious keywords: {', '.join(found_keywords)}"],
                rule_tags=['UNUSUAL_NARRATIVE']
            )
        
        return None
    
    def _check_structuring(self, txn: Transaction, matter_id: int, all_txns: List[Transaction]) -> TransactionAlert:
        """Structuring detection: three or more credits inside the
        configured window, each sitting just below the cash reporting
        threshold (within the configured band of it), together summing
        above the threshold — the classic pattern of deposits split
        deliberately to stay under the reporting line."""
        window_days = self.config.get('tr_structuring_window_days', 3)
        band_pct = self.config.get('tr_structuring_band_pct', 20.0)
        threshold = self.config.get('cfg_cash_threshold_deposit', 7500.0)

        if txn.direction != 'in' or not threshold or threshold <= 0:
            return None

        band_floor = threshold * (1.0 - float(band_pct) / 100.0)

        def _is_candidate(t: Transaction) -> bool:
            return (
                t.direction == 'in'
                and t.base_amount < threshold
                and t.base_amount >= band_floor
            )

        if not _is_candidate(txn):
            return None

        window_start = txn.txn_date - timedelta(days=window_days)
        candidates = [
            t for t in all_txns
            if window_start < t.txn_date <= txn.txn_date and _is_candidate(t)
        ]

        if len(candidates) >= 3:
            total = sum(t.base_amount for t in candidates)
            if total > threshold:
                return TransactionAlert(
                    matter_id=matter_id,
                    txn_id=txn.id,
                    customer_id=txn.customer_id,
                    score=80,
                    severity='HIGH',
                    reasons=[
                        f"Possible structuring: {len(candidates)} credits within {window_days} days, "
                        f"each just below the £{threshold:,.2f} threshold (within {band_pct:.0f}%), "
                        f"totalling £{total:,.2f}"
                    ],
                    rule_tags=['STRUCTURING_PATTERN']
                )

        return None

    def _check_round_number(self, txn: Transaction, matter_id: int) -> TransactionAlert:
        """Round-number credits at or above the configured amount
        (exact multiples of £1,000) — a possible sign of staged or
        structured payments."""
        min_amount = self.config.get('tr_round_number_alert_amount', 5000.0)

        if txn.direction != 'in' or not min_amount or min_amount <= 0:
            return None

        amount = txn.base_amount
        if amount >= min_amount and amount > 0 and amount % 1000 == 0:
            return TransactionAlert(
                matter_id=matter_id,
                txn_id=txn.id,
                customer_id=txn.customer_id,
                score=50,
                severity='MEDIUM',
                reasons=[f"Round-number credit of £{amount:,.2f} (multiple of £1,000) at or above £{min_amount:,.2f}"],
                rule_tags=['ROUND_NUMBER']
            )

        return None

    def _merge_transaction_alerts(self, alerts: List[TransactionAlert]) -> TransactionAlert:
        """Merge multiple alerts for the same transaction.

        Accumulation escalates: the merged score is the max plus 5 for
        every additional triggered rule (capped at 100), and the
        severity bumps one level when three or more rules fired."""
        if len(alerts) == 1:
            return alerts[0]

        # Combine reasons and tags
        all_reasons = []
        all_tags = []
        max_score = 0

        for alert in alerts:
            all_reasons.extend(alert.reasons)
            all_tags.extend(alert.rule_tags)
            max_score = max(max_score, alert.score)

        # Escalate on accumulation: max + 5 per extra rule, capped.
        merged_score = min(100, max_score + 5 * (len(alerts) - 1))

        # Determine severity from merged score
        if merged_score >= 90:
            severity = 'CRITICAL'
        elif merged_score >= 70:
            severity = 'HIGH'
        elif merged_score >= 45:
            severity = 'MEDIUM'
        elif merged_score >= 25:
            severity = 'LOW'
        else:
            severity = 'INFO'

        # Three or more rules on one transaction bumps severity a level.
        if len(alerts) >= 3:
            idx = _SEVERITY_ORDER.index(severity)
            severity = _SEVERITY_ORDER[min(idx + 1, len(_SEVERITY_ORDER) - 1)]

        # Create merged alert
        return TransactionAlert(
            matter_id=alerts[0].matter_id,
            txn_id=alerts[0].txn_id,
            customer_id=alerts[0].customer_id,
            score=merged_score,
            severity=severity,
            reasons=all_reasons,
            rule_tags=all_tags
        )
