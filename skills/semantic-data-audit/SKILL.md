---
name: semantic-data-audit
description: Stage 2 Fact Extraction Audit. Evaluates Schema.org JSON-LD structured data, baseline Organization/WebSite schema coverage, recursive @graph entity graphs, OpenGraph and Twitter card metadata, image alt-text plain-text parity, and vertical-specific schema opportunities (Product, FAQPage, LocalBusiness, BreadcrumbList). Use when auditing how effectively AI search engines can extract machine-readable facts without hallucination.
---

# Stage 2: Semantic Data & Fact Extraction Audit

Audits whether machines can reliably extract structured, unambiguous brand facts and product details.

## Execution Procedure
1. Execute structured data parsing against the target URL:
   ```bash
   python3 skills/semantic-data-audit/scripts/parse_structured_data.py <URL>
   ```
2. The script deterministically evaluates:
   - JSON-LD syntax, unpacking `@graph` hierarchies recursively without dropping typed container nodes.
   - Universal baseline coverage: checks for `Organization`, `Corporation`, or `WebSite` schema (critical identity anchor).
   - Generalized vertical schema gating: checks for detected on-page signals (currency+price AND cart actions for `Product`, `<details>` for `FAQPage`, `href="tel:` or store hours for `LocalBusiness`, breadcrumb nav for `BreadcrumbList`). If signals are present but schema is absent, emits proactive recommendations without penalizing non-commerce sites.
   - Plain-text parity: checks for specs locked exclusively inside images without corresponding text or `alt` attributes.
   - Reuses `/tmp/audit_runs/page.html` cache file if available to prevent redundant HTTP requests.
