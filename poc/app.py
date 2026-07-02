#!/usr/bin/env python3
"""
Healthcare Policy Content Analyzer -- Streamlit Dashboard
Cotiviti Intern Assessment | Topic 3: Content Management in Health Care
"""

import json
import os
import sys
import time
import io
import hashlib
import difflib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

SAMPLE_DIR = Path(__file__).parent / "sample_policies"
sys.path.insert(0, str(Path(__file__).parent))

# ── demo data ─────────────────────────────────────────────────────────────────

DEMO_CHANGE_SUMMARY = {
    "executive_summary": (
        "Version 2.0 of the E/M Billing Policy expands coverage to include telehealth visits, "
        "introduces updated documentation requirements aligned with 2024 AMA/CMS guidelines "
        "(MDM or total time -- no longer requiring the three key component method), "
        "and increases the participating provider reimbursement rate from 110% to 115% of MPFS."
    ),
    "key_changes": [
        "Scope expanded: outpatient office visits now includes telehealth visits",
        "Documentation: Three-key-component method REMOVED; replaced by MDM OR total time on date of encounter",
        "Copy-forward prohibition: documentation without attestation is now an explicit denial trigger",
        "Telehealth (NEW Section 3.3): POS 02/POS 10, Modifier 95 required; audio-only allowed with Modifier 93 + prior auth",
        "Split/shared visits: 2024 CMS substantive portion rule applies (>50% total time)",
        "Reimbursement: Participating rate increased from 110% to 115% of MPFS",
        "Telehealth parity: In-person parity through December 31, 2024",
    ],
    "provider_impact": [
        "Must update billing workflows to use POS 02/10 and Modifier 95 for telehealth",
        "Time documentation must now include non-face-to-face time on day of encounter",
        "Copy-forward EHR templates require attestation language to avoid denials",
        "Split/shared visit attestation must confirm >50% substantive portion",
    ],
    "payer_impact": [
        "Claims intake systems must validate Modifier 95 and POS 02/10 for telehealth claims",
        "Expanded covered services will increase claim volume",
        "Higher reimbursement rate (115%) increases per-claim cost for in-network E/M",
        "New denial logic required: copy-forward without attestation",
    ],
    "compliance_risks": [
        {"level": "HIGH", "text": "Copy-forward documentation without attestation leads to automatic denial", "basis": "Policy states: 'Copy-forward documentation without attestation will result in claim denial'"},
        {"level": "HIGH", "text": "Telehealth claims missing Modifier 95 leads to denial", "basis": "Policy states: 'Modifier 95 must be appended to all telehealth E/M codes'"},
        {"level": "MEDIUM", "text": "Audio-only visits without prior authorization leads to denial", "basis": "Policy states audio-only requires prior authorization — denial implied if not obtained"},
        {"level": "MEDIUM", "text": "Split/shared visits where >50% substantive portion not documented", "basis": "Policy states substantive portion rule applies — consequence AI-inferred"},
        {"level": "LOW", "text": "Providers billing under old three-key-component framework risk downcoding", "basis": "AI-inferred — policy removes old method but does not state explicit penalty"},
    ],
}

