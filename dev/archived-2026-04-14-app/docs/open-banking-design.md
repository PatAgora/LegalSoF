# Open Banking (AISP) statement fetch — design

Status: **design only** — implementation blocked on commercial/regulatory
prerequisites (below). This document exists so the integration can be built
without re-deriving the design, and so the schema/UX decisions elsewhere in
the platform stay compatible with it.

## Why

Every uploaded statement — PDF or CSV — is a client-supplied artefact. The
forensic pipeline can catch *clumsy* tampering, but a careful
flatten-and-reprint forgery is structurally indistinguishable from a genuine
document. Data fetched directly from the bank via an FCA-regulated AISP
connection has provenance by construction: it never passes through the
client's hands. This is the single highest-value trust upgrade available to
the product.

## Prerequisites (why this is not built yet)

1. **AISP access.** Either register the firm/product as an FCA-authorised
   AISP (slow, expensive) or — realistically — integrate via a licensed
   aggregator (TrueLayer, Plaid UK, Yapily, GoCardless Bank Account Data).
   All expose OAuth-style consent flows and normalised transaction APIs.
   Recommendation: **TrueLayer** (strong UK CMA9 coverage, sandbox available
   without commercial contract, per-connection pricing).
2. **Client consent UX.** The *client* (not the solicitor) must authorise
   access to their account. This rides on the client-portal feature: the
   evidence-request link is the natural place to offer "connect your bank
   instead of uploading statements".
3. **Data-protection assessment.** AIS data is special-category-adjacent
   financial data; the firm's privacy notice and Article 30 record need
   updating before live use.

## Architecture

```
client portal ── "Connect your bank" ──> aggregator consent flow (hosted)
                                              │ callback (code)
backend  /api/v1/open-banking/callback ───────┘
   └── OpenBankingService (provider adapter)
         ├── exchange code → access token (stored encrypted, per matter)
         ├── fetch accounts + transactions (90 days default, extendable)
         └── ingest → same transaction store as file uploads, with
             source='open_banking'  (vs 'file', 'ai_extracted')
```

- **Provider adapter interface** (`app/services/open_banking.py`, to create):
  `create_consent_link(matter_id) -> url`, `handle_callback(code) -> token`,
  `fetch_accounts(token)`, `fetch_transactions(token, account, from, to)`.
  One concrete adapter per aggregator; provider chosen by
  `OPEN_BANKING_PROVIDER` setting.
- **Config** (already reserved in this design): `ENABLE_OPEN_BANKING=false`,
  `OPEN_BANKING_PROVIDER=truelayer`, `TRUELAYER_CLIENT_ID/SECRET`,
  `OPEN_BANKING_REDIRECT_URI`.
- **Storage**: `open_banking_connections` table — matter_id FK, provider,
  encrypted access/refresh token, consent expiry (90 days under PSD2 SCA),
  account identifiers, created_by. Tokens encrypted with the same envelope
  key as documents (see encryption-at-rest work).

## How the rest of the platform treats OB data

- Transactions ingested with `source='open_banking'` are **provenance-grade**:
  the assessment engine should treat them as the corroboration baseline —
  uploaded documents are then checked *against* them (amounts, balances,
  account numbers), inverting today's trust model.
- Document verification gains a new cross-check: uploaded statement rows vs
  OB rows for the same account/period → `UPLOAD_OB_MISMATCH` (critical) when
  a client-supplied statement disagrees with the bank's own data.
- The evidence checklist marks statement requirements as satisfied by an OB
  connection covering the required period.
- The audit report records the provider, consent timestamp and account IDs
  (masked) so the SoF file note can cite bank-sourced data explicitly.

## Build order (when prerequisites clear)

1. Aggregator sandbox account; adapter + consent flow behind the flag (S/M).
2. Connection storage + ingest into the transaction store (M).
3. Engine trust-model inversion + upload-vs-OB cross-check (M).
4. Client-portal entry point + solicitor-side connection status UI (S).
5. Live pilot with one consenting client matter.
