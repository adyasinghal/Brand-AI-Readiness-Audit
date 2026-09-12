---
name: audit-orchestrator
description: Entrypoint for the brand-ai-readiness-audit marketplace. Given a website URL or domain, runs the full AI-discoverability and on-site-engagement audit by composing the crawl-render-audit, freshness-corroboration, and engagement-audit skills (plus the opt-in external-footprint-audit skill when explicitly enabled), then emits one structured JSON report of evidence-backed findings with severities and prioritized suggested actions. Use whenever asked to audit a website, diagnose why a brand is missing, stale, or misrepresented in AI assistants, or explain why visitors bounce.
license: MIT
allowed-tools: bash, python3, network(outbound http/https to the audited site only)
---

# Audit Orchestrator (marketplace entrypoint)

## When to use
Any request of the form: audit this site, why don't AI assistants cite this brand, why do visitors leave, produce an AI-readiness report for `<url>`.

## Inputs
- Required: a URL or bare domain (e.g. `https://example.com` or `example.com`).
- Optional: `--max-pages` (default 8), `--delay` seconds between fetches (default 1.0), `--out` report path, `--external-checks` to also run the opt-in external-footprint-audit skill (at most 3 keyless read-only queries to public endpoints, never to the audited site; off by default).

## Procedure
1. From the marketplace root, run:
   ```
   python3 skills/audit-orchestrator/scripts/run_audit.py <url> --out report.json
   ```
   This is the whole audit. The script resolves the other skills through `marketplace.json`, runs crawl-render-audit first (it fetches politely, honors robots.txt, and writes a shared `site_snapshot.json`), then runs freshness-corroboration and engagement-audit over that snapshot (and external-footprint-audit only if --external-checks was passed), merges all findings, sorts by severity, assigns stable `F-###` ids, appends proactive beyond-defect suggestions, and writes the report.
2. Read `report.json` and present it to the requester. Lead with critical and high findings; each already carries evidence and a prioritized suggested action.
3. If any `skill_runs` entry in `audit_meta` shows `DEGRADED`, say so: the report is still valid but that concern was only partially covered.

## Fallback if scripts cannot execute
If Python is unavailable, perform the audit manually: read each sub-skill's SKILL.md and its `references/checks.md`, apply the checks yourself using plain HTTP fetches (curl), and assemble the same report shape. The checklists are written to be executable by an agent without the scripts.

## Output
A single JSON report against the schema in `references/report-schema.md`:
- `site`, `audited_at`
- `summary` with `total_findings` and counts by severity (`critical`, `high`, `medium`, plus `low`)
- `findings[]`, each with `id`, `title`, `severity`, `evidence`, `suggested_action{summary, priority}`
- `proactive_suggestions[]` (improvements beyond detected defects)
- `audit_meta` (skill run status, pages sampled, and a coverage block: links discovered, pages sampled versus fetched versus robots-blocked, probe outcomes) so absence of a finding is never mistaken for evidence when coverage was the limit

Severity and priority semantics are defined in `references/severity-and-priority.md`.

## Guarantees
Read-only. Respects robots.txt. At most `max-pages` HTML fetches plus three probe fetches (robots.txt, sitemap, llms.txt), rate-limited by `--delay`. No authentication, no form submission, no site modification, no third-party services in the default path (the opt-in --external-checks mode makes at most 3 keyless read-only queries to public Common Crawl and Wikipedia endpoints and never touches the audited site). Standard library only. Completes well under 5 minutes on a typical site.
