---
name: audit-orchestrator
description: Entrypoint skill for the Brand AI-Readiness Audit marketplace. Given a
  website URL, acquires the site once, schedules crawl-render-audit,
  freshness-corroboration, and engagement-audit under one shared deadline, merges
  and deduplicates their findings, prioritizes them, validates the report against
  the required schema and Invariant I-1, and emits a single structured audit
  report (findings + suggested actions). Use this skill whenever a general audit
  of a website's AI discoverability and on-site engagement is requested.
license: MIT
---

# Audit Orchestrator

## When to use
Use when asked to audit a website for AI discoverability and on-site engagement
problems, or to run the brand-ai-readiness-audit marketplace end to end.

## Inputs
- `site_url`: a URL or bare domain.

## Procedure
1. Call `scripts/run_audit.py: run_audit(site_url)`.
2. It validates the URL, acquires the site once (`acquire_site.py`), runs the
   independent analysis batch (crawl-render-audit checks plus the data-producing
   steps of freshness-corroboration and engagement-audit), runs the mandatory
   sequential `identify_important_facts` step, then runs the dependent batch
   (freshness, corroboration, footprint, engagement).
3. Findings are merged (`merge_findings.py`), prioritized
   (`prioritize_findings.py`), and validated (`validate_report.py`).
4. Return the resulting report to the user as-is.

## Output
A JSON report matching `references/report-schema.md`: `site`, `audited_at`,
`summary`, `coverage`, and `findings` (each with evidence, severity, and a
suggested action). Recommend-only -- no skill ever modifies a live site.
