# By Aarush_Moha_Mathur; version-1 ; Not final yet; Analaysis doesnt prove 10/10 yet.

# Brand AI-Readiness Audit Marketplace (v4.0)

An Agent Skill Marketplace (agentskills.io format) that audits a website for
AI discoverability and on-site engagement problems, and emits a single
structured report of findings and prioritized suggested actions.

Recommend-only: no skill ever modifies a live site.

## Skills

- **audit-orchestrator** (entrypoint) -- validates input, acquires the site
  once, schedules the DAG across a single bounded thread pool, merges and
  deduplicates findings, prioritizes them, validates the report, and emits it.
- **crawl-render-audit** -- reachability, robots.txt, AI-crawler access,
  raw-vs-rendered gaps, structured data, llms.txt.
- **freshness-corroboration** -- claim extraction, important-fact ranking,
  one-time entity resolution, freshness, corroboration, external footprint
  (calibrated so missing evidence is never a confirmed defect).
- **engagement-audit** -- site graph, orphan pages, dead ends, breadcrumb
  cross-check.

## How the entrypoint composes the others

```
validate_input -> acquire_site (once)
-> independent batch (thread pool): crawlability, rendering,
   machine_readability, ai_crawler_access, llms_txt, extract_claims,
   resolve_entity_identity, build_site_graph
-> identify_important_facts (sequential, between the two batches)
-> dependent batch (same thread pool): freshness, corroboration, footprint,
   engagement
-> merge_findings -> prioritize_findings -> validate_report -> report
```

## Run it

```
pip install -r requirements.txt --break-system-packages
python3 skills/audit-orchestrator/scripts/run_audit.py https://example.com
```

## Note on this reference implementation

This environment has no outbound web access beyond package registries and no
headless-browser runtime, so `analyze_rendering`, `corroborate_claims`, and
`assess_external_footprint` report `insufficient_evidence` rather than
performing live rendering or external search -- exactly the fallback behavior
required by the spec (section 10) for unavailable evidence. Wire a headless
browser and a search API into those three functions for production use; no
other part of the architecture needs to change.

## Test

`tests/test_smoke.py` builds a synthetic `AuditArtifacts` fixture (no network
needed) and exercises the full DAG wiring: both batches, the mandatory
sequential `identify_important_facts` step, single entity resolution reused by
both consumers, dedup, Invariant I-1, and report validation.

```
python3 -m pytest tests/test_smoke.py -q
```
