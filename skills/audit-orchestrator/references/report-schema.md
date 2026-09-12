# Audit report schema

The entrypoint always emits this shape. Contest-required fields are marked REQUIRED; everything else is additive (the schema is a floor, not a ceiling).

```json
{
  "site": "example.com",                       // REQUIRED, hostname of the audited site
  "audited_at": "2026-09-20T14:32:00Z",        // REQUIRED, ISO 8601 UTC
  "summary": {                                  // REQUIRED
    "total_findings": 6,                        // REQUIRED
    "critical": 1,                              // REQUIRED
    "high": 2,                                  // REQUIRED
    "medium": 3,                                // REQUIRED
    "low": 0                                    // additive
  },
  "findings": [                                 // REQUIRED, sorted critical -> low
    {
      "id": "F-001",                            // REQUIRED, stable, assigned in sorted order
      "title": "No JSON-LD structured data on any sampled page",   // REQUIRED
      "severity": "high",                       // REQUIRED: critical | high | medium | low
      "evidence": "Crawled 8 pages; 0/8 contain a script[type=application/ld+json] block.",  // REQUIRED, always concrete and countable
      "suggested_action": {                     // REQUIRED
        "summary": "Add JSON-LD to key templates ...",             // REQUIRED
        "priority": "high"                      // REQUIRED: critical | high | medium | low
      },
      "check": "CR-07",                         // additive: which rule fired (CR/FC/EN namespace)
      "effort": "medium",                       // additive: low | medium | high, for quick-win triage
      "source_skill": "crawl-render-audit"      // additive: attribution inside the marketplace
    }
  ],
  "proactive_suggestions": [                    // additive: improvements beyond detected defects
    { "title": "...", "priority": "medium", "rationale": "..." }
  ],
  "audit_meta": {                               // additive: transparency and degraded-mode signaling
    "marketplace": "brand-ai-readiness-audit",
    "version": "1.0.0",
    "skill_runs": [ { "skill": "crawl-render-audit", "ok": true, "note": "..." } ],
    "pages_sampled": [ { "url": "https://example.com/", "status": 200 } ]
  }
}
```

Invariants the orchestrator enforces:
- Every finding carries all five required fields or it is dropped at merge time.
- `summary` counts are recomputed from the merged findings, never trusted from sub-skills.
- Sort order is severity rank, then check id, then title: byte-identical reports for identical inputs.
- A failed sub-skill never fails the audit; it is reported in `audit_meta.skill_runs` as degraded.
