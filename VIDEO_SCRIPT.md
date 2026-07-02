# Video Script — Cotiviti Generative AI Engineering Intern Assessment

## [SLIDE 1 — Title]
**[CAMERA]**
"Hi, I'm Likitha, presenting my submission for the Cotiviti Generative AI Engineering Intern Assessment — Topic 3, Content Management in Health Care. Over the next ten minutes: research, strategic analysis, and a working proof of concept showing how LLMs can automate one of the most labor-intensive processes in payer operations."

---

## [SLIDE 2 — Agenda]
"Problem, concept, key trends, opportunities and threats, three strategic recommendations, then a live demo."

---

## [SLIDE 3 — Problem]
"Health plans spend over $280 billion annually on administration; contracting inefficiencies alone cost $40–60 billion a year. When CMS updates the Medicare Physician Fee Schedule — annually — it can take teams *weeks* to turn that into updated claims-editing rules. That delay has teeth: DOJ recovered a record $5.7 billion in FY2025 healthcare False Claims Act settlements, much of it tied to outdated billing rules. The question: can an LLM close this gap?"

---

## [SLIDE 4 — Concept]
"Four document types: billing and coding policies, clinical practice guidelines, payer-provider contracts, and prior authorization rules. All four are high-volume, frequently updated, free-text — and all four need the same AI capability: read, understand, compare, extract, act."

---

## [SLIDE 5 — Key Trends]
"CMS updates the MPFS annually; ICD-10 adds hundreds of codes a year. Hospital AI adoption in billing jumped from 46% in 2023 to 70% in 2024. Domain-tuned LLMs hit 97% coding accuracy versus under 1% for general models. LLMs are already extracting rules from guidelines, automating prior auth, and flagging fee-schedule discrepancies. DOJ has named AI-enabled billing an enforcement priority — accuracy and human oversight aren't optional."

---

## [SLIDE 6 — Opportunities & Threats]
"Automating policy monitoring could cut analyst burden 40–60%. Extracting denial-prevention rules before submission could recover a share of the industry's $262 billion in avoidable rework. But LLMs hallucinate, policy language is ambiguous, and any policy-to-rule system needs expert validation before going live — plus HIPAA governance for PHI-adjacent processing. The answer isn't to avoid automation; it's to design it responsibly."

---

## [SLIDE 7 — Recommendations]
"Three investments. **PolicyIQ** — automated monitoring of CMS, AMA, and payer feeds with structured change summaries and risk flags; this is what my POC demonstrates. **Policy-to-Rule Compiler** — converts extracted rules into executable SQL, decision trees, or CDS Hooks, cutting the CMS-guidance-to-live-system cycle from weeks to hours. **Human-in-the-Loop Review** — routes AI output to coding experts before activation, making the other two viable in a regulated environment."

---

## [SLIDE 8 — POC Overview]
**[SCREEN SHARE]**
"The Healthcare Policy Content Analyzer takes two PDF policy versions and produces four outputs: a Policy Change Summary, Extracted Coding Rules with denial-risk flags, a Provider Alert draft, and a paragraph-level Policy Diff Viewer. Test case: the real 1995 vs. 1997 CMS E/M Documentation Guidelines."

---

## [SLIDE 9 — Architecture]
"Five stages in one Streamlit app: pypdf extraction, chunking at ~11,000 characters; parallel chunk analysis via Gemini with a 4-worker thread pool; programmatic merge into a unified comparison; two final Gemini calls for the rule set and provider draft. SHA-256 caching skips re-analysis on repeat uploads; exponential backoff handles rate limits. Full analysis on the ~100KB CMS document pair: about three minutes."

---

## [SLIDE 10 — Live Demo Results]
**[SCREEN SHARE]**
"[Policy Change Summary] 31 key changes detected — the biggest being the bullet-counting exam system: 1997 introduces specialty-specific thresholds, like 12 elements for a neurological or respiratory exam versus 9 for psychiatric, which directly gate E/M billing level.
[Extracted Coding Rules] 37 rules extracted, 34 flagged with denial risk — covering Chief Complaint, ROS, PFSH, and the bullet thresholds.
[Provider Alert] A ready-to-send communication draft summarizing what physicians need to act on.
[Policy Diff Viewer] Paragraph-level diff showing exactly what was added, removed, or modified. Six items flagged HIGH risk, one MEDIUM."

---

## [SLIDE 11 — Conclusion]
**[CAMERA]**
"Healthcare content management is broken at scale and expensive. LLMs are built for exactly this — summarization, extraction, generation. Cotiviti's 25-plus years in payment integrity makes it well-positioned to commercialize this. My POC demonstrates it end-to-end: real PDFs in, structured summaries, extracted rules, and a provider draft out. And human-in-the-loop isn't optional — that review step is what makes this responsible and defensible in production. Thank you — I'd welcome the chance to contribute to what Cotiviti is building here."
