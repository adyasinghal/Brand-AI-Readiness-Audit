---
name: crawl-render-audit
description: Analyzes off-site AI discoverability mechanics for a crawled website --
  reachability, robots.txt and AI-crawler-specific access, raw-vs-rendered content
  gaps, machine-readable structured data (JSON-LD), and llms.txt presence. Called
  by audit-orchestrator as part of its independent analysis batch; not intended to
  be invoked standalone.
license: MIT
---

# Crawl & Render Audit

## When to use
Called by audit-orchestrator. Not a standalone entrypoint.

## Inputs
An `AuditArtifacts` snapshot produced by `acquire_site.py`.

## Procedure
Run `analyze_crawlability`, `analyze_rendering`, `analyze_machine_readability`,
`check_ai_crawler_access`, and `check_llms_txt` -- see
`references/crawl-render-checklist.md`.

## Output
One `SkillResult` per script: findings (evidence + severity) plus metrics.
