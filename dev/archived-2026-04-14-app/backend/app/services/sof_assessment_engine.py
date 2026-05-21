"""
Source of Funds (SoF) Assessment Engine
UK Legal Sector - Business Purchase Matters

Free-text client explanations are extracted by an LLM (see
ai_claim_extractor — Anthropic by default, Gemini optional) when the
active provider's API key is configured; otherwise a fully local
deterministic parser is used. All other analysis — evidence matching,
scoring, transaction review — runs locally. Integrates with
Transaction Review for comprehensive AML assessment.
"""
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import re
import json
from decimal import Decimal

class SoFAssessmentEngine:
    """
    Automated SoF assessment engine for UK legal sector
    Analyzes client explanations against bank statement evidence
    Integrates with Transaction Review for holistic AML assessment
    """
    
    def __init__(self, matter_id: int, db: Session):
        self.matter_id = matter_id
        self.db = db
        self.settings = self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Load the operator-tunable risk-appetite settings from the
        transaction_config table, resolved for THIS matter's risk tier.

        Tiered settings (per-risk-tier values) are resolved against the
        matter's risk rating — critical/high matters get the High tier,
        etc. Falls back to sensible defaults if the table hasn't been
        seeded yet so the engine stays usable in unit tests."""
        defaults = {
            'sof_ai_extraction':             True,
            'sof_amount_tolerance_pct':       5.0,
            'sof_date_tolerance_days':        7,
            'sof_confidence_threshold':       0.999,
            'sof_partial_confidence_threshold': 0.99,
        }
        try:
            from app.models.transaction import TransactionConfig
            from app.models import Matter
            from app.services.config_resolver import map_risk_tier, resolve_value

            # Determine which risk tier's values apply to this matter.
            tier = 'medium'
            try:
                matter = self.db.query(Matter).filter(
                    Matter.id == self.matter_id
                ).first()
                if matter is not None:
                    rating = matter.risk_rating.value if matter.risk_rating else 'medium'
                    tier = map_risk_tier(rating)
            except Exception:
                tier = 'medium'
            self.risk_tier = tier

            rows = self.db.query(TransactionConfig).filter(
                TransactionConfig.key.in_(defaults.keys())
            ).all()
            out = dict(defaults)
            for row in rows:
                try:
                    out[row.key] = resolve_value(row.value, row.value_type, tier)
                except Exception:
                    pass  # keep default on a parse miss
            return out
        except Exception:
            self.risk_tier = 'medium'
            return defaults


    def assess(
        self,
        client_info: Dict[str, Any],
        purchase: Dict[str, Any],
        sof_explanation: str,
        bank_statements: List[Dict[str, Any]],
        known_documents: List[str] = None,
        supporting_docs_data: List[Dict[str, Any]] = None,
        constraints: Dict[str, Any] = None,
        flags: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main assessment method
        Returns structured JSON with claims, evidence, decision, and actions
        """
        from app.services.document_verifier import document_verifier
        
        # DEFENSIVE: Ensure all inputs are valid
        print(f"\n=== ASSESSMENT ENGINE INPUT DEBUG ===")
        print(f"client_info type: {type(client_info)}, value: {client_info}")
        print(f"purchase type: {type(purchase)}, value: {purchase}")
        print(f"sof_explanation type: {type(sof_explanation)}")
        print(f"bank_statements count: {len(bank_statements) if bank_statements else 0}")
        print(f"=====================================\n")
        
        # DEFENSIVE: Handle None or invalid client_info
        if client_info is None:
            print("⚠️ client_info is None, using defaults")
            client_info = {}
        
        if not isinstance(client_info, dict):
            print(f"⚠️ client_info is not a dict ({type(client_info)}), using defaults")
            client_info = {}
        
        # DEFENSIVE: Handle None or invalid purchase
        if purchase is None:
            print("⚠️ purchase is None, using defaults")
            purchase = {'amount': 0, 'currency': 'GBP'}
        
        if not isinstance(purchase, dict):
            print(f"⚠️ purchase is not a dict ({type(purchase)}), using defaults")
            purchase = {'amount': 0, 'currency': 'GBP'}
        
        # DEFENSIVE: Handle None sof_explanation
        if sof_explanation is None:
            print("⚠️ sof_explanation is None, using empty string")
            sof_explanation = ""
        
        # DEFENSIVE: Handle None bank_statements
        if bank_statements is None:
            print("⚠️ bank_statements is None, using empty list")
            bank_statements = []
        
        # Extract client risk rating with full defensive coding
        risk_rating = 'medium'  # Default
        if isinstance(client_info, dict) and client_info:
            risk_rating = client_info.get('client_risk_rating', 'medium')
            if risk_rating is None:
                risk_rating = 'medium'
            risk_rating = str(risk_rating).lower()
        
        print(f"✅ Risk rating: {risk_rating}")
        
        # Step 1: Parse SoF explanation into testable claims
        if isinstance(sof_explanation, dict):
            # Structured format with a sources array
            claims = self.parse_structured_sof(sof_explanation, purchase)
        else:
            # Free-text explanation — AI extraction with regex fallback
            claims = self.extract_claims_smart(str(sof_explanation), purchase)

        print(f"✅ Parsed {len(claims)} claims")

        # Attach the risk-tiered Source of Funds evidence checklist to
        # each claim — the documents the firm should obtain for that
        # source type, stricter for high-risk matters (LSAG §6.8).
        try:
            from app.services.sof_evidence_checklist import required_evidence
            _tier = getattr(self, 'risk_tier', 'medium')
            for _c in claims:
                _c['expected_evidence'] = required_evidence(
                    _c.get('source_type', ''), _tier
                )
        except Exception as _exc:
            print(f"[evidence-checklist] skipped: {_exc}")

        # Step 2: Find evidence in bank statements
        evidence_matches = self.match_evidence(claims, bank_statements)

        print(f"✅ Found {len(evidence_matches)} evidence matches")
        
        # Step 2.5: Verify supporting documents against claims (NEW!)
        document_verification = None
        if supporting_docs_data:
            print(f"\n=== DOCUMENT VERIFICATION DEBUG ===")
            print(f"Supporting docs received: {len(supporting_docs_data)}")
            for idx, doc in enumerate(supporting_docs_data):
                print(f"  Doc {idx}: {doc.get('document_type')} - extracted_data keys: {list(doc.get('extracted_data', {}).keys())}")
            print(f"Claims to verify: {len(claims)}")
            for idx, claim in enumerate(claims):
                print(f"  Claim {idx}: {claim['source_type']} £{claim['expected_amount']:,.0f}")
            
            document_verification = document_verifier.verify_documents_against_claims(
                claims=claims,
                supporting_docs=supporting_docs_data,
                bank_statements=bank_statements
            )
            
            # DEFENSIVE: Ensure document_verification is a valid dict
            if document_verification is None:
                print("⚠️ document_verification returned None, using empty structure")
                document_verification = {"verifications": [], "overall_verification_rate": 0.0, "missing_documents": []}
            
            print(f"Verification results: {len(document_verification.get('verifications', []))} verifications")
            for ver in document_verification.get('verifications', []):
                print(f"  Claim {ver['claim_id']}: verified={ver['verified']}, confidence={ver.get('confidence', 0):.2f}")
            print(f"====================================\n")
            
            # Enhance evidence_matches with document verification data
            print(f"\n=== UPDATING EVIDENCE MATCHES WITH DOC VERIFICATION ===")
            for verification in document_verification.get('verifications', []):
                claim_id = verification['claim_id']
                print(f"Claim {claim_id}: verified={verification.get('verified')}, confidence={verification.get('confidence')}")
                print(f"  verification_details keys: {list(verification.get('verification_details', {}).keys())}")
                print(f"  issues: {verification.get('issues', [])}")
                
                if claim_id < len(evidence_matches):
                    evidence_matches[claim_id]['document_verified'] = verification['verified']
                    evidence_matches[claim_id]['confidence'] = verification.get('confidence', 0.0)
                    evidence_matches[claim_id]['verification_details'] = verification.get('verification_details', {})
                    evidence_matches[claim_id]['issues'] = verification.get('issues', [])
                    evidence_matches[claim_id]['requires_review'] = verification.get('requires_review', False)
                    evidence_matches[claim_id]['review_reason'] = verification.get('review_reason')
                    evidence_matches[claim_id]['document_verification'] = verification
                    
                    # Also update match_quality based on document verification
                    if verification.get('verified') and verification.get('confidence', 0) >= 0.5:
                        if evidence_matches[claim_id].get('match_quality') == 'none':
                            evidence_matches[claim_id]['match_quality'] = 'document_verified'
                    
                    print(f"  Updated evidence_matches[{claim_id}]:")
                    print(f"    document_verified: {evidence_matches[claim_id]['document_verified']}")
                    print(f"    confidence: {evidence_matches[claim_id]['confidence']}")
                    print(f"    match_quality: {evidence_matches[claim_id].get('match_quality')}")
            print(f"======================================================\n")
        else:
            # No supporting documents uploaded - assessment can still proceed
            # but document verification will be incomplete
            print("\n=== NO SUPPORTING DOCUMENTS ===")
            print("Assessment will proceed with bank statement analysis only.")
            print("Document verification will show as incomplete.")
            print("================================\n")
            
            # Initialize document_verification with empty structure
            document_verification = {
                "verifications": [],
                "overall_verification_rate": 0.0,
                "missing_documents": ["No supporting documents uploaded"]
            }
            
            # Mark all evidence_matches as not document-verified
            for idx, match in enumerate(evidence_matches):
                match['document_verified'] = False
                match['confidence'] = 0.0
                match['verification_details'] = {}
                match['issues'] = ['No supporting documents uploaded for verification']
                match['requires_review'] = True
                match['review_reason'] = 'Supporting documents required'
                match['document_verification'] = {
                    'claim_id': idx,
                    'verified': False,
                    'confidence': 0.0,
                    'issues': ['No supporting documents uploaded'],
                    'requires_review': True,
                    'review_reason': 'Supporting documents required'
                }
        
        # Step 3: Trace funding paths
        funding_paths = self.trace_funding_paths(
            bank_statements, 
            purchase, 
            claims
        )
        
        # Step 4: Check date alignment
        date_alignment = self.check_date_alignment(
            claims,
            bank_statements,
            constraints
        )
        
        # Step 5: Get Transaction Review alerts (CRITICAL INTEGRATION)
        transaction_review_data = self.get_transaction_review_data()
        
        # Step 6: Identify red flags
        red_flags = self.identify_red_flags(
            bank_statements,
            claims,
            evidence_matches,
            flags or {},
            transaction_review_data
        )
        
        # Step 7: Make overall decision
        outcome = self.make_decision(
            risk_rating,
            claims,
            evidence_matches,
            funding_paths,
            red_flags,
            transaction_review_data,
            client_info=client_info,
            purchase=purchase
        )
        
        # Step 8: Generate next actions
        next_actions = self.generate_next_actions(
            risk_rating,
            claims,
            evidence_matches,
            red_flags,
            known_documents or [],
            transaction_review_data
        )
        
        # Step 9: Generate file note
        file_note = self.generate_file_note(
            client_info,
            purchase,
            claims,
            evidence_matches,
            funding_paths,
            red_flags,
            transaction_review_data,
            outcome,
            next_actions
        )
        
        return {
            "client_info": client_info,
            "purchase": purchase,
            "claims": claims,
            "evidence_matches": evidence_matches,
            "document_verification": document_verification,  # NEW: Document verification results
            "funding_paths": funding_paths,
            "date_alignment": date_alignment,
            "red_flags": red_flags,
            "transaction_review_summary": {
                **transaction_review_data.get('summary', {}),
                "alert_details": transaction_review_data.get('alerts', [])  # Include full alert objects
            },
            "outcome": outcome,
            "next_actions": next_actions,
            "file_note_summary": file_note,
            "assessment_date": datetime.now(timezone.utc).isoformat(),
            "matter_id": self.matter_id
        }
    
    # Source-of-funds lexicon. Each family is a list of REGEX patterns
    # (matched case-insensitively) so natural phrasing variations are
    # caught — "sold my previous house", "sold the flat", "sale of our
    # property" all hit the Property Sale family without needing an
    # exact-string entry for every wording. When an amount is near
    # keywords from two families the one physically closest wins, so
    # ordering only breaks exact-distance ties.
    _SOURCE_PATTERNS = [
        ('Inheritance',   [r'inherit(?:ed|ance|s|ing)?', r'\bprobate\b', r'\bbequest\b',
                           r'bequeath\w*', r'\blegacy\b', r'estate of', r'left (?:to )?me\b',
                           r'passed away', r'\bdeceased\b', r'the will of', r'my late \w+']),
        ('Property Sale', [r'sold (?:my |the |our |a )?(?:previous |former |old |current )?'
                           r'(?:house|home|flat|property|apartment|maisonette|bungalow|land)',
                           r'sale of (?:my |the |our |a )?(?:previous |former )?'
                           r'(?:house|home|flat|property|apartment|land)',
                           r'(?:house|flat|property|home|land) sale',
                           r'net proceeds', r'sale proceeds',
                           r'proceeds (?:of|from) (?:the )?sale',
                           r'completion statement', r'conveyanc\w*', r'previous property',
                           r'former home', r'disposal of (?:the |my )?propert\w+']),
        ('Business Sale', [r'sold (?:my |the |our )?(?:business|company|firm)',
                           r'sale of (?:my |the |our )?(?:business|company|firm)',
                           r'(?:business|company) sale',
                           r'sold (?:my |the |our )?shares', r'sale of shares',
                           r'disposal of (?:the |my )?compan\w+']),
        ('Gift',          [r'gift(?:ed|s)?\b', r'a gift from', r'given to me by',
                           r'donat\w+ to me']),
        ('Pension',       [r'\bpension\b', r'(?:tax[- ]free |retirement )?lump sum',
                           r'drawdown', r'annuity']),
        ('Compensation',  [r'compensation', r'\bsettlement\b', r'\bdamages\b',
                           r'redundancy']),
        ('Insurance',     [r'insurance (?:payout|claim|settlement)', r'life insurance',
                           r'(?:policy|endowment)(?: has)? matured',
                           r'matured (?:policy|endowment)', r'\bendowment\b']),
        ('Lottery',       [r'lottery', r'winnings', r'premium bond', r'jackpot']),
        ('Loan',          [r'\bmortgage\b', r'remortgage', r'bridging (?:finance|loan)',
                           r'credit facility', r'\bloan\b', r'borrowed']),
        ('Investment',    [r'investment\w*', r'\bshares\b', r'\bstocks\b', r'dividend\w*',
                           r'\bportfolio\b', r'mutual fund', r'\bbonds\b', r'crypto\w*',
                           r'\bisa\b']),
        ('Salary',        [r'\bsalary\b', r'\bwages\b', r'employment income', r'\bbonus\b',
                           r'\bearnings\b', r'remuneration', r'paid by my employer']),
        ('Savings',       [r'savings', r'\bsaved\b', r'accumulated', r'set aside',
                           r'put aside', r'put away', r'nest egg']),
    ]

    # Phrases that, when they precede an amount, mean "this is the net /
    # actual figure that reached the client" — preferred over a gross
    # headline price for the same source.
    _NET_PHRASES = [
        'net proceeds', 'net of', 'net amount', 'net figure', 'proceeds of',
        'proceeds from', 'received', 'totalling', 'totaling', 'amounting to',
        'after deduct', 'after fees', 'after the mortgage', 'after redemption',
        'left with', 'remaining',
    ]

    _UK_BANKS = ['barclays', 'hsbc', 'lloyds', 'natwest', 'santander', 'nationwide',
                 'rbs', 'halifax', 'bank of scotland', 'tesco bank', 'metro bank',
                 'monzo', 'starling', 'revolut', 'co-operative bank', 'tsb',
                 'first direct', 'virgin money']

    def _extract_money(self, text: str) -> List[Dict[str, Any]]:
        """Find money amounts in free text.

        Matches a £/GBP prefix OR a pounds/sterling/GBP suffix, with an
        optional k / m / thousand / million multiplier. Requiring an
        explicit currency marker keeps house numbers, postcodes, dates
        and percentages from being mistaken for amounts.

        Returns a list of {amount, start, end, raw}.
        """
        money_re = re.compile(
            r'(?:£|GBP\s?)(?P<a>[\d,]+(?:\.\d+)?)\s?(?P<am>k|m|bn|thousand|million|billion)?'
            r'|'
            r'(?P<b>[\d,]+(?:\.\d+)?)\s?(?P<bm>k|m|bn|thousand|million|billion)?'
            r'\s?(?:pounds?|sterling|gbp)\b',
            re.IGNORECASE,
        )
        mult = {'k': 1e3, 'thousand': 1e3, 'm': 1e6, 'million': 1e6,
                'bn': 1e9, 'billion': 1e9}
        out: List[Dict[str, Any]] = []
        for m in money_re.finditer(text):
            num = m.group('a') or m.group('b')
            if not num:
                continue
            suffix = (m.group('am') or m.group('bm') or '').lower()
            try:
                val = float(num.replace(',', ''))
            except ValueError:
                continue
            if suffix:
                val *= mult.get(suffix, 1)
            # Sub-£500 figures are almost always fees / noise, not a
            # source of funds for a property-scale matter.
            if val < 500:
                continue
            out.append({'amount': val, 'start': m.start(), 'end': m.end(),
                        'raw': m.group(0).strip()})
        return out

    def extract_claims_smart(
        self,
        text: str,
        purchase: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract claims from a free-text Source of Funds explanation.

        Prefers Google Gemini for extraction — the model understands
        paraphrasing, so the platform is not limited to an exact-phrase
        keyword bank and is far less likely to miss an unusually-worded
        source. Falls back to the deterministic regex parser when AI
        extraction is turned off in the Configuration page, when no
        Gemini API key is configured, or when the API call fails — so
        the assessment always produces a result.
        """
        if self.settings.get('sof_ai_extraction', True):
            try:
                from app.services import ai_claim_extractor as ace
                if ace.is_configured():
                    sources = ace.extract_sources(text)
                    if sources:
                        claims = self.parse_structured_sof(
                            {'sources': sources}, purchase
                        )
                        if claims:
                            print(f"✅ AI extracted {len(claims)} claim(s) "
                                  f"from free-text explanation")
                            return claims
                    # sources is None (API failure) or [] / unusable —
                    # fall through to the deterministic parser.
            except Exception as exc:
                print(f"[ai_extract] smart extraction unavailable — "
                      f"{type(exc).__name__}: {exc}")
        return self.parse_sof_claims(text, purchase)

    def parse_sof_claims(
        self,
        sof_explanation: str,
        purchase: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract testable claims from a free-text Source of Funds
        explanation.

        Real client narratives are prose, not structured data — e.g.
        "I sold my previous house for £425,000 with net proceeds of
        £269,280, and I also have £50k in personal savings." This
        parser anchors on every money amount, pairs each with the
        nearest declared source of funds, groups amounts by source,
        and — where a source quotes both a gross and a net figure —
        keeps the net (the money that actually reached the client).
        """
        claims: List[Dict[str, Any]] = []

        if not sof_explanation:
            print("⚠️ sof_explanation is empty or None")
            return claims
        if not purchase:
            purchase = {'currency': 'GBP', 'amount': 0}

        text = str(sof_explanation)
        lower = text.lower()
        currency = purchase.get('currency', 'GBP')

        money = self._extract_money(text)

        # All source-keyword hits across the text: (source_type, mid_pos).
        # Patterns are regexes so natural phrasing variants all match.
        kw_hits: List[Tuple[str, int]] = []
        for source_type, patterns in self._SOURCE_PATTERNS:
            for pat in patterns:
                for m in re.finditer(pat, lower):
                    kw_hits.append((source_type, (m.start() + m.end()) // 2))

        # Sentence/clause spans. An amount must pair with a keyword in
        # its OWN sentence first — otherwise an amount at the end of one
        # sentence ("...for £600,000.") wrongly grabs a keyword in the
        # next sentence ("My savings are £55,000.") just because it is
        # physically closer. Boundaries: . ; ! ? followed by whitespace,
        # or a newline. A decimal point inside a number is never
        # followed by whitespace, so "£1.5m" is left intact.
        clause_spans: List[Tuple[int, int]] = []
        pos = 0
        for m in re.finditer(r'[.;!?]\s+|\n+', text):
            clause_spans.append((pos, m.start()))
            pos = m.end()
        if pos < len(text):
            clause_spans.append((pos, len(text)))
        if not clause_spans:
            clause_spans = [(0, len(text))]

        def clause_index(p: int) -> int:
            for i, (s, e) in enumerate(clause_spans):
                if s <= p <= e:
                    return i
            return -1

        # Pair every amount with a source keyword — keywords in the
        # SAME sentence are always preferred; only when the amount's
        # sentence has none do we fall back to the nearest keyword
        # elsewhere (and only if it is reasonably close).
        paired: List[Dict[str, Any]] = []
        for mm in money:
            mid = (mm['start'] + mm['end']) // 2
            m_clause = clause_index(mid)
            same_sentence = [h for h in kw_hits if clause_index(h[1]) == m_clause]
            pool = same_sentence if same_sentence else kw_hits
            if not pool:
                continue
            best_source, best_pos = min(pool, key=lambda h: abs(h[1] - mid))
            # A cross-sentence fallback must be within ~one sentence.
            if not same_sentence and abs(best_pos - mid) > 200:
                continue
            paired.append({**mm, 'source_type': best_source})

        # Group amounts under their source type.
        by_source: Dict[str, List[Dict[str, Any]]] = {}
        for p in paired:
            by_source.setdefault(p['source_type'], []).append(p)

        def _is_net(item: Dict[str, Any]) -> bool:
            window = lower[max(0, item['start'] - 32):item['start']]
            return any(phrase in window for phrase in self._NET_PHRASES)

        claim_id = 1
        for source_type, items in by_source.items():
            # Prefer a net / proceeds / received figure; among those
            # take the smallest (net is post-deduction). Otherwise take
            # the largest amount mentioned for the source.
            net_items = [it for it in items if _is_net(it)]
            chosen = (min(net_items, key=lambda it: it['amount'])
                      if net_items else max(items, key=lambda it: it['amount']))

            date_range = self._extract_date_range(text, chosen['start'])
            cp_key = source_type.lower().replace(' ', '_')
            counterparty = self._extract_counterparty(text, chosen['start'], cp_key)

            expected_account = None
            for bank in self._UK_BANKS:
                if bank in lower:
                    expected_account = bank.title()
                    break

            start_pos = max(0, chosen['start'] - 160)
            end_pos = min(len(text), chosen['end'] + 160)
            ctx = text[start_pos:end_pos].strip()
            if start_pos > 0:
                ctx = "..." + ctx
            if end_pos < len(text):
                ctx = ctx + "..."

            claims.append({
                "claim_id": claim_id,
                "source_type": source_type,
                "expected_amount": chosen['amount'],
                "expected_currency": currency,
                "expected_date_range": date_range,
                "expected_payer": counterparty,
                "expected_account": expected_account,
                "claim_text": chosen['raw'],
                "description": ctx,
            })
            claim_id += 1

        # Sort the largest sources first so the headline claim leads.
        claims.sort(key=lambda c: c['expected_amount'], reverse=True)
        for idx, c in enumerate(claims, start=1):
            c['claim_id'] = idx

        # Nothing recognisable — fall back to a single generic claim so
        # the matter still produces a reviewable result.
        if not claims:
            claims.append({
                "claim_id": 1,
                "source_type": "Unspecified",
                "expected_amount": purchase.get('amount', 0),
                "expected_currency": currency,
                "expected_date_range": None,
                "expected_payer": None,
                "expected_account": None,
                "claim_text": "Source not clearly specified in explanation",
            })

        print(f"✅ parse_sof_claims extracted {len(claims)} claim(s) from free text")
        return claims
    
    def parse_structured_sof(
        self,
        sof_explanation: Dict[str, Any],
        purchase: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Parse structured SoF explanation (new format with sources array)
        """
        claims = []
        sources = sof_explanation.get('sources', [])
        
        for idx, source in enumerate(sources, start=1):
            claim = {
                "claim_id": idx,
                "source_type": source.get('source_type', 'unknown'),
                "expected_amount": float(source.get('amount', 0)),
                "currency": source.get('currency', 'GBP'),
                "description": source.get('description', ''),
                "expected_date_range": {},
                "expected_payer": None,
                "expected_account": None,
                "claim_text": source.get('description', '')
            }
            
            # Extract type-specific fields
            if source.get('source_type') == 'inheritance':
                claim['expected_payer'] = source.get('deceased_name')
                claim['probate_reference'] = source.get('probate_reference')
                if source.get('distribution_date'):
                    claim['expected_date_range'] = {
                        'start': source['distribution_date'],
                        'end': source['distribution_date']
                    }
            
            elif source.get('source_type') == 'property_sale':
                claim['property_address'] = source.get('property_address')
                claim['title_number'] = source.get('title_number')
                claim['solicitor_firm'] = source.get('solicitor_firm')
                if source.get('completion_date'):
                    claim['expected_date_range'] = {
                        'start': source['completion_date'],
                        'end': source['completion_date']
                    }
            
            elif source.get('source_type') == 'business_sale':
                claim['company_name'] = source.get('company_name')
                claim['company_number'] = source.get('company_number')
                claim['solicitor_firm'] = source.get('solicitor_firm')
                if source.get('completion_date'):
                    claim['expected_date_range'] = {
                        'start': source['completion_date'],
                        'end': source['completion_date']
                    }
            
            elif source.get('source_type') == 'business_loan':
                claim['expected_payer'] = source.get('lender')
                claim['loan_date'] = source.get('loan_date')
                if source.get('loan_date'):
                    claim['expected_date_range'] = {
                        'start': source['loan_date'],
                        'end': source['loan_date']
                    }
            
            elif source.get('source_type') == 'gift':
                claim['expected_payer'] = source.get('donor_name')
                claim['gift_date'] = source.get('gift_date')
                if source.get('gift_date'):
                    claim['expected_date_range'] = {
                        'start': source['gift_date'],
                        'end': source['gift_date']
                    }
            
            claims.append(claim)
        
        return claims
    
    def _extract_date_range(self, text: str, position: int) -> Optional[Dict[str, str]]:
        """Extract date range from text near position"""
        # Look 200 chars before and after
        snippet = text[max(0, position-200):min(len(text), position+200)]
        
        # Common date patterns
        date_patterns = [
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',  # DD/MM/YYYY
            r'(\d{4})[/-](\d{1,2})[/-](\d{1,2})',  # YYYY-MM-DD
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',  # Month Year
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'  # Mon Year
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.finditer(pattern, snippet, re.IGNORECASE)
            for match in matches:
                dates_found.append(match.group(0))
        
        if dates_found:
            # Simple heuristic: use first and last date as range
            if len(dates_found) >= 2:
                return {"start": dates_found[0], "end": dates_found[-1]}
            else:
                return {"start": dates_found[0], "end": dates_found[0]}
        
        return None
    
    def _extract_counterparty(
        self, 
        text: str, 
        position: int, 
        source_type: str
    ) -> Optional[str]:
        """Extract counterparty/payer from text"""
        snippet = text[max(0, position-150):min(len(text), position+150)]
        
        # Source-specific patterns
        if source_type == 'inheritance':
            patterns = [
                r'(?:from|estate of)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'(?:grandmother|grandfather|mother|father|aunt|uncle)\s+([A-Z][a-z]+ [A-Z][a-z]+)?'
            ]
        elif source_type == 'loan':
            patterns = [
                r'(?:from|lender)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)?(?:\s+Bank)?)'
            ]
        elif source_type in ['property_sale', 'business_sale']:
            patterns = [
                r'(?:buyer|purchaser)\s+([A-Z][a-z]+ [A-Z][a-z]+)',
                r'sold to\s+([A-Z][a-z]+ [A-Z][a-z]+)'
            ]
        else:
            patterns = [r'(?:from|by)\s+([A-Z][a-z]+ [A-Z][a-z]+)']
        
        for pattern in patterns:
            match = re.search(pattern, snippet)
            if match:
                return match.group(1).strip()
        
        return None
    
    def match_evidence(
        self,
        claims: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Find evidence in bank statements supporting each claim
        """
        evidence_matches = []
        
        for claim in claims:
            matches = []
            expected_amount = claim['expected_amount']
            # Tolerance comes from the Configuration page
            # (sof_amount_tolerance_pct, default 5%).
            tolerance_pct = float(self.settings.get('sof_amount_tolerance_pct', 5.0)) / 100.0
            tolerance = expected_amount * tolerance_pct
            
            # Filter to credit transactions
            credits = [t for t in bank_statements if t.get('direction') == 'credit']
            
            for txn in credits:
                txn_amount = txn.get('amount', 0)
                
                # Check amount match (within tolerance)
                if abs(txn_amount - expected_amount) <= tolerance:
                    match_quality = "exact" if txn_amount == expected_amount else "approximate"
                    
                    # Check counterparty match if specified
                    counterparty_match = False
                    if claim.get('expected_payer'):
                        payer_lower = claim['expected_payer'].lower()
                        desc_lower = txn.get('description', '').lower()
                        counterparty_lower = txn.get('counterparty_name', '').lower()
                        
                        if payer_lower in desc_lower or payer_lower in counterparty_lower:
                            counterparty_match = True
                            match_quality = "strong"
                    
                    matches.append({
                        "account_id": txn.get('account_id'),
                        "date": txn.get('date'),
                        "amount": txn.get('amount'),
                        "currency": txn.get('currency', 'GBP'),
                        "direction": txn.get('direction'),
                        "description": txn.get('description'),
                        "counterparty": txn.get('counterparty_name'),
                        "balance": txn.get('balance'),
                        "match_quality": match_quality,
                        "counterparty_match": counterparty_match
                    })
            
            evidence_matches.append({
                "claim_id": claim['claim_id'],
                "claim_source": claim.get('source_type', 'Unknown'),
                "expected_amount": claim.get('expected_amount', 0),
                "match_quality": "strong" if any(m['match_quality'] == 'strong' for m in matches) else 
                                "exact" if matches else "none",
                "transactions": matches,
                "verified": len(matches) > 0,
                "document_verified": False,  # Initialize to False, will be set to True if docs verify
                "document_verification": None  # Will be populated if docs are provided
            })
        
        return evidence_matches
    
    def trace_funding_paths(
        self,
        bank_statements: List[Dict[str, Any]],
        purchase: Dict[str, Any],
        claims: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Attempt to trace funds from sources to purchase payment
        """
        paths = []
        purchase_amount = purchase.get('amount', 0)
        purchase_date = purchase.get('expected_payment_date')
        
        # Group transactions by account
        accounts = {}
        for txn in bank_statements:
            acc_id = txn.get('account_id', 'Unknown')
            if acc_id not in accounts:
                accounts[acc_id] = []
            accounts[acc_id].append(txn)
        
        # Sort each account by date
        for acc_id in accounts:
            accounts[acc_id].sort(key=lambda x: x.get('date', ''))
        
        # Simple heuristic: find large credits, then check if balance/transfers support purchase
        large_credits = [
            t for t in bank_statements 
            if t.get('direction') == 'credit' and t.get('amount', 0) > purchase_amount * 0.1
        ]
        
        if large_credits:
            # Build a plausible path
            path_steps = []
            total_traced = 0
            
            for credit in large_credits[:3]:  # Top 3 credits
                path_steps.append(
                    f"£{credit['amount']:,.2f} received into {credit.get('account_id', 'account')} "
                    f"on {credit.get('date', 'unknown date')}"
                )
                total_traced += credit['amount']
                
                if total_traced >= purchase_amount:
                    break
            
            # Check for transfers between accounts
            transfers = [
                t for t in bank_statements
                if t.get('direction') == 'debit' and 
                   'transfer' in t.get('description', '').lower() and
                   t.get('amount', 0) > purchase_amount * 0.1
            ]
            
            for transfer in transfers[:2]:
                path_steps.append(
                    f"£{transfer['amount']:,.2f} transferred from {transfer.get('account_id', 'account')} "
                    f"on {transfer.get('date', 'unknown date')}"
                )
            
            # Calculate coverage
            coverage = min(100, int((total_traced / purchase_amount) * 100))
            
            paths.append({
                "path_id": 1,
                "description": " → ".join([c.get('account_id', 'Account') for c in large_credits[:2]]) + " → Purchase",
                "steps": path_steps,
                "total_traced": total_traced,
                "purchase_amount": purchase_amount,
                "coverage": coverage,
                "plausible": coverage >= 80
            })
        else:
            # No clear path
            paths.append({
                "path_id": 1,
                "description": "Unable to trace clear funding path",
                "steps": ["No large credits identified that match purchase amount"],
                "total_traced": 0,
                "purchase_amount": purchase_amount,
                "coverage": 0,
                "plausible": False
            })
        
        return paths
    
    def check_date_alignment(
        self,
        claims: List[Dict[str, Any]],
        bank_statements: List[Dict[str, Any]],
        constraints: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check if statement periods cover claimed receipt periods
        """
        # Get statement date range
        dates = [t.get('date') for t in bank_statements if t.get('date')]
        if not dates:
            return {
                "statement_coverage": None,
                "claimed_receipt_period": None,
                "coverage_adequate": False,
                "gaps": ["No transaction dates available"]
            }
        
        dates.sort()
        stmt_start = dates[0]
        stmt_end = dates[-1]
        
        # Get claimed date ranges
        claimed_ranges = [
            c.get('expected_date_range') 
            for c in claims 
            if c.get('expected_date_range')
        ]
        
        coverage_adequate = True
        gaps = []
        
        if claimed_ranges:
            # Check if statements cover claimed periods
            for claim_range in claimed_ranges:
                claim_start = claim_range.get('start')
                claim_end = claim_range.get('end')
                
                # Simple string comparison (assuming ISO dates)
                if claim_start and claim_start < stmt_start:
                    gaps.append(
                        f"Statements start {stmt_start} but claim mentions {claim_start}"
                    )
                    coverage_adequate = False
                
                if claim_end and claim_end > stmt_end:
                    gaps.append(
                        f"Statements end {stmt_end} but claim mentions {claim_end}"
                    )
                    coverage_adequate = False
        
        # Check for unexplained large credits outside claimed periods
        # (implementation detail - would need date parsing)
        
        return {
            "statement_coverage": {
                "start": stmt_start,
                "end": stmt_end
            },
            "claimed_receipt_period": claimed_ranges[0] if claimed_ranges else None,
            "coverage_adequate": coverage_adequate,
            "gaps": gaps if gaps else []
        }
    
    def get_transaction_review_data(self) -> Dict[str, Any]:
        """
        CRITICAL: Get Transaction Review alerts for this matter
        This integrates AML monitoring findings into SoF assessment
        
        NEW: Analyzes bank statements directly for AML risks when TransactionAlert table is empty
        - Sanctioned countries: IR, KP, SY, CU → CRITICAL
        - Large cash (≥£10k) → HIGH
        """
        from app.models import TransactionAlert, Transaction
        
        # Check if database connection is available
        alerts = []
        if self.db:
            alerts = self.db.query(TransactionAlert).filter(
                TransactionAlert.matter_id == self.matter_id
            ).all()
        
        # If no alerts in database, analyze bank statements directly
        if not alerts:
            # Load bank statements from DB
            from app.models.assessment_storage import AssessmentStorage
            matter_storage = None
            if self.db:
                _as_row = self.db.query(AssessmentStorage).filter(
                    AssessmentStorage.matter_id == self.matter_id
                ).first()
                matter_storage = _as_row.data if _as_row and _as_row.data else None

            if matter_storage and matter_storage.get('bank_statements'):
                bank_statements = matter_storage['bank_statements']

                # Analyze for AML risks - SYNCHRONIZED WITH TRANSACTION REVIEW ENDPOINT
                # Sanctioned countries that trigger CRITICAL alerts
                sanctioned_countries = ['IR', 'KP', 'SY', 'CU', 'VE', 'RU', 'BY', 'AF']
                # High-risk countries that trigger HIGH alerts
                high_risk_countries = ['PK', 'MM', 'YE', 'LY', 'SO', 'SD', 'SS', 'IQ', 'LB', 'ZW']

                # Country name mappings
                country_names = {
                    'IR': 'Iran', 'KP': 'North Korea', 'SY': 'Syria', 'CU': 'Cuba',
                    'VE': 'Venezuela', 'RU': 'Russia', 'BY': 'Belarus', 'AF': 'Afghanistan',
                    'PK': 'Pakistan', 'MM': 'Myanmar', 'YE': 'Yemen', 'LY': 'Libya',
                    'SO': 'Somalia', 'SD': 'Sudan', 'SS': 'South Sudan', 'IQ': 'Iraq',
                    'LB': 'Lebanon', 'ZW': 'Zimbabwe'
                }

                key_concerns = []
                alert_objects = []  # Create actual alert objects for questions
                sanctions_count = 0
                cash_count = 0
                high_risk_count = 0

                for stmt in bank_statements:
                    country = stmt.get('country_iso2', '').upper() if stmt.get('country_iso2') else ''
                    channel = stmt.get('channel', '')
                    # Ensure amount is a float for comparison
                    try:
                        amount = float(stmt.get('amount', 0))
                    except (ValueError, TypeError):
                        amount = 0.0
                    date = stmt.get('date', '')
                    direction = stmt.get('direction', 'credit')
                    description = stmt.get('description', 'Unknown transaction')
                    counterparty = stmt.get('counterparty', 'Unknown')

                    # Check for sanctioned countries
                    if country in sanctioned_countries:
                        sanctions_count += 1
                        country_display = country_names.get(country, country)
                        alert_objects.append({
                            "severity": "CRITICAL",
                            "score": 100,
                            "reasons": [f"Transaction to sanctioned jurisdiction: {country_display}",
                                       "UK/EU sanctions regulations apply",
                                       "Immediate review and enhanced due diligence required"],
                            "transaction": {
                                "id": f"BANK-{self.matter_id}-{date}",
                                "amount": amount,
                                "currency": "GBP",
                                "country": country,
                                "date": date,
                                "narrative": description
                            }
                        })

                    # Check for high-risk countries
                    elif country in high_risk_countries:
                        high_risk_count += 1
                        country_display = country_names.get(country, country)
                        alert_objects.append({
                            "severity": "HIGH",
                            "score": 80,
                            "reasons": [f"Transaction to high-risk jurisdiction: {country_display}",
                                       "Enhanced due diligence recommended"],
                            "transaction": {
                                "id": f"BANK-{self.matter_id}-{date}",
                                "amount": amount,
                                "currency": "GBP",
                                "country": country,
                                "date": date,
                                "narrative": description
                            }
                        })

                    # Check for large cash transactions - detect from narrative or channel
                    narrative_upper = description.upper() if description else ''
                    is_cash_deposit = any(term in narrative_upper for term in [
                        'CASH DEPOSIT', 'CASH DEP', 'BRANCH DEPOSIT', 'COUNTER DEPOSIT', 'CASH PAID IN'
                    ])
                    is_cash_withdrawal = any(term in narrative_upper for term in [
                        'CASH WITHDRAWAL', 'CASH W/D', 'ATM WITHDRAWAL', 'CASH - ATM', 'ATM CASH',
                        'WITHDRAWAL - ATM', 'ATM W/D'
                    ]) or ('CASH' in narrative_upper and 'WITHDRAWAL' in narrative_upper) or \
                       ('ATM' in narrative_upper and direction in ('out', 'debit'))

                    cash_threshold = 7500  # £7,500 threshold
                    is_cash = channel == 'cash' or is_cash_deposit or is_cash_withdrawal

                    if is_cash and amount >= cash_threshold:
                        cash_count += 1
                        cash_type = 'deposit' if is_cash_deposit or direction in ('in', 'credit') else 'withdrawal'
                        alert_objects.append({
                            "severity": "HIGH",
                            "score": 75,
                            "reasons": [
                                f"Large cash {cash_type} exceeds £{cash_threshold:,} threshold",
                                f"Amount: £{amount:,.2f}",
                                f"Cash transactions over threshold require source verification"
                            ],
                            "transaction": {
                                "id": f"BANK-{self.matter_id}-{date}",
                                "amount": amount,
                                "currency": "GBP",
                                "country": country or "GB",
                                "date": date,
                                "narrative": description
                            }
                        })

                if sanctions_count > 0:
                    key_concerns.append(f"{sanctions_count} transaction(s) involving prohibited/sanctioned jurisdictions")
                if high_risk_count > 0:
                    key_concerns.append(f"{high_risk_count} transaction(s) involving high-risk jurisdictions")
                if cash_count > 0:
                    key_concerns.append(f"{cash_count} large cash transaction(s) identified")

                total_alerts = sanctions_count + high_risk_count + cash_count

                if total_alerts > 0:
                    return {
                        "summary": {
                            "total_alerts": total_alerts,
                            "critical_alerts": sanctions_count,
                            "high_alerts": high_risk_count + cash_count,
                            "medium_alerts": 0,
                            "key_concerns": key_concerns
                        },
                        "alerts": alert_objects  # Now includes actual alert objects for questions
                    }

            # No alerts and no bank statement risks
            return {
                "summary": {
                    "total_alerts": 0,
                    "critical_alerts": 0,
                    "high_alerts": 0,
                    "medium_alerts": 0,
                    "key_concerns": []
                },
                "alerts": []
            }
        
        # Count by severity
        critical = sum(1 for a in alerts if a.severity == 'CRITICAL')
        high = sum(1 for a in alerts if a.severity == 'HIGH')
        medium = sum(1 for a in alerts if a.severity == 'MEDIUM')
        
        # Extract key concerns
        key_concerns = []
        sanctions_count = sum(1 for a in alerts if any('sanction' in r.lower() or 'prohibited' in r.lower() for r in a.reasons))
        cash_count = sum(1 for a in alerts if any('cash' in r.lower() for r in a.reasons))
        structuring_count = sum(1 for a in alerts if any('structur' in r.lower() for r in a.reasons))
        
        if sanctions_count > 0:
            key_concerns.append(f"{sanctions_count} transaction(s) involving prohibited/sanctioned jurisdictions")
        if cash_count > 0:
            key_concerns.append(f"{cash_count} suspicious cash deposit(s) identified")
        if structuring_count > 0:
            key_concerns.append(f"{structuring_count} potential structuring pattern(s) detected")
        
        # Build alert details
        alert_details = []
        for alert in alerts[:10]:  # Top 10 most severe
            txn = self.db.query(Transaction).filter(Transaction.id == alert.txn_id).first()
            alert_details.append({
                "alert_id": alert.id,
                "severity": alert.severity,
                "score": alert.score,
                "reasons": alert.reasons if isinstance(alert.reasons, list) else [],
                "transaction": {
                    "id": alert.txn_id,
                    "amount": txn.amount if txn else 0,
                    "currency": txn.currency if txn else 'GBP',
                    "country": txn.country_iso2 if txn else None,
                    "date": txn.txn_date.isoformat() if txn else None,
                    "narrative": txn.narrative if txn else None
                }
            })
        
        return {
            "summary": {
                "total_alerts": len(alerts),
                "critical_alerts": critical,
                "high_alerts": high,
                "medium_alerts": medium,
                "key_concerns": key_concerns
            },
            "alerts": alert_details
        }
    
    def identify_red_flags(
        self,
        bank_statements: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        flags: Dict[str, Any],
        transaction_review_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Identify red flags including Transaction Review alerts
        """
        red_flags = []
        
        # 1. Add Transaction Review CRITICAL and HIGH alerts as red flags
        tr_alerts = transaction_review_data.get('alerts', [])
        for alert in tr_alerts:
            if alert['severity'] in ['CRITICAL', 'HIGH']:
                # Handle both new format (flat fields) and old format (nested transaction object)
                if 'transaction' in alert:
                    # Old format from database
                    amount = alert['transaction']['amount']
                    date = alert['transaction']['date']
                    txn_id = alert['transaction']['id']
                    alert_id = alert.get('alert_id')
                else:
                    # New format from direct bank statement analysis
                    amount = alert['amount']
                    date = alert['date']
                    txn_id = None
                    alert_id = None
                
                red_flags.append({
                    "severity": alert['severity'],
                    "source": "TRANSACTION_REVIEW",
                    "flag": f"{alert['reasons'][0] if alert['reasons'] else 'AML alert'} - "
                           f"£{amount:,.2f} on {date}",
                    "transaction_ref": txn_id,
                    "alert_id": alert_id,
                    "details": alert['reasons']
                })
        
        # 2. Unmatched claims
        for i, evidence in enumerate(evidence_matches):
            if not evidence['verified']:
                claim = claims[i]
                red_flags.append({
                    "severity": "HIGH",
                    "source": "SoF_ANALYSIS",
                    "flag": f"No evidence found for claimed {claim['source_type']} of "
                           f"£{claim['expected_amount']:,.2f}",
                    "claim_id": claim['claim_id']
                })
        
        # 3. Large unexplained credits
        explained_amounts = set()
        for evidence in evidence_matches:
            for txn in evidence['transactions']:
                explained_amounts.add((txn['date'], txn['amount']))
        
        large_threshold = 10000  # £10k
        for txn in bank_statements:
            if txn.get('direction') == 'credit' and txn.get('amount', 0) > large_threshold:
                if (txn.get('date'), txn.get('amount')) not in explained_amounts:
                    red_flags.append({
                        "severity": "MEDIUM",
                        "source": "SoF_ANALYSIS",
                        "flag": f"Large unexplained credit of £{txn['amount']:,.2f} on {txn.get('date')} "
                               f"in {txn.get('account_id', 'account')}",
                        "transaction_ref": f"{txn.get('account_id')}-{txn.get('date')}"
                    })
        
        # 4. Cash deposits
        cash_keywords = ['cash', 'deposit', 'atm deposit']
        for txn in bank_statements:
            desc = txn.get('description', '').lower()
            if txn.get('direction') == 'credit' and any(kw in desc for kw in cash_keywords):
                if txn.get('amount', 0) > 5000:  # £5k threshold
                    red_flags.append({
                        "severity": "MEDIUM",
                        "source": "SoF_ANALYSIS",
                        "flag": f"Cash deposit of £{txn['amount']:,.2f} on {txn.get('date')}",
                        "transaction_ref": f"{txn.get('account_id')}-{txn.get('date')}"
                    })
        
        # 5. PEP flag
        if flags.get('pep'):
            red_flags.append({
                "severity": "HIGH",
                "source": "CLIENT_FLAGS",
                "flag": "Client is a Politically Exposed Person (PEP) - enhanced due diligence required"
            })
        
        # 6. High-risk jurisdictions
        if flags.get('high_risk_jurisdictions'):
            for txn in bank_statements:
                # Check if any transaction involves these jurisdictions
                # (would need more detailed transaction data)
                pass
        
        # Sort by severity
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        red_flags.sort(key=lambda x: severity_order.get(x['severity'], 4))
        
        return red_flags
    
    def make_decision(
        self,
        risk_rating: str,
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        funding_paths: List[Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        transaction_review_data: Dict[str, Any],
        client_info: Dict[str, Any] = None,
        purchase: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Make overall risk decision considering all factors
        Now properly considers BOTH bank transaction matches AND document verification
        AND requires 100% confidence for full verification
        """
        # Count verified claims - must have:
        # 1. Bank match (verified=True)
        # 2. Document verification (document_verified=True)  
        # 3. 100% confidence (no issues found)
        verified_claims = sum(
            1 for e in evidence_matches 
            if e.get('verified', False) 
            and e.get('document_verified', False)
            and e.get('document_verification', {}).get('confidence', 0) >= 1.0
        )
        total_claims = len(claims)
        verification_rate = verified_claims / total_claims if total_claims > 0 else 0
        
        # Check funding coverage
        best_coverage = max([p['coverage'] for p in funding_paths], default=0)
        
        # Count red flags by severity
        critical_flags = sum(1 for f in red_flags if f['severity'] == 'CRITICAL')
        high_flags = sum(1 for f in red_flags if f['severity'] == 'HIGH')
        
        # Transaction Review integration - CRITICAL impact
        tr_summary = transaction_review_data.get('summary', {})
        tr_critical = tr_summary.get('critical_alerts', 0)
        tr_high = tr_summary.get('high_alerts', 0)
        
        # Base confidence score
        confidence = 50
        
        # Adjust for claim verification
        confidence += int(verification_rate * 30)
        
        # Adjust for funding coverage
        confidence += int(best_coverage * 0.2)
        
        # Penalize for red flags
        confidence -= (critical_flags * 30)
        confidence -= (high_flags * 15)
        
        # Transaction Review penalties - SEVERE impact
        if tr_critical > 0:
            confidence = min(confidence, 40)  # Cap at 40% if CRITICAL alerts exist
        if tr_high > 0:
            confidence -= (tr_high * 10)
        
        # Adjust for risk rating
        if risk_rating == 'high':
            confidence -= 10
        elif risk_rating == 'low':
            confidence += 10
        
        # Clamp confidence
        confidence = max(0, min(100, confidence))
        
        # Determine status
        if confidence >= 80 and critical_flags == 0 and tr_critical == 0:
            status = "sufficient"
        elif confidence >= 50 and critical_flags == 0 and tr_critical == 0:
            status = "borderline"
        else:
            status = "insufficient"
        
        # Build structured, detailed rationale
        rationale = self._build_detailed_rationale(
            verified_claims=verified_claims,
            total_claims=total_claims,
            best_coverage=best_coverage,
            evidence_matches=evidence_matches,
            claims=claims,
            funding_paths=funding_paths,
            tr_summary=tr_summary,
            tr_critical=tr_critical,
            tr_high=tr_high,
            critical_flags=critical_flags,
            high_flags=high_flags,
            status=status,
            red_flags=red_flags,
            client_info=client_info,
            purchase=purchase
        )
        
        return {
            "status": status,
            "confidence": confidence,
            "rationale": rationale
        }
    
    def _build_detailed_rationale(
        self,
        verified_claims: int,
        total_claims: int,
        best_coverage: int,
        evidence_matches: List[Dict[str, Any]],
        claims: List[Dict[str, Any]],
        funding_paths: List[Dict[str, Any]],
        tr_summary: Dict[str, Any],
        tr_critical: int,
        tr_high: int,
        critical_flags: int,
        high_flags: int,
        status: str,
        red_flags: List[Dict[str, Any]],
        client_info: Dict[str, Any] = None,
        purchase: Dict[str, Any] = None
    ) -> str:
        """
        Build detailed, structured rationale with sections and tables
        """
        sections = []
        
        # ============================================================
        # CLIENT INFORMATION HEADER
        # ============================================================
        if client_info and purchase:
            client_section = ["=== CLIENT INFORMATION ==="]
            client_section.append(f"Client Name: {client_info.get('client_name', 'Not provided')}")
            client_section.append(f"Risk Rating: {client_info.get('client_risk_rating', 'Not specified').upper()}")
            client_section.append(f"Business Sector: {client_info.get('business_sector', 'Not specified')}")
            client_section.append(f"PEP Status: {'Yes' if client_info.get('is_pep', False) else 'No'}")
            client_section.append(f"Purchase Amount: £{purchase.get('amount', 0):,.2f} {purchase.get('currency', 'GBP')}")
            client_section.append(f"Purchase Description: {purchase.get('description', 'Not specified')}")
            client_section.append(f"Expected Payment Date: {purchase.get('expected_payment_date', 'Not specified')}")
            client_section.append("")  # Empty line
            sections.append("\n".join(client_section))
        
        # ============================================================
        # SECTION 1: SOURCE OF FUNDS ANALYSIS
        # ============================================================
        sof_section = ["=== SOURCE OF FUNDS ANALYSIS ===\n"]
        
        # Overall funding status
        # Count how many claims have BOTH bank and document verification AND 100% confidence
        fully_verified = sum(
            1 for e in evidence_matches 
            if e.get('verified') 
            and e.get('document_verified')
            and e.get('confidence', 0) >= self.settings.get('sof_confidence_threshold', 0.999)
        )
        total_claims = len(claims)
        
        if best_coverage >= 90:
            if fully_verified == total_claims:
                # ALL claims have both bank AND document verification
                sof_section.append(
                    f"✅ BANK PAYMENT STATUS: Incoming payments found covering {best_coverage}% of purchase amount.\n"
                    f"✅ DOCUMENTATION STATUS: All claims verified with supporting documents.\n"
                    f"   ✅ FULLY VERIFIED: Bank transactions and source documents confirm all {total_claims} claims.\n"
                )
            elif fully_verified > 0:
                # SOME claims have both
                sof_section.append(
                    f"✅ BANK PAYMENT STATUS: Incoming payments found covering {best_coverage}% of purchase amount.\n"
                    f"⚠️ DOCUMENTATION STATUS: {fully_verified}/{total_claims} claims verified with documents.\n"
                    f"   Additional source documents REQUIRED for remaining {total_claims - fully_verified} claims.\n"
                )
            else:
                # NO documents verified yet
                sof_section.append(
                    f"✅ BANK PAYMENT STATUS: Incoming payments found covering {best_coverage}% of purchase amount.\n"
                    f"⚠️ DOCUMENTATION STATUS: Corroborating source documents REQUIRED to prove legitimacy.\n"
                    f"   Bank payments alone are INSUFFICIENT for AML compliance.\n"
                )
        elif best_coverage >= 70:
            sof_section.append(
                f"⚠️ BANK PAYMENT STATUS: Partial payments traced ({best_coverage}% coverage). Gaps identified.\n"
                f"⚠️ DOCUMENTATION STATUS: Source documents REQUIRED for all claims.\n"
            )
        else:
            sof_section.append(
                f"❌ BANK PAYMENT STATUS: Insufficient payments traced ({best_coverage}% coverage). Material gaps exist.\n"
                f"❌ DOCUMENTATION STATUS: Source documents REQUIRED for all claims.\n"
            )
        
        # Claim-by-claim table
        sof_section.append("\nCLAIM-BY-CLAIM ANALYSIS:\n")
        sof_section.append("-" * 120 + "\n")
        sof_section.append(f"{'CLAIM':<25} | {'EVIDENCE FOUND':<35} | {'OUTREACH QUESTIONS':<30} | {'SUMMARY':<20}\n")
        sof_section.append("-" * 120 + "\n")
        
        for i, evidence in enumerate(evidence_matches):
            claim = claims[i]
            claim_name = f"{evidence['claim_source']} £{evidence['expected_amount']:,.0f}"
            
            # Check for document verification first
            doc_verified = evidence.get('document_verified', False)
            doc_verification = evidence.get('document_verification', {})
            
            # Evidence found - check both bank transactions AND document verification
            evidence_parts = []
            
            # Bank transaction evidence
            if evidence['verified'] and evidence['transactions']:
                txn = evidence['transactions'][0]
                evidence_parts.append(f"✅ Bank: {txn['date']}: £{txn['amount']:,.0f}")
                if len(evidence['transactions']) > 1:
                    evidence_parts[-1] += f" (+{len(evidence['transactions'])-1})"
            else:
                evidence_parts.append("❌ No bank transaction")
            
            # Document verification evidence - check if document exists, not just if fully verified
            doc_details = doc_verification.get('verification_details', {})
            document_used = doc_details.get('document_used', {})
            has_document = bool(document_used.get('filename'))
            
            if has_document:
                doc_filename = document_used.get('filename', 'Doc')
                doc_confidence = doc_verification.get('confidence', 0)
                issues = doc_verification.get('issues', [])
                
                # Shorten filename for display (show first 20 chars + extension)
                if len(doc_filename) > 25:
                    doc_filename = doc_filename[:20] + '...' + doc_filename[-5:]
                
                if doc_verified:
                    evidence_parts.append(f"✅ Doc: {doc_filename}")
                else:
                    # Document uploaded but has issues
                    confidence_pct = int(doc_confidence * 100)
                    evidence_parts.append(f"⚠️ Doc: {doc_filename} ({confidence_pct}%)")
            else:
                evidence_parts.append("❌ No doc")
            
            evidence_text = " | ".join(evidence_parts)
            
            # Outreach questions - based on verification status
            if doc_verified:
                # Document is fully verified
                outreach = "✅ Verified"
            elif has_document:
                # Document provided but has issues
                issues = doc_verification.get('issues', [])
                if issues:
                    # Show the first issue
                    first_issue = issues[0]
                    if "distribution" in first_issue.lower() or "amount" in first_issue.lower():
                        outreach = "Verify amount in document"
                    elif "date" in first_issue.lower():
                        outreach = "Verify date in document"
                    else:
                        outreach = f"Review: {first_issue[:20]}..."
                else:
                    outreach = "Review document details"
            else:
                # Still need documents
                if 'inheritance' in evidence['claim_source'].lower():
                    outreach = "Request probate grant"
                elif 'property' in evidence['claim_source'].lower():
                    outreach = "Request completion statement"
                elif 'loan' in evidence['claim_source'].lower():
                    outreach = "Request loan agreement"
                elif 'business' in evidence['claim_source'].lower():
                    outreach = "Request sale agreement"
                elif 'savings' in evidence['claim_source'].lower():
                    outreach = "Request historical statements"
                elif 'investment' in evidence['claim_source'].lower():
                    outreach = "Request investment statements"
                else:
                    outreach = "Request source documentation"
            
            # Summary - more accurate based on verification
            if doc_verified and evidence['verified']:
                summary = "✅ VERIFIED"
            elif doc_verified and not evidence['verified']:
                summary = "⚠️ Doc OK, no bank txn"
            elif evidence['verified'] and has_document and not doc_verified:
                # Bank txn found, doc provided but not fully verified
                summary = "⚠️ Review doc"
            elif evidence['verified'] and not has_document:
                # Bank txn found but no document
                summary = "⚠️ Bank txn, need doc"
            elif has_document and not evidence['verified']:
                # Doc provided but no bank txn
                summary = "⚠️ Doc, no bank txn"
            else:
                summary = "❌ MISSING"
            
            sof_section.append(f"{claim_name:<25} | {evidence_text:<35} | {outreach:<30} | {summary:<20}\n")
        
        sof_section.append("-" * 120 + "\n")
        
        # SoF Summary
        sof_section.append("\nSOURCE OF FUNDS SUMMARY:\n")
        
        # Count fully verified claims (both bank + docs)
        fully_verified_count = sum(
            1 for e in evidence_matches 
            if e.get('verified') 
            and e.get('document_verified')
            and e.get('confidence', 0) >= self.settings.get('sof_confidence_threshold', 0.999)
        )
        
        if fully_verified_count == total_claims:
            # ALL claims have both bank AND documents
            sof_section.append(
                f"✅ All {total_claims} SoF claims have matching bank statement evidence.\n"
                f"✅ All {total_claims} SoF claims have supporting document verification.\n"
                f"✅ FULLY VERIFIED: Both bank transactions and source documents confirm all claims.\n\n"
                f"The source of funds has been thoroughly verified with:\n"
                f"  • Bank statement evidence showing receipt of funds\n"
                f"  • Supporting documents proving legitimacy and lawful origin\n"
                f"  • Complete audit trail connecting funds to their claimed source\n\n"
                f"AML compliance requirements for source documentation have been met.\n"
            )
        elif verified_claims == total_claims and fully_verified_count < total_claims:
            # All have bank, but not all have documents
            sof_section.append(
                f"✅ All {total_claims} SoF claims have matching bank statement evidence. "
                f"However, bank statements alone are INSUFFICIENT for regulatory compliance.\n\n"
                f"⚠️ IMPORTANT: Incoming payments verify that funds were received, but do NOT prove "
                f"the legitimacy or lawful origin of those funds. Source documentation (e.g., probate "
                f"grants, completion statements, loan agreements) is REQUIRED to demonstrate:\n"
                f"  • The stated source is genuine and legitimate\n"
                f"  • The client has lawful entitlement to the funds\n"
                f"  • There is an audit trail connecting the funds to their claimed origin\n\n"
                f"The matter CANNOT proceed until appropriate corroborating documents are provided.\n"
            )
        elif verified_claims > 0:
            verified_list = [e['claim_source'] for e in evidence_matches if e['verified']]
            unverified_list = [e['claim_source'] for e in evidence_matches if not e['verified']]
            
            sof_section.append(
                f"⚠️ Partial verification achieved: {verified_claims}/{total_claims} claims have matching bank transactions.\n\n"
                f"⚠️ IMPORTANT: Bank statements show incoming payments but do NOT prove legitimacy. "
                f"Source documents are REQUIRED for all claims to demonstrate lawful origin.\n\n"
                f"VERIFIED CLAIMS (bank payments found): {', '.join(verified_list)}\n"
                f"These claims have matching bank transactions, but still require corroborating documents "
                f"(e.g., probate grants, completion statements) to prove legitimacy and lawful entitlement.\n\n"
                f"UNVERIFIED CLAIMS (no bank payments found): {', '.join(unverified_list)}\n"
            )
            
            if best_coverage >= 90:
                sof_section.append(
                    f"While these claims lack direct transaction evidence, sufficient alternative incoming "
                    f"payments have been identified to cover the full purchase amount. This suggests the "
                    f"unverified sources may have been received before the statement period or through "
                    f"different accounts. Direct documentation is recommended to complete the audit trail, "
                    f"though the overall funding position is mathematically sufficient.\n"
                )
            else:
                sof_section.append(
                    f"These unverified claims represent material funding gaps. Without supporting evidence, "
                    f"we cannot confirm the source of approximately £{(evidence_matches[0]['expected_amount'] * (total_claims - verified_claims)):,.0f}. "
                    f"This is a regulatory compliance concern that must be addressed before proceeding.\n"
                )
        else:
            sof_section.append(
                f"❌ CRITICAL: No claims could be directly verified against the bank statements provided. "
                f"This represents a complete absence of documentary evidence for the stated funding sources. "
                f"Without bank statement evidence showing the receipt of these funds, we cannot proceed "
                f"under UK AML regulations. Immediate action required.\n"
            )
        
        # Add funding path detail
        if funding_paths:
            best_path = max(funding_paths, key=lambda p: p['coverage'])
            sof_section.append(f"\nFUNDING PATH TRACED:\n")
            for step in best_path['steps'][:5]:
                sof_section.append(f"  • {step}\n")
        
        sections.append("".join(sof_section))
        
        # ============================================================
        # SECTION 2: TRANSACTION REVIEW INTEGRATION
        # ============================================================
        tr_section = ["\n=== AUTOMATED TRANSACTION REVIEW ===\n"]
        
        if tr_summary.get('total_alerts', 0) > 0:
            tr_section.append(
                f"\n⚠️ OVERALL STATUS: {tr_summary['total_alerts']} alert(s) identified by automated monitoring:\n"
                f"  • {tr_critical} CRITICAL severity\n"
                f"  • {tr_high} HIGH severity\n"
                f"  • {tr_summary.get('medium_alerts', 0)} MEDIUM severity\n\n"
            )
            
            # Transaction Review table header
            tr_section.append("ALERT ANALYSIS:\n")
            tr_section.append("-" * 120 + "\n")
            tr_section.append(f"{'SEVERITY':<12} | {'ISSUE IDENTIFIED':<45} | {'OUTREACH QUESTIONS':<35} | {'SUMMARY':<20}\n")
            tr_section.append("-" * 120 + "\n")
            
            # Group alerts by type for table
            alert_rows = []
            
            if tr_critical > 0:
                key_concerns = tr_summary.get('key_concerns', [])
                for concern in key_concerns[:3]:  # Top 3 concerns
                    if 'sanctioned' in concern.lower() or 'prohibited' in concern.lower():
                        alert_rows.append({
                            'severity': '🔴 CRITICAL',
                            'issue': concern[:45],
                            'outreach': 'Explain all sanctioned transactions',
                            'summary': '❌ BLOCKS COMPLETION'
                        })
                    elif 'cash deposit' in concern.lower():
                        alert_rows.append({
                            'severity': '🔴 CRITICAL',
                            'issue': concern[:45],
                            'outreach': 'Provide cash source documentation',
                            'summary': '❌ HIGH RISK'
                        })
            
            if tr_high > 0:
                alert_rows.append({
                    'severity': '🟠 HIGH',
                    'issue': f'{tr_high} high-risk jurisdiction transaction(s)',
                    'outreach': 'Explain business purpose and parties',
                    'summary': '⚠️ REQUIRES REVIEW'
                })
            
            # Populate table
            for row in alert_rows[:5]:  # Max 5 rows
                tr_section.append(
                    f"{row['severity']:<12} | {row['issue']:<45} | {row['outreach']:<35} | {row['summary']:<20}\n"
                )
            
            tr_section.append("-" * 120 + "\n")
            
            # Transaction Review summary
            tr_section.append("\nTRANSACTION REVIEW SUMMARY:\n")
            
            if tr_critical > 0:
                tr_section.append(
                    f"❌ CRITICAL AML CONCERNS: The automated transaction monitoring has identified {tr_critical} "
                    f"CRITICAL-severity alerts that represent material AML/CTF risks. These include:\n"
                )
                for concern in tr_summary.get('key_concerns', [])[:3]:
                    tr_section.append(f"  • {concern}\n")
                
                tr_section.append(
                    f"\nThese findings materially impact the overall assessment. Even with complete SoF documentation, "
                    f"CRITICAL transaction alerts indicate potential sanctions violations, terrorism financing, "
                    f"or other prohibited activities. Under UK AML regulations, we cannot proceed until these "
                    f"concerns are fully investigated and resolved. The matter must be escalated to the MLRO "
                    f"for review.\n"
                )
            elif tr_high > 0:
                tr_section.append(
                    f"⚠️ HIGH-RISK TRANSACTIONS: {tr_high} transaction(s) flagged as HIGH severity require "
                    f"enhanced due diligence. While not immediately blocking, these alerts indicate elevated "
                    f"AML risk that must be addressed through additional client outreach and documentation.\n"
                )
            
            # Red flags
            if critical_flags > 0 or high_flags > 0:
                tr_section.append(f"\nADDITIONAL RED FLAGS:\n")
                for flag in red_flags[:5]:
                    tr_section.append(f"  • [{flag['severity']}] {flag['flag']}\n")
        else:
            tr_section.append(
                "✅ OVERALL STATUS: No transaction alerts identified.\n\n"
                "TRANSACTION REVIEW SUMMARY:\n"
                "The automated transaction monitoring has not identified any AML/CTF concerns in the "
                "transaction data reviewed. This is a positive indicator, though it does not replace "
                "the requirement for proper SoF documentation.\n"
            )
        
        sections.append("".join(tr_section))
        
        # ============================================================
        # SECTION 3: FINAL ASSESSMENT
        # ============================================================
        final_section = ["\n=== FINAL ASSESSMENT ===\n\n"]
        
        if status == "sufficient":
            final_section.append(
                "✅ DECISION: SUFFICIENT\n\n"
                "The Source of Funds documentation and transaction review findings are sufficient to "
                "proceed under a risk-based approach. All material funding sources have been verified, "
                "no critical AML concerns exist, and the matter can proceed to completion subject to "
                "standard ongoing monitoring.\n"
            )
        elif status == "borderline":
            final_section.append(
                "⚠️ DECISION: BORDERLINE\n\n"
                "The current evidence is borderline sufficient. While core funding has been traced and "
                "no critical AML alerts exist, some documentation gaps or medium-priority concerns should "
                "be addressed to strengthen the file. The matter may proceed with enhanced monitoring, or "
                "additional documentation can be requested to achieve a 'sufficient' rating.\n"
            )
        else:
            final_section.append(
                "❌ DECISION: INSUFFICIENT\n\n"
                "The current evidence is insufficient to proceed. Material gaps in SoF documentation "
                "and/or critical AML concerns prevent completion under UK regulatory requirements. "
                "The specific issues identified above must be resolved before the matter can proceed.\n"
            )
        
        sections.append("".join(final_section))
        
        return "\n".join(sections)
    
    def generate_next_actions(
        self,
        risk_rating: str,
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        known_documents: List[str],
        transaction_review_data: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """
        Generate specific questions and document requests
        """
        questions = []
        documents = []
        
        # 1. Transaction Review issues - HIGHEST PRIORITY
        # Use individual alert objects to generate specific, actionable questions
        # Check both 'alert_details' (from DB) and 'alerts' (from direct bank statement analysis)
        tr_alerts = transaction_review_data.get('alert_details', transaction_review_data.get('alerts', []))
        
        if tr_alerts:
            critical_tr = [a for a in tr_alerts if a['severity'] == 'CRITICAL']
            high_tr = [a for a in tr_alerts if a['severity'] == 'HIGH']
            
            # Generate specific questions for each CRITICAL alert
            if critical_tr:
                for alert in critical_tr[:3]:  # Top 3 critical alerts
                    # Handle both new format (flat fields) and old format (nested transaction object)
                    if 'transaction' in alert:
                        # Old format from database
                        txn = alert['transaction']
                        amount = txn['amount']
                        date = txn['date']
                    else:
                        # New format from direct bank statement analysis
                        amount = alert['amount']
                        date = alert['date']
                    
                    reason = alert['reasons'][0] if alert['reasons'] else "AML concern"
                    questions.append(
                        f"URGENT: Transaction of £{amount:,.2f} on {date} "
                        f"flagged as CRITICAL - {reason}. Provide immediate explanation."
                    )
                
                # Add document request for all critical alerts
                if any('sanction' in str(a.get('reasons', [])).lower() or 
                       'prohibited' in str(a.get('reasons', [])).lower() 
                       for a in critical_tr):
                    documents.append("Written explanation and supporting evidence for all transactions to sanctioned/prohibited countries")
            
            # Generate specific questions for each HIGH alert
            if high_tr:
                for alert in high_tr[:5]:  # Top 5 high alerts
                    # Handle both formats
                    if 'transaction' in alert:
                        amount = alert['transaction']['amount']
                        date = alert['transaction']['date']
                    else:
                        amount = alert['amount']
                        date = alert['date']
                    
                    reason = alert['reasons'][0] if alert['reasons'] else "High-risk transaction"
                    questions.append(
                        f"HIGH RISK: Transaction of £{amount:,.2f} on {date} "
                        f"requires explanation - {reason}."
                    )
                
                # Add document request for cash transactions
                if any('cash' in str(a.get('reasons', [])).lower() for a in high_tr):
                    documents.append("Source documentation for all cash transactions over £10,000")
        
        # 2. Document requirements for ALL claims (verified and unverified)
        # Bank payments alone are insufficient - we need source documents
        for i, evidence in enumerate(evidence_matches):
            claim = claims[i]
            source_lower = claim['source_type'].lower()
            
            # Add questions for unverified claims
            if not evidence['verified']:
                questions.append(
                    f"No bank statement evidence found for your claimed {claim['source_type']} "
                    f"of £{claim['expected_amount']:,.2f}. Please provide supporting documentation."
                )
            
            # Check if this specific claim is fully verified
            claim_fully_verified = (
                evidence.get('verified', False) and 
                evidence.get('document_verified', False) and
                evidence.get('document_verification', {}).get('confidence', 0) >= self.settings.get('sof_partial_confidence_threshold', 0.99)
            )
            
            # Skip document requests for fully verified claims (100% confidence)
            if claim_fully_verified:
                continue
            
            # Source-specific documents required for ALL claims to prove legitimacy
            if 'inheritance' in source_lower:
                if "Probate grant" not in ' '.join(known_documents):
                    documents.append(f"Probate grant or letters of administration (for {claim['source_type']} claim of £{claim['expected_amount']:,.2f})")
                if "Estate account" not in ' '.join(known_documents):
                    documents.append(f"Estate account summary showing distribution (for {claim['source_type']} claim)")
            elif 'property' in source_lower or 'sale' in source_lower:
                if "completion statement" not in ' '.join(known_documents).lower():
                    documents.append(f"Property completion statement (for {claim['source_type']} claim of £{claim['expected_amount']:,.2f})")
                if "Solicitor's statement" not in ' '.join(known_documents):
                    documents.append(f"Solicitor's statement of account showing sale proceeds (for {claim['source_type']} claim)")
                
                # Check if completion statement was uploaded but missing amount
                doc_ver = evidence.get('document_verification', {})
                differences = doc_ver.get('differences', [])
                for diff in differences:
                    if diff.get('field') == 'payment_amount' and 'not found' in diff.get('issue', '').lower():
                        questions.append(
                            f"Please provide an explanation for why the completion statement does not show the sale proceeds amount "
                            f"for your {claim['source_type']} claim of £{claim['expected_amount']:,.2f}."
                        )
            elif 'loan' in source_lower:
                if "Loan" not in ' '.join(known_documents):
                    documents.append(f"Loan offer letter and agreement (for {claim['source_type']} claim of £{claim['expected_amount']:,.2f})")
                    documents.append(f"Evidence of loan drawdown")
            elif 'business' in source_lower:
                if "Share purchase" not in ' '.join(known_documents):
                    documents.append(f"Share purchase agreement (for {claim['source_type']} claim of £{claim['expected_amount']:,.2f})")
                    documents.append(f"Completion accounts")
            elif 'savings' in source_lower:
                if "Historical" not in ' '.join(known_documents):
                    documents.append(f"Historical bank statements showing savings accumulation (for {claim['source_type']} claim)")
        
        # 3. Red flags from analysis
        # Skip transaction-related red flags as they're covered by Transaction Review above
        for flag in red_flags:
            if flag['source'] == 'SoF_ANALYSIS':
                # Only add questions for non-transaction red flags
                if 'unexplained credit' not in flag['flag'].lower() and 'cash deposit' not in flag['flag'].lower():
                    # Other SoF analysis flags
                    questions.append(f"Explain the {flag['flag']}")
        
        # 4. Risk-specific requirements
        if risk_rating == 'high':
            if 'Beneficial ownership details' not in documents:
                documents.append("Beneficial ownership details and structure chart")
        
        # 5. Standard documents if not already provided
        # BUT: Skip if all evidence is fully verified (100% confidence)
        all_fully_verified = all(
            match.get('verified', False) and 
            match.get('document_verified', False) and
            match.get('document_verification', {}).get('confidence', 0) >= self.settings.get('sof_partial_confidence_threshold', 0.99)
            for match in evidence_matches
        ) if evidence_matches else False
        
        if not all_fully_verified:
            standard_docs = {
                "Bank statements": "Complete bank statements covering receipt and payment periods"
                # ID verification is captured elsewhere, not needed here
            }
            
            for doc_type, doc_desc in standard_docs.items():
                if doc_type.lower() not in [d.lower() for d in known_documents]:
                    documents.append(doc_desc)
        
        # Deduplicate - smart deduplication that removes semantically similar questions
        # First, simple dedup
        questions = list(dict.fromkeys(questions))
        documents = list(dict.fromkeys(documents))
        
        # Now remove questions that are semantically similar (same claim type and amount)
        def extract_claim_key(q: str) -> tuple:
            """Extract claim type and amount from a question for dedup"""
            import re
            amount_match = re.search(r'£([\d,]+(?:\.\d{2})?)', q)
            amount = amount_match.group(1) if amount_match else ''
            
            # Extract claim type
            claim_type = ''
            for ct in ['inheritance', 'property sale', 'property', 'savings', 'loan', 'gift', 'salary', 'bonus']:
                if ct.lower() in q.lower():
                    claim_type = ct.lower()
                    break
            
            return (claim_type, amount)
        
        # Keep only unique questions by claim key (prefer first occurrence)
        seen_keys = set()
        unique_questions = []
        for q in questions:
            key = extract_claim_key(q)
            # Allow questions with no identifiable key through, but filter duplicates
            if key == ('', '') or key not in seen_keys:
                if key != ('', ''):
                    seen_keys.add(key)
                unique_questions.append(q)
        
        questions = unique_questions
        
        return {
            "questions": questions,
            "documents": documents
        }
    
    def generate_file_note(
        self,
        client_info: Dict[str, Any],
        purchase: Dict[str, Any],
        claims: List[Dict[str, Any]],
        evidence_matches: List[Dict[str, Any]],
        funding_paths: List[Dict[str, Any]],
        red_flags: List[Dict[str, Any]],
        transaction_review_data: Dict[str, Any],
        outcome: Dict[str, Any],
        next_actions: Dict[str, List[str]]
    ) -> str:
        """
        Generate audit-ready file note
        """
        note_parts = []
        
        # Header
        note_parts.append(
            f"SOURCE OF FUNDS ASSESSMENT\n"
            f"Date: {datetime.now(timezone.utc).strftime('%d %B %Y')}\n"
            f"Matter: {self.matter_id}\n"
            f"Client: {client_info.get('client_name', 'N/A')}\n"
            f"Risk Rating: {client_info.get('client_risk_rating', 'N/A').upper()}\n"
            f"Purchase: {purchase.get('description', 'Business purchase')} - "
            f"£{purchase.get('amount', 0):,.2f} {purchase.get('currency', 'GBP')}\n"
        )
        
        # Claims summary
        note_parts.append("\nCLIENT'S SoF EXPLANATION:")
        for claim in claims:
            evidence = evidence_matches[claim['claim_id']-1]
            has_bank = evidence.get('verified', False)
            has_doc = evidence.get('document_verified', False)
            
            if has_bank and has_doc:
                status = "VERIFIED"
            elif has_bank:
                status = "REQUIRES DOCUMENTATION"
            elif has_doc:
                status = "REQUIRES BANK EVIDENCE"
            else:
                status = "NOT VERIFIED"
            
            note_parts.append(
                f"- {claim['source_type']}: £{claim['expected_amount']:,.2f} [{status}]"
            )
        
        # Evidence review with clear distinction
        note_parts.append("\nEVIDENCE REVIEW (Claim-by-Claim):")
        bank_verified_count = sum(1 for e in evidence_matches if e.get('verified', False))
        doc_verified_count = sum(1 for e in evidence_matches if e.get('document_verified', False))
        
        # FULLY VERIFIED requires: bank + docs + 100% confidence
        fully_verified_count = sum(
            1 for e in evidence_matches 
            if e.get('verified', False) 
            and e.get('document_verified', False)
            and e.get('document_verification', {}).get('confidence', 0) >= 1.0
        )
        
        note_parts.append(
            f"Bank transactions: {bank_verified_count}/{len(claims)} claims matched."
        )
        note_parts.append(
            f"Supporting documents: {doc_verified_count}/{len(claims)} claims verified with source documentation."
        )
        note_parts.append(
            f"FULLY VERIFIED (bank + docs + 100% confidence): {fully_verified_count}/{len(claims)} claims."
        )
        
        # Show warning if any claims have less than 100% confidence
        partial_verified = sum(
            1 for e in evidence_matches 
            if e.get('verified', False) 
            and e.get('document_verified', False)
            and e.get('document_verification', {}).get('confidence', 0) < 1.0
        )
        if partial_verified > 0:
            note_parts.append(
                f"⚠️ REQUIRES REVIEW: {partial_verified} claim(s) have document issues (confidence < 100%)."
            )
        
        note_parts.append("")
        
        for evidence in evidence_matches:
            doc_verified = evidence.get('document_verified', False)
            doc_verification = evidence.get('document_verification', {})
            
            # Show bank transaction status
            if evidence['verified']:
                txns = evidence['transactions']
                first_txn = txns[0]
                
                # Determine status based on confidence
                confidence = doc_verification.get('confidence', 0)
                is_fully_verified = doc_verified and confidence >= 1.0
                
                status_icon = '✅' if is_fully_verified else '⚠️'
                status_text = 'FULLY VERIFIED' if is_fully_verified else 'REQUIRES REVIEW'
                
                note_parts.append(
                    f"{status_icon} Claim {evidence['claim_id']} ({evidence['claim_source']}): "
                    f"£{evidence['expected_amount']:,.2f} - {status_text}"
                )
                note_parts.append(
                    f"   • Bank Transaction: £{first_txn['amount']:,.2f} on {first_txn['date']}"
                )
                note_parts.append(
                    f"   • Description: {first_txn['description']}"
                )
                note_parts.append(
                    f"   • Counterparty: {first_txn.get('counterparty', 'Not specified')}"
                )
                
                # Show document verification status
                if doc_verified:
                    verification_details = doc_verification.get('verification_details', {})
                    checks_passed = verification_details.get('checks_passed', [])
                    document_used = verification_details.get('document_used', {})
                    
                    note_parts.append(f"   • ✅ SUPPORTING DOCUMENT VERIFIED:")
                    
                    # AUDIT TRAIL: Show which document was used
                    if document_used:
                        note_parts.append(f"      📄 Document: {document_used.get('filename', 'Unknown')}")
                        note_parts.append(f"      📋 Type: {document_used.get('document_type', 'Unknown')}")
                        if document_used.get('probate_reference'):
                            note_parts.append(f"      🔖 Reference: {document_used['probate_reference']}")
                        if document_used.get('title_number'):
                            note_parts.append(f"      🔖 Title Number: {document_used['title_number']}")
                        if document_used.get('solicitor_firm'):
                            note_parts.append(f"      ⚖️ Solicitor: {document_used['solicitor_firm']}")
                    
                    for check in checks_passed[:3]:  # Show first 3 checks
                        note_parts.append(f"      - {check}")
                    if doc_verification.get('confidence'):
                        confidence_pct = doc_verification['confidence']*100
                        note_parts.append(f"      - Verification confidence: {confidence_pct:.0f}%")
                        
                        # FLAG if confidence < 100%
                        if confidence_pct < 100:
                            note_parts.append(f"      ⚠️ ATTENTION: Confidence below 100% - review required")
                            issues = doc_verification.get('issues', [])
                            if issues:
                                note_parts.append(f"      📋 Issues found:")
                                for issue in issues:
                                    note_parts.append(f"         • {issue}")
                    
                    # ADD COMPARISON: Customer Claim vs Document Evidence
                    comparison = verification_details.get('comparison', {})
                    if comparison:
                        note_parts.append(f"\n   • 📊 EVIDENCE COMPARISON:")
                        
                        customer_claim = comparison.get('customer_claim', {})
                        doc_evidence = comparison.get('document_evidence', {})
                        matches = comparison.get('matches', {})
                        
                        # Customer's claim
                        note_parts.append(f"      👤 Customer stated:")
                        note_parts.append(f"         • Source: {customer_claim.get('source_type')}")
                        note_parts.append(f"         • Amount: £{customer_claim.get('claimed_amount', 0):,.2f}")
                        if customer_claim.get('description') and customer_claim['description'] != 'Not provided':
                            desc = customer_claim['description']
                            # Limit to 200 chars for readability
                            if len(desc) > 200:
                                desc = desc[:197] + "..."
                            note_parts.append(f"         • Explanation: \"{desc}\"")
                        
                        # Document confirms
                        note_parts.append(f"      ✅ Document confirms:")
                        if doc_evidence.get('deceased_name'):
                            note_parts.append(f"         • Estate of: {doc_evidence['deceased_name']}")
                        if doc_evidence.get('executor'):
                            note_parts.append(f"         • Executor/Beneficiary: {doc_evidence['executor']}")
                        if doc_evidence.get('distribution_amount'):
                            note_parts.append(f"         • Distribution: £{doc_evidence['distribution_amount']:,.2f}")
                        if doc_evidence.get('payment_date'):
                            note_parts.append(f"         • Payment date: {doc_evidence['payment_date']}")
                        if doc_evidence.get('property_address'):
                            note_parts.append(f"         • Property: {doc_evidence['property_address']}")
                        if doc_evidence.get('vendor_name'):
                            note_parts.append(f"         • Vendor: {doc_evidence['vendor_name']}")
                        if doc_evidence.get('net_proceeds'):
                            note_parts.append(f"         • Net proceeds: £{doc_evidence['net_proceeds']:,.2f}")
                        if doc_evidence.get('completion_date'):
                            note_parts.append(f"         • Completion: {doc_evidence['completion_date']}")
                        
                        # Match status
                        if matches.get('amount_matches'):
                            diff = matches.get('amount_difference', 0)
                            if diff < 100:
                                note_parts.append(f"      ✅ Amount matches exactly")
                            else:
                                note_parts.append(f"      ✅ Amount matches (difference: £{diff:,.2f})")
                        else:
                            note_parts.append(f"      ⚠️ Amount mismatch detected")
                else:
                    note_parts.append(
                        f"   • ⚠️ REQUIRES: Source documentation to prove legitimacy"
                    )
            else:
                note_parts.append(
                    f"❌ Claim {evidence['claim_id']} ({evidence['claim_source']}): "
                    f"NOT VERIFIED - No matching transaction found in statements."
                )
                if doc_verified:
                    note_parts.append(f"   • Note: Supporting document provided but no bank transaction found")
            
            note_parts.append("")  # Empty line between claims
        
        # Funding trace with interpretation
        note_parts.append("\nFUNDING ANALYSIS (Overall Position):")
        best_path = max(funding_paths, key=lambda p: p['coverage'], default=None)
        if best_path:
            note_parts.append(
                f"Total funding traced: {best_path['coverage']}% of purchase amount.\n"
            )
            
            if best_path['coverage'] >= 90 and fully_verified_count < len(claims):
                note_parts.append(
                    "INTERPRETATION: While not all individual claims have direct evidence in the "
                    "provided statements, sufficient aggregate funding has been traced to cover the "
                    "full purchase amount. This may indicate:"
                )
                note_parts.append("  • Some source transactions occurred before the statement period")
                note_parts.append("  • Funds arrived via intermediate accounts not yet documented")
                note_parts.append("  • Alternative credits provide equivalent funding coverage")
                note_parts.append(
                    "\nRecommendation: Request specific documentation for unverified claims to "
                    "complete the audit trail, even though funding is mathematically sufficient.\n"
                )
            
            note_parts.append(f"Funding path analysis:")
            for step in best_path['steps'][:5]:
                note_parts.append(f"  • {step}")
        
        # Transaction Review - CRITICAL SECTION
        tr_summary = transaction_review_data.get('summary', {})
        if tr_summary.get('total_alerts', 0) > 0:
            note_parts.append("\nAUTOMATED TRANSACTION MONITORING (TRANSACTION REVIEW):")
            note_parts.append(
                f"System identified {tr_summary['total_alerts']} alert(s): "
                f"{tr_summary['critical_alerts']} CRITICAL, "
                f"{tr_summary['high_alerts']} HIGH, "
                f"{tr_summary['medium_alerts']} MEDIUM."
            )
            if tr_summary.get('key_concerns'):
                note_parts.append("Key concerns:")
                for concern in tr_summary['key_concerns']:
                    note_parts.append(f"  • {concern}")
            note_parts.append(
                "Full alert details available in Transaction Review tab. "
                "These findings materially impact the SoF assessment."
            )
        
        # Red flags
        if red_flags:
            note_parts.append(f"\nRED FLAGS IDENTIFIED ({len(red_flags)}):")
            for flag in red_flags[:5]:  # Top 5
                note_parts.append(f"  • [{flag['severity']}] {flag['flag']}")
        
        # Decision
        note_parts.append(f"\nASSESSMENT DECISION:")
        note_parts.append(
            f"Status: {outcome['status'].upper()} (Confidence: {outcome['confidence']}%)\n"
            f"Rationale: {outcome['rationale']}"
        )
        
        # Actions required
        if next_actions['questions']:
            note_parts.append("\nQUESTIONS FOR CLIENT:")
            for i, q in enumerate(next_actions['questions'][:5], 1):
                note_parts.append(f"{i}. {q}")
        
        if next_actions['documents']:
            note_parts.append("\nDOCUMENTS REQUIRED:")
            for i, d in enumerate(next_actions['documents'][:5], 1):
                note_parts.append(f"{i}. {d}")
        
        # Footer
        note_parts.append(
            f"\n---\n"
            f"This assessment was conducted using a risk-based approach in accordance with "
            f"UK AML regulations. The matter {'CAN' if outcome['status'] == 'sufficient' else 'CANNOT'} "
            f"proceed to completion in its current state."
        )
        
        return "\n".join(note_parts)

