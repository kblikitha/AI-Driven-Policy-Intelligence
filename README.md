# Cotiviti Intern Assessment — Content Management in Health Care

**Topic 3:** Content Management in Health Care: Billing and Coding Policies, Clinical Practice
Guidelines, Payer-Provider Contracts, Summarization of Content, Comparison of Content Changes,
Conversion of Written Policy into Programming Languages, Rules, Features, or Models

**Candidate:** Likitha KB  
**University:** University of North Texas  
**Date:** June 2026

---

## Repository Structure

```
cotiviti-intern-assessment/
├── README.md                          ← This file
├── VIDEO_SCRIPT.md                    ← Word-for-word presentation script
│
├── poc/                               ← Hackathon Proof of Concept
│   ├── app.py                         ← Main Streamlit web app (run this)
│   ├── requirements.txt
│   └── sample_policies/               ← (legacy CLI reference files)
│
├── report/
│   ├── generate_report.py             ← Script that builds the .docx
│   └── Content_Management_Healthcare_Report.docx  ← Final Word report
│
└── presentation/
    ├── generate_slides.py             ← Script that builds the .pptx
    └── Content_Management_Healthcare_Slides.pptx  ← Final PowerPoint
```

---

## Proof of Concept — Quick Start

### Option A: Offline Demo (no API key needed)
```bash
pip install -r poc/requirements.txt
streamlit run poc/app.py
```
Select **"Offline Demo"** in the sidebar. Pre-computed results display instantly with
no API calls required.

### Option B: Live Mode (requires Gemini API key)
```bash
pip install -r poc/requirements.txt
export GEMINI_API_KEY=your_key_here
streamlit run poc/app.py
```
Select **"Gemini (free)"** in the sidebar, upload two PDF policy documents, and click
**"Analyze Policy Changes"**.

---

## What the POC Does

The **Healthcare Policy Content Analyzer** is a Streamlit web dashboard that takes two
PDF versions of a healthcare billing policy and runs AI-powered analysis using the
Google Gemini API (Gemini 2.5 Flash, free tier):

| Tab | Description | Output |
|-----|-------------|--------|
| Policy Change Summary | Structured diff of policy versions | Executive summary, key changes (15 shown, remainder expandable), provider/payer impact table, denial risks |
| Extracted Coding Rules | All coding rules as structured data | CPT codes, billing rules with `denial_risk` flags, reimbursement rates |
| Provider Alert | Ready-to-send network communication | Professional provider communication draft |
| Policy Diff Viewer | Paragraph-level diff of the two PDFs | Inline diff highlighting additions/removals |

### Technical highlights
- **PDF extraction** via `pypdf`
- **Chunked processing** — documents split at paragraph boundaries (~11,000 chars/chunk)
- **Parallel chunk analysis** — `ThreadPoolExecutor(max_workers=4)` per document
- **SHA-256 caching** — re-uploading the same PDF skips re-analysis
- **Exponential backoff** — automatic retry on Gemini 503/429/quota errors

### Validated output (1995 vs 1997 CMS E/M Documentation Guidelines)
- 31 key policy changes detected
- 37 billing rules extracted
- 34 of 37 rules carry denial risk flags
- 6 HIGH + 1 MEDIUM compliance risk items
- Analysis completed in ~189 seconds on the real CMS PDF pair

---

## Deliverables

| Deliverable | File | Status |
|-------------|------|--------|
| Written Report (Word) | `report/Content_Management_Healthcare_Report.docx` | ✅ Complete |
| POC Demo (Streamlit App) | `poc/app.py` | ✅ Complete |
| PowerPoint Presentation | `presentation/Content_Management_Healthcare_Slides.pptx` | ✅ Complete |
| Video Recording | `presentation/Video.MOV` | ✅ Complete |

---

## Report Summary

The two-page report (+ bibliography) covers:

1. **Concept Definition** — what healthcare content management encompasses and why it matters
2. **Key Trends** — AI adoption velocity in RCM, policy-to-code automation, regulatory pressure
3. **Opportunities & Threats** — strategic landscape for AI-driven policy intelligence
4. **Strategic Recommendations** — three Cotiviti-specific investments:
   - **PolicyIQ:** Automated policy change monitoring pipeline
   - **Policy-to-Rule Compiler:** LLM-to-executable-logic conversion
   - **Human-in-the-Loop Review:** Expert validation workflow

---

## Technology Stack

- **Language:** Python 3.14
- **AI Model:** Google Gemini 2.5 Flash (free tier) via `google-genai` SDK
- **Web Framework:** Streamlit
- **PDF Extraction:** `pypdf`
- **Libraries:** `google-genai`, `streamlit`, `pypdf`, `pandas`
- **Input format:** PDF policy documents
- **Output formats:** Interactive Streamlit dashboard, structured JSON, provider communication draft

---

## Citations

Full bibliography is on page 3 of the Word report. Key sources:
- Cotiviti (2025). Everest Group Payment Integrity PEAK Matrix Leader
- BCBS (2024). AI in Hospital Billing Trends
- PMC 12413144 (2025). Extracting Clinical Guideline Info Using LLMs
- DOJ (2025). FY2025 False Claims Act Settlements
- Zapro.ai (2026). Payer Contract Management Strategies

---


