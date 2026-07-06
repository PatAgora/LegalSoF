"""
Risk-tiered Source of Funds evidence checklist.

For each type of declared source of funds, the LSAG Guidance (§6.8)
expects the firm to obtain documentary evidence proportionate to risk.
This module maps each source type to the documents that should be
obtained — a baseline set, plus extra documents required when the
matter is high-risk (Enhanced Due Diligence).

required_evidence(source_type, tier) returns the list of expected
documents for a given matter risk tier ('low' | 'medium' | 'high').
"""
from typing import Dict, List

# source_type -> {"base": [...], "enhanced": [...]}.
# base   — obtain on every matter for this source type.
# enhanced — additionally obtain for High / Critical risk matters.
_CHECKLIST: Dict[str, Dict[str, List[str]]] = {
    "property_sale": {
        "base": [
            "Completion statement or solicitor's letter for the sale",
            "Sale contract or memorandum of sale",
            "Bank statement showing the sale proceeds credited",
        ],
        "enhanced": [
            "Estate agent's invoice / commission account",
            "Land Registry title confirming prior ownership",
            "Confirmation of the conveyancing solicitor acting on the sale",
        ],
    },
    "business_sale": {
        "base": [
            "Share purchase agreement or sale agreement",
            "Completion statement for the disposal",
            "Bank statement showing the sale proceeds credited",
        ],
        "enhanced": [
            "Company accounts for the period before sale",
            "Confirmation from the corporate solicitor or accountant",
            "Companies House filing reflecting the change of ownership",
        ],
    },
    "inheritance": {
        "base": [
            "Grant of probate or letters of administration",
            "Will, or executor / solicitor letter confirming the bequest",
            "Bank statement showing the distribution received",
        ],
        "enhanced": [
            "Estate accounts",
            "Death certificate of the deceased",
            "Identity confirmation of the executor / administrator",
        ],
    },
    "savings": {
        "base": [
            "Bank or savings statements covering the accumulation period",
            "Evidence of the income that funded the savings",
        ],
        "enhanced": [
            "Full statement history back to the start of accumulation",
            "Tax returns or P60s covering the accumulation period",
        ],
    },
    "salary": {
        "base": [
            "Recent payslips (at least three months)",
            "Bank statement showing salary credits from the employer",
        ],
        "enhanced": [
            "Employment contract",
            "P60 / annual tax summary",
            "Employer confirmation of remuneration",
        ],
    },
    "gift": {
        # A third-party gift must be checked in the same way as the
        # client's own funds (SRA thematic review, case study 1): the
        # donor's identity, a gift deed, and the donor's own source of
        # funds are required on every matter, not only high-risk ones.
        "base": [
            "Signed gift letter or deed from the donor confirming the amount and that it is unconditional",
            "Identity verification of the donor",
            "Explanation and Evidence of the donor's source of funds (e.g Bank statements)",
            "Bank statement showing the gift received",
        ],
        "enhanced": [
            "Confirmation of the donor's relationship to the client",
            "Independent corroboration of the donor's wealth",
        ],
    },
    "pension": {
        "base": [
            "Pension provider statement or lump-sum settlement letter",
            "Bank statement showing the pension payment received",
        ],
        "enhanced": [
            "Pension scheme membership history",
        ],
    },
    "investment": {
        "base": [
            "Investment / brokerage statement showing the holding and disposal",
            "Bank statement showing the proceeds credited",
        ],
        "enhanced": [
            "Contract notes for the disposal",
            "Evidence of the original source of funds invested",
        ],
    },
    "business_loan": {
        "base": [
            "Business loan agreement setting out the amount and repayment terms",
            "Confirmation of the lender's identity and regulated status (FCA register check), or for a private lender their verified identity",
            "Evidence of the lender's own source of funds where the lender is private / non-regulated",
            "Bank statement showing the loan advance received",
        ],
        "enhanced": [
            "Board minutes / director authorisation for the borrowing",
            "Confirmation of the lender's relationship to the client or business (private loans)",
        ],
    },
    "loan": {
        "base": [
            "Loan or mortgage agreement",
            "Confirmation of the lender's regulated status, or for a private lender their verified identity",
            "Evidence of the lender's own source of funds (private / non-regulated loans)",
            "Bank statement showing the loan advance received",
        ],
        "enhanced": [
            "Confirmation of the lender's relationship to the client (private loans)",
        ],
    },
    "compensation": {
        "base": [
            "Settlement agreement, court order or award letter",
            "Bank statement showing the compensation received",
        ],
        "enhanced": [
            "Solicitor confirmation of the underlying claim",
        ],
    },
    "insurance": {
        "base": [
            "Insurer settlement / policy maturity letter",
            "Bank statement showing the payout received",
        ],
        "enhanced": [
            "Policy schedule and claim documentation",
        ],
    },
    "lottery": {
        "base": [
            "Operator's confirmation of the win",
            "Bank statement showing the winnings received",
        ],
        "enhanced": [
            "Operator payout records",
        ],
    },
    "dividend": {
        "base": [
            "Dividend voucher(s)",
            "Bank statement showing the dividend received",
        ],
        "enhanced": [
            "Company accounts supporting the distribution",
        ],
    },
    "gambling_winnings": {
        "base": [
            "Operator (casino / bookmaker / lottery) statement or account history showing the win",
            "Evidence of the winnings being paid out (payout confirmation or receipt)",
            "Bank statement showing the winnings credited",
        ],
        "enhanced": [
            "Operator payout records / cheque copy",
            "Evidence of the funds originally staked",
        ],
    },
    "crypto": {
        "base": [
            "Exchange transaction history showing the acquisition and disposal of the cryptoassets",
            "Wallet statements / addresses evidencing the holding",
            "Evidence of the fiat off-ramp — the exchange withdrawal matching the bank credit",
            "Bank statement showing the proceeds credited",
        ],
        "enhanced": [
            "Evidence of the original source of funds used to purchase the cryptoassets",
            "Exchange KYC confirmation that the account belongs to the client",
        ],
    },
}

# Fallback for an unrecognised / 'other' source type. An unclassified
# source is itself a risk indicator — it must not pass with generic
# paperwork: the solicitor must obtain and record a documented
# explanation of exactly what the source is before it can be accepted.
_DEFAULT = {
    "base": [
        "REQUIRED: Solicitor to obtain and record a documented explanation "
        "from the client of exactly what this source of funds is — an "
        "'other'/unclassified source cannot be accepted without one",
        "Documentary evidence of the origin of the funds, specific to the explained source",
        "Bank statement showing the funds received",
    ],
    "enhanced": [
        "Independent corroboration of the stated source",
        "MLRO sign-off recording why the unclassified source was accepted",
    ],
}


def _normalise(source_type: str) -> str:
    return str(source_type or "").strip().lower().replace(" ", "_").replace("-", "_")


def required_evidence(source_type: str, tier: str = "medium") -> List[str]:
    """Return the documents expected for a source type at a risk tier.

    For high-risk (and critical) matters the enhanced documents are
    appended to the baseline set.
    """
    entry = _CHECKLIST.get(_normalise(source_type), _DEFAULT)
    docs = list(entry.get("base", []))
    if str(tier).lower() in ("high", "critical"):
        docs += list(entry.get("enhanced", []))
    return docs
