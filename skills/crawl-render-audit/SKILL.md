---
name: crawl-render-audit
description: Analyzes off-site AI discoverability mechanics for a crawled website --
  reachability, robots.txt (with fetch-status calibration: ok/absent/timeout/
  inaccessible/malformed/blocked, never inferring a disallow from a failed fetch)
  and AI-crawler-specific access, raw-vs-rendered content gaps, machine-readable
  structured data (JSON-LD), sitemap.xml discovery, and llms.txt presence. Called
  by audit-orchestrator as part of its independent analysis batch; not intended to
  be invoked standalone.
license: MIT
allowed-tools: []
---

# Crawl & Render Audit

## When to use
Called by audit-orchestrator. Not a standalone entrypoint.

## Dependencies
Pure-Python analysis over an already-acquired `AuditArtifacts` snapshot --
no network calls of its own. `analyze_rendering.py` additionally checks for
`playwright` (optional; degrades to a heuristic, `suspected` gap-detection
when absent, per `common/capabilities.py`).

## Inputs
An `AuditArtifacts` snapshot produced by `acquire_site.py`.

## Procedure
Run `analyze_crawlability`, `analyze_rendering`, `analyze_machine_readability`,
`check_ai_crawler_access`, and `check_llms_txt` -- see
`references/crawl-render-checklist.md`.

## Output
One `SkillResult` per script: findings (evidence + severity) plus metrics.

## Example

Input: an `AuditArtifacts` with one page that has no JSON-LD.
`analyze_machine_readability` output:

```json
{"skill": "crawl-render-audit", "status": "success",
 "findings": [{"id": "F-002", "category": "ai_discoverability",
               "severity": "high", "status": "confirmed",
               "root_cause": "Home page has no Organization/WebSite JSON-LD"}],
 "metrics": {"pages_missing_jsonld": 1}}
```
