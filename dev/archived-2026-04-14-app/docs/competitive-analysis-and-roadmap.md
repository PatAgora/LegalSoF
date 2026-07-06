# Competitive analysis & all-in-one platform roadmap

*Research date: 6 July 2026. Full cited reports were produced in-session; this
is the condensed strategy record.*

## Competitors researched

| | Legl | Thirdfort | Amiqus | Verify365 | Armalytix ("ALX") |
|---|---|---|---|---|---|
| Core | Onboarding+payments+CDD orchestrator | Consumer-app CDD (KYC+SoF) | Onboarding + staff checks (Scotland-strong) | 9-in-1 onboarding (tmGroup-owned) | Open-banking SoF specialist |
| E-IDV engine | Onfido/Entrust + Mitek | Onfido + iProov + Inverid NFC | Onfido + TransUnion/Equifax | Own "DynamicID" (DIATF unconfirmed) | Own NFC Safe-Harbour flow |
| Screening data | ComplyAdvantage | ComplyAdvantage | Undisclosed | Undisclosed | Undisclosed |
| Open banking | TrueLayer | TrueLayer | TrueLayer | Undisclosed | Own FCA AISP registration |
| Payments | Yes (Adyen/Banked) — differentiator | No | No | Stripe ePayments | No (account verification only) |
| In-product risk assessments | Yes (2025 module) | No | Yes (CMRA templates) | No | Risk Insights v2 (SoF-scoped) |
| Known gaps | No hit-remediation workflow; fragmented per-check tabs; no SAR module; no LEAP | No Clio/LEAP/Osprey; no API docs; consumer UX complaints | SoF is visualisation not tracing; no e-sign | Trustpilot 2.3; unverifiable badges | SoF-only breadth (closing via bundles) |

**Pattern: everyone assembles the same third-party engines and competes on
workflow + distribution. Nobody does forensic document verification or deep
funds-lineage tracing (our moat), and nobody covers firm governance, MLRO/SAR
case management, or retention automation.**

"Kaptcher" could not be identified (no UK company of that name; closest:
Katchr, law-firm BI dashboards). "ALX" identified as **Armalytix** (~85%
confidence).

## Regulatory process map a complete platform must cover (LSAG 2025 v1.1 / MLR 2017 as amended June 2026)

1. **FWRA** (reg 18/18A) — SRA found only 47% compliant. → FWRA builder module.
2. **CMRA** (reg 28(12)-(13)) — SRA: 51% ineffective; reasoning mandatory. → CMRA module with blocking gate.
3. **CDD/E-IDV** — HMT guidance (Feb 2026): DIATF-certified IDSPs satisfy reg 28(19). Companies: PSC register is a cross-check, NOT BO verification (reg 28(9)); reg 30A discrepancy reporting duty. → E-IDV framework + KYB module.
4. **Screening** — sanctions is strict-liability (all clients, all work); PEP regime reg 35 (domestic PEPs lower-risk start since Jan 2024). NB: OFSI consolidated list CLOSED Jan 2026 → FCDO UK Sanctions List is the free source (no PEPs). → Screening module with adjudication/remediation.
5. **SoF/SoW** — Nov 2025 SRA thematic review: 11% no checks, 18% collected-never-assessed, 8% ledger mismatch; matter-blocking until SoF established = good practice. → our existing core; the review is the sales narrative.
6. **Ongoing monitoring** (reg 28(11)) — Clyde & Co £500k. → rescreening + review scheduler.
7. **SARs/MLRO** (POCA s.330/331/333A; DAML 7 working days + 31-day moratorium; NCA portal is human-only). → MLRO workbench.
8. **Training/PCPs/audit/retention** (regs 19/21/24/40 — 5yr retention then deletion). → governance modules + existing retention automation.

**LSAG ch.7 reliance rule:** tools never make a firm compliant; keep human
decision points + rationale capture everywhere; ship a vendor-documentation
pack for firms' PCPs; never market as "compliance in a box".

## Build-vs-integrate decisions

- **Screening data:** build on free FCDO UK Sanctions List now (strict-liability layer) + provider adapter. PEP/adverse-media upgrade: dilisense PAYG (€0.10/check, 100 free/mo, self-serve) or ComplyAdvantage Starter ($99/mo); scale option OpenSanctions + self-hosted yente (needs commercial data licence).
- **E-IDV:** integrate, never build — shortlist ComplyCube ($99/mo, UK, DIATF), Veriff ($49/mo, $0.80/check, DIATF), Yoti (UK-native DIATF pioneer). Verify certification on the official DVS register before contracting.
- **Open banking:** TrueLayer (see docs/open-banking-design.md).
- **KYB:** Companies House Public Data API is free (needs API key).
- **Payments:** replicate last or partner (FCA/PCI lift).

## Phased roadmap

- **Phase 1 (built in-session, July 2026):** sanctions screening + hit
  adjudication/remediation + rescreening · CMRA + FWRA modules · KYB
  (Companies House, PSC tree, reg 30A discrepancy flow) · E-IDV framework
  (manual provider + ComplyCube-shaped stub) · MLRO workbench (internal
  reports with tipping-off access control, SAR records, DAML working-day
  timers, training records, policy repository).
- **Phase 2:** live E-IDV provider; dilisense/ComplyAdvantage screening data;
  party-type compliance bundles in the client portal (Armalytix pattern);
  ongoing-monitoring scheduler; engagement-letter e-sign.
- **Phase 3:** open banking SoF; account/payee verification; smart adaptive
  SoF questionnaire (Legl's 8-type taxonomy); AI hit narratives; LEAP + Clio
  integrations (LEAP is uncovered by Legl AND Thirdfort — clearest
  distribution gap); reusable identity wallet (Amiqus pattern).

## Distribution/commercial notes

- Pricing norm: platform fee + per-check credits; client recharge is accepted
  practice (Thirdfort suggests £5–£40/check recharge).
- The SRA thematic review, unlimited SRA fining powers (Mar 2024), and the
  HMT digital-ID guidance (Feb 2026) are the three regulatory tailwinds to
  anchor marketing on.
