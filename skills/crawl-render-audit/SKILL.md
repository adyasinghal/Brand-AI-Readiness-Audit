---
name: crawl-render-audit
description: Stage 1 Machine Access Audit. Evaluates website crawlability, robots.txt AI bot access (GPTBot, ClaudeBot, PerplexityBot, Google-Extended), meta robots noindex/nosnippet directives, sitemap.xml availability and lastmod recency, and Client-Side Rendering (CSR) single-page application render gaps. Use when evaluating whether AI crawlers and search assistants can reach, fetch, and render a domain's HTML content.
---

# Stage 1: Crawl & Machine Access Audit

Audits whether automated AI search crawlers can reach, fetch, render, and index domain content.

## Execution Procedure
1. Execute the access check script against the target URL:
   ```bash
   python3 skills/crawl-render-audit/scripts/check_access.py <URL>
   ```
2. The script deterministically evaluates:
   - `robots.txt` AI crawler access using `urllib.robotparser.RobotFileParser` against known AI bot signatures in `references/ai-bot-signatures.md`.
   - Meta tag `<meta name="robots" content="...">` and HTTP `X-Robots-Tag` headers for `noindex`/`nosnippet` directives.
   - Sitemap discovery (`robots.txt` `Sitemap:` directive or `/sitemap.xml`) and `<lastmod>` recency using `xml.etree.ElementTree`.
   - CSR render gaps: flags 100% empty client-side rendering shells as `critical` and partial gaps as `high`.
   - Forward-looking `/llms.txt` discovery file presence.
   - Writes fetched HTML to `/tmp/audit_runs/page.html` for downstream pipeline caching.
