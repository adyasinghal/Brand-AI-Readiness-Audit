# Brand AI-Readiness Audit

A multi-skill Agent Skill Marketplace that audits any website for **AI discoverability** and **on-site engagement** problems. Given a URL, the entrypoint crawls the site (read-only, bounded) and produces a single structured JSON report containing evidence-backed findings and prioritized suggested actions. It never modifies a live site.

## Skills

### 1. `audit-orchestrator` *(entrypoint)*

Validates the target URL, performs a single bounded acquisition (robots.txt, sitemap, llms.txt, HTML pages), then schedules and composes the outputs of all other skills into one final report. Handles deduplication, severity prioritization, recommendation generation, and report validation.

### 2. `crawl-render-audit`

Analyzes the acquisition snapshot for crawlability and machine-readability issues:
- Robots.txt and AI-crawler access (GPTBot, ChatGPT-User, etc.)
- Sitemap and llms.txt presence
- Recursive JSON-LD structured data inspection and schema-type coverage
- Technical metadata (titles, descriptions, canonicals, language, social cards)
- Page performance (HTML size, markup ratio, fetch latency)
- Rendering gap detection (JS-dependent content)

### 3. `freshness-corroboration`

Analyzes page content quality and entity identity:
- Claim extraction and important-fact ranking
- Freshness assessment of dated commercial facts
- Entity identity resolution from structured data
- Answer-content quality (title-body alignment, keyword stuffing, brand definition)
- External footprint and corroboration (when search is available)

### 4. `engagement-audit`

Analyzes on-site visitor engagement and navigation:
- Site graph construction (internal link structure)
- Orphan pages, isolated clusters, and dead-end detection
- Breadcrumb and orientation analysis
- Internal discoverability and generic anchor text
- Visitor retention opportunities

### 5. `entity-corroboration-agent`

An agent-executed qualitative stage. When invoked by an AI agent with web search capability, it:
- Assesses About-page concreteness
- Checks cross-web entity agreement or contradiction
- Produces structured findings the entrypoint merges into the report

Skips gracefully when no search capability is available — does not report its own absence as a site defect.

## How the entrypoint composes them

```
URL input
    │
    ▼
┌─────────────────────────┐
│   audit-orchestrator     │  ← entrypoint
│   1. Validate URL        │
│   2. Acquire site once   │
│      (robots, sitemap,   │
│       llms.txt, pages)   │
│   3. Schedule analysis   │
│      DAG in parallel:    │
│      ┌─────────────────┐ │
│      │ crawl-render     │ │
│      │ freshness        │ │
│      │ engagement       │ │
│      │ entity-agent     │ │
│      └─────────────────┘ │
│   4. Merge & deduplicate │
│   5. Prioritize findings │
│   6. Generate recs       │
│   7. Validate report     │
│   8. Emit JSON to stdout │
└─────────────────────────┘
```

All four analysis skills read the same immutable acquisition snapshot — no redundant fetching.

## Quick start

```bash
python3 skills/audit-orchestrator/scripts/run_audit.py https://example.com > report.json
```

No installation required beyond Python 3.10+ standard library. No pip install, no API keys, no browser download.

## Safety

- **Read-only**: only HTTP GET; no authentication, form submission, or site modification.
- **SSRF protection**: every URL (target, redirects, discovered links, sitemaps) is validated against loopback, private, link-local, multicast, reserved, and cloud-metadata ranges.
- **Robots-first**: unknown robots permission prevents page acquisition (fail closed, not open).
- **Bounded**: 50-page crawl cap, 90-request budget, 40 MiB body limit, 270-second wall-clock timeout.
- **Streaming**: response bodies are streamed under per-request byte caps to prevent memory exhaustion.

## Marketplace structure

