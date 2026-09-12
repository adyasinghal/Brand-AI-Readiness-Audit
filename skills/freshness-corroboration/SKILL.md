---
name: freshness-corroboration
description: Audit whether a site's facts look current, corroborated, and attributable to an unambiguous entity. Checks publication and modification dates (machine-readable and visible), staleness signals, outdated copyright years, Organization and WebSite identity markup, sameAs profile links, cross-page brand-name consistency, entity ambiguity risk, and About-page presence. Also audits answer-engine readiness (AEO/GEO): question-shaped headings assistants can match, a quotable one-sentence brand definition, llms.txt presence, and whether structured data actually covers the article and product content the site has. Use for questions about stale content, uncorroborated claims, mistaken brand identity, or why assistants describe a brand incorrectly or hesitantly.
license: MIT
allowed-tools: python3
---

# Freshness and Corroboration Audit

## When to use
Diagnosing trust: a machine that CAN read the site still decides whether the facts are current, whether independent sources agree, and which entity they belong to. This skill audits those signals.

## Inputs
- Required: a `site_snapshot.json` in the workdir, produced by crawl-render-audit. This skill performs no network fetches of its own.
- If the snapshot is missing, run crawl-render-audit first (or, without scripts, fetch the pages manually and apply `references/checks.md` directly).

## Procedure
1. Run:
   ```
   python3 skills/freshness-corroboration/scripts/freshness_audit.py --workdir <dir>
   ```
2. The script extracts date signals (JSON-LD datePublished/dateModified, article meta tags, visible textual dates, footer copyright years), identity signals (Organization/WebSite types, sameAs arrays, og:site_name, title patterns), and corroboration signals (outbound links to independent profile hosts), then runs checks FC-01 to FC-15 (freshness, entity identity, corroboration, and answer/generative engine optimization).

Check definitions, thresholds (e.g. the 18-month staleness cutoff), and rationale: `references/checks.md`. That file also documents an optional manual off-site corroboration procedure (searching community platforms for the brand) that stays out of the automated path so the marketplace never depends on a third-party service.

## Output
`freshness_findings.json`: `{"skill": "freshness-corroboration", "findings": [...]}` with the same finding shape as every skill in this marketplace.

## Guarantees
Zero network access; pure analysis of the snapshot. Deterministic. Standard library only.
