# brand-ai-readiness-audit

An Agent Skill Marketplace that audits any website for the two halves of the brand-visibility problem: off-site AI discoverability (getting found and cited by AI assistants) and on-site engagement (keeping the visitor once they arrive). Given a URL, it emits one structured JSON report of evidence-backed findings, each with a severity and a prioritized, mechanism-sound suggested action, plus proactive improvements beyond the detected defects.

## Quick start

```
python3 skills/audit-orchestrator/scripts/run_audit.py https://example.com --out report.json
```

Add `--external-checks` to also verify the brand's presence in the Common Crawl corpus and Wikipedia (opt-in; at most 3 keyless read-only queries to public endpoints, never to the audited site).

60 automated checks run by default (27 crawl/render/SEO/keyword/performance/deep-linking, 16 freshness/identity/AEO, 17 engagement), plus 2 opt-in external footprint checks.

Requirements: Python 3.10+ standard library only. No pip installs, no third-party services, no API keys, no GPU. Typical runtime: 20 to 90 seconds; hard-capped well under 5 minutes.

## The skills and how they compose

```
brand-ai-readiness-audit/            <- marketplace root (zip this)
  marketplace.json                   <- manifest; audit-orchestrator is the entrypoint
  README.md
  examples/sample-report.json
  skills/
    audit-orchestrator/              <- ENTRYPOINT
      SKILL.md
      scripts/run_audit.py
      references/report-schema.md
      references/severity-and-priority.md
    crawl-render-audit/
      SKILL.md
      scripts/crawl_audit.py
      references/checks.md           <- CR-01..CR-27
      references/snapshot-format.md
    freshness-corroboration/
      SKILL.md
      scripts/freshness_audit.py
      references/checks.md           <- FC-01..FC-16
    engagement-audit/
      SKILL.md
      scripts/engagement_audit.py
      references/checks.md           <- EN-01..EN-17
    external-footprint-audit/        <- OPT-IN (only runs with --external-checks)
      SKILL.md
      scripts/footprint_audit.py
      references/checks.md           <- EX-01..EX-02
```

The decomposition mirrors the causal pipeline of how a brand ends up in (or out of) an AI answer:

1. crawl-render-audit answers: can a machine reach the site, read what a human sees, and rank it for the right queries? It performs the default pipeline's only network access: a polite, robots.txt-honoring fetch of the homepage plus a deterministic, diverse sample of internal pages (about/contact/product/blog paths first, then shallowest). Checks CR-01 to CR-26 cover the crawl layer (robots rules including named AI-crawler blocks, sitemap, HTTPS, redirects, noindex, latency), the render layer (JS render gaps, JSON-LD presence and validity, titles, descriptions, canonicals, lang, alt coverage), technical SEO structure (semantic main/article landmarks, heading hierarchy, Open Graph, text-to-markup ratio, title hygiene), keyword strategy and intent (title/body vocabulary alignment, keyword stuffing), and performance (document weight, render-blocking head scripts, image dimension and lazy-loading hygiene). It writes `site_snapshot.json`, a per-page feature cache.
2. freshness-corroboration answers: will a machine that read the site trust, quote, and attribute the facts? Pure analysis over the snapshot, checks FC-01 to FC-16: date and staleness signals, Organization/WebSite identity markup, sameAs corroboration and corroboration depth, entity-ambiguity risk, cross-page naming consistency, About-page presence, and the AEO/GEO layer (question-shaped headings assistants can match, a quotable one-sentence brand definition, llms.txt, and whether schema types actually cover the article and product content the site has).
3. engagement-audit answers: can a visitor who arrives orient, scan, act, and continue? Pure analysis over the snapshot, checks EN-01 to EN-17: viewport, H1s, nav landmarks, wall-of-text and subheading structure, calls to action, contact reachability, FAQ/help, dead-end pages, duplicate titles, breadcrumbs, internal cross-linking depth (hub-and-spoke link graphs, generic anchor text), and interactivity (purely static text with no forms, tools, or media).
4. external-footprint-audit (opt-in, EX-01 and EX-02) answers: does the brand exist beyond its own site? It runs only with `--external-checks` and makes at most 3 keyless read-only queries to public endpoints, never the audited site: presence in the Common Crawl corpus (the open corpus many AI training and retrieval pipelines derive from) and a Wikipedia entity match. Classic domain-authority scores need commercial link-graph services, so the skill measures the footprint that actually gates AI visibility and stays off by default to keep the standard audit fully self-contained.
5. audit-orchestrator (entrypoint) resolves the others through `marketplace.json`, runs them in dependency order, merges and severity-sorts every finding, assigns stable ids, appends proactive beyond-defect suggestions (FAQPage markup, a quotable brand definition, independent-platform presence), recomputes the summary, and writes the report. A failing sub-skill degrades gracefully: the audit completes and the degradation is disclosed in `audit_meta.skill_runs`.

The one-crawl/many-analyses design is deliberate: the site is fetched exactly once per audit (polite, fast, deterministic), and the analysis skills are cleanly separated concerns over a shared, documented contract (`references/snapshot-format.md`).

## Runtime budget, shown to compose

The 5-minute ceiling is enforced by construction, not hope. Worst case: the crawl phase is capped at 150 seconds (8 page fetches with 1 second delays plus 3 probes normally finish in 20 to 40 seconds; the cap only binds on pathologically slow origins). Each offline analysis skill runs under a 45 second subprocess timeout but is pure computation over the snapshot and completes in well under a second. The opt-in external skill is capped at 60 seconds (3 requests with 10 second timeouts). Merging and writing the report is milliseconds. Sum of all caps: 150 + 45 + 45 + 60 + overhead, comfortably under 300 seconds, and the typical real run finishes in 20 to 90 seconds.

## Report shape

Required schema fields (`site`, `audited_at`, severity-count `summary`, and `findings[]` with `id`, `title`, `severity`, `evidence`, `suggested_action{summary, priority}`) are always present; the report adds `low` counts, per-finding `check`/`effort`/`source_skill`, `proactive_suggestions`, and `audit_meta` on top. Full schema: `skills/audit-orchestrator/references/report-schema.md`. Severity and priority semantics: `skills/audit-orchestrator/references/severity-and-priority.md`. A sample report is in `examples/sample-report.json`.

## Design principles

- Generalization by construction. Every check targets a repeatable root cause stated as a mechanism (why machines behave this way), fires only on countable evidence (ratios, counts, explicit directives), and uses a sampling procedure with zero site-specific knowledge. Thresholds are documented with rationale in each skill's `references/checks.md`.
- False-positive discipline. Corpus-level checks require the pattern to hold across the sample majority; every evidence string carries the observed numbers so it can be verified against the site.
- Self-contained and robust. Standard library only; no third-party APIs or hosted services anywhere in the default path; the opt-in --external-checks mode is the single, clearly fenced exception (3 keyless read-only public queries, graceful degradation, never the audited site), and the community-platform corroboration remains a documented manual procedure. Sub-skill failures never fail the audit.
- Read-only and polite. GET requests with an honest user agent, robots.txt honored per URL, 1 second default delay, 1.5 MB response cap, at most `max-pages` (default 8) HTML fetches plus three probes (robots.txt, sitemap, llms.txt), 150 second crawl budget. No authentication, no form submission, nothing destructive.
- Deterministic. Fixed sampling order, fixed check order, fixed sort; identical inputs produce identical reports.
- Agent-first authoring. Each SKILL.md is lean with progressive disclosure into `references/` and `scripts/`, and every checklist is written so an agent can execute it manually with curl if the scripts cannot run.

## License

MIT.
