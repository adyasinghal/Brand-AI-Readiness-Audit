---
name: entity-authority-audit
description: Stage 3 Identity & Trust Audit. Evaluates brand naming consistency across <title>, <h1>, and OpenGraph tags, footer copyright freshness, Organization sameAs authoritative disambiguation links (Wikidata, Wikipedia, LinkedIn, Crunchbase), About-page entity clarity, and external cross-web corroboration on Reddit and Quora. Use when diagnosing brand entity confusion, hallucinated attributes, or lack of multi-source web consensus.
---

# Stage 3: Entity Authority & Identity Disambiguation Audit

Audits whether the brand's identity is consistent, uniquely disambiguated, and corroborated across the wider web.

## Part 1: Automated Mechanical Checks

Execute the mechanical entity trust script against the target URL:
```bash
python3 skills/entity-authority-audit/scripts/check_entity_trust.py <URL> > /tmp/audit_runs/03_entity_mechanical.json
```
The script evaluates:
- Brand naming consistency across `<title>`, `<h1>` (sliced to 128KB), and `<meta property="og:title">`.
- Missing primary `<h1>` document anchor.
- Missing or diverging OpenGraph social graph tags.
- Footer copyright freshness (flagging dates >2 years behind current year).
- Missing `sameAs` authoritative entity disambiguation links in `Organization` JSON-LD.
- Reuses `/tmp/audit_runs/page.html` cache file if available.

---

## Part 2: Evaluator Agent Qualitative Procedure (About-Page & Web Corroboration)

1. **About-Page Entity Clarity:**
   - Inspect the brand's About page or introductory mission paragraph.
   - Verify if the first 2 sentences explicitly answer: (a) Who is the company, (b) What specific product/service do they offer, and (c) In what category or market.
   - If vague marketing speak obscures what the company actually does, create a `medium` severity finding object.

2. **Cross-Web Corroboration Search:**
   - Using your available web search tool, query:
     `site:reddit.com OR site:quora.com "Brand Name"`
   - **Explicit Graceful Fallback Path:**
     - If the web search tool is unavailable, disabled, returns an API error, or returns 0 results:
     - **DO NOT fail or abort the audit.**
     - Create an advisory finding object with severity capped to `low` per Invariant I-1:
       ```json
       {
         "category": "entity_trust",
         "title": "External cross-web corroboration unverifiable via search plugin",
         "severity": "low",
         "evidence": "Search tool unavailable or returned 0 corroborating forum threads.",
         "mechanism": "Independent third-party citations on discussion boards corroborate entity claims for retrieval-augmented generation.",
         "suggested_action": {
           "summary": "Build organic presence and factual mentions in industry community discussions.",
           "priority": "low",
           "implementation_detail": "Engage authentically in relevant subreddits and forums answering questions in the brand's domain.",
           "expected_outcome": "Improved multi-source consensus in LLM answer synthesis."
         }
       }
       ```

3. **Deterministic Agent Handoff Protocol:**
   - Assemble all generated qualitative finding objects into a JSON array.
   - Write this array directly into the audit scratch directory:
     `/tmp/audit_runs/04_entity_agent.json`
   - *Do not attempt to merge this manually into the final report.* The orchestrator will automatically ingest `/tmp/audit_runs/04_entity_agent.json` via `merge_and_prioritize.py`.