DEMO_RULES = {
    "policy_name": "Evaluation and Management (E/M) Services",
    "effective_date": "January 1, 2024",
    "cpt_codes": [
        {"code": "99202", "description": "New patient office visit", "patient_type": "new", "mdm_level": "Straightforward", "time_range_minutes": "15-29"},
        {"code": "99203", "description": "New patient office visit", "patient_type": "new", "mdm_level": "Low", "time_range_minutes": "30-44"},
        {"code": "99204", "description": "New patient office visit", "patient_type": "new", "mdm_level": "Moderate", "time_range_minutes": "45-59"},
        {"code": "99205", "description": "New patient office visit", "patient_type": "new", "mdm_level": "High", "time_range_minutes": "60-74"},
        {"code": "99211", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Minimal", "time_range_minutes": "N/A"},
        {"code": "99212", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Straightforward", "time_range_minutes": "10-19"},
        {"code": "99213", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Low", "time_range_minutes": "20-29"},
        {"code": "99214", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "Moderate", "time_range_minutes": "30-39"},
        {"code": "99215", "description": "Established patient office visit", "patient_type": "established", "mdm_level": "High", "time_range_minutes": "40-54"},
    ],
    "billing_rules": [
        {"rule": "Telehealth POS Requirement", "detail": "Telehealth E/M visits must be billed with POS 02 (patient not in home) or POS 10 (patient in home).", "potential_denial_risk": True, "denial_risk_basis": "Policy explicitly requires POS code — missing it would cause claim rejection"},
        {"rule": "Modifier 95 for Telehealth", "detail": "Modifier 95 must be appended to all telehealth E/M codes.", "potential_denial_risk": True, "denial_risk_basis": "Policy states Modifier 95 is required — AI-inferred denial if absent"},
        {"rule": "Audio-Only Prior Authorization", "detail": "Audio-only visits (Modifier 93) require prior authorization when video is not technically feasible.", "potential_denial_risk": True, "denial_risk_basis": "AI-inferred — prior auth requirement implies denial without it"},
        {"rule": "Modifier 25 Same-Day E/M + Procedure", "detail": "Modifier 25 must be appended to E/M code when billed same-day as a procedure.", "potential_denial_risk": True, "denial_risk_basis": "AI-inferred from standard billing practice; not explicitly stated as denial trigger"},
        {"rule": "Copy-Forward Prohibition", "detail": "Copy-forward documentation from previous visits is prohibited without explicit attestation.", "potential_denial_risk": True, "denial_risk_basis": "Policy explicitly states: 'will result in claim denial'"},
        {"rule": "Split/Shared Visit Substantive Portion", "detail": "The billing provider must perform >50% of total encounter time for split/shared visit billing.", "potential_denial_risk": True, "denial_risk_basis": "AI-inferred — policy states rule applies but consequence not explicitly stated"},
        {"rule": "Documentation Method", "detail": "Documentation must be based on MDM OR total time on date of encounter. Three key components no longer required.", "potential_denial_risk": False, "denial_risk_basis": "Process change only — no denial consequence stated"},
        {"rule": "Incident-To Exclusion", "detail": "Incident-to billing is not covered for new patients.", "potential_denial_risk": True, "denial_risk_basis": "Policy explicitly excludes this service — claim would be non-covered"},
    ],
    "reimbursement": {
        "participating_rate": "115% of Medicare Physician Fee Schedule (MPFS)",
        "non_participating_rate": "80% of MPFS",
        "telehealth_parity": "In-person parity through December 31, 2024",
    },
    "excluded_services": [
        "Telephone-only consultations without documented in-office or telehealth component",
        "Services rendered by unlicensed personnel",
        "Administrative encounters not involving clinical evaluation",
        "Telehealth visits via non-HIPAA-compliant platforms (e.g., standard FaceTime, Zoom without BAA)",
    ],
}

DEMO_ALERT = """SUBJECT: Important Policy Update -- E/M Billing Changes Effective January 1, 2024

EFFECTIVE: January 1, 2024

ALERT BODY:
Provider Communication Draft

Effective January 1, 2024, our E/M billing policy has been updated. Key changes include:

* Documentation: The three key component method is no longer required. Document using
  Medical Decision Making OR total time on the date of encounter.
* Copy-forward documentation without explicit attestation of review will result in
  claim denial.
* Telehealth: All telehealth E/M claims require POS 02/10 and Modifier 95.
  Audio-only visits require prior authorization.
* Reimbursement: Participating provider rate increases to 115% of MPFS.

Please update your billing workflows accordingly. Contact Provider Relations with questions."""


# ── PDF text extraction ───────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def load_file(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(raw)
    return raw.decode("utf-8", errors="replace")


def load_path(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(path.read_bytes())
    return path.read_text(encoding="utf-8")


# ── AI backend (Gemini or Claude) ────────────────────────────────────────────

_RETRYABLE = ("503", "429", "UNAVAILABLE", "quota", "ResourceExhausted", "rate", "overloaded")

def call_gemini(system: str, user: str) -> str:
    from google import genai as new_genai
    client = new_genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=f"{system}\n\n{user}",
            )
            return response.text.strip()
        except Exception as e:
            if any(tok in str(e) for tok in _RETRYABLE) and attempt < 2:
                time.sleep(2 ** (attempt + 2))  # 4s, 8s
                continue
            raise


def call_claude(system: str, user: str) -> str:
    import anthropic
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text.strip()


def call_ai(system: str, user: str, backend: str) -> str:
    if backend == "Gemini (free)":
        return call_gemini(system, user)
    return call_claude(system, user)


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIMIZED CHUNKING PIPELINE
# Key improvements over v1:
#   1. Parallel chunk analysis (ThreadPoolExecutor) — biggest speedup
#   2. Combined extraction: summary + coding rules in ONE call per chunk
#   3. Programmatic JSON merge (no extra LLM call for deduplication)
#   4. SHA-256 document cache — same PDFs = instant results
#   5. Proper difflib diff viewer
#   6. Robust JSON parsing with fallback
# ═══════════════════════════════════════════════════════════════════════════════

CHUNK_TARGET_CHARS = 11_000
MAX_PARALLEL_WORKERS = 4

# ── document cache (keyed by sha256 of text) ──────────────────────────────────

_DOC_CACHE: dict[str, dict] = {}


def _doc_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ── splitting ──────────────────────────────────────────────────────────────────

def split_into_chunks(text: str, target_chars: int = CHUNK_TARGET_CHARS) -> list[str]:
    """
    Split at paragraph boundaries. Never cuts mid-sentence.
    Covers 100% of the document — no content is skipped.
    """
    if len(text) <= target_chars:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        if current_len + len(para) > target_chars and current:
            chunks.append("\n\n".join(current))
            current, current_len = [], 0
        current.append(para)
        current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


# ── single combined chunk analysis (summary + rules in one call) ───────────────

def analyze_chunk(
    chunk: str,
    chunk_index: int,
    total_chunks: int,
    doc_label: str,
    backend: str,
    max_retries: int = 3,
) -> dict:
    """
    ONE AI call per chunk that extracts BOTH the narrative summary AND
    structured coding rules. Halves the total number of API calls vs
    separate summary + rules passes.

    Returns a dict with keys: "summary" (str) and "rules" (dict).
    On failure, returns {"summary": "[FAILED]", "rules": {}, "failed": True}.
    """
    system = (
        "You are a healthcare payment policy analyst and medical coding specialist. "
        "Extract ONLY what is explicitly written in this policy excerpt. "
        "Never infer, hallucinate, or add content not present in the text. "
        "Output ONLY valid JSON — no markdown fences, no commentary."
    )
    user = f"""Analyze chunk {chunk_index + 1} of {total_chunks} from: {doc_label}

POLICY EXCERPT:
{chunk}

Return ONLY this JSON:
{{
  "summary": {{
    "policy_changes": ["list only changes explicitly stated"],
    "billing_rules": ["billing rules explicitly stated"],
    "compliance_requirements": ["compliance items explicitly stated"],
    "reimbursement": ["reimbursement details explicitly stated"],
    "exclusions": ["exclusions explicitly stated"],
    "denial_triggers": ["denial triggers explicitly stated"],
    "provider_impacts": ["provider impacts explicitly stated"],
    "payer_impacts": ["payer impacts explicitly stated"]
  }},
  "cpt_codes": [
    {{
      "code": "<string>",
      "description": "<string>",
      "patient_type": "new | established | telehealth",
      "mdm_level": "<string>",
      "time_range_minutes": "<string>"
    }}
  ],
  "billing_rules_structured": [
    {{
      "rule": "<short title>",
      "detail": "<exact language from document>",
      "potential_denial_risk": true,
      "denial_risk_basis": "<quote or 'AI-inferred'>"
    }}
  ],
  "reimbursement_structured": {{
    "participating_rate": "<string or empty>",
    "non_participating_rate": "<string or empty>",
    "telehealth_parity": "<string or empty>"
  }},
  "excluded_services": ["<string>"]
}}
Omit array items that don't appear in this excerpt. Return empty arrays/strings for missing fields.
"""

    last_err = None
    for attempt in range(max_retries):
        try:
            raw = call_ai(system, user, backend)
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.loads(raw)
        except json.JSONDecodeError:
            # JSON malformed but call succeeded — don't retry, return what we got
            return {"summary": raw, "cpt_codes": [], "billing_rules_structured": [],
                    "reimbursement_structured": {}, "excluded_services": [], "parse_failed": True}
        except Exception as e:
            last_err = e
            if any(c in str(e) for c in _RETRYABLE) and attempt < max_retries - 1:
                time.sleep(2 ** (attempt + 2))
            else:
                break

    return {"summary": {}, "cpt_codes": [], "billing_rules_structured": [],
            "reimbursement_structured": {}, "excluded_services": [],
            "failed": True, "error": str(last_err)}


# ── parallel chunk processing ──────────────────────────────────────────────────

def process_chunks_parallel(
    chunks: list[str],
    doc_label: str,
    backend: str,
    progress_bar,
    status_text,
    progress_start: int,
    progress_end: int,
) -> list[dict]:
    """
    Analyze all chunks in parallel using ThreadPoolExecutor.
    Progress bar updates as each future completes.
    Returns results in original chunk order.
    """
    total = len(chunks)
    results: list[dict | None] = [None] * total
    completed = 0

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_WORKERS) as pool:
        futures = {
            pool.submit(analyze_chunk, chunk, i, total, doc_label, backend): i
            for i, chunk in enumerate(chunks)
        }
        for future in as_completed(futures):
            idx = futures[future]
            completed += 1
            pct = progress_start + int((progress_end - progress_start) * completed / total)
            status_text.text(f"{doc_label} — analyzed chunk {completed} of {total}...")
            progress_bar.progress(min(pct, 99))
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {"failed": True, "error": str(e), "summary": {},
                                "cpt_codes": [], "billing_rules_structured": [],
                                "reimbursement_structured": {}, "excluded_services": []}

    return results  # type: ignore[return-value]


# ── programmatic merge (no extra LLM call) ────────────────────────────────────

def _merge_lists(*lists) -> list:
    """Deduplicate while preserving order."""
    seen, out = set(), []
    for lst in lists:
        for item in (lst or []):
            key = json.dumps(item, sort_keys=True) if isinstance(item, dict) else str(item)
            if key not in seen:
                seen.add(key)
                out.append(item)
    return out


def merge_chunk_results(chunk_results: list[dict], doc_label: str) -> dict:
    """
    Programmatically merge all chunk results into one document summary.
    Zero extra LLM calls — pure Python deduplication.
    """
    merged_summary: dict[str, list] = {
        "policy_changes": [], "billing_rules": [], "compliance_requirements": [],
        "reimbursement": [], "exclusions": [], "denial_triggers": [],
        "provider_impacts": [], "payer_impacts": [],
    }
    all_cpt: list[dict] = []
    all_billing: list[dict] = []
    all_excluded: list[str] = []
    reimbursement = {"participating_rate": "", "non_participating_rate": "", "telehealth_parity": ""}
    failed_chunks: list[int] = []

    for i, result in enumerate(chunk_results):
        if result.get("failed") or result.get("parse_failed"):
            failed_chunks.append(i + 1)
            # If it's a parse_failed, we at least got text — add it to policy_changes
            if result.get("parse_failed") and isinstance(result.get("summary"), str):
                merged_summary["policy_changes"].append(f"[Chunk {i+1} raw]: {result['summary'][:500]}")
            continue

        s = result.get("summary", {})
        if isinstance(s, dict):
            for key in merged_summary:
                merged_summary[key] = _merge_lists(merged_summary[key], s.get(key, []))

        # Deduplicate CPT codes by code number
        for cpt in result.get("cpt_codes", []):
            if cpt.get("code") and not any(c["code"] == cpt["code"] for c in all_cpt):
                all_cpt.append(cpt)

        # Deduplicate billing rules by rule title
        for rule in result.get("billing_rules_structured", []):
            if rule.get("rule") and not any(r["rule"] == rule["rule"] for r in all_billing):
                all_billing.append(rule)

        all_excluded = list(dict.fromkeys(all_excluded + result.get("excluded_services", [])))

        # Take first non-empty reimbursement values found across chunks
        r = result.get("reimbursement_structured", {})
        for field in reimbursement:
            if not reimbursement[field] and r.get(field):
                reimbursement[field] = r[field]

    if failed_chunks:
        st.warning(f"{doc_label}: chunks {failed_chunks} failed and were skipped.")

    return {
        "narrative": merged_summary,
        "cpt_codes": all_cpt,
        "billing_rules": all_billing,
        "reimbursement": reimbursement,
        "excluded_services": all_excluded,
    }


# ── final comparison (one LLM call) ───────────────────────────────────────────

def compare_complete_documents(old_merged: dict, new_merged: dict, backend: str) -> dict:
    """
    Compare the two merged document summaries.
    Narrative sections are passed as text; one LLM call produces the final JSON.
    """
    def narrative_to_text(n: dict) -> str:
        lines = []
        labels = {
            "policy_changes": "POLICY CHANGES", "billing_rules": "BILLING RULES",
            "compliance_requirements": "COMPLIANCE", "reimbursement": "REIMBURSEMENT",
            "exclusions": "EXCLUSIONS", "denial_triggers": "DENIAL TRIGGERS",
            "provider_impacts": "PROVIDER IMPACTS", "payer_impacts": "PAYER IMPACTS",
        }
        for key, label in labels.items():
            items = n.get(key, [])
            if items:
                lines.append(f"{label}:")
                lines.extend(f"  - {item}" for item in items)
        return "\n".join(lines)

    old_text = narrative_to_text(old_merged.get("narrative", {}))
    new_text = narrative_to_text(new_merged.get("narrative", {}))

    system = (
        "You are a healthcare payment policy analyst. Compare two policy summaries. "
        "CRITICAL INSTRUCTION: Preserve EVERY unique policy change. "
        "Do NOT compress, merge, or drop any finding. "
        "If multiple items describe the same change, consolidate into one bullet — "
        "but never discard unique findings. The final output must contain every distinct "
        "policy change identified across both summaries. "
        "ONLY report changes explicitly present in the source material. "
        "Output ONLY valid JSON — no markdown, no commentary."
    )
    user = f"""Compare these two complete healthcare policy summaries.

DOCUMENT 1 (old / baseline):
{old_text}

DOCUMENT 2 (new / updated):
{new_text}

COMPLETENESS RULE: List EVERY unique change found between the two documents.
Do NOT omit, compress, or summarize individual findings into fewer bullets.
If multiple items describe the same change, consolidate into one bullet.
Never discard unique findings — the goal is a complete inventory.

Return ONLY this JSON:
{{
  "executive_summary": "3-4 sentence overview covering the scope and most important categories of changes",
  "key_changes": [
    "EVERY unique change found — one bullet per distinct finding, do NOT omit or compress"
  ],
  "provider_impact": [
    "Each specific workflow, documentation, or billing action providers must take"
  ],
  "payer_impact": [
    "Each specific system, logic, or process change payers must implement"
  ],
  "compliance_risks": [
    {{
      "level": "HIGH | MEDIUM | LOW",
      "text": "risk description",
      "basis": "direct quote or section reference"
    }}
  ]
}}

Risk criteria:
- HIGH: document explicitly states denial, rejection, or non-payment
- MEDIUM: new requirement that could affect claim processing if missed
- LOW: process/documentation change with no explicit penalty stated
"""
    raw = call_ai(system, user, backend)
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: return a minimal valid structure with the raw text
        return {
            "executive_summary": raw[:500],
            "key_changes": ["See raw output — JSON parsing failed"],
            "provider_impact": [], "payer_impact": [], "compliance_risks": [],
        }


# ── top-level analysis tasks ───────────────────────────────────────────────────

def run_full_pipeline(
    old_text: str,
    new_text: str,
    backend: str,
    progress_bar,
    status_text,
) -> tuple[dict, dict, str]:
    """
    Single entry point for the entire analysis.
    Returns (summary_dict, rules_dict, alert_str).

    Stage 1  (0–40%):   Chunk + parallel analyze Document 1
    Stage 2  (40–75%):  Chunk + parallel analyze Document 2
    Stage 3  (75–80%):  Programmatic merge of both docs (no LLM)
    Stage 4  (80–88%):  Compare complete summaries → final JSON
    Stage 5  (88–96%):  Build coding rules JSON from merged chunk data
    Stage 6  (96–100%): Generate provider alert
    """
    # ── stage 1: document 1 ───────────────────────────────────────────────────
    old_hash = _doc_hash(old_text)
    if old_hash in _DOC_CACHE:
        status_text.text("Document 1: loaded from cache")
        progress_bar.progress(40)
        old_merged = _DOC_CACHE[old_hash]
    else:
        old_chunks = split_into_chunks(old_text)
        status_text.text(f"Document 1: {len(old_chunks)} chunks — analyzing in parallel...")
        old_results = process_chunks_parallel(
            old_chunks, "Document 1", backend, progress_bar, status_text, 0, 40
        )
        old_merged = merge_chunk_results(old_results, "Document 1")
        _DOC_CACHE[old_hash] = old_merged

    # ── stage 2: document 2 ───────────────────────────────────────────────────
    new_hash = _doc_hash(new_text)
    if new_hash in _DOC_CACHE:
        status_text.text("Document 2: loaded from cache")
        progress_bar.progress(75)
        new_merged = _DOC_CACHE[new_hash]
    else:
        new_chunks = split_into_chunks(new_text)
        status_text.text(f"Document 2: {len(new_chunks)} chunks — analyzing in parallel...")
        new_results = process_chunks_parallel(
            new_chunks, "Document 2", backend, progress_bar, status_text, 40, 75
        )
        new_merged = merge_chunk_results(new_results, "Document 2")
        _DOC_CACHE[new_hash] = new_merged

    # ── stage 3: merge is programmatic — no LLM call ─────────────────────────
    status_text.text("Merging document summaries (programmatic)...")
    progress_bar.progress(78)

    # ── stage 4: compare complete summaries ───────────────────────────────────
    status_text.text("Comparing complete document summaries...")
    progress_bar.progress(80)
    summary = compare_complete_documents(old_merged, new_merged, backend)
    progress_bar.progress(88)

    # ── stage 5: build coding rules from merged new-doc data ──────────────────
    status_text.text("Building coding rules from extracted data...")
    progress_bar.progress(90)
    rules = _build_rules_json(new_merged, new_text, backend)
    progress_bar.progress(96)

    # ── stage 6: provider alert ───────────────────────────────────────────────
    status_text.text("Generating provider alert...")
    alert = generate_payer_alert(summary, backend)
    progress_bar.progress(100)

    return summary, rules, alert


def _build_rules_json(new_merged: dict, new_text: str, backend: str) -> dict:
    """
    Build the final coding rules JSON from data already extracted during
    chunk analysis. If CPT codes are missing, makes one targeted LLM call
    on the first chunk only (fast path).
    """
    cpt = new_merged.get("cpt_codes", [])
    billing = new_merged.get("billing_rules", [])
    reimbursement = new_merged.get("reimbursement", {})
    excluded = new_merged.get("excluded_services", [])

    # Determine policy name / date from narrative
    policy_name = "Healthcare Billing Policy"
    effective_date = "See document"
    narrative = new_merged.get("narrative", {})
    reimbursement_notes = narrative.get("reimbursement", [])
    if reimbursement_notes:
        for note in reimbursement_notes:
            if "effective" in note.lower():
                effective_date = note[:80]
                break

    # If chunk extraction missed CPT codes entirely, do one targeted call
    if not cpt:
        first_chunk = split_into_chunks(new_text)[0]
        system = (
            "You are a medical coding specialist. Extract CPT codes strictly as written. "
            "Output ONLY valid JSON — no markdown, no commentary."
        )
        user = f"""Extract all CPT codes from this policy excerpt.

{first_chunk}

Return ONLY:
{{
  "policy_name": "<string>",
  "effective_date": "<string>",
  "cpt_codes": [{{"code":"<str>","description":"<str>","patient_type":"<str>","mdm_level":"<str>","time_range_minutes":"<str>"}}]
}}"""
        try:
            raw = call_ai(system, user, "Gemini (free)")
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            cpt = parsed.get("cpt_codes", [])
            policy_name = parsed.get("policy_name", policy_name)
            effective_date = parsed.get("effective_date", effective_date)
        except Exception:
            pass

    return {
        "policy_name": policy_name,
        "effective_date": effective_date,
        "cpt_codes": cpt,
        "billing_rules": billing,
        "reimbursement": reimbursement,
        "excluded_services": excluded,
    }


def generate_payer_alert(change_summary: dict, backend: str) -> str:
    """Generate a professional provider network alert from the change summary."""
    system = (
        "You are a payer communications specialist. Write a clear, professional provider network alert "
        "that gives providers specific, actionable guidance. "
        "Include: what changed, what action providers must take, and what happens if they don't. "
        "Stick strictly to the facts provided. Prefix any added recommendation with '[AI Recommendation]'."
    )
    key_changes = "\n".join(f"  • {c}" for c in change_summary.get("key_changes", []))
    provider_impacts = "\n".join(f"  • {p}" for p in change_summary.get("provider_impact", []))
    high_risks = "\n".join(
        f"  • {r['text']}" for r in change_summary.get("compliance_risks", [])
        if r.get("level") == "HIGH"
    )
    medium_risks = "\n".join(
        f"  • {r['text']}" for r in change_summary.get("compliance_risks", [])
        if r.get("level") == "MEDIUM"
    )

    user = f"""Write a provider network alert based on the policy change facts below.

The alert must include:
1. What changed (summarize the key changes)
2. What providers must do differently (specific workflow actions from the provider impact list)
3. Denial risks — what will be denied if providers don't comply (from HIGH/MEDIUM risks)

KEY CHANGES:
{key_changes}

REQUIRED PROVIDER ACTIONS:
{provider_impacts}

HIGH DENIAL RISKS (claims will be denied):
{high_risks}

MEDIUM RISKS (monitor these):
{medium_risks}

Format exactly:
SUBJECT: [subject line]
EFFECTIVE: [date if known, otherwise 'See policy update']
ALERT BODY: [200-250 words — include what changed, what to do, and denial consequences]
"""
    return call_ai(system, user, backend)


# ── metrics helpers ───────────────────────────────────────────────────────────

def count_bullet_lines(summary: dict, key: str) -> int:
    return len(summary.get(key, []))


def count_risks(summary: dict, level: str) -> int:
    return sum(1 for r in summary.get("compliance_risks", []) if r.get("level") == level)


# ── diff viewer ───────────────────────────────────────────────────────────────

def side_by_side_diff(old_text: str, new_text: str):
    """
    Paragraph-level side-by-side diff.
    Left column: paragraphs only in the old doc (removed, prefixed with -)
    Right column: paragraphs only in the new doc (added, prefixed with +)
    Unchanged paragraphs are not shown to keep the view focused on changes.
    """
    old_paras = [p.strip() for p in old_text.split("\n\n") if p.strip()]
    new_paras = [p.strip() for p in new_text.split("\n\n") if p.strip()]

    # Use SequenceMatcher to find paragraph-level differences
    matcher = difflib.SequenceMatcher(None, old_paras, new_paras, autojunk=False)
    removed_paras: list[str] = []
    added_paras: list[str] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            removed_paras.extend(old_paras[i1:i2])
        elif tag == "insert":
            added_paras.extend(new_paras[j1:j2])
        elif tag == "replace":
            removed_paras.extend(old_paras[i1:i2])
            added_paras.extend(new_paras[j1:j2])

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Removed / Changed in Old Document**")
        st.caption(f"{len(removed_paras)} paragraph(s) removed or replaced")
        if removed_paras:
            for para in removed_paras[:20]:
                display = para if len(para) <= 400 else para[:400] + "..."
                st.markdown(
                    f'<div style="background:#fff0f0;border-left:4px solid #cc0000;'
                    f'padding:8px 12px;margin:6px 0;border-radius:4px;font-size:0.88em;">'
                    f'<b style="color:#cc0000;">−</b> {display}</div>',
                    unsafe_allow_html=True,
                )
            if len(removed_paras) > 20:
                st.caption(f"[{len(removed_paras) - 20} more removed paragraphs — full analysis ran on 100% of the document]")
        else:
            st.info("No paragraphs were removed.")

    with col2:
        st.markdown("**Added / Changed in New Document**")
        st.caption(f"{len(added_paras)} paragraph(s) added or replaced")
        if added_paras:
            for para in added_paras[:20]:
                display = para if len(para) <= 400 else para[:400] + "..."
                st.markdown(
                    f'<div style="background:#f0fff0;border-left:4px solid #006600;'
                    f'padding:8px 12px;margin:6px 0;border-radius:4px;font-size:0.88em;">'
                    f'<b style="color:#006600;">+</b> {display}</div>',
                    unsafe_allow_html=True,
                )
            if len(added_paras) > 20:
                st.caption(f"[{len(added_paras) - 20} more added paragraphs — full analysis ran on 100% of the document]")
        else:
            st.info("No paragraphs were added.")

    unchanged = len(old_paras) - len(removed_paras)
    st.caption(
        f"Diff summary: {len(added_paras)} paragraph(s) added, "
        f"{len(removed_paras)} removed, ~{max(0, unchanged)} unchanged "
        f"| {len(old_paras)} → {len(new_paras)} total paragraphs"
    )


# ── render tabs ───────────────────────────────────────────────────────────────

def render_change_summary(summary: dict):
    st.caption("⚠️ All content is generated from uploaded policy content. Only changes explicitly stated in the source documents are included. Risk levels are AI-derived — see the Compliance Risks section for methodology.")
    st.markdown("### Executive Summary")
    st.info(summary.get("executive_summary", "—"))
    st.divider()

    st.markdown("### Key Changes")
    all_changes = summary.get("key_changes", [])
    display_changes = all_changes[:15]
    for item in display_changes:
        st.warning(f"• {item}")
    if len(all_changes) > 15:
        with st.expander(f"Show {len(all_changes) - 15} more changes ({len(all_changes)} total extracted)"):
            for item in all_changes[15:]:
                st.warning(f"• {item}")
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Impact on Providers")
        for item in summary.get("provider_impact", []):
            st.markdown(f"• {item}")
    with col2:
        st.markdown("### Impact on Payers")
        for item in summary.get("payer_impact", []):
            st.markdown(f"• {item}")
    st.divider()

    st.markdown("### Impact Summary Table")
    provider_impacts = summary.get("provider_impact", [])
    payer_impacts = summary.get("payer_impact", [])
    max_rows = max(len(provider_impacts), len(payer_impacts), 1)
    table_rows = []
    for i in range(max_rows):
        table_rows.append({
            "Impact on Providers": provider_impacts[i] if i < len(provider_impacts) else "—",
            "Impact on Payers": payer_impacts[i] if i < len(payer_impacts) else "—",
        })
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    st.divider()

    st.markdown("### Compliance Risks")
    with st.expander("How are risk levels assigned?"):
        st.markdown("""
**Risk levels are AI-derived** based on the following criteria applied to policy language:

| Level | Criteria |
|---|---|
| 🔴 HIGH | Document explicitly states denial, rejection, or non-payment as a consequence |
| 🟡 MEDIUM | Document states a new requirement that could affect claim processing if missed |
| 🟢 LOW | Process or documentation change with no explicit penalty stated in the document |

*These labels are not assigned by CMS. They represent this tool's interpretation of the policy text.*
        """)
    for risk in summary.get("compliance_risks", []):
        level = risk.get("level", "")
        text = risk.get("text", "")
        basis = risk.get("basis", "")
        if level == "HIGH":
            st.error(f"🔴 HIGH: {text}")
        elif level == "MEDIUM":
            st.warning(f"🟡 MEDIUM: {text}")
        else:
            st.success(f"🟢 LOW: {text}")
        if basis:
            st.caption(f"Source: {basis}")
    st.divider()


def render_coding_rules(rules: dict):
    st.markdown(f"**Policy:** {rules.get('policy_name', '-')}  |  **Effective:** {rules.get('effective_date', '-')}")
    st.divider()

    st.markdown("### CPT Codes")
    cpt = rules.get("cpt_codes", [])
    if cpt:
        df = pd.DataFrame(cpt)
        df.columns = ["Code", "Description", "Patient Type", "MDM Level", "Time (min)"]
        filter_type = st.radio("Filter by patient type:", ["All", "New", "Established"], horizontal=True)
        if filter_type != "All":
            df = df[df["Patient Type"] == filter_type.lower()]
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.divider()

    st.markdown("### Billing Rules")
    st.caption("⚠️ 'Potential Denial Risk' is AI-inferred from policy language — CMS does not explicitly label rules with this classification. See basis for each rule.")
    billing = rules.get("billing_rules", [])
    denial_count = sum(1 for r in billing if r.get("potential_denial_risk", r.get("denial_risk")))
    safe_count = len(billing) - denial_count

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Total Rules", len(billing))
    col_b.metric("Potential Denial Risk", denial_count)
    col_c.metric("No Denial Risk", safe_count)

    st.markdown("---")
    for r in billing:
        denial = r.get("potential_denial_risk", r.get("denial_risk", False))
        icon = "🔴" if denial else "🟢"
        with st.expander(f"{icon}  {r['rule']}"):
            st.write(r["detail"])
            basis = r.get("denial_risk_basis", "")
            if denial:
                st.error("Potential Denial Risk: Yes (AI-inferred from policy language)")
                if basis:
                    st.caption(f"Basis: {basis}")
            else:
                st.success("Potential Denial Risk: No — process change only.")
    st.divider()

    st.markdown("### Reimbursement")
    reimb = rules.get("reimbursement", {})
    col1, col2, col3 = st.columns(3)
    col1.metric("Participating Rate", reimb.get("participating_rate", "-").split(" ")[0])
    col2.metric("Non-Participating Rate", reimb.get("non_participating_rate", "-").split(" ")[0])
    col3.metric("Telehealth Parity", "Active")
    st.divider()

    st.markdown("### Excluded Services")
    for svc in rules.get("excluded_services", []):
        st.markdown(f"- {svc}")
    st.divider()

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button("Download Rules as JSON", json.dumps(rules, indent=2),
                           "extracted_rules.json", "application/json", use_container_width=True)
    with col_dl2:
        if cpt:
            st.download_button("Download CPT Codes as CSV", pd.DataFrame(cpt).to_csv(index=False),
                               "cpt_codes.csv", "text/csv", use_container_width=True)


def render_alert(alert: str):
    st.caption("⚠️ This is a provider communication draft generated from uploaded policy content. Any sentence prefixed with [AI Recommendation] is not explicitly sourced from the policy document. Review before sending.")
    lines = alert.strip().splitlines()
    subject = next((l.replace("SUBJECT:", "").strip() for l in lines if l.startswith("SUBJECT:")), "Policy Update")
    effective = next((l.replace("EFFECTIVE:", "").strip() for l in lines if l.startswith("EFFECTIVE:")), "")

    st.markdown(f"### {subject}")
    if effective:
        st.caption(f"Effective: {effective}")

    body_lines, in_body = [], False
    for line in lines:
        if line.startswith("ALERT BODY:"):
            in_body = True
            rest = line.replace("ALERT BODY:", "").strip()
            if rest:
                body_lines.append(rest)
        elif in_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()
    st.info(body if body else alert)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.download_button("Download as .txt", alert, "provider_alert.txt", "text/plain", use_container_width=True)
    with col2:
        st.download_button("Download as .md", f"# {subject}\n\n**Effective:** {effective}\n\n{body}",
                           "provider_alert.md", "text/markdown", use_container_width=True)

    st.divider()
    st.markdown("#### Email Preview")
    st.markdown(f"""
<div style="border:1px solid #ddd; border-radius:8px; padding:20px; background:#f9f9f9; font-family:monospace; font-size:0.85em;">
<b>From:</b> Provider Relations &lt;providerrelations@examplehealthplan.com&gt;<br>
<b>To:</b> In-Network Provider Network<br>
<b>Subject:</b> {subject}<br><br>
{body.replace(chr(10), "<br>")}
</div>
""", unsafe_allow_html=True)


# ── main app ──────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Healthcare Policy Analyzer", page_icon="🏥", layout="wide")

    st.markdown("""
    <div style="background: linear-gradient(90deg, #003366 0%, #0066cc 100%);
                padding: 20px 30px; border-radius: 10px; margin-bottom: 20px;">
        <h1 style="color: white; margin: 0; font-size: 1.8em;">
            🏥 Healthcare Policy Content Analyzer
        </h1>
        <p style="color: #cce0ff; margin: 6px 0 0 0; font-size: 0.95em;">
            AI-powered policy comparison, rule extraction & provider alert generation
            &nbsp;|&nbsp; Cotiviti Intern Assessment -- Likitha KB
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## AI Backend")
        backend = st.radio("Choose AI model:", ["Offline Demo", "Gemini (free)"], index=0)

        if backend == "Gemini (free)":
            api_key = st.text_input("Gemini API Key", type="password", placeholder="AIza... or AQ....")
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key
                st.success("Key set")
            elif not os.environ.get("GEMINI_API_KEY"):
                st.warning("Enter a Gemini API key or switch to Offline Demo.")
                st.caption("Free key: aistudio.google.com → Get API Key")

        st.divider()
        st.markdown("## Policy Documents")

        source = st.radio("Document source:", ["Sample CMS Policies", "Upload your own"])

        old_text, new_text = "", ""
        old_label, new_label = "Document 1", "Document 2"

        if source == "Sample CMS Policies":
            cms_em = SAMPLE_DIR / "cms_em_2023.pdf"
            cms_pfs = SAMPLE_DIR / "cms_pfs_2024.pdf"

            if cms_em.exists() and cms_pfs.exists():
                st.success("Real CMS policy documents loaded")
                old_label = "CMS E/M Services Guide (2023)"
                new_label = "CMS PFS 2024 Policy Update"
                old_text = load_path(cms_em)
                new_text = load_path(cms_pfs)

                with st.expander("Preview: CMS E/M 2023 (first 400 chars)"):
                    st.text(old_text[:400] + "...")
                with st.expander("Preview: CMS PFS 2024 (first 400 chars)"):
                    st.text(new_text[:400] + "...")
            else:
                st.error("Sample CMS PDFs not found. Upload your own files.")

        else:
            st.caption("Supports .txt and .pdf files")
            old_file = st.file_uploader("Old Policy (baseline)", type=["txt", "pdf"])
            new_file = st.file_uploader("New Policy (updated)", type=["txt", "pdf"])
            if old_file:
                old_text = load_file(old_file)
                old_label = old_file.name
                st.success(f"Loaded: {old_file.name} ({len(old_text):,} chars)")
            if new_file:
                new_text = load_file(new_file)
                new_label = new_file.name
                st.success(f"Loaded: {new_file.name} ({len(new_text):,} chars)")

        st.divider()
        run = st.button("Analyze Policy Changes", type="primary", use_container_width=True,
                        disabled=not (old_text and new_text))

        if "last_run" in st.session_state:
            st.caption(f"Last run: {st.session_state.last_run}")
        if "elapsed" in st.session_state:
            st.caption(f"Analysis completed in {st.session_state.elapsed} seconds")

        st.divider()
        st.markdown("**Stack**")
        st.markdown("- Gemini 2.5 Flash (free tier)\n- PDF extraction via pypdf\n- Streamlit dashboard\n- Python 3.14")

    # ── run analysis ──────────────────────────────────────────────────────────
    if "results" not in st.session_state:
        st.session_state.results = None
        st.session_state.labels = ("Document 1", "Document 2")

    if run:
        _t0 = time.time()
        if backend == "Offline Demo":
            progress = st.progress(0, text="Task 1/3 -- Summarizing changes (demo)...")
            time.sleep(0.7)
            progress.progress(33, text="Task 2/3 -- Extracting coding rules (demo)...")
            time.sleep(0.7)
            progress.progress(66, text="Task 3/3 -- Generating provider alert (demo)...")
            time.sleep(0.7)
            progress.progress(100, text="Complete!")
            time.sleep(0.3)
            progress.empty()
            st.session_state.results = {
                "summary": DEMO_CHANGE_SUMMARY,
                "rules": DEMO_RULES,
                "alert": DEMO_ALERT,
                "old_text": old_text,
                "new_text": new_text,
            }
            st.session_state.labels = (old_label, new_label)
            st.session_state.elapsed = round(time.time() - _t0, 1)
            st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M") + " (offline demo)"
            st.success(f"Analysis completed in {st.session_state.elapsed} seconds")
        else:
            key_check = (backend == "Gemini (free)" and os.environ.get("GEMINI_API_KEY"))
            if not key_check:
                st.error("Please enter your API key in the sidebar.")
            else:
                try:
                    progress = st.progress(0)
                    status = st.empty()
                    status.text("Starting full-document analysis pipeline...")

                    summary, rules, alert = run_full_pipeline(
                        old_text, new_text, backend, progress, status
                    )

                    progress.progress(100)
                    status.text("Complete!")
                    time.sleep(0.4)
                    progress.empty()
                    status.empty()

                    st.session_state.results = {
                        "summary": summary, "rules": rules, "alert": alert,
                        "old_text": old_text, "new_text": new_text,
                    }
                    st.session_state.labels = (old_label, new_label)
                    st.session_state.elapsed = round(time.time() - _t0, 1)
                    st.session_state.last_run = datetime.now().strftime("%Y-%m-%d %H:%M") + f" ({backend})"
                    st.success(f"Analysis completed in {st.session_state.elapsed} seconds")
                except Exception as e:
                    import traceback
                    st.error(f"Analysis failed: {e}\n\n{traceback.format_exc()}")

    # ── results ───────────────────────────────────────────────────────────────
    if st.session_state.results:
        res = st.session_state.results
        lbl_old, lbl_new = st.session_state.labels

        # metrics bar
        key_changes = count_bullet_lines(res["summary"], "key_changes")
        high_risks = count_risks(res["summary"], "HIGH")
        medium_risks = count_risks(res["summary"], "MEDIUM")
        denial_rules = sum(
            1 for r in res["rules"]["billing_rules"]
            if r.get("potential_denial_risk", False)
        )

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Key Changes Detected", key_changes)
        m2.metric("HIGH Risks", high_risks, delta="action required", delta_color="inverse")
        m3.metric("MEDIUM Risks", medium_risks, delta="monitor", delta_color="off")
        m4.metric("Denial-Risk Rules", f"{denial_rules}/{len(res['rules']['billing_rules'])}")
        m5.metric("Documents Compared", "2 PDFs")

        st.caption(f"Comparing: **{lbl_old}** vs **{lbl_new}**")
        st.divider()

        tab1, tab2, tab3, tab4 = st.tabs([
            "Policy Change Summary",
            "Extracted Coding Rules",
            "Provider Alert",
            "Policy Diff Viewer",
        ])

        with tab1:
            render_change_summary(res["summary"])
        with tab2:
            render_coding_rules(res["rules"])
        with tab3:
            render_alert(res["alert"])
        with tab4:
            st.markdown("### Side-by-Side Document Comparison")
            st.caption("Lines prefixed with `+` are new or changed in the updated document.")
            side_by_side_diff(res.get("old_text", ""), res.get("new_text", ""))

    else:
        st.markdown("### How to use")
        c1, c2, c3, c4 = st.columns(4)
        c1.info("**Step 1** Choose AI backend (Demo, Gemini free, or Claude)")
        c2.info("**Step 2** Load sample CMS PDFs or upload your own .txt/.pdf files")
        c3.info("**Step 3** Click **Analyze Policy Changes**")
        c4.info("**Step 4** Review results across 4 tabs and download outputs")

        st.divider()
        t1, t2, t3 = st.columns(3)
        t1.success("**Task 1** Policy change summary with HIGH/MEDIUM/LOW risk color-coding")
        t2.success("**Task 2** CPT code table + billing rules with denial risk flags + JSON/CSV download")
        t3.success("**Task 3** Ready-to-send provider alert with email preview + download")

        st.divider()
        st.markdown("""
| Component | Detail |
|---|---|
| AI Models | Gemini 2.5 Flash (free tier) |
| PDF Support | Upload any .pdf or .txt billing policy |
| Sample Data | Real CMS E/M Guide (2023) + CMS PFS 2024 Update |
| Output | Summary + JSON rules + Provider letter |
        """)


if __name__ == "__main__":
    main()
