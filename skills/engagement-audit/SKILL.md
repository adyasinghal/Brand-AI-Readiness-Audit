---
name: engagement-audit
description: Audit whether visitors who reach a site can orient, scan, act, and get help. Checks mobile viewport, H1 orientation, navigation landmarks, wall-of-text and missing-subheading scannability problems, calls to action, contact reachability, FAQ and self-serve help, on-site search, dead-end pages with no internal links, duplicate titles, and breadcrumbs. Also audits internal cross-linking depth (hub-and-spoke link graphs, generic anchor text) and interactivity (purely static sites with no forms, tools, or media). Use for questions about bounce rate, visitors leaving without acting, confusing pages, or on-site experience of traffic arriving from AI answers and search.
license: MIT
allowed-tools: python3
---

# On-Site Engagement Audit

## When to use
Diagnosing the second half of the problem: the brand gets found, the visitor arrives, and then leaves. Most AI-referred visitors land mid-site on a deep page, so orientation and continuity matter as much as the homepage.

## Inputs
- Required: a `site_snapshot.json` in the workdir, produced by crawl-render-audit. No network fetches of its own.
- If the snapshot is missing, run crawl-render-audit first (or apply `references/checks.md` manually against fetched pages).

## Procedure
1. Run:
   ```
   python3 skills/engagement-audit/scripts/engagement_audit.py --workdir <dir>
   ```
2. The script evaluates four groups over the sampled pages: orientation (EN-01 to EN-04), scannability (EN-05, EN-06), action paths (EN-07, EN-08), help and continuity (EN-09 to EN-13), cross-linking depth (EN-14, EN-15), interactivity (EN-16), and interruption friction from interstitial popups (EN-17).

Check definitions, thresholds (e.g. paragraph-length and word-count cutoffs), and rationale: `references/checks.md`.

## Output
`engagement_findings.json`: `{"skill": "engagement-audit", "findings": [...]}` with the marketplace-standard finding shape.

## Guarantees
Zero network access; pure analysis of the snapshot. Deterministic. Standard library only.
