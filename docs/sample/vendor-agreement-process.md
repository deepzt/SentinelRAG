# Vendor Onboarding Agreement Process

**Department:** Legal / Procurement  
**Classification:** Confidential  
**Version:** v1 | **Last Updated:** 2026-02  
**Owner:** Legal Team  
**Access:** Managers and above

---

## Overview

This SOP defines the end-to-end process for onboarding a new vendor, from initial evaluation through contract execution and ongoing governance. All vendors must complete this process before any purchase order, software access, or data sharing can occur.

Vendors fall into three risk tiers:
- **Tier 1 (Critical):** Vendors with access to customer data or core infrastructure
- **Tier 2 (Standard):** Business tools and SaaS with internal data access
- **Tier 3 (Low-risk):** One-time purchases, office supplies, no data access

---

## Phase 1 — Vendor Evaluation

### Step 1.1 — Business Justification

The requesting department must complete a **Vendor Request Form** in Workday:
- Business need and use case
- Estimated annual spend
- Data access requirements (what data will the vendor touch?)
- Alternatives considered
- Proposed contract term

Approval required before proceeding:
- Annual spend < $10k: Manager approval
- $10k – $50k: Manager + Finance approval
- $50k – $250k: VP + Finance + Legal review
- > $250k: C-suite + Board budget committee

### Step 1.2 — Security Risk Assessment

**Tier 1 and Tier 2 vendors only.** The Security team conducts a vendor security review:

1. Send the vendor the **Security Questionnaire** (standardized CAIQ/SIG Lite)
2. Review responses and request evidence (SOC 2 Type II, ISO 27001 certificate, penetration test reports)
3. Verify data residency: where will our data be stored?
4. Review the vendor's subprocessor list (GDPR requirement for EU data)
5. Security team issues a risk rating: **Approved / Conditionally Approved / Rejected**

Turnaround time: 5–10 business days.

### Step 1.3 — Financial Due Diligence

Finance reviews:
- Vendor financial stability (for contracts >$50k/year)
- Payment terms compatibility
- Insurance requirements (general liability, E&O, cyber liability minimums)

---

## Phase 2 — Contract Negotiation

### Step 2.1 — Contract Type Selection

| Vendor Type | Standard Contract |
|-------------|------------------|
| SaaS subscription | SaaS Agreement + DPA |
| Professional services | Master Services Agreement (MSA) + SOW |
| Hardware / physical goods | Purchase Agreement |
| Reseller / partner | Reseller Agreement |

Never use vendor-paper without Legal review. Always start from our standard templates.

### Step 2.2 — Data Processing Agreement (DPA)

A DPA is **mandatory** when the vendor will process personal data of employees or customers. Legal will assess whether GDPR, CCPA, or other frameworks apply.

DPA must include:
- Scope of processing (purpose, categories of data, duration)
- Data subject rights obligations
- Sub-processor notification requirements
- Breach notification SLA (72 hours from vendor discovery)
- Audit rights
- Data deletion obligations upon contract termination

### Step 2.3 — Key Contract Terms to Negotiate

**Always negotiate:**
- **Liability cap:** Should be ≥ 12 months of fees paid. For Tier 1 vendors handling customer data, seek 2x annual fees.
- **SLA and credits:** Minimum 99.5% uptime for production services; 99.9% for critical infrastructure
- **Termination for convenience:** Maximum 90-day notice period
- **Price lock:** At least 12 months; ideally matching contract term
- **Data portability:** Right to export all data in machine-readable format upon termination

**Standard boilerplate to include:**
- Governing law: Delaware (or local jurisdiction for international vendors)
- Dispute resolution: Arbitration
- Anti-bribery / anti-corruption representations (FCPA clause)
- Modern Slavery Act representations (for UK operations)

### Step 2.4 — Legal Review and Redlines

1. Legal drafts or reviews contract in ContractPodAi
2. Redlines exchanged with vendor (maximum 3 rounds before escalation)
3. If vendor insists on unacceptable terms: escalate to VP + Legal Director

---

## Phase 3 — Contract Execution

### Step 3.1 — Approval to Sign

Final contract must be approved before signature:

| Annual Value | Authorized Signer |
|-------------|------------------|
| < $25k | Manager |
| $25k – $100k | VP |
| $100k – $500k | C-suite |
| > $500k | CEO + Board approval required |

### Step 3.2 — DocuSign Execution

1. Legal uploads final contract to ContractPodAi
2. DocuSign envelope sent to authorized signers
3. Vendor countersigns
4. Fully executed contract auto-filed in ContractPodAi

### Step 3.3 — Vendor Setup in Finance Systems

After execution, Finance team:
1. Creates vendor record in NetSuite (ERP)
2. Collects W-9 or W-8BEN for tax compliance
3. Verifies payment information (bank transfer preferred; checks require Finance Director approval)
4. Sets up purchase order (PO) matching for payments > $5k

---

## Phase 4 — Ongoing Vendor Governance

### Annual Review

All active vendors with annual spend > $25k must undergo annual review:
- Updated security questionnaire (Tier 1/2 only)
- Contract renewal decision (renew / renegotiate / terminate)
- Performance review against SLAs
- Finance review of actual vs. budgeted spend

### Vendor Offboarding

When a vendor contract terminates:
1. **Data deletion:** Confirm all company data deleted within 30 days
2. **Access revocation:** IT removes all vendor SSO access, API keys, and network permissions
3. **DPA closeout:** Legal confirms DPA obligations fulfilled
4. **Final payment:** Finance processes final invoice after data deletion confirmed

---

## Contact Directory

| Role | Contact |
|------|---------|
| Legal (contracts) | `legal@sentinelcorp.internal` |
| Security review | `security-review@sentinelcorp.internal` |
| Finance / procurement | `procurement@sentinelcorp.internal` |
| Data Privacy Officer | `dpo@sentinelcorp.internal` |
