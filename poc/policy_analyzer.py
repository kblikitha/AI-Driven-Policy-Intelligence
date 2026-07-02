#!/usr/bin/env python3
"""
Healthcare Policy Content Analyzer — Cotiviti Intern Assessment POC
Topic 3: Content Management in Health Care

Demonstrates:
  1. Policy change summarization (what changed between v1 and v2)
  2. Structured coding rule extraction from the new policy (JSON output)
  3. Plain-language payer alert generation

Usage:
    python3 policy_analyzer.py                          # live mode (requires ANTHROPIC_API_KEY)
    python3 policy_analyzer.py --demo                   # offline demo with pre-computed output
    python3 policy_analyzer.py <old_policy> <new_policy>  # use your own files
"""

import sys
import json
import os
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent / "sample_policies"
MODEL = "claude-opus-4-8"
DIVIDER = "─" * 70


# ── helpers ──────────────────────────────────────────────────────────────────

def load_policy(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def print_section(title: str, body: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)
    print(body)


# ── live Claude API calls ─────────────────────────────────────────────────────

def call_claude(system: str, user: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def summarize_changes(old_text: str, new_text: str) -> str:
    system = (
        "You are a healthcare payment policy analyst at a managed care organization. "
        "You specialize in comparing billing and coding policies to identify impactful changes "
        "for payers, providers, and revenue cycle teams. "
        "Be concise, accurate, and clinically aware. Never hallucinate."
    )
    user = f"""Compare the following two versions of a healthcare billing policy.

OLD POLICY (Version 1):
{old_text}

NEW POLICY (Version 2):
{new_text}

Produce a structured change summary with these sections:
1. EXECUTIVE SUMMARY (2–3 sentences on the most important changes)
2. KEY CHANGES (bullet list — what specifically changed, with old vs. new where relevant)
3. IMPACT ON PROVIDERS (brief bullets)
4. IMPACT ON PAYERS (brief bullets)
5. COMPLIANCE RISKS (any new restrictions or denial triggers)
"""
    return call_claude(system, user)


def extract_coding_rules(policy_text: str) -> dict:
    system = (
        "You are a medical coding specialist. Extract actionable billing and coding rules "
        "from healthcare policy documents as structured data. "
        "Output ONLY valid JSON — no markdown fences, no commentary."
    )
    user = f"""Extract all coding rules from the following healthcare billing policy.

POLICY:
{policy_text}

Return a JSON object with this exact schema:
{{
  "policy_name": "<string>",
  "effective_date": "<string>",
  "cpt_codes": [
    {{
      "code": "<string>",
      "description": "<string>",
      "patient_type": "new | established | telehealth",
      "mdm_level": "<string>",
      "time_range_minutes": "<string>"
    }}
  ],
  "billing_rules": [
    {{
      "rule": "<short rule title>",
      "detail": "<full description>",
      "denial_risk": true | false
    }}
  ],
  "reimbursement": {{
    "participating_rate": "<string>",
    "non_participating_rate": "<string>",
    "telehealth_parity": "<string>"
  }},
  "excluded_services": ["<string>"]
}}
"""
    raw = call_claude(system, user)
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def generate_payer_alert(change_summary: str) -> str:
    system = (
        "You are a payer communications specialist. Write clear, professional provider "
        "network alerts based on policy change summaries. Keep alerts under 150 words."
    )
    user = f"""Based on the following policy change summary, write a brief provider network alert
that a health plan would send to in-network physicians. Use a professional tone.

CHANGE SUMMARY:
{change_summary}

Format:
SUBJECT: [subject line]
EFFECTIVE: [date]
ALERT BODY: [body text]
"""
    return call_claude(system, user)


# ── demo mode (pre-computed realistic output) ─────────────────────────────────

DEMO_CHANGE_SUMMARY = """
1. EXECUTIVE SUMMARY
Version 2.0 of the E/M Billing Policy expands coverage to include telehealth visits,
introduces updated documentation requirements aligned with 2024 AMA/CMS guidelines
(MDM or total time — no longer requiring the traditional three key component method),
and increases the participating provider reimbursement rate from 110% to 115% of MPFS.

2. KEY CHANGES
• Scope expanded: "outpatient office visits" now includes "telehealth visits"
• Documentation method: Three-key-component method REMOVED; replaced by MDM OR
  total time on date of encounter (including non-face-to-face time)
• Copy-forward prohibition: Copy-forward documentation without attestation is now
  explicitly prohibited and constitutes a denial trigger
• Telehealth (NEW Section 3.3): POS 02 / POS 10, Modifier 95 required; audio-only
  allowed with Modifier 93 + prior authorization
• Split/shared visits: 2024 CMS "substantive portion" rule now applies (>50% total time)
• Reimbursement: Participating rate increased from 110% → 115% of MPFS
• Telehealth parity: In-person parity through December 31, 2024

3. IMPACT ON PROVIDERS
• Must update billing workflows to use POS 02/10 and Modifier 95 for telehealth
• Time documentation must now include non-face-to-face time on day of encounter
• Copy-forward EHR templates require attestation language to avoid denials
• Split/shared visit attestation must confirm >50% substantive portion

4. IMPACT ON PAYERS
• Claims intake systems must validate Modifier 95 and POS 02/10 for telehealth claims
• Expanded covered services will increase claim volume (telehealth inclusion)
• Higher reimbursement rate (115%) increases per-claim cost for in-network E/M
• New denial logic required: copy-forward without attestation → denial

5. COMPLIANCE RISKS
• HIGH: Copy-forward documentation without attestation → automatic denial
• HIGH: Telehealth claims missing Modifier 95 → denial
• MEDIUM: Audio-only visits without prior authorization → denial
• MEDIUM: Split/shared visits where >50% substantive portion not documented → denial
• LOW: Providers billing under old three-key-component framework → potential downcoding
"""

DEMO_RULES_JSON = {
    "policy_name": "Evaluation and Management (E/M) Services",
    "effective_date": "January 1, 2024",
    "cpt_codes": [
        {"code": "99202", "description": "New patient office visit", "patient_type": "new", "mdm_level": "Straightforward", "time_range_minutes": "15–29"},
        {"code": "99203", "description": "New patient office visit", "patient_type": "new", "mdm_level": "Low", "time_range_minutes": "30–44"},
        {"code": "99204", "description": "New patient office visit", "patient_type": "new", "mdm_level": "Moderate", "time_range_minutes": "45–59"},
        {"code": "99205", "description": "New patient office visit", "patient_type": "new", "mdm_level": "High", "time_range_minutes": "60–74"},
        {"code": "99211", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Minimal", "time_range_minutes": "N/A"},
        {"code": "99212", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Straightforward", "time_range_minutes": "10–19"},
        {"code": "99213", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Low", "time_range_minutes": "20–29"},
        {"code": "99214", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Moderate", "time_range_minutes": "30–39"},
        {"code": "99215", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "High", "time_range_minutes": "40–54"}
    ],
    "billing_rules": [
        {"rule": "Telehealth POS Requirement", "detail": "Telehealth E/M visits must be billed with POS 02 (patient not in home) or POS 10 (patient in home).", "denial_risk": True},
        {"rule": "Modifier 95 for Telehealth", "detail": "Modifier 95 must be appended to all telehealth E/M codes.", "denial_risk": True},
        {"rule": "Audio-Only Prior Authorization", "detail": "Audio-only visits (Modifier 93) require prior authorization when video is not technically feasible.", "denial_risk": True},
        {"rule": "Modifier 25 — Same-Day E/M + Procedure", "detail": "Modifier 25 must be appended to E/M code when billed same-day as a procedure.", "denial_risk": True},
        {"rule": "Copy-Forward Prohibition", "detail": "Copy-forward documentation from previous visits is prohibited without explicit attestation of review and update.", "denial_risk": True},
        {"rule": "Split/Shared Visit — Substantive Portion", "detail": "The billing provider must perform >50% of total encounter time for split/shared visit billing.", "denial_risk": True},
        {"rule": "Documentation Method", "detail": "Documentation must be based on MDM OR total time on date of encounter (including non-face-to-face time). Three key components no longer required.", "denial_risk": False},
        {"rule": "Incident-To Exclusion", "detail": "Incident-to billing is not covered for new patients.", "denial_risk": True}
    ],
    "reimbursement": {
        "participating_rate": "115% of Medicare Physician Fee Schedule (MPFS)",
        "non_participating_rate": "80% of MPFS",
        "telehealth_parity": "In-person parity through December 31, 2024"
    },
    "excluded_services": [
        "Telephone-only consultations without documented in-office or telehealth component",
        "Services rendered by unlicensed personnel",
        "Administrative encounters not involving clinical evaluation",
        "Telehealth visits via non-HIPAA-compliant platforms (e.g., standard FaceTime, standard Zoom without BAA)"
    ]
}

DEMO_ALERT = """
SUBJECT: Important Policy Update — E/M Billing Changes Effective January 1, 2024

EFFECTIVE: January 1, 2024

ALERT BODY:
Dear Network Provider,

Effective January 1, 2024, our E/M billing policy has been updated. Key changes include:

• Documentation: The three key component method is no longer required. Document using
  Medical Decision Making OR total time on the date of encounter.
• Copy-forward documentation without explicit attestation of review will result in
  claim denial.
• Telehealth: All telehealth E/M claims require POS 02/10 and Modifier 95.
  Audio-only visits require prior authorization.
• Reimbursement: Participating provider rate increases to 115% of MPFS.

Please update your billing workflows accordingly. Contact Provider Relations with questions.
"""


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    demo_mode = "--demo" in sys.argv

    if len(sys.argv) == 3 and sys.argv[1] != "--demo":
        old_path = Path(sys.argv[1])
        new_path = Path(sys.argv[2])
    else:
        old_path = SAMPLE_DIR / "policy_v1.txt"
        new_path = SAMPLE_DIR / "policy_v2.txt"

    print("\n╔══════════════════════════════════════════════════════════════════════╗")
    print("║       Healthcare Policy Content Analyzer  —  Cotiviti POC           ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"\n  Old policy : {old_path.name}")
    print(f"  New policy : {new_path.name}")
    print(f"  Model      : {MODEL}")
    print(f"  Mode       : {'DEMO (pre-computed output)' if demo_mode else 'LIVE (Claude API)'}")

    if demo_mode:
        # ── Task 1 ────────────────────────────────────────────────────────────
        print("\n[1/3] Summarizing policy changes...")
        print_section("POLICY CHANGE SUMMARY", DEMO_CHANGE_SUMMARY)

        # ── Task 2 ────────────────────────────────────────────────────────────
        print("\n[2/3] Extracting structured coding rules from new policy...")
        print_section("EXTRACTED CODING RULES (JSON)", json.dumps(DEMO_RULES_JSON, indent=2))

        output_path = Path(__file__).parent / "extracted_rules.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(DEMO_RULES_JSON, f, indent=2)
        print(f"\n  Saved to: {output_path}")

        # ── Task 3 ────────────────────────────────────────────────────────────
        print("\n[3/3] Generating provider network alert...")
        print_section("GENERATED PROVIDER ALERT", DEMO_ALERT)

    else:
        if not old_path.exists() or not new_path.exists():
            print(f"ERROR: Cannot find policy files.\n  old: {old_path}\n  new: {new_path}")
            sys.exit(1)

        old_text = load_policy(old_path)
        new_text = load_policy(new_path)

        # ── Task 1 ────────────────────────────────────────────────────────────
        print("\n[1/3] Summarizing policy changes...")
        change_summary = summarize_changes(old_text, new_text)
        print_section("POLICY CHANGE SUMMARY", change_summary)

        # ── Task 2 ────────────────────────────────────────────────────────────
        print("\n[2/3] Extracting structured coding rules from new policy...")
        rules = extract_coding_rules(new_text)
        print_section("EXTRACTED CODING RULES (JSON)", json.dumps(rules, indent=2))

        output_path = Path(__file__).parent / "extracted_rules.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2)
        print(f"\n  Saved to: {output_path}")

        # ── Task 3 ────────────────────────────────────────────────────────────
        print("\n[3/3] Generating provider network alert...")
        alert = generate_payer_alert(change_summary)
        print_section("GENERATED PROVIDER ALERT", alert)

    print(f"\n{DIVIDER}")
    print("  Analysis complete.")
    print(DIVIDER + "\n")


if __name__ == "__main__":
    main()
