---
name: crawl-render-audit
description: Audit whether machines can reach and read a website at all. Fetches a small polite sample of pages, then checks the crawl layer (robots.txt rules including AI-crawler blocks, sitemap with lastmod capture, HTTPS and TLS certificate health, redirects, noindex via meta tag or X-Robots-Tag header, response times) and the render layer (JavaScript render gaps, missing or invalid JSON-LD, titles, meta descriptions, canonicals, lang, image alt coverage), plus technical SEO structure (semantic landmarks, heading hierarchy, Open Graph, text-to-markup ratio, title hygiene), on-page keyword strategy (title/body intent alignment, keyword stuffing), and performance signals (document weight, render-blocking head scripts, image loading hygiene). Also produces the site_snapshot.json feature cache other skills in this marketplace consume. Use for questions about crawlability, indexability, structured data, or content invisible to bots.
license: MIT
allowed-tools: bash, python3, network(outbound http/https to the audited site only)
---

# Crawl and Render Audit

## When to use
Diagnosing step one of visibility: can a crawler get in, and can it read what a human sees. Runs first in the marketplace because it produces the shared snapshot.

## Inputs
- Required: site URL. Optional: `--workdir` (default `./audit_work`), `--max-pages` (default 8), `--delay` (default 1.0s).

## Procedure
1. Run:
   ```
   python3 skills/crawl-render-audit/scripts/crawl_audit.py <url> --workdir <dir>
   ```
2. The script, in order: fetches and parses robots.txt (compliance plus analysis of `*` and AI-crawler rules); probes the sitemap and llms.txt; fetches the homepage; deterministically selects a diverse internal-page sample (about, contact, product, blog paths first); fetches each with a delay, skipping anything robots.txt disallows; extracts per-page features with a single-pass HTML parser; runs checks CR-01 to CR-27 (crawl layer, render layer, metadata layer, technical SEO structure, keyword strategy and intent, performance and asset loading, deep-link citability). Fetches decompress forced-gzip responses, and the llms.txt probe rejects soft-404 pages.
3. Outputs land in the workdir: `site_snapshot.json` (page features, for downstream skills) and `crawl_findings.json`.

The full check list with severities, thresholds, and the reasoning behind each is in `references/checks.md`. The snapshot schema is in `references/snapshot-format.md`.

## Output
`crawl_findings.json`: `{"skill": "crawl-render-audit", "findings": [...]}` where each finding has `check`, `title`, `severity`, `evidence`, `suggested_action{summary, priority}`, `effort`.

## Guarantees
Read-only GET requests with an honest user agent. Honors robots.txt for every URL. Hard caps: max-pages HTML fetches, 1.5 MB per response, 150 second crawl budget. Standard library only.
