---
name: audit-orchestrator
description: Master entrypoint for the Brand AI-Readiness Audit. Coordinates comprehensive website audits evaluating machine discoverability, AI search crawler access, Schema.org structured data, brand entity disambiguation, and user engagement retention. Use this skill whenever auditing a website, brand, or URL for AI readiness, GEO (Generative Engine Optimization), LLM search visibility (ChatGPT, Claude, Perplexity), or crawl-and-retention performance.
---

# Brand AI-Readiness Audit Orchestrator

Coordinates the multi-stage Brand AI-Readiness Audit across machine access, structured data extraction, entity authority, and visitor retention.

## Execution Procedure (Imperative Steps)

1. **Accept and Normalize Target URL:**
   - Normalize target URL: prepend `https://` if protocol is missing.
2. **Prepare Isolated Audit Directory:**
   ```bash
   mkdir -p /tmp/audit_runs/
   rm -f /tmp/audit_runs/*
   ```
3. **Run Stage 1: Machine Access Audit:**
   ```bash
   python3 skills/crawl-render-audit/scripts/check_access.py <URL> > /tmp/audit_runs/01_access.json
   ```
4. **Run Stage 2: Semantic Structured Data Audit:**
   ```bash
   python3 skills/semantic-data-audit/scripts/parse_structured_data.py <URL> > /tmp/audit_runs/02_semantic.json
   ```
5. **Run Stage 3: Mechanical Entity Trust Audit:**
   ```bash
   python3 skills/entity-authority-audit/scripts/check_entity_trust.py <URL> > /tmp/audit_runs/03_entity_mechanical.json
   ```
6. **Execute Stage 3 Agent Qualitative Evaluation (About-Page & Web Corroboration):**
   - Follow procedure in `skills/entity-authority-audit/SKILL.md`.
   - If findings or recommendations are generated, write them as a valid JSON array into `/tmp/audit_runs/04_entity_agent.json`.
7. **Run Stage 4: Visitor Retention & Engagement Friction Audit:**
   ```bash
   python3 skills/engagement-friction-audit/scripts/check_friction.py <URL> > /tmp/audit_runs/05_friction.json
   ```
8. **Merge, Prioritize, and Validate Output:**
   ```bash
   python3 skills/audit-orchestrator/scripts/merge_and_prioritize.py <URL> /tmp/audit_runs/*.json > /tmp/final_report.json
   ```
9. **Emit Final Report:**
   - Output `/tmp/final_report.json` cleanly to stdout.
