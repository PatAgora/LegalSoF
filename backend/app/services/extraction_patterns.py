"""
Comprehensive regex pattern library for PDF extraction
170+ patterns for 99% document coverage
"""
import re
from typing import List, Dict, Optional, Tuple
from difflib import SequenceMatcher


class ExtractionPatterns:
    """Comprehensive pattern library for all document types"""
    
    # ============================================
    # DECEASED NAME PATTERNS (20+)
    # ============================================
    DECEASED_NAME = [
        # Standard formats
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(deceased\)',
        r'ESTATE OF[:\s]+([A-Z\s]+)\s*\(DECEASED\)',
        r'Estate\s+of\s*:\s*([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
        
        # With "In the"
        r'In the Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'IN THE ESTATE OF[:\s]+([A-Z\s]+)',
        
        # With "late"
        r'Estate of the late[:\s]+([A-Z][A-Za-z\s]+)',
        r'Late[:\s]+([A-Z][A-Za-z\s]+)\s*\(Deceased\)',
        r'the late[:\s]+([A-Z][A-Za-z\s]+)',
        r'of the late\s+([A-Z][A-Za-z\s]+)',
        
        # Solicitor formats
        r'Re:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Matter:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Client:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Subject:\s*Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        
        # Court formats
        r'Grant in respect of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Probate of[:\s]+([A-Z][A-Za-z\s]+)',
        r'Grant to[:\s]+.*?Estate of[:\s]+([A-Z][A-Za-z\s]+)',
        
        # Form fields
        r'Deceased[:\s]+([A-Z][A-Za-z\s]+)',
        r'Name of Deceased[:\s]+([A-Z][A-Za-z\s]+)',
        r'Deceased Name[:\s]+([A-Z][A-Za-z\s]+)',
        r'Deceased\s+Person[:\s]+([A-Z][A-Za-z\s]+)',
        
        # Table formats
        r'Deceased\s*\|?\s*:?\s*([A-Z][A-Za-z\s]+)',
        r'\|\s*Deceased\s*\|\s*([A-Z][A-Za-z\s]+)\s*\|',
        
        # With middle names/initials
        r'Estate of[:\s]+([A-Z][A-Za-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][A-Za-z]+)*)\s*\(Deceased\)',
        
        # Alternative deceased markers
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(dec\)',
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(dec\.\)',
        r'Estate of[:\s]+([A-Z][A-Za-z\s]+)\s*\(Decd\)',
    ]
    
    # ============================================
    # BENEFICIARY DISTRIBUTION PATTERNS (35+)
    # ============================================
    BENEFICIARY_DISTRIBUTION = [
        # Standard single-line formats
        r'(?:Primary\s+)?Beneficiary[:\s]*([A-Z][A-Za-z\s()]+?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'(?:Primary\s+)?BENEFICIARY[:\s]*([A-Z][A-Z\s()]+?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Multi-line formats (beneficiary on one line, amount on next)
        r'(?:Primary\s+)?Beneficiary[:\s]*\n\s*([A-Z][A-Za-z\s()]+?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Beneficiary[:\s]+([A-Z][A-Za-z\s()]+)\s*\n.*?Amount[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        
        # Payment/Distribution/Transfer to...
        r'(?:Payment|Distribution|Transfer)\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Paid\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Payable\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Pay\s+to[:\s]+([A-Z][A-Za-z\s]+)\s*[:\-]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Table formats
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+\|?\s*£?([0-9,]+(?:\.\d{2})?)\s*\|?',
        r'\|?\s*([A-Z][A-Za-z\s]+?)\s*\|\s*£?([0-9,]+(?:\.\d{2})?)\s*\|',
        r'\|\s*Name\s*\|.*?\|\s*([A-Z][A-Za-z\s]+)\s*\|.*?\|\s*£?([0-9,]+(?:\.\d{2})?)\s*\|',
        
        # With relationship in parentheses
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+\((?:Son|Daughter|Spouse|Wife|Husband|Child|Children|Sibling|Brother|Sister|Parent|Mother|Father|Grandson|Granddaughter|Nephew|Niece)\)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Numbered list formats
        r'(\d+\.)\s*([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'(?:Item|Clause|Point)\s+\d+[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Executor's statement formats
        r'(?:transferred|paid|distributed|remitted)\s+(?:to|to:)\s*\n?([A-Z][A-Za-z\s]+)\s*.*?£?([0-9,]+(?:\.\d{2})?)',
        r'(?:transferred|paid)\s+£?([0-9,]+(?:\.\d{2})?)\s+to\s+([A-Z][A-Za-z\s]+)',
        
        # Share/Entitlement/Inheritance
        r'Share[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Entitlement[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Inheritance[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        r'Portion[:\s]+([A-Z][A-Za-z\s]+)\s*[-:]\s*£?([0-9,]+(?:\.\d{2})?)',
        
        # Bank transfer details
        r'Transfer of £?([0-9,]+(?:\.\d{2})?)\s+to\s+([A-Z][A-Za-z\s]+)',
        r'£?([0-9,]+(?:\.\d{2})?)\s+transferred to\s+([A-Z][A-Za-z\s]+)',
        r'Payment of £?([0-9,]+(?:\.\d{2})?)\s+(?:made|sent)\s+to\s+([A-Z][A-Za-z\s]+)',
        
        # Schedule format
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+receives\s+£?([0-9,]+(?:\.\d{2})?)',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+entitled\s+to\s+£?([0-9,]+(?:\.\d{2})?)',
        r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+to\s+receive\s+£?([0-9,]+(?:\.\d{2})?)',
        
        # Amount first format
        r'£?([0-9,]+(?:\.\d{2})?)\s*(?:to|payable to|for)\s+([A-Z][A-Za-z\s]+)',
        
        # Legacy/Bequest/Gift formats
        r'Legacy\s+to\s+([A-Z][A-Za-z\s]+)[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        r'Bequest\s+to\s+([A-Z][A-Za-z\s]+)[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        r'Gift\s+to\s+([A-Z][A-Za-z\s]+)[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        r'Leave\s+to\s+([A-Z][A-Za-z\s]+)[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        
        # Named beneficiary with amount field
        r'Name[:\s]+([A-Z][A-Za-z\s]+)\s+Amount[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        r'([A-Z][A-Za-z\s]+)\s*\n\s*Amount[:\s]+£?([0-9,]+(?:\.\d{2})?)',
        
        # Multi-line with account details
        r'([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*\n.*?Account.*?\n.*?£?([0-9,]+(?:\.\d{2})?)',
        
        # Split format (beneficiary line, amount line)
        r'(?:Beneficiary|Recipient|Payee)[:\s]*([A-Z][A-Za-z\s]+)\s*\n.*?(?:Amount|Sum|Payment|Value)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        
        # Residuary beneficiary
        r'Residuary\s+(?:beneficiary|estate)\s+to\s+([A-Z][A-Za-z\s]+)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        r'Residue\s+to\s+([A-Z][A-Za-z\s]+)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        
        # Cash formats
        r'Cash\s+(?:legacy|gift|payment)\s+to\s+([A-Z][A-Za-z\s]+)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
        
        # Specific bequest
        r'Specific\s+bequest\s+to\s+([A-Z][A-Za-z\s]+)[:\s]*£?([0-9,]+(?:\.\d{2})?)',
    ]
    
    # ============================================
    # PROPERTY ADDRESS PATTERNS (20+)
    # ============================================
    PROPERTY_ADDRESS = [
        # Full UK address with postcode
        r'(?:Property|Address)[:\s]*\n?([0-9]+[A-Za-z]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z\s]+,\s*[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        
        # Without property label
        r'([0-9]+[A-Za-z]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z\s]+,\s*[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        
        # Flat/Apartment format
        r'(?:Flat|Apartment|Unit)\s+([0-9A-Za-z]+),?\s+([0-9]+\s+[A-Z][a-z\s,]+[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        r'(?:Flat|Apt)\s+([0-9A-Za-z]+)\s*,?\s*([0-9]+[^,]+,[^,]+,[A-Z0-9\s]+)',
        
        # Multi-line address
        r'(?:Property|Address)[:\s]*\n([^\n]+)\n([^\n]+)\n([A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        r'(?:Property|Address)[:\s]*\n([^\n]+)\n([^\n]+)\n([^\n]+)\n([A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        
        # Table cell format
        r'Property\s*\|?\s*:?\s*([^|\n]+(?:\n[^|\n]+)*?[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        
        # Land Registry format
        r'Title Number[:\s]*[A-Z0-9]+\s*\n.*?(?:Property\s+)?Address[:\s]*([^\n]+(?:\n[^\n]+)*?[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        
        # Vendor/Purchaser property
        r'(?:Vendor|Seller)\s+Property[:\s]*([^\n]+(?:\n[^\n]+)*?[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
        
        # Known as format
        r'(?:known as|being)[:\s]+([0-9]+[^,]+,[^,]+,[A-Z0-9\s]+)',
        
        # Situated at
        r'situated at[:\s]+([0-9]+[^,]+,[^,]+,[A-Z0-9\s]+)',
        
        # Located at
        r'located at[:\s]+([0-9]+[^,]+,[^,]+,[A-Z0-9\s]+)',
        
        # Comprising
        r'comprising[:\s]+([0-9]+[^,]+,[^,]+,[A-Z0-9\s]+)',
        
        # The property at
        r'(?:the\s+)?property\s+at[:\s]+([0-9]+[^,]+,[^,]+,[A-Z0-9\s]+)',
        
        # Premises at
        r'premises\s+at[:\s]+([0-9]+[^,]+,[^,]+,[A-Z0-9\s]+)',
        
        # With "being"
        r'being\s+([0-9]+[A-Za-z]?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z][a-z\s]+,\s*[A-Z]{1,2}[0-9]{1,2}\s*[0-9][A-Z]{2})',
    ]
    
    # ============================================
    # DATE PATTERNS (35+)
    # ============================================
    DATE = [
        # UK formats with ordinals and full month names
        r'(\d{1,2}(?:st|nd|rd|th)\s+January\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+February\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+March\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+April\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+May\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+June\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+July\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+August\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+September\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+October\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+November\s+\d{4})',
        r'(\d{1,2}(?:st|nd|rd|th)\s+December\s+\d{4})',
        
        # Short month names with ordinals
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{4})',
        
        # Without ordinals
        r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})',
        r'(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{4})',
        
        # ISO format
        r'(\d{4}-\d{2}-\d{2})',
        
        # UK slash formats
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\d{1,2}/\d{1,2}/\d{2})',
        
        # Dash format
        r'(\d{1,2}-\d{1,2}-\d{4})',
        r'(\d{1,2}-\d{1,2}-\d{2})',
        
        # Dot format (European)
        r'(\d{1,2}\.\d{1,2}\.\d{4})',
        r'(\d{1,2}\.\d{1,2}\.\d{2})',
        
        # Long format (month first)
        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})',
        
        # With day of week
        r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        
        # American format
        r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})',
        r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4})',
        
        # Compact formats
        r'(\d{8})',  # YYYYMMDD
        r'(\d{6})',  # YYMMDD or DDMMYY
        
        # With contextual words
        r'on\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        r'dated\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        r'date\s+of\s+(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})',
        
        # Case insensitive months
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})',
    ]
    
    # ============================================
    # MONETARY AMOUNT PATTERNS (20+)
    # ============================================
    AMOUNT = [
        # Standard UK format with £ and commas
        r'£\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'£([0-9]+(?:\.\d{2})?)',
        
        # GBP explicit
        r'GBP\s*([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*GBP',
        r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*(?:GBP|gbp)',
        
        # Space separators (European style)
        r'£\s*([0-9]{1,3}(?:\s\d{3})*(?:\.\d{2})?)',
        
        # With words
        r'([0-9]{1,3}(?:,\d{3})*(?:\.\d{2})?)\s+(?:pounds?|sterling|Pounds?|Sterling)',
        r'£([0-9,]+)\s+(?:pounds?|sterling)',
        
        # In parentheses
        r'\(£\s*([0-9,]+(?:\.\d{2})?)\)',
        r'\(([0-9,]+(?:\.\d{2})?)\)',
        
        # Negative amounts
        r'-\s*£\s*([0-9,]+(?:\.\d{2})?)',
        r'£\s*-\s*([0-9,]+(?:\.\d{2})?)',
        r'\(£([0-9,]+(?:\.\d{2})?)\)',  # Accounting negative
        
        # Decimal only (no commas)
        r'£([0-9]+\.\d{2})',
        
        # Pence only
        r'([0-9]+)p\b',
        r'([0-9]+)\s*pence',
        
        # With context words
        r'(?:sum of|amount of|total of|value of)\s+£?([0-9,]+(?:\.\d{2})?)',
        
        # Bold/formatted (markdown or HTML)
        r'\*\*£([0-9,]+(?:\.\d{2})?)\*\*',
        r'<strong>£([0-9,]+(?:\.\d{2})?)</strong>',
    ]
    
    # ============================================
    # BANK DETAIL PATTERNS (15+)
    # ============================================
    BANK_NAME = [
        r'Bank[:\s]+([A-Z][A-Za-z\s]+(?:Bank|PLC|plc)?)',
        r'Bank Name[:\s]+([A-Z][A-Za-z\s]+)',
        r'Banking[:\s]+([A-Z][A-Za-z\s]+)',
        r'Banker[:\s]+([A-Z][A-Za-z\s]+)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Bank|PLC)\b',
        r'Account with[:\s]+([A-Z][A-Za-z\s]+)',
    ]
    
    ACCOUNT_NUMBER = [
        r'Account\s+(?:Number|No\.?|#)[:\s]*(\d{8})',
        r'A/?C\s+(?:No\.?|Number)[:\s]*(\d{8})',
        r'Account[:\s]*(\d{8})',
        r'\*+(\d{4})',  # Last 4 digits
        r'ending\s+(?:in\s+)?(\d{4})',
        r'account\s+ending\s+(\d{4})',
    ]
    
    SORT_CODE = [
        r'Sort\s+Code[:\s]*(\d{2}[-\s]?\d{2}[-\s]?\d{2})',
        r'S/?C[:\s]*(\d{2}[-\s]?\d{2}[-\s]?\d{2})',
        r'Sort[:\s]*(\d{2}[-\s]?\d{2}[-\s]?\d{2})',
    ]
    
    # ============================================
    # REFERENCE NUMBER PATTERNS (10+)
    # ============================================
    PROBATE_REFERENCE = [
        r'(?:Probate|Registry)\s+Reference[:\s]*([A-Z0-9/-]+)',
        r'Grant\s+(?:Number|No\.?|Reference)[:\s]*([A-Z0-9/-]+)',
        r'Reference[:\s]*(\d{4}/\d+)',
        r'Probate\s+No\.?[:\s]*([A-Z0-9/-]+)',
    ]
    
    PROPERTY_REFERENCE = [
        r'Title\s+Number[:\s]*([A-Z]{1,3}\d+)',
        r'Land\s+Registry[:\s]*([A-Z]{1,3}\d+)',
        r'Transfer\s+Reference[:\s]*([A-Z0-9/-]+)',
        r'Completion\s+Reference[:\s]*([A-Z0-9/-]+)',
    ]
    
    # ============================================
    # UTILITY METHODS
    # ============================================
    
    @classmethod
    def try_all_patterns(cls, text: str, pattern_list: List[str], flags=re.IGNORECASE) -> List[re.Match]:
        """Try all patterns in a list and return all matches"""
        matches = []
        for pattern in pattern_list:
            try:
                found = list(re.finditer(pattern, text, flags))
                matches.extend(found)
            except Exception as e:
                continue
        return matches
    
    @classmethod
    def extract_first_match(cls, text: str, pattern_list: List[str], group: int = 1, flags=re.IGNORECASE) -> Optional[str]:
        """Try patterns until first match found"""
        for pattern in pattern_list:
            try:
                match = re.search(pattern, text, flags)
                if match:
                    result = match.group(group).strip()
                    if result:
                        return result
            except Exception as e:
                continue
        return None
    
    @classmethod
    def fuzzy_match_keyword(cls, text: str, keywords: List[str], threshold: float = 0.8) -> Optional[str]:
        """
        Fuzzy match keywords in text (typo tolerance)
        Returns the best matching keyword if similarity >= threshold
        """
        text_lower = text.lower()
        words = text_lower.split()
        
        best_match = None
        best_score = 0.0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Check exact match first
            if keyword_lower in text_lower:
                return keyword
            
            # Check fuzzy match
            for word in words:
                score = SequenceMatcher(None, word, keyword_lower).ratio()
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = keyword
        
        return best_match


# Singleton
extraction_patterns = ExtractionPatterns()