```
Brand-AI-Readiness-Audit/          <- marketplace root 
├── marketplace.json               <- manifest: lists all skills, marks the entrypoint
├── README.md                      <- this file
├── .gitignore
├── common/                        <- shared library imported by every skill
│   ├── __init__.py
│   ├── action_catalog.py          <- baseline suggested-action templates per category
│   ├── capabilities.py            <- runtime capability detection (rendering, search)
│   ├── check_catalog.py           <- single source of check_id -> mechanism/fix wording
│   ├── check_helpers.py
│   ├── constants.py               <- crawl caps, budgets, timeouts
│   ├── errors.py
│   ├── html_features.py
│   ├── instrumentation.py         <- request/stage telemetry
│   ├── models.py                  <- immutable AuditArtifacts, finding factory, invariants
│   ├── robots_policy.py           <- robots.txt parsing and fail-closed policy
│   ├── search_provider.py         <- optional external-search adapter
│   ├── structured_data.py         <- JSON-LD extraction/parsing
│   ├── subprocess_isolation.py    <- bounded worker isolation
│   ├── tls_context.py             <- verified-TLS transport context
│   ├── transport.py               <- streaming, byte-capped HTTP GET
│   └── url_safety.py              <- SSRF validation (loopback/private/metadata ranges)
├── skills/
│   ├── audit-orchestrator/        <- ENTRYPOINT: composes all other skills
│   │   ├── SKILL.md
│   │   ├── references/
│   │   │   ├── audit-state-schema.md
│   │   │   ├── execution-policy.md
│   │   │   ├── finding-schema.md
│   │   │   └── report-schema.md
│   │   └── scripts/
│   │       ├── run_audit.py               <- CLI + top-level pipeline
│   │       ├── acquire_site.py            <- single bounded acquisition
│   │       ├── merge_findings.py          <- dedup + merge across skills
│   │       ├── prioritize_findings.py     <- severity ordering
│   │       ├── generate_recommendations.py
│   │       ├── validate_report.py         <- schema + invariant enforcement
│   │       ├── execution_summary.py       <- status/limitations/confidence
│   │       └── diagnose_transport.py
│   ├── crawl-render-audit/        <- crawlability + machine-readability checks
│   │   ├── SKILL.md
│   │   ├── references/crawl-render-checklist.md
│   │   └── scripts/
│   │       ├── analyze_crawlability.py
│   │       ├── analyze_directives.py
│   │       ├── analyze_machine_readability.py
│   │       ├── analyze_metadata.py
│   │       ├── analyze_performance.py
│   │       ├── analyze_rendering.py
│   │       ├── check_ai_crawler_access.py
│   │       └── check_llms_txt.py
│   ├── freshness-corroboration/  <- content quality, freshness, entity identity
│   │   ├── SKILL.md
│   │   ├── references/freshness-corroboration-methodology.md
│   │   └── scripts/
│   │       ├── extract_claims.py
│   │       ├── identify_important_facts.py
│   │       ├── assess_freshness.py
│   │       ├── resolve_entity_identity.py
│   │       ├── analyze_answer_content.py
│   │       ├── corroborate_claims.py
│   │       └── assess_external_footprint.py
│   ├── engagement-audit/         <- on-site navigation + visitor engagement
│   │   ├── SKILL.md
│   │   ├── references/engagement-checklist.md
│   │   └── scripts/
│   │       ├── build_site_graph.py
│   │       ├── analyze_engagement.py
│   │       └── analyze_experience.py
│   └── entity-corroboration-agent/  <- agent-executed qualitative corroboration
│       ├── SKILL.md
│       ├── references/checks.md
│       └── scripts/ingest_agent_findings.py
└── tests/                        <- pytest suite + local fixtures (not required to run an audit)
    ├── fixtures_server.py
    ├── tls-fixtures/             <- self-signed certs for TLS-recovery tests
    └── test_*.py
```

## Testing

```bash
pip install pytest   # optional, for pytest runner
python3 tests/test_smoke.py              # quick DAG + report validation
python3 tests/test_safety.py             # SSRF, robots, redirects
python3 tests/test_integration.py        # full end-to-end against local fixture
python3 tests/test_dedup_and_recommendations.py  # dedup + recommendations
```
