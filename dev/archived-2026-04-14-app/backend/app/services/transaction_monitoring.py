"""
Transaction monitoring service - AML alert generation engine.
Implements 7 built-in rules for detecting suspicious transactions.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.transaction import Transaction, TransactionAlert, CountryRisk, TransactionConfig
import json


class TransactionMonitoringService:
    """Service for running AML checks on transactions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.config = self._load_config()
        self.country_risks = self._load_country_risks()
    
    def _load_config(self) -> Dict[str, any]:
        """Load configuration from database"""
        config_items = self.db.query(TransactionConfig).all()
        config = {}
        
        for item in config_items:
            key = item.key
            value = item.value
            value_type = item.value_type
            
            # Convert value to appropriate type
            if value_type == 'int':
                config[key] = int(value)
            elif value_type == 'float':
                config[key] = float(value)
            elif value_type == 'bool':
                config[key] = value.lower() in ('true', '1', 'yes')
            elif value_type == 'json':
                config[key] = json.loads(value)
            else:
                config[key] = value
        
        return config
    
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
    
    def _check_cash_deposit(self, txn: Transaction, matter_id: int) -> TransactionAlert:
        """Rule 3: Check for large cash deposits"""
        threshold = self.config.get('cfg_cash_threshold_deposit', 7500.0)
        
        if txn.direction == 'in' and txn.channel and 'cash' in txn.channel.lower():
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
        
        same_direction.sort()
        median = same_direction[len(same_direction) // 2]
        
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
        
        # Count transactions in window
        window_start = txn.txn_date - timedelta(days=velocity_days)
        window_end = txn.txn_date
        
        txns_in_window = [
            t for t in all_txns 
            if window_start <= t.txn_date <= window_end and t.direction == txn.direction
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
    
    def _merge_transaction_alerts(self, alerts: List[TransactionAlert]) -> TransactionAlert:
        """Merge multiple alerts for the same transaction"""
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
        
        # Determine severity from max score
        if max_score >= 90:
            severity = 'CRITICAL'
        elif max_score >= 70:
            severity = 'HIGH'
        elif max_score >= 45:
            severity = 'MEDIUM'
        elif max_score >= 25:
            severity = 'LOW'
        else:
            severity = 'INFO'
        
        # Create merged alert
        return TransactionAlert(
            matter_id=alerts[0].matter_id,
            txn_id=alerts[0].txn_id,
            customer_id=alerts[0].customer_id,
            score=max_score,
            severity=severity,
            reasons=all_reasons,
            rule_tags=all_tags
        )
