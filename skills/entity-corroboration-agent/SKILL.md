---
name: entity-corroboration-agent
description: >-
  Agent-executed qualitative stage. Judges whether the brand About-page self-description is concrete enough for an assistant to quote (AG-01), and whether independent sources across the wider web corroborate (AG-02) or contradict (AG-03) what the site claims about itself. Unlike every other skill in this marketplace it runs no deterministic script: the calling agent performs it with its own reading and web_search tools, then hands structured findings back to the entrypoint, which ingests them in-process. Use when diagnosing entity confusion, hallucinated brand attributes, or a lack of multi-source consensus.
license: MIT
allowed-tools: Read WebSearch
---

# Entity Corroboration (agent stage)

## When to use

Two things the handout asks for cannot be settled by a deterministic script:
whether a self-description is concrete enough to quote, and whether the wider web
agrees with it. Both are judgment calls over natural language. This skill is where
the calling agent contributes that judgment, in the same finding shape as every
script, so the entrypoint composes it like any other source.

Skip it entirely if no reading or search capability is available. A skipped stage
is recorded as not_supplied and costs nothing; an invented stage would cost
accuracy.

## Execution model

This marketplace runs one orchestration model: the entrypoint acquires a single
immutable site snapshot and every specialist is an in-process function that
returns a SkillResult. This stage fits that model. It is not a subprocess and does
not use a workdir handoff. The calling agent writes its observations to a small
JSON file, points the environment variable AGENT_FINDINGS_PATH at that file, and
run_audit.py ingests it in-process through ingest_agent_findings.py, which
reconstructs each entry with the shared finding factory. That means catalog
enrichment and Invariant I-1 cap agent findings exactly as they cap script
findings; the agent supplies only what it observed.

## Inputs

- The audited site URL and the already-acquired site snapshot. Do not re-fetch the
  site: the page text, titles and JSON-LD are already available to the audit. Read
  the brand name from the resolved identity (Organization JSON-LD name, og:site_name
  or title).

## Procedure

Step 1, About-page concreteness (AG-01). Read the About page text (or the homepage
if there is no About page). Check whether the opening answers all three of: who the
organization is, what it specifically sells or does, and in what category or
market. Fire AG-01 only if at least one of the three is genuinely unanswerable from
that text. Marketing register is not itself a defect: enthusiastic phrasing that
still names a product and a market passes. If all three are answerable, record
nothing; a passing check is not a finding.

Step 2, cross-web corroboration (AG-02 / AG-03). If a web_search tool is available,
search for the brand name plus its category, and separately restrict to public
community platforms, for example:

```
"<brand name>" <category>
"<brand name>" site:reddit.com OR site:quora.com
```

The handout explicitly allows querying public community platforms such as Reddit
and Quora for brand visibility. Then classify into exactly one of three outcomes:

| Outcome | Finding | Severity | Status |
| --- | --- | --- | --- |
| Independent sources exist and agree with the site | none, record in notes | -- | -- |
| No independent mention found at all | AG-02 | low | confirmed |
| An independent source contradicts the site (different category, ownership, location, or a same-named different entity dominating results) | AG-03 | high | confirmed |

Step 3, graceful fallback. If no search tool exists, it errors, or it is
rate-limited: do not abort, and do not report absence of corroboration. Supply
nothing (or a single entry with status insufficient_evidence). The distinction
matters: "nobody discusses this brand" is a finding about the brand; "I could not
check" is a finding about the audit. Collapsing the second into the first is the
single most common way an audit manufactures a false negative.

Step 4, handoff. Write a JSON array of finding objects to the file named by
AGENT_FINDINGS_PATH. Do not merge them into the report; the entrypoint ingests that
file, reconstructs each finding through the shared factory, re-applies Invariant
I-1, deduplicates against script findings by check ID, and prioritizes everything
together.

## Output

The file named by AGENT_FINDINGS_PATH: a JSON array of findings (or an object with
a findings array). Useful keys per finding: check (AG-01, AG-02 or AG-03), title,
severity, status, evidence, and suggested_action with summary and steps. mechanism,
implementation_detail and expected_outcome are filled automatically from
common/check_catalog.py, so supply only what you observed.

```json
[
  {
    "check": "AG-03",
    "title": "Independent sources describe the brand differently from the site",
    "severity": "high",
    "status": "confirmed",
    "evidence": "Site describes itself as a payroll platform; two community threads and one directory describe it as an accounting firm. A same-named consultancy dominates the first page of results.",
    "suggested_action": {
      "summary": "Reconcile the category description on-site and in Organization markup, and correct the third-party listings that state the wrong category.",
      "steps": ["Identify the contradicted fact and its source", "Correct the wrong source", "State the accurate version on-site and in markup"]
    }
  }
]
```

If nothing fires, supply an empty array, or do not set AGENT_FINDINGS_PATH at all.
Both are valid; the stage records not_supplied when the variable is unset.

## Guarantees

Read-only. Does not fetch the audited site (it reads the already-acquired
snapshot). Never reports an unavailable capability as a site defect: the absence of
the stage is recorded as insufficient_evidence, capped low and advisory by
Invariant I-1.
