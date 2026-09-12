---
name: external-footprint-audit
description: Optional, opt-in check of the brand's footprint beyond its own site. Verifies presence in the Common Crawl open-web corpus and looks for a matching Wikipedia entity, using at most three keyless read-only queries to public endpoints. Runs only when the orchestrator is invoked with --external-checks.
---

# External Footprint Audit (opt-in)

## What this skill answers

Domain authority in the classic sense (proprietary link-graph scores) requires
commercial third-party services, which this marketplace deliberately avoids.
What CAN be measured with public, keyless, read-only queries is the footprint
that matters most for AI discoverability:

1. **Is the domain in the open web corpus at all?** Common Crawl is the corpus
   many AI training sets and retrieval pipelines derive from. A domain with
   zero captures there is invisible to that whole downstream ecosystem.
2. **Does a knowledge-graph entity exist for the brand?** A Wikipedia match is
   the strongest corroboration and disambiguation source machines have.

## Why it is off by default

The live-session guidance favors self-contained execution with no reliance on
external services. This skill therefore:

- never runs unless the entrypoint is invoked with `--external-checks`
- makes at most 3 requests, all keyless, read-only, and to public endpoints
  (Common Crawl index API, Wikipedia OpenSearch API)
- never touches the audited site itself
- degrades gracefully: an unreachable endpoint yields a note in the output,
  never an error and never a speculative finding

The default audit is complete without it; this skill only adds corroboration
signals that cannot exist on-site by definition.

## How to run it

Through the entrypoint (recommended):

```
python3 skills/audit-orchestrator/scripts/run_audit.py https://example.com --external-checks --out report.json
```

Directly, against an existing snapshot:

```
python3 skills/external-footprint-audit/scripts/footprint_audit.py --workdir ./audit_work
```

Output: `<workdir>/footprint_findings.json` with `findings` and `notes`
(notes record probe outcomes, including positive confirmations).

## Checks

See `references/checks.md` for EX-01 and EX-02 definitions, thresholds, and
the exact endpoints queried, written so an agent can run the same checks
manually with curl.

## Manual extension for an agent

When operating with broader network access, an agent can extend this skill's
question ("is the brand corroborated off-site?") by checking the brand's
presence and sentiment on community platforms (Reddit, Quora, review sites)
and verifying that facts stated there match the site. Keep the same
discipline: read-only, rate-limited, and reported with countable evidence.
